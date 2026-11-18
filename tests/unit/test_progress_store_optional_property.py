"""Property 28: Prática opcional não bloqueia a conclusão.

**Feature: aws-data-engineer-workshop, Property 28: Prática opcional não
bloqueia a conclusão**
**Validates: Requirements 5.8, 19.2**

Para qualquer módulo com steps de tipos mistos e para qualquer progresso, o
módulo fica `completed` se e somente se todos os steps `task` não opcionais e
todos os steps `quiz` estão `passed`, independentemente das práticas opcionais.
"""

import tempfile
from pathlib import Path

from hypothesis import given, settings, strategies as st

from app.models import LabMetadata, StepMetadata
from app.progress_store import ProgressStore

LAB_ID = "lab-p28"
STATUSES = ["not_visited", "failed", "passed"]


@st.composite
def step_kinds(draw):
    """Tipos de step, com pelo menos um obrigatório (task não opcional ou quiz)."""
    kinds = draw(
        st.lists(
            st.sampled_from(["info", "deploy", "teardown", "completion", "task", "optional", "quiz"]),
            min_size=1,
            max_size=10,
        )
    )
    required = draw(st.sampled_from(["task", "quiz"]))
    kinds.insert(draw(st.integers(0, len(kinds))), required)
    return kinds


def build_lab(kinds):
    steps = []
    for i, kind in enumerate(kinds):
        sid = f"s{i}"
        if kind in ("task", "optional"):
            optional = kind == "optional"
            steps.append(
                StepMetadata(
                    sid, sid, "task", paths=["console", "cli"],
                    optional=optional, cost_note="custo" if optional else None,
                )
            )
        elif kind == "quiz":
            steps.append(StepMetadata(sid, sid, "quiz", pass_score=0.7))
        else:
            steps.append(StepMetadata(sid, sid, kind))
    return LabMetadata(
        lab_id=LAB_ID, title="t", description="d", difficulty="iniciante",
        estimated_duration_minutes=10, estimated_cost_usd=None, cost_disclaimer="",
        dea_domains=["D1"], dea_tasks=["1.1"], services=["Amazon S3"],
        prerequisites={}, steps=steps,
    )


@settings(max_examples=200, deadline=None)
@given(kinds=step_kinds(), data=st.data())
def test_status_completed_iff_required_steps_passed(kinds, data):
    lab = build_lab(kinds)
    statuses = {s.step_id: data.draw(st.sampled_from(STATUSES)) for s in lab.steps}
    progress = {
        "status": "in_progress",
        "steps": {sid: {"status": st_} for sid, st_ in statuses.items()},
    }
    required_passed = all(
        statuses[s.step_id] == "passed"
        for s in lab.steps
        if (s.type == "task" and not s.optional) or s.type == "quiz"
    )
    completed = ProgressStore._status_from(progress, lab) == "completed"
    assert completed == required_passed


@settings(max_examples=50, deadline=None)
@given(kinds=step_kinds(), data=st.data())
def test_optional_progress_never_changes_completion(kinds, data):
    """Passar ou falhar práticas opcionais no store não muda a conclusão."""
    lab = build_lab(kinds)
    optional = [s.step_id for s in lab.steps if s.type == "task" and s.optional]
    required = [s.step_id for s in lab.steps if s.required]
    with tempfile.TemporaryDirectory() as tmp:
        store = ProgressStore(str(Path(tmp) / "progress.json"))
        for sid in optional:
            store.update_step(LAB_ID, sid, data.draw(st.sampled_from(["passed", "failed"])), lab_metadata=lab)
            assert store.get_lab_progress(LAB_ID)["status"] != "completed"
        for sid in required:
            store.update_step(LAB_ID, sid, "passed", lab_metadata=lab)
        assert store.get_lab_progress(LAB_ID)["status"] == "completed"
