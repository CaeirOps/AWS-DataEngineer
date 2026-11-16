"""Testes de propriedade de contagem de progresso do ProgressStore.

Feature: aws-data-engineer-workshop
"""

import os
import tempfile

from hypothesis import given, settings, strategies as st

from app.models import LabMetadata, StepMetadata
from app.progress_store import ProgressStore

TYPES = ["info", "deploy", "task", "teardown", "completion"]


def _lab(types: list[str]) -> LabMetadata:
    steps = [
        StepMetadata(step_id=f"step-{i:02d}", title=f"s{i}", type=t)
        for i, t in enumerate(types, start=1)
    ]
    return LabMetadata(
        lab_id="lab-01",
        title="t",
        description="d",
        difficulty="iniciante",
        estimated_duration_minutes=1,
        estimated_cost_usd=0.0,
        cost_disclaimer="c",
        dea_domains=[],
        dea_tasks=[],
        services=["Amazon S3"],
        prerequisites={},
        steps=steps,
    )


@st.composite
def scenarios(draw):
    types = draw(st.lists(st.sampled_from(TYPES), min_size=1, max_size=8))
    n = len(types)
    ops = draw(
        st.lists(
            st.tuples(
                st.integers(min_value=0, max_value=n - 1),
                st.sampled_from(["passed", "failed"]),
                st.booleans(),
            ),
            max_size=30,
        )
    )
    return types, ops


@settings(max_examples=50, deadline=None)
@given(scenarios())
def test_property_2_counts_match_model(scenario):
    """Property 2: concluidos == steps `passed` e total == steps do metadata.

    **Validates: Requirements 2.2**
    """
    types, ops = scenario
    meta = _lab(types)
    with tempfile.TemporaryDirectory() as tmp:
        store = ProgressStore(os.path.join(tmp, "progress.json"))
        model: dict[str, str] = {}  # modelo em memoria: step_id -> status
        for idx, status, inc in ops:
            sid = meta.steps[idx].step_id
            store.update_step("lab-01", sid, status, increment_attempts=inc, lab_metadata=meta)
            # `passed` e terminal: um `failed` posterior nao regride
            if model.get(sid) != "passed":
                model[sid] = status

        completed, total = store.get_lab_counts("lab-01", meta)
        assert completed == sum(1 for v in model.values() if v == "passed")
        assert total == len(types)
        # contagem direta a partir de get_lab_progress
        raw = store.get_lab_progress("lab-01")["steps"]
        assert completed == sum(1 for v in raw.values() if v["status"] == "passed")


@settings(max_examples=50, deadline=None)
@given(scenarios())
def test_property_7_lab_status_completed_iff_all_tasks_passed(scenario):
    """Property 7 (auxiliar): `completed` sse todos os steps `task` estao `passed`.

    **Validates: Requirements 5.7**
    """
    types, ops = scenario
    meta = _lab(types)
    with tempfile.TemporaryDirectory() as tmp:
        store = ProgressStore(os.path.join(tmp, "progress.json"))
        model: dict[str, str] = {}
        for idx, status, inc in ops:
            sid = meta.steps[idx].step_id
            store.update_step("lab-01", sid, status, increment_attempts=inc, lab_metadata=meta)
            if model.get(sid) != "passed":
                model[sid] = status

        required = [s for s in meta.steps if s.type == "task"] or list(meta.steps)
        expected_done = all(model.get(s.step_id) == "passed" for s in required)
        status = store._compute_lab_status("lab-01", meta)
        assert (status == "completed") == expected_done


def test_counts_for_unvisited_lab(tmp_path):
    """Lab nunca visitado: 0 concluidos e total igual ao metadata."""
    store = ProgressStore(str(tmp_path / "progress.json"))
    meta = _lab(["info", "task", "task"])
    assert store.get_lab_counts("lab-01", meta) == (0, 3)
