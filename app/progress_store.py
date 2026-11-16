"""Gerenciador do `progress.json`.

Seguro entre threads (`threading.Lock`) e entre processos (`fcntl.flock`),
pois o gunicorn executa 2 workers. Cada operação executa o ciclo completo
ler-modificar-gravar dentro da seção protegida, e a gravação é atômica
(arquivo temporário no mesmo diretório + `os.replace`).
"""

import copy
import fcntl
import json
import os
import tempfile
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator, Optional

from app.errors import (
    InvalidPathError,
    InvalidPayloadError,
    StepNotFoundError,
    StepRequiresValidationError,
)
from app.models import LabMetadata

SCHEMA_VERSION = "1.0"
DEFAULT_PATH = "console"
VALID_PATHS = ("console", "cli")
DEFAULT_FILEPATH = "/app/progress/progress.json"
ENV_FILEPATH = "WORKSHOP_PROGRESS_FILE"

STEP_STATUSES = ("not_visited", "failed", "passed")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_step() -> dict:
    return {
        "status": "not_visited",
        "attempts": 0,
        "last_attempt_at": None,
        "passed_at": None,
    }


class ProgressStore:
    """Lê e grava o progresso do usuário em um único arquivo JSON."""

    def __init__(self, filepath: Optional[str] = None):
        """Cria o store.

        Args:
            filepath: caminho do `progress.json`. Se omitido, usa a variável
                de ambiente `WORKSHOP_PROGRESS_FILE` ou `/app/progress/progress.json`.
        """
        self._filepath = filepath or os.environ.get(ENV_FILEPATH, DEFAULT_FILEPATH)
        self._lockpath = self._filepath + ".lock"
        self._lock = threading.Lock()  # entre threads

    # ------------------------------------------------------------------
    # Infraestrutura de lock e I/O
    # ------------------------------------------------------------------

    @contextmanager
    def _locked(self) -> Iterator[None]:
        """Seção crítica: lock de thread + `flock` exclusivo entre processos."""
        directory = os.path.dirname(self._filepath) or "."
        os.makedirs(directory, exist_ok=True)
        with self._lock:
            with open(self._lockpath, "a") as lock_fh:
                fcntl.flock(lock_fh.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(lock_fh.fileno(), fcntl.LOCK_UN)

    def _read(self) -> dict:
        """Lê o arquivo (cria com o schema inicial se não existir).

        Deve ser chamado dentro de `_locked`.
        """
        if not os.path.exists(self._filepath):
            data = {
                "schema_version": SCHEMA_VERSION,
                "last_updated": _now(),
                "preferences": {"path": DEFAULT_PATH},
                "labs": {},
            }
            self._write(data)
            return data
        with open(self._filepath, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        data.setdefault("labs", {})
        return data

    def _write(self, data: dict) -> None:
        """Grava de forma atômica: temporário no mesmo diretório + `os.replace`."""
        directory = os.path.dirname(self._filepath) or "."
        fd, tmp = tempfile.mkstemp(dir=directory, prefix=".progress-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, indent=2)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, self._filepath)
        except BaseException:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    # ------------------------------------------------------------------
    # Leitura
    # ------------------------------------------------------------------

    def get_progress(self) -> dict:
        """Retorna o progresso completo, sempre com `preferences`."""
        with self._locked():
            data = self._read()
        data = copy.deepcopy(data)
        data["preferences"] = {"path": self._path_of(data)}
        return data

    def get_lab_progress(self, lab_id: str) -> dict:
        """Retorna o progresso de um lab (`not_started` se nunca visitado)."""
        with self._locked():
            data = self._read()
        lab = data["labs"].get(lab_id)
        if lab is None:
            return {
                "status": "not_started",
                "started_at": None,
                "completed_at": None,
                "steps": {},
            }
        return copy.deepcopy(lab)

    @staticmethod
    def _path_of(data: dict) -> str:
        path = (data.get("preferences") or {}).get("path")
        return path if path in VALID_PATHS else DEFAULT_PATH

    def get_preferred_path(self) -> str:
        """Retorna `preferences.path`, ou `console` se ausente (arquivos antigos)."""
        with self._locked():
            data = self._read()
        return self._path_of(data)

    # ------------------------------------------------------------------
    # Escrita
    # ------------------------------------------------------------------

    def set_preferred_path(self, path: str) -> None:
        """Grava a Trilha preferida.

        Altera somente `preferences.path` e `last_updated`; nenhum dado de
        steps é modificado (11.2, 11.3).

        Raises:
            InvalidPathError: se `path` não for `console` nem `cli`.
        """
        if path not in VALID_PATHS:
            raise InvalidPathError(
                f"Trilha inválida: {path!r}. Use 'console' ou 'cli'."
            )
        with self._locked():
            data = self._read()
            prefs = data.get("preferences")
            if not isinstance(prefs, dict):
                prefs = {}
            prefs["path"] = path
            data["preferences"] = prefs
            data["last_updated"] = _now()
            self._write(data)

    def apply_update(self, payload: dict) -> dict:
        """Aplica o corpo de `PUT /api/progress` (usado pelo handler da task 12.1).

        Suporta `{"preferences": {"path": "console|cli"}}`, delegando a
        `set_preferred_path`. Retorna o progresso atualizado.

        Raises:
            InvalidPathError: Trilha inválida (HTTP 400, `INVALID_PATH`).
            InvalidPayloadError: payload sem `preferences` válido (HTTP 400).
        """
        prefs = payload.get("preferences") if isinstance(payload, dict) else None
        if not isinstance(prefs, dict) or "path" not in prefs:
            raise InvalidPayloadError(
                'Corpo inválido. Esperado: {"preferences": {"path": "console|cli"}}.'
            )
        self.set_preferred_path(prefs["path"])
        return self.get_progress()

    def update_step(
        self,
        lab_id: str,
        step_id: str,
        status: str,
        increment_attempts: bool = True,
        lab_metadata: Optional[LabMetadata] = None,
    ) -> None:
        """Atualiza status e tentativas de um step atomicamente.

        Transições: `not_visited -> failed|passed`, `failed -> passed`,
        `passed -> passed` (um `failed` posterior não regride um step já
        `passed`; a tentativa é contada). Se `lab_metadata` for informado,
        o status do lab é recalculado com `_compute_lab_status`; caso
        contrário o lab vira `in_progress` (sem regredir de `completed`).

        Raises:
            ValueError: se `status` não for `passed` nem `failed`.
        """
        if status not in ("passed", "failed"):
            raise ValueError(f"Status de step inválido: {status!r}")
        now = _now()
        with self._locked():
            data = self._read()
            lab = data["labs"].setdefault(lab_id, self._new_lab(now))
            step = lab["steps"].setdefault(step_id, _new_step())

            if increment_attempts:
                step["attempts"] += 1
                step["last_attempt_at"] = now
            if step["status"] != "passed":
                step["status"] = status
                if status == "passed":
                    step["passed_at"] = now

            self._refresh_lab_status(lab, lab_metadata, now)
            data["last_updated"] = now
            self._write(data)

    def mark_visited(self, lab_id: str, step_id: str, lab_metadata: LabMetadata) -> dict:
        """Marca um step que não é `task` como `passed` (2.4, 2.6, 3.2).

        Não incrementa `attempts` e é idempotente: se o step já está
        `passed`, `passed_at` não muda. O status do lab é recalculado com
        `lab_metadata`.

        Returns:
            Dicionário com `step_status`, `attempt_count`, `lab_status` e
            `resume_step`.

        Raises:
            StepNotFoundError: `step_id` não existe no metadata.
            StepRequiresValidationError: o step é do tipo `task`.
        """
        meta = next((s for s in lab_metadata.steps if s.step_id == step_id), None)
        if meta is None:
            raise StepNotFoundError(
                f"Step '{step_id}' não encontrado no lab '{lab_id}'."
            )
        if meta.type == "task":
            raise StepRequiresValidationError(
                f"Step '{step_id}' é do tipo task e só é concluído por validação."
            )
        now = _now()
        with self._locked():
            data = self._read()
            lab = data["labs"].setdefault(lab_id, self._new_lab(now))
            step = lab["steps"].setdefault(step_id, _new_step())
            if step["status"] != "passed":
                step["status"] = "passed"
                step["passed_at"] = now
                self._refresh_lab_status(lab, lab_metadata, now)
                data["last_updated"] = now
                self._write(data)
            result = {
                "step_status": step["status"],
                "attempt_count": step["attempts"],
                "lab_status": lab["status"],
            }
        result["resume_step"] = self.get_resume_step(lab_id, lab_metadata)
        return result

    def get_resume_step(self, lab_id: str, lab_metadata: LabMetadata) -> Optional[str]:
        """Retorna o `step_id` do primeiro step (ordem do metadata) não `passed`.

        Se todos estiverem `passed`, retorna o último step do lab.
        """
        steps = self.get_lab_progress(lab_id)["steps"]
        for meta in lab_metadata.steps:
            if steps.get(meta.step_id, {}).get("status") != "passed":
                return meta.step_id
        return lab_metadata.steps[-1].step_id if lab_metadata.steps else None

    def get_lab_counts(self, lab_id: str, lab_metadata: LabMetadata) -> tuple[int, int]:
        """Retorna `(concluidos, total)` de um lab para o dashboard.

        `concluidos` conta os steps do metadata com status `passed`;
        `total` e o numero de steps definidos no metadata.
        """
        steps = self.get_lab_progress(lab_id)["steps"]
        completed = sum(
            1 for s in lab_metadata.steps if steps.get(s.step_id, {}).get("status") == "passed"
        )
        return completed, len(lab_metadata.steps)

    def _compute_lab_status(self, lab_id: str, lab_metadata: LabMetadata) -> str:
        """Calcula o status do lab: `not_started`, `in_progress` ou `completed`.

        `completed` somente se todos os steps do tipo `task` estão `passed`
        (se o lab não tem steps `task`, consideram-se todos os steps).
        """
        lab = self.get_lab_progress(lab_id)
        return self._status_from(lab, lab_metadata)

    # ------------------------------------------------------------------
    # Helpers internos
    # ------------------------------------------------------------------

    @staticmethod
    def _new_lab(now: str) -> dict:
        return {
            "status": "in_progress",
            "started_at": now,
            "completed_at": None,
            "steps": {},
        }

    @staticmethod
    def _status_from(lab: dict, lab_metadata: LabMetadata) -> str:
        steps = lab.get("steps", {})
        if lab.get("status") == "completed":
            return "completed"  # estado final, sem regressão
        required = [s for s in lab_metadata.steps if s.type == "task"] or list(
            lab_metadata.steps
        )
        if required and all(
            steps.get(s.step_id, {}).get("status") == "passed" for s in required
        ):
            return "completed"
        visited = any(v.get("status") != "not_visited" for v in steps.values())
        return "in_progress" if visited else "not_started"

    def _refresh_lab_status(
        self, lab: dict, lab_metadata: Optional[LabMetadata], now: str
    ) -> None:
        if lab_metadata is not None:
            new_status = self._status_from(lab, lab_metadata)
        else:
            new_status = "completed" if lab["status"] == "completed" else "in_progress"
        if new_status == "completed" and lab["status"] != "completed":
            lab["completed_at"] = now
        lab["status"] = new_status
