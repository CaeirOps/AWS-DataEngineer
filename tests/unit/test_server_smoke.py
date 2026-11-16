"""Smoke tests do servidor Flask e do Dockerfile (Requisito 1.4)."""

import re
from pathlib import Path

import pytest

from app.server import create_app
from tests.fixtures.http_client import workshop_client

DOCKERFILE = Path(__file__).resolve().parents[2] / "Dockerfile"


def _make_app(tmp_path, **extra):
    labs_dir = tmp_path / "labs"
    labs_dir.mkdir(exist_ok=True)
    config = {
        "labs_dir": str(labs_dir),
        "session_env": {"WORKSHOP_CREDENTIALS_EXPIRATION": "2999-01-01T00:00:00Z"},
        "progress_file": str(tmp_path / "progress" / "progress.json"),
    }
    config.update(extra)
    return create_app(config)


@pytest.fixture
def client(tmp_path):
    return workshop_client(_make_app(tmp_path))


def test_health_retorna_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_create_app_com_catalogo_vazio_e_labs_vazio(client):
    response = client.get("/api/labs")
    assert response.status_code == 200
    assert response.get_json() == {"labs": []}


def test_debug_desabilitado(tmp_path):
    assert _make_app(tmp_path).config["DEBUG"] is False


def test_erro_inesperado_vira_500_sem_traceback(tmp_path):
    class ValidacaoQuebrada:
        def validate(self, lab_id, step_id, context):
            raise RuntimeError("detalhe-interno-secreto")

    app = _make_app(tmp_path, validation_service=ValidacaoQuebrada())
    response = workshop_client(app).post("/api/validate/lab/step", json={})
    assert response.status_code == 500
    body = response.get_json()
    assert body["error"] is True
    assert body["code"] == "INTERNAL_ERROR"
    assert body["http_status"] == 500
    texto = response.get_data(as_text=True)
    assert "Traceback" not in texto
    assert "detalhe-interno-secreto" not in texto


def test_dockerfile_cmd_usa_gunicorn_com_bind_e_2_workers():
    conteudo = DOCKERFILE.read_text(encoding="utf-8")
    cmd = re.search(r"^CMD\s+(\[.*\])\s*$", conteudo, re.MULTILINE)
    assert cmd is not None
    args = eval(cmd.group(1), {"__builtins__": {}})  # lista literal de strings
    assert args[0] == "gunicorn"
    assert args[args.index("--workers") + 1] == "2"
    assert args[args.index("--bind") + 1] == "0.0.0.0:5000"


def test_dockerfile_healthcheck_nao_usa_curl():
    conteudo = DOCKERFILE.read_text(encoding="utf-8")
    healthcheck = re.search(
        r"^HEALTHCHECK.*?(?=^\S*(?:CMD|ENTRYPOINT)\b)", conteudo, re.MULTILINE | re.DOTALL
    )
    assert healthcheck is not None
    assert "curl" not in healthcheck.group(0).lower()
