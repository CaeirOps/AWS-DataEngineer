"""Property 19: marcar steps não-task não altera os steps task e avança a retomada.

**Validates: Requirements 2.4, 2.6, 3.2**
"""

import copy
import dataclasses
import os
import shutil
import tempfile

import pytest
from hypothesis import HealthCheck, given, settings, strategies as st

from app.errors import StepRequiresValidationError
from app.models import LabMetadata, StepMetadata
from app.progress_store import ProgressStore

LAB_ID = "lab-visited"
NON_TASK_TYPES = ("info", "deploy", "teardown", "completion")


def _build_lab(types: list[str]) -> LabMetadata:
    """Monta um LabMetadata no próprio teste, sem depender do LabCatalog."""
    steps = [
        StepMetadata(step_id=f"s{i}", title=f"Step {i}", type=t)
        for i, t in enumerate(types)
    ]
    kwargs = dict(
        lab_id=LAB_ID,
        title="Lab",
        description="d",
        difficulty="iniciante",
        estimated_duration_minutes=10,
        estimated_cost_usd=0.0,
        cost_disclaimer="c",
        dea_domains=["1"],
        dea_tasks=["1.1"],
        prerequisites={},
        steps=steps,
    )
    # Passa `services` somente se o modelo já exigir/aceitar o campo
    fields = {f.name for f in dataclasses.fields(LabMetadata)}
    if "services" in fields:
        kwargs["services"] = ["Amazon S3"]
    return LabMetadata(**kwargs)


@st.composite
def scenarios(draw):
    """Gera tipos de step mistos (ao menos um task e um não-task) e operações."""
    types = draw(
        st.lists(
            st.sampled_from(("task",) + NON_TASK_TYPES), min_size=2, max_size=10
        ).filter(lambda ts: "task" in ts and any(t != "task" for t in ts))
    )
    n = len(types)
    task_idx = [i for i, t in enumerate(types) if t == "task"]
    other_idx = [i for i, t in enumerate(types) if t != "task"]
    # Progresso prévio: tentativas em steps task e visitas prévias em não-task
    task_ops = draw(
        st.lists(
            st.tuples(st.sampled_from(task_idx), st.sampled_from(("passed", "failed"))),
            max_size=12,
        )
    )
    pre_visited = draw(st.sets(st.sampled_from(other_idx)))
    to_mark = draw(st.lists(st.sampled_from(other_idx), min_size=1, max_size=12))
    return types, task_ops, sorted(pre_visited), to_mark


def _first_not_passed(lab: LabMetadata, progress: dict) -> str:
    for s in lab.steps:
        if progress["steps"].get(s.step_id, {}).get("status") != "passed":
            return s.step_id
    return lab.steps[-1].step_id


@pytest.fixture
def fresh_store_factory():
    """Cria um diretório temporário novo por exemplo (não usa tmp_path)."""
    dirs = []

    def make():
        d = tempfile.mkdtemp(prefix="progress-visited-")
        dirs.append(d)
        return ProgressStore(os.path.join(d, "progress.json")), d

    yield make
    for d in dirs:
        shutil.rmtree(d, ignore_errors=True)


@settings(
    max_examples=60,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(data=scenarios())
def test_property_19_mark_visited(fresh_store_factory, data):
    """**Validates: Requirements 2.4, 2.6, 3.2**"""
    types, task_ops, pre_visited, to_mark = data
    lab = _build_lab(types)
    store, _ = fresh_store_factory()

    # Monta um progresso válido
    for i in pre_visited:
        store.mark_visited(LAB_ID, f"s{i}", lab)
    for i, status in task_ops:
        store.update_step(LAB_ID, f"s{i}", status, lab_metadata=lab)

    task_ids = [s.step_id for s in lab.steps if s.type == "task"]
    before = copy.deepcopy(store.get_lab_progress(LAB_ID))

    for i in to_mark:
        step_id = f"s{i}"
        prev = copy.deepcopy(store.get_lab_progress(LAB_ID)["steps"].get(step_id))
        result = store.mark_visited(LAB_ID, step_id, lab)
        now_step = store.get_lab_progress(LAB_ID)["steps"][step_id]

        # (b) status passed e attempts inalterado (0 em steps não visitados por tentativa)
        assert now_step["status"] == "passed"
        assert now_step["attempts"] == (prev["attempts"] if prev else 0) == 0
        assert result["attempt_count"] == 0
        # Idempotência: passed_at preservado em chamadas repetidas
        if prev and prev["status"] == "passed":
            assert now_step["passed_at"] == prev["passed_at"]
        else:
            assert now_step["passed_at"] is not None

    after = store.get_lab_progress(LAB_ID)

    # (a) steps task intocados (status, attempts, timestamps)
    for sid in task_ids:
        assert after["steps"].get(sid) == before["steps"].get(sid)

    # (c) resume_step é o primeiro step não passed, na ordem do metadata
    assert store.get_resume_step(LAB_ID, lab) == _first_not_passed(lab, after)

    # completed depende somente dos steps task
    all_tasks_passed = all(
        after["steps"].get(sid, {}).get("status") == "passed" for sid in task_ids
    )
    assert (after["status"] == "completed") == all_tasks_passed
    assert (store._compute_lab_status(LAB_ID, lab) == "completed") == all_tasks_passed


@settings(
    max_examples=30,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(data=scenarios())
def test_property_19_task_step_rejected_without_changes(fresh_store_factory, data):
    """**Validates: Requirements 2.4, 2.6, 3.2**"""
    types, task_ops, pre_visited, _ = data
    lab = _build_lab(types)
    store, d = fresh_store_factory()
    for i in pre_visited:
        store.mark_visited(LAB_ID, f"s{i}", lab)
    for i, status in task_ops:
        store.update_step(LAB_ID, f"s{i}", status, lab_metadata=lab)
    # Garante que o arquivo existe antes de comparar bytes
    store.get_progress()
    path = os.path.join(d, "progress.json")
    with open(path, "rb") as fh:
        raw_before = fh.read()

    for s in lab.steps:
        if s.type == "task":
            with pytest.raises(StepRequiresValidationError):
                store.mark_visited(LAB_ID, s.step_id, lab)

    with open(path, "rb") as fh:
        assert fh.read() == raw_before


def test_mark_visited_example_resume_advances(fresh_store_factory):
    """Exemplo: info visitado avança a retomada para o primeiro task."""
    lab = _build_lab(["info", "deploy", "task", "teardown"])
    store, _ = fresh_store_factory()
    r = store.mark_visited(LAB_ID, "s0", lab)
    assert r["resume_step"] == "s1"
    r = store.mark_visited(LAB_ID, "s1", lab)
    assert r["resume_step"] == "s2"
    assert r["lab_status"] == "in_progress"
    store.update_step(LAB_ID, "s2", "passed", lab_metadata=lab)
    assert store.get_lab_progress(LAB_ID)["status"] == "completed"
