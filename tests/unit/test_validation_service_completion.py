"""Property 7: lab concluído somente quando todos os steps `task` passam.

**Validates: Requirements 5.7**
"""

import json
import os
import tempfile

from hypothesis import given, settings, strategies as st

from app.lab_catalog import LabCatalog
from app.models import ValidationResult
from app.progress_store import ProgressStore
from app.validation_service import ValidationService

LAB_ID = "lab-01"
NON_TASK_TYPES = ["info", "deploy", "teardown", "completion"]


def _build_catalog(root: str, task_count: int, extra_types: list) -> LabCatalog:
    """Cria um lab temporário com steps de tipos mistos."""
    steps = [{"step_id": "s-info", "title": "Info", "type": "info"}]
    for i, t in enumerate(extra_types):
        steps.append({"step_id": f"s-{t}-{i}", "title": t, "type": t})
    for i in range(task_count):
        steps.append(
            {
                "step_id": f"task-{i}",
                "title": f"Task {i}",
                "type": "task",
                "paths": ["console", "cli"],
            }
        )
    meta = {
        "lab_id": LAB_ID,
        "title": "Lab",
        "description": "d",
        "difficulty": "iniciante",
        "estimated_duration_minutes": 10,
        "estimated_cost_usd": 0,
        "cost_disclaimer": "c",
        "dea_domains": [],
        "dea_tasks": [],
        "services": ["Amazon S3"],
        "steps": steps,
    }
    lab_dir = os.path.join(root, LAB_ID)
    os.makedirs(lab_dir)
    with open(os.path.join(lab_dir, "metadata.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh)
    return LabCatalog(root)


@settings(max_examples=50, deadline=None)
@given(
    task_count=st.integers(min_value=1, max_value=4),
    extra_types=st.lists(st.sampled_from(NON_TASK_TYPES), max_size=4),
    data=st.data(),
)
def test_lab_completed_iff_all_tasks_passed(task_count, extra_types, data):
    calls = data.draw(
        st.lists(
            st.tuples(st.integers(0, task_count - 1), st.booleans()),
            max_size=25,
        )
    )
    with tempfile.TemporaryDirectory() as tmp:
        catalog = _build_catalog(os.path.join(tmp, "labs"), task_count, extra_types)
        store = ProgressStore(os.path.join(tmp, "progress", "progress.json"))

        # Resultado do validador fake definido pela chamada corrente
        current = {"passed": False}

        def validate_step(session, ctx):
            return ValidationResult(passed=current["passed"], message="m")

        service = ValidationService(
            catalog,
            store,
            session_factory=lambda: object(),
            validator_loader=lambda lab_id: validate_step,
        )

        passed_ids: set = set()
        was_completed = False
        all_tasks = {f"task-{i}" for i in range(task_count)}
        for idx, ok in calls:
            step_id = f"task-{idx}"
            current["passed"] = ok
            service.validate(LAB_ID, step_id)
            if ok:
                passed_ids.add(step_id)

            progress = store.get_lab_progress(LAB_ID)
            for sid in all_tasks:
                expected = "passed" if sid in passed_ids else None
                actual = progress["steps"].get(sid, {}).get("status")
                if expected:
                    assert actual == "passed"
            completed = progress["status"] == "completed"
            assert completed == (passed_ids == all_tasks)
            if was_completed:
                assert completed  # nunca regride
            was_completed = completed
