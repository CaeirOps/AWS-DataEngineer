"""Property 22: requisições sem Host, Origin, Content-Type ou cabeçalho próprio válidos são recusadas.

**Validates: Requirements 13.1, 13.2, 13.4**

Gera combinações de método, rota, `Host`, `Origin`, `Content-Type` e
`X-Workshop-Request` e verifica que o guarda só aceita a combinação totalmente
válida, que a recusa devolve o código da primeira checagem que falhou (ordem:
Host, Origin, Content-Type, cabeçalho próprio), que a recusa não altera o
`progress.json` nem cria sessão boto3 e que os cinco cabeçalhos de segurança
estão sempre presentes.
"""

import tempfile
from pathlib import Path
from typing import Optional

from flask.testing import FlaskClient
from hypothesis import given, settings, strategies as st

from app.server import create_app
from tests.fixtures import EXAMPLE_LAB_ID, LABS_FIXTURE_DIR
from tests.fixtures.http_client import workshop_client

# Porta explícita e diferente da padrão, para não depender do ambiente.
PORT = "5050"
OTHER_PORT = "5051"
LAB = EXAMPLE_LAB_ID

SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
    ),
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
}

GUARD_CODES = {
    "HOST_NOT_ALLOWED",
    "ORIGIN_NOT_ALLOWED",
    "UNSUPPORTED_MEDIA_TYPE",
    "MISSING_WORKSHOP_HEADER",
}

# Oráculo independente da implementação: valores aceitos, já em minúsculas.
VALID_HOSTS = {f"127.0.0.1:{PORT}", f"localhost:{PORT}"}
VALID_ORIGINS = {f"http://127.0.0.1:{PORT}", f"http://localhost:{PORT}"}


class SessionFactoryCalled(AssertionError):
    """Levantada se alguma rota criar a sessão boto3."""


# --- Estratégias -----------------------------------------------------------

methods = st.sampled_from(["GET", "POST", "PUT", "DELETE"])

routes = st.sampled_from(
    [
        "/",
        "/health",
        f"/lab/{LAB}",
        "/api/labs",
        f"/api/labs/{LAB}",
        f"/api/labs/{LAB}/steps/step-01/visit",
        f"/api/labs/{LAB}/steps/step-01/content?path=console",
        f"/api/labs/{LAB}/steps/step-01/hint?path=console",
        "/api/progress",
        f"/api/validate/{LAB}/step-03",
        f"/api/deploy/{LAB}",
        f"/api/teardown/{LAB}",
        f"/api/stack-status/{LAB}",
        "/api/session",
        "/static/a.txt",
        "/inexistente",
    ]
)

hosts = st.sampled_from(
    [
        f"127.0.0.1:{PORT}",
        f"localhost:{PORT}",
        f"LOCALHOST:{PORT}",
        f"Localhost:{PORT}",
        f"localhost:{OTHER_PORT}",
        f"127.0.0.1:{OTHER_PORT}",
        "localhost",
        "127.0.0.1",
        "evil.example",
        f"evil.example:{PORT}",
        f"127.0.0.1.evil.example:{PORT}",
        f"localhost.evil.example:{PORT}",
        f"evil-localhost:{PORT}",
        f"localhost:{PORT}.evil",
        f" localhost:{PORT}",
        "",
    ]
)

# `None` significa cabeçalho ausente.
origins = st.sampled_from(
    [
        None,
        "null",
        "",
        f"http://localhost:{PORT}",
        f"http://127.0.0.1:{PORT}",
        f"http://localhost:{OTHER_PORT}",
        f"https://localhost:{PORT}",
        f"https://127.0.0.1:{PORT}",
        f"http://localhost:{PORT}.evil.example",
        f"http://127.0.0.1.evil.example:{PORT}",
        f"http://evil.example:{PORT}",
        f"http://localhost:{PORT}/",
        f"HTTP://LOCALHOST:{PORT}",
    ]
)

content_types = st.sampled_from(
    [
        None,
        "application/json",
        "application/json; charset=utf-8",
        "Application/JSON",
        "text/plain",
        "application/x-www-form-urlencoded",
        "multipart/form-data; boundary=xyz",
        "application/jsonx",
        "text/json",
    ]
)

workshop_headers = st.sampled_from([None, "1", "0", "", "true", "11"])


def _content_type_ok(value: Optional[str]) -> bool:
    if value is None:
        return False
    return value.split(";", 1)[0].strip().lower() == "application/json"


def _expected_code(method, route, host, origin, content_type, header) -> Optional[str]:
    """Código da primeira checagem que falha, ou `None` se o guarda aceita."""
    path = route.split("?", 1)[0]
    if not (method == "GET" and path == "/health") and host.lower() not in VALID_HOSTS:
        return "HOST_NOT_ALLOWED"
    if method == "GET":
        return None
    if origin not in VALID_ORIGINS:
        return "ORIGIN_NOT_ALLOWED"
    if not _content_type_ok(content_type):
        return "UNSUPPORTED_MEDIA_TYPE"
    if header != "1":
        return "MISSING_WORKSHOP_HEADER"
    return None


def _build_app(tmp: Path, sessions_created: list):
    static = tmp / "static"
    static.mkdir()
    (static / "index.html").write_text("<html></html>")
    (static / "a.txt").write_text("ok")

    def failing_session_factory():
        sessions_created.append(1)
        raise SessionFactoryCalled("sessão boto3 criada")

    progress_file = tmp / "progress.json"
    app = create_app(
        {
            "labs_dir": str(LABS_FIXTURE_DIR),
            "progress_file": str(progress_file),
            "session_factory": failing_session_factory,
            # Sessão válida (expira muito no futuro).
            "session_env": {"WORKSHOP_CREDENTIALS_EXPIRATION": "2999-01-01T00:00:00Z"},
            "static_folder": str(static),
            "workshop_port": PORT,
        }
    )
    return app, progress_file


def _snapshot(path: Path):
    return path.read_bytes() if path.exists() else None


@settings(max_examples=300, deadline=None)
@given(methods, routes, hosts, origins, content_types, workshop_headers)
def test_only_fully_valid_requests_pass_the_guard(
    method, route, host, origin, content_type, header
):
    """Só a combinação válida passa; o resto é recusado sem efeito colateral."""
    sessions_created: list = []
    with tempfile.TemporaryDirectory() as tmp_name:
        app, progress_file = _build_app(Path(tmp_name), sessions_created)
        client = workshop_client(app)

        # Cria o progress.json com um efeito real, para comparar bytes depois.
        seed = client.post(f"/api/labs/{LAB}/steps/step-01/visit", json={})
        assert seed.status_code == 200
        before = _snapshot(progress_file)
        assert before is not None
        sessions_created.clear()

        headers = {"Host": host}
        if origin is not None:
            headers["Origin"] = origin
        if content_type is not None:
            headers["Content-Type"] = content_type
        if header is not None:
            headers["X-Workshop-Request"] = header

        # Chamada direta ao FlaskClient, sem os cabeçalhos padrão do cliente.
        kwargs = {} if method == "GET" else {"data": "{}"}
        response = FlaskClient.open(
            client,
            route,
            method=method,
            base_url=f"http://localhost:{PORT}",
            headers=headers,
            **kwargs,
        )

        # Os cinco cabeçalhos de segurança valem para toda resposta.
        for name, value in SECURITY_HEADERS.items():
            assert response.headers.get(name) == value, name

        expected = _expected_code(method, route, host, origin, content_type, header)
        payload = response.get_json(silent=True)
        code = payload.get("code") if isinstance(payload, dict) else None

        if expected is None:
            # Aceita pelo guarda: nenhuma resposta com código do guarda.
            assert code not in GUARD_CODES
            assert response.status_code not in (421, 415) or code is not None
        else:
            assert code == expected
            assert isinstance(payload, dict) and payload.get("error") is True
            assert response.status_code == {
                "HOST_NOT_ALLOWED": 421,
                "ORIGIN_NOT_ALLOWED": 403,
                "UNSUPPORTED_MEDIA_TYPE": 415,
                "MISSING_WORKSHOP_HEADER": 403,
            }[expected]
            # Recusada: estado intacto e nenhuma sessão boto3 criada.
            assert _snapshot(progress_file) == before
            assert sessions_created == []
            # Os valores recebidos não são repetidos na mensagem de erro.
            message = payload.get("message", "")
            for value in (host, origin, content_type):
                if value and len(value) > 3:
                    assert value not in message
