"""Testes de propriedade para retry ilimitado do ValidationService.

Feature: aws-data-engineer-workshop
Property 5: Retry ilimitado, tentativas não bloqueiam validação
**Validates: Requirements 5.4**
"""
import json
import os
import shutil
import tempfile

from hypothesis import given, settings, strategies as st

from app.lab_catalog import LabCatalog
from app.models import ValidationResult
from app.progress_store import ProgressStore
from app.validation_service import ValidationService

LAB_ID = "lab-01"
STEP_ID = "step-task"


def _write_catalog(labs_dir: str, hint_threshold: int) -> None:
    """Cria um lab mínimo com um step task em `labs_dir`."""
    lab_dir = os.path.join(labs_dir, LAB_ID)
    os.makedirs(lab_dir, exist_ok=True)
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
                "hint_threshold": hint_threshold,
            }
        ],
    }
    with open(os.path.join(lab_dir, "metadata.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh)


def _seed_progress(filepath: str, status: str, attempts: int) -> None:
    """Pré-grava o progress.json com um número alto de tentativas."""
    data = {
        "schema_version": "1.0",
        "last_updated": "2025-01-01T00:00:00Z",
        "preferences": {"path": "console"},
        "labs": {
            LAB_ID: {
                "status": "in_progress",
                "started_at": "2025-01-01T00:00:00Z",
                "completed_at": None,
                "steps": {
                    STEP_ID: {
                        "status": status,
                        "attempts": attempts,
                        "last_attempt_at": "2025-01-01T00:00:00Z",
                        "passed_at": "2025-01-01T00:00:00Z" if status == "passed" else None,
                    }
                },
            }
        },
    }
    with open(filepath, "w", encoding="utf-8") as fh:
        json.dump(data, fh)


@settings(max_examples=50, deadline=None)
@given(
    previous=st.one_of(
        st.integers(min_value=0, max_value=20),
        st.integers(min_value=0, max_value=10**9),
    ),
    status=st.sampled_from(["failed", "passed"]),
    outcomes=st.lists(st.booleans(), min_size=1, max_size=4),
    threshold=st.integers(min_value=1, max_value=10),
)
def test_retry_ilimitado(previous, status, outcomes, threshold):
    """Qualquer número de tentativas anteriores nunca bloqueia a validação."""
    tmp = tempfile.mkdtemp()
    try:
        labs_dir = os.path.join(tmp, "labs")
        _write_catalog(labs_dir, threshold)
        progress_file = os.path.join(tmp, "progress.json")
        _seed_progress(progress_file, status, previous)

        calls = []
        queue = list(outcomes)

        def validate_step(session, ctx):
            calls.append(ctx["attempt_count"])
            ok = queue[len(calls) - 1]
            return ValidationResult(passed=ok, message="ok" if ok else "falhou", hint="dica")

        service = ValidationService(
            LabCatalog(labs_dir),
            ProgressStore(progress_file),
            session_factory=lambda: object(),
            validator_loader=lambda lab_id: validate_step,
        )

        for i, ok in enumerate(outcomes, start=1):
            resp = service.validate(LAB_ID, STEP_ID)
            # O validador foi executado e o resultado retornado, sem bloqueio
            assert len(calls) == i
            assert resp["passed"] is ok
            # attempt_count cresce de 1 em 1 a partir das tentativas anteriores
            assert resp["attempt_count"] == previous + i
            assert calls[-1] == previous + i
            # Dica só aparece em falha e acima do limiar, nunca bloqueia
            assert resp["show_hint_button"] is (previous + i >= threshold)
            assert (resp["hint"] is not None) is ((not ok) and previous + i >= threshold)
            # Step já passed não regride
            if status == "passed":
                assert resp["step_status"] == "passed"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
