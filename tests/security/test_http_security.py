"""Testes da proteção da API contra CSRF e DNS rebinding (Requirement 13)."""

import pytest
from flask.testing import FlaskClient

from app.server import create_app
from tests.fixtures.http_client import workshop_client

CSP = "default-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
EXPECTED_HEADERS = {
    "Content-Security-Policy": CSP,
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
}
PORT = "5000"
GOOD_ORIGIN = f"http://localhost:{PORT}"
JSON = {"Content-Type": "application/json"}
SEGREDO = "segredo-refletido-123"


@pytest.fixture
def app(tmp_path):
    labs = tmp_path / "labs"
    labs.mkdir()
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("<html></html>")
    (static / "a.txt").write_text("ok")
    return create_app(
        {
            "labs_dir": str(labs),
            "progress_file": str(tmp_path / "progress.json"),
            "session_env": {"WORKSHOP_CREDENTIALS_EXPIRATION": "2999-01-01T00:00:00Z"},
            "static_folder": str(static),
            # Porta fixa, independente de WORKSHOP_PORT no ambiente.
            "workshop_port": PORT,
        }
    )


@pytest.fixture
def client(app):
    return workshop_client(app)


def _raw(client, method, headers):
    """Requisição sem os cabeçalhos padrão que o cliente de teste injeta."""
    return FlaskClient.open(
        client, "/api/progress", method=method, base_url=GOOD_ORIGIN, headers=headers, data="{}"
    )


def _raw_post(client, headers):
    return _raw(client, "POST", headers)


def _assert_security_headers(response):
    for name, value in EXPECTED_HEADERS.items():
        assert response.headers.get(name) == value, name


# ------------------------------------------------------------------ Host


@pytest.mark.parametrize("host", ["localhost:5000", "127.0.0.1:5000", "LOCALHOST:5000"])
def test_host_permitido(client, host):
    assert client.get("/api/labs", headers={"Host": host}).status_code == 200


@pytest.mark.parametrize(
    "host", ["evil.example", "localhost", "localhost:9999", "127.0.0.1:80", "evil.example:5000"]
)
def test_host_negado_retorna_421(client, host):
    response = client.get("/api/labs", headers={"Host": host})
    assert response.status_code == 421
    assert response.get_json()["code"] == "HOST_NOT_ALLOWED"


def test_health_isento_de_host(client):
    assert client.get("/health", headers={"Host": "evil.example"}).status_code == 200


def test_host_negado_vale_tambem_para_estaticos_e_post(client):
    assert client.get("/", headers={"Host": "evil.example"}).status_code == 421
    response = client.post("/api/progress", json={}, headers={"Host": "evil.example"})
    assert response.status_code == 421


# ---------------------------------------------------- Origin, tipo e cabeçalho


def test_put_valido_passa_pelo_guard(client):
    response = client.put("/api/progress", json={"visited": []})
    assert response.status_code not in (403, 415, 421)


def test_origin_ausente_retorna_403(client):
    response = _raw_post(client, {**JSON, "X-Workshop-Request": "1"})
    assert response.status_code == 403
    assert response.get_json()["code"] == "ORIGIN_NOT_ALLOWED"


@pytest.mark.parametrize("origin", ["http://evil.example", "http://localhost:9999", "null"])
def test_origin_diferente_retorna_403(client, origin):
    response = _raw_post(client, {**JSON, "X-Workshop-Request": "1", "Origin": origin})
    assert response.status_code == 403
    assert response.get_json()["code"] == "ORIGIN_NOT_ALLOWED"


@pytest.mark.parametrize("content_type", ["text/plain", "application/x-www-form-urlencoded", ""])
def test_content_type_invalido_retorna_415(client, content_type):
    headers = {"Origin": GOOD_ORIGIN, "X-Workshop-Request": "1"}
    if content_type:
        headers["Content-Type"] = content_type
    response = _raw_post(client, headers)
    assert response.status_code == 415
    assert response.get_json()["code"] == "UNSUPPORTED_MEDIA_TYPE"


def test_content_type_json_com_charset_e_aceito(client):
    response = _raw_post(
        client,
        {
            "Origin": GOOD_ORIGIN,
            "X-Workshop-Request": "1",
            "Content-Type": "application/json; charset=utf-8",
        },
    )
    assert response.status_code not in (403, 415, 421)


@pytest.mark.parametrize("value", [None, "0", "true", ""])
def test_cabecalho_proprio_ausente_ou_invalido_retorna_403(client, value):
    headers = {**JSON, "Origin": GOOD_ORIGIN}
    if value is not None:
        headers["X-Workshop-Request"] = value
    response = _raw_post(client, headers)
    assert response.status_code == 403
    assert response.get_json()["code"] == "MISSING_WORKSHOP_HEADER"


def test_get_nao_exige_origin_nem_cabecalho_proprio(client):
    assert client.get("/api/labs").status_code == 200


@pytest.mark.parametrize("method", ["PUT", "DELETE"])
def test_put_e_delete_tambem_sao_protegidos(client, method):
    response = _raw(client, method, JSON)
    assert response.status_code == 403
    assert response.get_json()["code"] == "ORIGIN_NOT_ALLOWED"


# ------------------------------------------------------------------ ordem


def test_ordem_host_antes_de_origin(client):
    response = _raw_post(client, {"Host": "evil.example", "Origin": "http://evil.example"})
    assert response.status_code == 421


def test_ordem_origin_antes_de_content_type(client):
    response = _raw_post(client, {"Content-Type": "text/plain"})
    assert response.get_json()["code"] == "ORIGIN_NOT_ALLOWED"


def test_ordem_content_type_antes_de_cabecalho_proprio(client):
    response = _raw_post(client, {"Origin": GOOD_ORIGIN, "Content-Type": "text/plain"})
    assert response.status_code == 415


# -------------------------------------------------- sem refletir valores


def test_mensagens_nao_refletem_valores_recebidos(client):
    respostas = [
        client.get("/api/labs", headers={"Host": f"{SEGREDO}.example"}),
        _raw_post(
            client,
            {**JSON, "Origin": f"http://{SEGREDO}.example", "X-Workshop-Request": "1"},
        ),
        _raw_post(
            client,
            {"Origin": GOOD_ORIGIN, "Content-Type": f"text/{SEGREDO}", "X-Workshop-Request": "1"},
        ),
        _raw_post(client, {**JSON, "Origin": GOOD_ORIGIN, "X-Workshop-Request": SEGREDO}),
    ]
    assert [r.status_code for r in respostas] == [421, 403, 415, 403]
    for response in respostas:
        assert SEGREDO not in response.get_data(as_text=True)


# ---------------------------------------------------- cabeçalhos de segurança


def test_cabecalhos_em_resposta_200(client):
    _assert_security_headers(client.get("/api/labs"))
    _assert_security_headers(client.get("/health"))


def test_cabecalhos_em_respostas_4xx(client):
    _assert_security_headers(client.get("/api/labs", headers={"Host": "evil.example"}))  # 421
    _assert_security_headers(client.get("/api/labs/inexistente"))  # 404
    _assert_security_headers(_raw_post(client, {}))  # 403
    _assert_security_headers(_raw_post(client, {"Origin": GOOD_ORIGIN}))  # 415


def test_cabecalhos_em_resposta_5xx(app, client, monkeypatch):
    store = app.extensions["workshop"]["progress"]

    def falha():
        raise RuntimeError("falha simulada")

    monkeypatch.setattr(store, "get_progress", falha)
    response = client.get("/api/progress")
    assert response.status_code == 500
    _assert_security_headers(response)


def test_cabecalhos_em_arquivos_estaticos(client):
    ok = client.get("/static/a.txt")
    assert ok.status_code == 200
    _assert_security_headers(ok)
    ausente = client.get("/static/inexistente.js")
    assert ausente.status_code == 404
    _assert_security_headers(ausente)
    _assert_security_headers(client.get("/"))


def test_cache_control_no_store_apenas_em_api(client):
    for path in ("/api/labs", "/api/progress", "/api/labs/inexistente", "/api/session"):
        assert client.get(path).headers.get("Cache-Control") == "no-store", path
    erro = client.get("/api/labs", headers={"Host": "evil.example"})
    assert erro.headers.get("Cache-Control") == "no-store"
    assert client.get("/health").headers.get("Cache-Control") != "no-store"
    assert client.get("/static/a.txt").headers.get("Cache-Control") != "no-store"


# ---------------------------------------------------- porta efetiva


def test_porta_do_config_prevalece_sobre_o_ambiente(tmp_path, monkeypatch):
    monkeypatch.setenv("WORKSHOP_PORT", "5050")
    labs = tmp_path / "labs"
    labs.mkdir()
    app = create_app(
        {
            "labs_dir": str(labs),
            "progress_file": str(tmp_path / "p.json"),
            "workshop_port": "5000",
        }
    )
    assert app.config["WORKSHOP_EFFECTIVE_PORT"] == "5000"
    assert workshop_client(app).get("/api/labs").status_code == 200
