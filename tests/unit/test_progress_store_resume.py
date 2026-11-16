"""Testes de propriedade para `ProgressStore.get_resume_step`.

Feature: aws-data-engineer-workshop
Property 3: Step de retomada é sempre o primeiro step não concluído.
**Validates: Requirements 2.3, 2.4**
"""

import tempfile
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from app.models import LabMetadata, StepMetadata
from app.progress_store import ProgressStore

LAB_ID = "lab-teste"
TIPOS = ["info", "deploy", "task", "teardown", "completion"]


def _make_lab(step_ids: list[str], tipos: list[str]) -> LabMetadata:
    """Monta um LabMetadata mínimo com os steps na ordem dada."""
    steps = [
        StepMetadata(step_id=sid, title=sid, type=tipo)
        for sid, tipo in zip(step_ids, tipos)
    ]
    return LabMetadata(
        lab_id=LAB_ID,
        title="Lab de teste",
        description="",
        difficulty="iniciante",
        estimated_duration_minutes=10,
        estimated_cost_usd=0.0,
        cost_disclaimer="",
        dea_domains=[],
        dea_tasks=[],
        services=["Amazon S3"],
        prerequisites={},
        steps=steps,
    )


@st.composite
def lab_with_statuses(draw):
    """Gera um lab (ids únicos) e um status por step: passed, failed ou None."""
    n = draw(st.integers(min_value=1, max_value=12))
    ids = [f"step-{i}" for i in draw(st.permutations(range(n)))]
    tipos = draw(st.lists(st.sampled_from(TIPOS), min_size=n, max_size=n))
    statuses = draw(
        st.lists(st.sampled_from(["passed", "failed", None]), min_size=n, max_size=n)
    )
    return _make_lab(ids, tipos), statuses


def _novo_store() -> ProgressStore:
    # Diretório temporário novo por exemplo gerado (tmp_path é por teste).
    tmp = tempfile.mkdtemp(prefix="resume-")
    return ProgressStore(str(Path(tmp) / "progress.json"))


@settings(max_examples=100, deadline=None)
@given(data=lab_with_statuses())
def test_property_3_resume_is_first_non_passed(data):
    lab, statuses = data
    store = _novo_store()
    for meta, status in zip(lab.steps, statuses):
        if status is not None:
            store.update_step(LAB_ID, meta.step_id, status, lab_metadata=lab)

    # Oráculo simples: primeiro step cujo status não é passed
    esperado = None
    for meta, status in zip(lab.steps, statuses):
        if status != "passed":
            esperado = meta.step_id
            break
    if esperado is None:
        # Todos passed: comportamento atual retorna o último step
        esperado = lab.steps[-1].step_id

    assert store.get_resume_step(LAB_ID, lab) == esperado


def test_lab_never_started_returns_first_step(tmp_path):
    lab = _make_lab(["a", "b", "c"], ["info", "task", "completion"])
    store = ProgressStore(str(tmp_path / "progress.json"))
    assert store.get_resume_step(LAB_ID, lab) == "a"


def test_all_passed_returns_last_step(tmp_path):
    # Documenta o comportamento atual: com tudo passed, retorna o último step.
    lab = _make_lab(["a", "b", "c"], ["info", "task", "completion"])
    store = ProgressStore(str(tmp_path / "progress.json"))
    for s in lab.steps:
        store.update_step(LAB_ID, s.step_id, "passed", lab_metadata=lab)
    assert store.get_resume_step(LAB_ID, lab) == "c"


def test_failed_step_is_resume_point(tmp_path):
    lab = _make_lab(["a", "b", "c"], ["info", "task", "task"])
    store = ProgressStore(str(tmp_path / "progress.json"))
    store.update_step(LAB_ID, "a", "passed", lab_metadata=lab)
    store.update_step(LAB_ID, "b", "failed", lab_metadata=lab)
    store.update_step(LAB_ID, "c", "passed", lab_metadata=lab)
    assert store.get_resume_step(LAB_ID, lab) == "b"
