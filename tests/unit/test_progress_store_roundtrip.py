"""Testes de propriedade para a serialização do `progress.json`.

**Feature: aws-data-engineer-workshop, Property 12: Serialização/deserialização
de progress.json preserva dados**
**Validates: Requirements 2.5, 9.2**
"""
import copy
import json
import os
import tempfile

from hypothesis import given, settings, strategies as st

from app.progress_store import ProgressStore

LAB_IDS = ["lab-01", "lab-02", "lab-03", "lab-04"]
STEP_IDS = ["step-1", "step-2", "step-3", "step-4", "step-5"]

# Timestamps no formato ISO 8601 usado pelo store
timestamps = st.datetimes(
    min_value=__import__("datetime").datetime(2020, 1, 1),
    max_value=__import__("datetime").datetime(2035, 1, 1),
).map(lambda d: d.strftime("%Y-%m-%dT%H:%M:%SZ"))

steps_st = st.fixed_dictionaries(
    {
        "status": st.sampled_from(["not_visited", "failed", "passed"]),
        "attempts": st.integers(min_value=0, max_value=50),
        "last_attempt_at": st.none() | timestamps,
        "passed_at": st.none() | timestamps,
    }
)

labs_st = st.fixed_dictionaries(
    {
        "status": st.sampled_from(["in_progress", "completed"]),
        "started_at": timestamps,
        "completed_at": st.none() | timestamps,
        "steps": st.dictionaries(st.sampled_from(STEP_IDS), steps_st, max_size=5),
    }
)


@st.composite
def progress_states(draw, with_preferences=True):
    """Gera um estado completo e válido de progresso."""
    state = {
        "schema_version": "1.0",
        "last_updated": draw(timestamps),
        "labs": draw(st.dictionaries(st.sampled_from(LAB_IDS), labs_st, max_size=4)),
    }
    if with_preferences:
        state["preferences"] = {"path": draw(st.sampled_from(["console", "cli"]))}
    return state


def _run_roundtrip(state, lab_id, step_id, status):
    """Grava o estado inicial, aplica `update_step` e verifica a preservação."""
    with tempfile.TemporaryDirectory() as tmp:
        filepath = os.path.join(tmp, "progress.json")
        with open(filepath, "w", encoding="utf-8") as fh:
            json.dump(state, fh)
        before = copy.deepcopy(state)

        ProgressStore(filepath).update_step(lab_id, step_id, status)

        # JSON válido após a gravação
        with open(filepath, "r", encoding="utf-8") as fh:
            after = json.load(fh)

        # Sem temporários residuais (gravação atômica); o .lock é permitido
        leftovers = [
            f for f in os.listdir(tmp) if f not in ("progress.json", "progress.json.lock")
        ]
        assert leftovers == []

        # Campos de topo preservados
        assert after["schema_version"] == before["schema_version"]
        if "preferences" in before:
            assert after["preferences"] == before["preferences"]

        # Labs que não foram tocados ficam idênticos
        for other_id, other in before["labs"].items():
            if other_id != lab_id:
                assert after["labs"][other_id] == other
        assert set(after["labs"]) == set(before["labs"]) | {lab_id}

        # Steps do mesmo lab, exceto o alterado, ficam idênticos
        old_lab = before["labs"].get(lab_id)
        new_lab = after["labs"][lab_id]
        old_steps = old_lab["steps"] if old_lab else {}
        for sid, old_step in old_steps.items():
            if sid != step_id:
                assert new_lab["steps"][sid] == old_step
        assert set(new_lab["steps"]) == set(old_steps) | {step_id}

        # O step alterado reflete exatamente a modificação
        old_step = old_steps.get(step_id)
        new_step = new_lab["steps"][step_id]
        prev_attempts = old_step["attempts"] if old_step else 0
        prev_status = old_step["status"] if old_step else "not_visited"
        assert new_step["attempts"] == prev_attempts + 1
        # Um step `passed` nunca regride
        assert new_step["status"] == ("passed" if prev_status == "passed" else status)

        # Campos do lab que o update não deve mexer
        if old_lab:
            assert new_lab["started_at"] == old_lab["started_at"]
            if old_lab["status"] == "completed":
                assert new_lab["status"] == "completed"
                assert new_lab["completed_at"] == old_lab["completed_at"]


@settings(max_examples=100, deadline=None)
@given(
    state=progress_states(),
    lab_id=st.sampled_from(LAB_IDS),
    step_id=st.sampled_from(STEP_IDS),
    status=st.sampled_from(["passed", "failed"]),
)
def test_roundtrip_preserva_dados(state, lab_id, step_id, status):
    _run_roundtrip(state, lab_id, step_id, status)


@settings(max_examples=50, deadline=None)
@given(
    state=progress_states(with_preferences=False),
    lab_id=st.sampled_from(LAB_IDS),
    step_id=st.sampled_from(STEP_IDS),
    status=st.sampled_from(["passed", "failed"]),
)
def test_roundtrip_arquivo_antigo_sem_preferences(state, lab_id, step_id, status):
    # Arquivo antigo: sem `preferences`; a Trilha padrão deve ser `console`
    _run_roundtrip(state, lab_id, step_id, status)
    with tempfile.TemporaryDirectory() as tmp:
        filepath = os.path.join(tmp, "progress.json")
        with open(filepath, "w", encoding="utf-8") as fh:
            json.dump(state, fh)
        assert ProgressStore(filepath).get_preferred_path() == "console"


def test_arquivo_inexistente_e_criado_com_schema_inicial(tmp_path):
    filepath = tmp_path / "progress.json"
    ProgressStore(str(filepath)).update_step("lab-01", "step-1", "passed")
    data = json.loads(filepath.read_text(encoding="utf-8"))
    assert data["preferences"] == {"path": "console"}
    assert data["labs"]["lab-01"]["steps"]["step-1"]["status"] == "passed"
