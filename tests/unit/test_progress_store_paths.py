"""Testes da troca de Trilha do ProgressStore.

Feature: aws-data-engineer-workshop
Property 17: Troca de Trilha só altera a preferência
**Validates: Requirements 11.2, 11.3**
"""
import json
import os
import shutil
import tempfile

import pytest
from hypothesis import given, settings, strategies as st

from app.errors import InvalidPathError, InvalidPayloadError
from app.progress_store import ProgressStore

STATUSES = ["not_visited", "failed", "passed"]
TS = st.one_of(st.none(), st.just("2025-01-01T10:00:00Z"), st.just("2025-02-03T04:05:06Z"))

step_st = st.fixed_dictionaries(
    {
        "status": st.sampled_from(STATUSES),
        "attempts": st.integers(min_value=0, max_value=20),
        "last_attempt_at": TS,
        "passed_at": TS,
    }
)
lab_st = st.fixed_dictionaries(
    {
        "status": st.sampled_from(["not_started", "in_progress", "completed"]),
        "started_at": TS,
        "completed_at": TS,
        "steps": st.dictionaries(
            st.text(alphabet="abcdefgh-0123456789", min_size=1, max_size=8),
            step_st,
            max_size=5,
        ),
    }
)
labs_st = st.dictionaries(
    st.text(alphabet="abcdefgh-0123456789", min_size=1, max_size=8), lab_st, max_size=4
)
paths_st = st.lists(st.sampled_from(["console", "cli"]), min_size=1, max_size=8)


def _step_fields(labs: dict) -> dict:
    """Extrai os campos de step que não podem mudar na troca de Trilha."""
    return {
        (lab_id, step_id): (
            s["status"], s["attempts"], s["last_attempt_at"], s["passed_at"]
        )
        for lab_id, lab in labs.items()
        for step_id, s in lab["steps"].items()
    }


def _write_progress(directory: str, labs: dict, preferences=None) -> str:
    filepath = os.path.join(directory, "progress.json")
    data = {"schema_version": "1.0", "last_updated": "2025-01-01T00:00:00Z", "labs": labs}
    if preferences is not None:
        data["preferences"] = preferences
    with open(filepath, "w", encoding="utf-8") as fh:
        json.dump(data, fh)
    return filepath


@given(labs=labs_st, seq=paths_st, use_apply=st.booleans())
@settings(max_examples=50, deadline=None)
def test_property_17_troca_de_trilha_so_altera_preferencia(labs, seq, use_apply):
    directory = tempfile.mkdtemp()
    try:
        store = ProgressStore(_write_progress(directory, labs, {"path": "console"}))
        before = _step_fields(store.get_progress()["labs"])
        for path in seq:
            if use_apply:
                store.apply_update({"preferences": {"path": path}})
            else:
                store.set_preferred_path(path)
        after = store.get_progress()
        assert after["preferences"]["path"] == seq[-1]
        assert store.get_preferred_path() == seq[-1]
        assert _step_fields(after["labs"]) == before
        assert _step_fields(after["labs"]) == _step_fields(labs)
    finally:
        shutil.rmtree(directory, ignore_errors=True)


def test_arquivo_sem_preferences_e_lido_como_console():
    directory = tempfile.mkdtemp()
    try:
        store = ProgressStore(_write_progress(directory, {}))
        assert store.get_preferred_path() == "console"
        assert store.get_progress()["preferences"] == {"path": "console"}
    finally:
        shutil.rmtree(directory, ignore_errors=True)


@pytest.mark.parametrize("invalido", ["", "CLI", "terminal", None, 1])
def test_valor_invalido_e_rejeitado_sem_alterar_preferencia(invalido):
    directory = tempfile.mkdtemp()
    try:
        store = ProgressStore(_write_progress(directory, {}, {"path": "cli"}))
        with pytest.raises(InvalidPathError):
            store.set_preferred_path(invalido)
        with pytest.raises(InvalidPathError):
            store.apply_update({"preferences": {"path": invalido}})
        assert store.get_preferred_path() == "cli"
    finally:
        shutil.rmtree(directory, ignore_errors=True)


@pytest.mark.parametrize(
    "payload", [{}, {"preferences": {}}, {"preferences": "cli"}, {"path": "cli"}, None, []]
)
def test_payload_invalido_e_rejeitado(payload):
    directory = tempfile.mkdtemp()
    try:
        store = ProgressStore(_write_progress(directory, {}, {"path": "cli"}))
        with pytest.raises(InvalidPayloadError):
            store.apply_update(payload)
        assert store.get_preferred_path() == "cli"
    finally:
        shutil.rmtree(directory, ignore_errors=True)
