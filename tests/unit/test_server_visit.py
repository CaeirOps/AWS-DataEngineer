"""Testes de unidade da rota `visit` e da injeção de `validator_loader` em `create_app`.

Valida: 2.4, 2.6, 3.2.
"""

import json
from pathlib import Path

import pytest

from app.models import ValidationResult
from app.server import create_app

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "labs"
LAB = "lab-example"


@pytest.fixture
def progress_file(tmp_path):
    return tmp_path / "progress.json"


@pytest.fixture
def client(progress_file):
    app = create_app({"labs_dir": str(FIXTURES), "progress_file": str(progress_file)})
    return app.test_client()


def _visit(client, lab_id, step_id):
    return client.post(f"/api/labs/{lab_id}/steps/{step_id}/visit")


def test_visit_step_nao_task_vira_passed_e_resume_avanca(client):
    resp = _visit(client, LAB, "step-01")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["step_status"] == "passed"
    assert body["attempt_count"] == 0
    assert body["resume_step"] == "step-02"

    body = _visit(client, LAB, "step-02").get_json()
    assert body["attempt_count"] == 0
    # step-03 é task: o resume para nele até a validação.
    assert body["resume_step"] == "step-03"


def test_visit_repetida_nao_altera_passed_at(client, progress_file):
    _visit(client, LAB, "step-01")
    first = json.loads(progress_file.read_text(encoding="utf-8"))
    passed_at = first["labs"][LAB]["steps"]["step-01"]["passed_at"]
    assert passed_at

    resp = _visit(client, LAB, "step-01")
    assert resp.status_code == 200
    again = json.loads(progress_file.read_text(encoding="utf-8"))
    assert again["labs"][LAB]["steps"]["step-01"]["passed_at"] == passed_at
    assert again["labs"][LAB]["steps"]["step-01"]["attempts"] == 0


def test_visit_em_step_task_retorna_409(client):
    resp = _visit(client, LAB, "step-03")
    assert resp.status_code == 409
    assert resp.get_json()["code"] == "STEP_REQUIRES_VALIDATION"


def test_visit_ids_invalidos_retornam_404(client):
    lab_resp = _visit(client, "lab-inexistente", "step-01")
    assert lab_resp.status_code == 404
    assert lab_resp.get_json()["code"] == "LAB_NOT_FOUND"

    step_resp = _visit(client, LAB, "step-inexistente")
    assert step_resp.status_code == 404
    assert step_resp.get_json()["code"] == "STEP_NOT_FOUND"


def test_create_app_usa_validator_loader_injetado_sem_variavel_de_ambiente(
    progress_file, monkeypatch
):
    # Nenhuma variável de ambiente pode ser necessária para escolher o validador.
    monkeypatch.delenv("WORKSHOP_VALIDATOR_MODULE", raising=False)
    carregados = []

    def validate_step(session, ctx):
        return ValidationResult(passed=True, message="ok")

    def loader(lab_id):
        carregados.append(lab_id)
        return validate_step

    app = create_app(
        {
            "labs_dir": str(FIXTURES),
            "progress_file": str(progress_file),
            "session_factory": lambda: object(),
            "validator_loader": loader,
        }
    )
    resp = app.test_client().post(f"/api/validate/{LAB}/step-03", json={})
    assert resp.status_code == 200
    assert resp.get_json()["passed"] is True
    assert carregados == [LAB]
