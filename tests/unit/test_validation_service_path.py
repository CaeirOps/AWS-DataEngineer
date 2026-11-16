"""Testes de unidade: o resultado da validação não depende da Trilha.

Requisito 11.4: o `context` repassado ao validador não contém `path`.
"""

import copy
import json

import pytest
from botocore.exceptions import ClientError

from app.lab_catalog import LabCatalog
from app.models import ValidationResult
from app.progress_store import ProgressStore
from app.validation_service import ValidationService

LAB_ID = "lab-01"
STEP_ID = "step-task"
TRAILS = ("console", "cli")


def _build_service(tmp_path, validator, session):
    """Monta catálogo temporário e serviço com validador e sessão injetados."""
    lab_dir = tmp_path / "labs" / LAB_ID
    lab_dir.mkdir(parents=True)
    meta = {
        "lab_id": LAB_ID,
        "title": "Lab de teste",
        "description": "d",
        "difficulty": "iniciante",
        "estimated_duration_minutes": 10,
        "estimated_cost_usd": 0.0,
        "cost_disclaimer": "c",
        "dea_domains": [],
        "dea_tasks": [],
        "services": ["Amazon S3"],
        "steps": [
            {
                "step_id": STEP_ID,
                "title": "Task",
                "type": "task",
                "paths": ["console", "cli"],
            }
        ],
    }
    (lab_dir / "metadata.json").write_text(json.dumps(meta), encoding="utf-8")
    catalog = LabCatalog(str(tmp_path / "labs"))
    store = ProgressStore(str(tmp_path / "progress" / "progress.json"))
    return ValidationService(
        catalog,
        store,
        session_factory=lambda: session,
        validator_loader=lambda lab_id: validator,
    )


@pytest.mark.parametrize("trail", TRAILS)
def test_validador_recebe_context_sem_path(tmp_path, trail):
    recebidos = []

    def validator(session, context):
        recebidos.append(dict(context))
        return ValidationResult(passed=True, message="ok")

    service = _build_service(tmp_path, validator, object())
    service.validate(LAB_ID, STEP_ID, {"path": trail, "extra": "x"})

    assert len(recebidos) == 1
    assert "path" not in recebidos[0]
    assert recebidos[0]["extra"] == "x"
    assert recebidos[0]["step_id"] == STEP_ID
    assert recebidos[0]["lab_id"] == LAB_ID


@pytest.mark.parametrize("passed", [True, False])
def test_resultado_identico_para_as_duas_trilhas(tmp_path, passed):
    session = object()
    sessoes = []

    def validator(s, context):
        sessoes.append(s)
        return ValidationResult(passed=passed, message="msg", hint="dica")

    respostas = []
    for i, trail in enumerate(TRAILS):
        service = _build_service(tmp_path / f"t{i}", validator, session)
        resp = service.validate(LAB_ID, STEP_ID, {"path": trail})
        respostas.append(resp)

    assert respostas[0] == respostas[1]
    assert respostas[0]["passed"] is passed
    assert all(s is session for s in sessoes)


def test_erro_de_credencial_identico_para_as_duas_trilhas(tmp_path):
    session = object()

    def validator(s, context):
        raise ClientError(
            {"Error": {"Code": "ExpiredToken", "Message": "token expirado"}},
            "ListBuckets",
        )

    respostas = []
    for i, trail in enumerate(TRAILS):
        service = _build_service(tmp_path / f"t{i}", validator, session)
        respostas.append(service.validate(LAB_ID, STEP_ID, {"path": trail}))

    assert respostas[0] == respostas[1]
    assert respostas[0]["passed"] is False
    assert "ExpiredToken" in respostas[0]["message"]
    assert "token expirado" in respostas[0]["message"]


@pytest.mark.parametrize("trail", TRAILS)
def test_context_do_chamador_nao_e_mutado(tmp_path, trail):
    def validator(session, context):
        context["mutado_pelo_validador"] = True
        return ValidationResult(passed=True, message="ok")

    service = _build_service(tmp_path, validator, object())
    original = {"path": trail, "extra": ["a", "b"]}
    copia = copy.deepcopy(original)

    service.validate(LAB_ID, STEP_ID, original)

    assert original == copia
