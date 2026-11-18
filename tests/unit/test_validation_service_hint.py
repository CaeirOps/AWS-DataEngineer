"""Testes de propriedade da lógica de limiar de dica do `ValidationService`.

Feature: aws-data-engineer-workshop, Property 6: exibição de dica segue o
limiar configurado.

Decisão atual do serviço (documentada aqui):
- `show_hint_button` é verdadeiro se e somente se `attempt_count >= hint_threshold`.
- `hint` só é repassado quando a validação falhou E `show_hint_button` é
  verdadeiro; em caso de sucesso ou abaixo do limiar, `hint` é `None`.
"""

import json
import tempfile
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from app.lab_catalog import LabCatalog
from app.models import ValidationResult
from app.progress_store import ProgressStore
from app.validation_service import ValidationService
from tests.fixtures import NO_INFRA_FIELDS

LAB_ID = "lab-01"
STEP_ID = "step-task"
HINT_TEXT = "dica do validador"


def _build_catalog(labs_dir: Path, threshold: int) -> LabCatalog:
    """Cria um lab mínimo com um step `task` e o limiar informado."""
    lab_dir = labs_dir / LAB_ID
    lab_dir.mkdir(parents=True)
    meta = {
        "lab_id": LAB_ID,
        "title": "Lab",
        "description": "d",
        "difficulty": "iniciante",
        "estimated_duration_minutes": 10,
        "estimated_cost_usd": 0,
        "cost_disclaimer": "n/a",
        "dea_domains": [],
        "dea_tasks": [],
        "services": ["Amazon S3"],
        **NO_INFRA_FIELDS,
        "steps": [
            {
                "step_id": STEP_ID,
                "title": "Task",
                "type": "task",
                "hint_threshold": threshold,
                "paths": ["console", "cli"],
            }
        ],
    }
    (lab_dir / "metadata.json").write_text(json.dumps(meta), encoding="utf-8")
    return LabCatalog(str(labs_dir))


@settings(max_examples=100, deadline=None)
@given(
    threshold=st.integers(min_value=1, max_value=10),
    outcomes=st.lists(st.booleans(), min_size=1, max_size=15),
)
def test_hint_button_follows_threshold(threshold, outcomes):
    """**Validates: Requirements 5.5**"""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        catalog = _build_catalog(root / "labs", threshold)
        store = ProgressStore(str(root / "progress" / "progress.json"))

        # Resultados controlados, consumidos um por chamada.
        queue = iter(outcomes)

        def fake_validate(session, ctx):
            passed = next(queue)
            return ValidationResult(passed=passed, message="m", hint=HINT_TEXT)

        service = ValidationService(
            catalog,
            store,
            session_factory=lambda: object(),
            validator_loader=lambda lab_id: fake_validate,
        )

        for expected_attempts, passed in enumerate(outcomes, start=1):
            resp = service.validate(LAB_ID, STEP_ID)
            assert resp["attempt_count"] == expected_attempts
            assert resp["passed"] is passed
            # Property 6: botão de dica se e somente se tentativas >= limiar
            assert resp["show_hint_button"] == (expected_attempts >= threshold)
            # Decisão do serviço: dica só quando falhou e o botão está visível
            if not passed and expected_attempts >= threshold:
                assert resp["hint"] == HINT_TEXT
            else:
                assert resp["hint"] is None
