"""Property 4: validação atualiza o progresso conforme o resultado.

Feature: aws-data-engineer-workshop, Property 4
**Validates: Requirements 5.2**
"""

import json
import os
import tempfile

from hypothesis import given, settings, strategies as st

from app.lab_catalog import LabCatalog
from app.models import ValidationResult
from app.progress_store import ProgressStore
from app.validation_service import ValidationService
from tests.fixtures import NO_INFRA_FIELDS

_ID = st.from_regex(r"[a-z][a-z0-9]{0,8}", fullmatch=True)


def _build_catalog(root, lab_id, task_ids):
    """Cria um lab temporário com steps task e retorna o catálogo."""
    steps = [
        {"step_id": sid, "title": sid, "type": "task", "paths": ["console", "cli"]}
        for sid in task_ids
    ]
    meta = {
        "lab_id": lab_id,
        "title": "Lab",
        "description": "d",
        "difficulty": "iniciante",
        "estimated_duration_minutes": 10,
        "estimated_cost_usd": 0.0,
        "cost_disclaimer": "n/a",
        "dea_domains": [],
        "dea_tasks": [],
        "services": ["Amazon S3"],
        **NO_INFRA_FIELDS,
        "steps": steps,
    }
    lab_dir = os.path.join(root, "labs", lab_id)
    os.makedirs(lab_dir)
    with open(os.path.join(lab_dir, "metadata.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh)
    return LabCatalog(os.path.join(root, "labs"))


@settings(max_examples=50, deadline=None)
@given(
    lab_num=st.integers(1, 20),
    task_ids=st.lists(_ID, min_size=1, max_size=4, unique=True),
    outcomes=st.lists(st.booleans(), min_size=1, max_size=6),
    pick=st.integers(0, 3),
)
def test_validation_updates_progress(lab_num, task_ids, outcomes, pick):
    lab_id = f"lab-{lab_num:02d}"
    step_id = task_ids[pick % len(task_ids)]
    with tempfile.TemporaryDirectory() as root:
        catalog = _build_catalog(root, lab_id, task_ids)
        store = ProgressStore(os.path.join(root, "progress", "progress.json"))
        current = {"passed": False}

        def loader(_lab_id):
            return lambda session, ctx: ValidationResult(
                passed=current["passed"], message="m", hint="h"
            )

        service = ValidationService(
            catalog, store, session_factory=lambda: object(), validator_loader=loader
        )

        for i, outcome in enumerate(outcomes, start=1):
            before = store.get_lab_progress(lab_id)["steps"].get(step_id)
            was_passed = before is not None and before["status"] == "passed"
            old_passed_at = before["passed_at"] if before else None

            current["passed"] = outcome
            response = service.validate(lab_id, step_id)

            after = store.get_lab_progress(lab_id)["steps"][step_id]
            assert after["attempts"] == i
            assert response["attempt_count"] == i
            assert after["last_attempt_at"] is not None
            if outcome:
                assert after["status"] == "passed"
                assert after["passed_at"] is not None
                if was_passed:
                    # passed_at preservado em novas validações bem-sucedidas
                    assert after["passed_at"] == old_passed_at
            elif was_passed:
                assert after["status"] == "passed"
                assert after["passed_at"] == old_passed_at
            else:
                assert after["status"] == "failed"
                assert after["passed_at"] is None
            assert response["step_status"] == after["status"]
