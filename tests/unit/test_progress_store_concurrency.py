"""Testes de concorrência do ProgressStore (Requisitos 2.5 e 9.2).

Vários processos (contexto `spawn`) e threads atualizam steps distintos do
mesmo `progress.json`; nenhuma atualização pode ser perdida.
"""

import json
import multiprocessing
import os
import threading

from app.progress_store import ProgressStore

LAB_ID = "lab-concorrencia"
N_PROCS = 4
N_UPDATES = 30  # atualizações por processo (cada uma em um step distinto)
ATTEMPTS_PER_STEP = 2  # cada step é atualizado 2 vezes: failed e depois passed


def _worker(filepath: str, worker_id: int) -> None:
    """Executa em um processo filho: atualiza steps exclusivos do worker."""
    store = ProgressStore(filepath)
    for i in range(N_UPDATES):
        step_id = f"w{worker_id}-s{i}"
        store.update_step(LAB_ID, step_id, "failed")
        store.update_step(LAB_ID, step_id, "passed")


def _thread_worker(store: ProgressStore, worker_id: int) -> None:
    for i in range(N_UPDATES):
        step_id = f"t{worker_id}-s{i}"
        store.update_step(LAB_ID, step_id, "failed")
        store.update_step(LAB_ID, step_id, "passed")


def _verify(filepath: str, prefixes: list) -> None:
    # Arquivo final é JSON válido
    with open(filepath, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    steps = data["labs"][LAB_ID]["steps"]

    # Nenhuma atualização perdida e contagem de attempts correta
    expected = {f"{p}-s{i}" for p in prefixes for i in range(N_UPDATES)}
    assert set(steps) == expected
    for step_id, step in steps.items():
        assert step["attempts"] == ATTEMPTS_PER_STEP, step_id
        assert step["status"] == "passed", step_id

    # Não sobra arquivo temporário do `os.replace`
    leftovers = [f for f in os.listdir(os.path.dirname(filepath)) if f.endswith(".tmp")]
    assert leftovers == []


def test_concurrent_processes_do_not_lose_updates(tmp_path):
    filepath = str(tmp_path / "progress.json")
    ctx = multiprocessing.get_context("spawn")
    procs = [ctx.Process(target=_worker, args=(filepath, n)) for n in range(N_PROCS)]
    for p in procs:
        p.start()
    for p in procs:
        p.join(timeout=60)
    assert all(p.exitcode == 0 for p in procs)

    _verify(filepath, [f"w{n}" for n in range(N_PROCS)])


def test_concurrent_threads_do_not_lose_updates(tmp_path):
    filepath = str(tmp_path / "progress.json")
    store = ProgressStore(filepath)
    threads = [
        threading.Thread(target=_thread_worker, args=(store, n)) for n in range(N_PROCS)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)

    _verify(filepath, [f"t{n}" for n in range(N_PROCS)])
