"""Catálogo de labs carregado a partir dos `metadata.json`.

Estrutura esperada em disco (ver design.md, seção Lab Content):

    <labs_dir>/<lab_id>/metadata.json
    <labs_dir>/<lab_id>/steps/<step_id>/content.md          (steps que não são task)
    <labs_dir>/<lab_id>/steps/<step_id>/scenario.md         (steps task)
    <labs_dir>/<lab_id>/steps/<step_id>/{console,cli}.md    (instruções por Trilha)
    <labs_dir>/<lab_id>/steps/<step_id>/hint-{console,cli}.md
"""

import json
import os
import re
from pathlib import Path
from typing import Optional

from app.errors import (
    InvalidPathError,
    LabNotFoundError,
    PathUnavailableError,
    StepNotFoundError,
    WorkshopError,
)
from app.models import LabMetadata, StepMetadata

VALID_PATHS = ("console", "cli")
STEP_TYPES = ("info", "deploy", "task", "teardown", "completion")
CONTENT_SEPARATOR = "\n\n---\n\n"
DEFAULT_HINT_THRESHOLD = 3

# Ids viram nomes de diretório: aceitar somente este formato evita path traversal.
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


class InvalidLabMetadataError(WorkshopError):
    """`metadata.json` inválido, com lab, step (se aplicável) e motivo."""

    code = "INVALID_LAB_METADATA"
    http_status = 500

    def __init__(self, lab_id: str, reason: str, step_id: Optional[str] = None):
        self.lab_id = lab_id
        self.step_id = step_id
        self.reason = reason
        where = f"lab '{lab_id}'" + (f", step '{step_id}'" if step_id else "")
        super().__init__(f"metadata.json inválido ({where}): {reason}")


def default_labs_dir() -> str:
    """Diretório de labs: `WORKSHOP_LABS_DIR` ou `labs/` na raiz do projeto."""
    env = os.environ.get("WORKSHOP_LABS_DIR")
    if env:
        return env
    return str(Path(__file__).resolve().parent.parent / "labs")


def _is_valid_id(value: object) -> bool:
    return isinstance(value, str) and _ID_RE.match(value) is not None


class LabCatalog:
    """Carrega e consulta os labs. Instanciado uma vez por processo."""

    def __init__(self, labs_dir: Optional[str] = None):
        self._labs_dir = Path(labs_dir if labs_dir is not None else default_labs_dir())
        self._labs: dict[str, LabMetadata] = {}
        self._load_all()

    @property
    def labs_dir(self) -> Path:
        """Diretório raiz dos labs usado por este catálogo."""
        return self._labs_dir

    # ------------------------------------------------------------------
    # Carga e validação
    # ------------------------------------------------------------------

    def _load_all(self) -> None:
        """Carrega todos os labs. Diretório ausente ou sem labs gera catálogo vazio."""
        if not self._labs_dir.is_dir():
            return
        for entry in sorted(self._labs_dir.iterdir()):
            if not entry.is_dir() or entry.name.startswith("."):
                continue
            meta_file = entry / "metadata.json"
            if not meta_file.is_file():
                continue
            lab = self._load_lab(entry.name, meta_file)
            self._labs[lab.lab_id] = lab

    def _load_lab(self, dir_name: str, meta_file: Path) -> LabMetadata:
        try:
            with open(meta_file, encoding="utf-8") as fh:
                raw = json.load(fh)
        except (OSError, ValueError) as exc:
            raise InvalidLabMetadataError(dir_name, f"não foi possível ler o JSON: {exc}")
        if not isinstance(raw, dict):
            raise InvalidLabMetadataError(dir_name, "o JSON raiz deve ser um objeto")

        lab_id = raw.get("lab_id")
        if not _is_valid_id(lab_id):
            raise InvalidLabMetadataError(dir_name, f"lab_id inválido: {lab_id!r}")
        if lab_id != dir_name:
            raise InvalidLabMetadataError(
                dir_name, f"lab_id '{lab_id}' difere do nome do diretório"
            )

        for key in ("title", "description", "difficulty", "cost_disclaimer"):
            if not isinstance(raw.get(key), str):
                raise InvalidLabMetadataError(lab_id, f"campo '{key}' ausente ou não é texto")
        for key in ("dea_domains", "dea_tasks"):
            if not isinstance(raw.get(key), list):
                raise InvalidLabMetadataError(lab_id, f"campo '{key}' ausente ou não é lista")
        services = raw.get("services")
        if not isinstance(services, list) or not services:
            raise InvalidLabMetadataError(
                lab_id, "campo 'services' ausente ou não é uma lista não vazia"
            )
        if any(not isinstance(s, str) or not s.strip() for s in services):
            raise InvalidLabMetadataError(
                lab_id, "'services' deve conter somente textos não vazios"
            )
        duration = raw.get("estimated_duration_minutes")
        cost = raw.get("estimated_cost_usd")
        if isinstance(duration, bool) or not isinstance(duration, int):
            raise InvalidLabMetadataError(lab_id, "estimated_duration_minutes deve ser inteiro")
        if isinstance(cost, bool) or not isinstance(cost, (int, float)):
            raise InvalidLabMetadataError(lab_id, "estimated_cost_usd deve ser numérico")
        prerequisites = raw.get("prerequisites", {})
        if not isinstance(prerequisites, dict):
            raise InvalidLabMetadataError(lab_id, "prerequisites deve ser um objeto")
        residual = raw.get("residual_resources", [])
        if not isinstance(residual, list):
            raise InvalidLabMetadataError(lab_id, "residual_resources deve ser uma lista")

        raw_steps = raw.get("steps")
        if not isinstance(raw_steps, list):
            raise InvalidLabMetadataError(lab_id, "campo 'steps' ausente ou não é lista")
        steps: list[StepMetadata] = []
        seen: set[str] = set()
        for raw_step in raw_steps:
            step = self._parse_step(lab_id, raw_step)
            if step.step_id in seen:
                raise InvalidLabMetadataError(lab_id, "step_id duplicado", step.step_id)
            seen.add(step.step_id)
            steps.append(step)

        return LabMetadata(
            lab_id=lab_id,
            title=raw["title"],
            description=raw["description"],
            difficulty=raw["difficulty"],
            estimated_duration_minutes=duration,
            estimated_cost_usd=float(cost),
            cost_disclaimer=raw["cost_disclaimer"],
            dea_domains=list(raw["dea_domains"]),
            dea_tasks=list(raw["dea_tasks"]),
            services=list(services),
            prerequisites=prerequisites,
            steps=steps,
            residual_resources=list(residual),
        )

    @staticmethod
    def _parse_step(lab_id: str, raw: object) -> StepMetadata:
        if not isinstance(raw, dict):
            raise InvalidLabMetadataError(lab_id, "cada step deve ser um objeto")
        step_id = raw.get("step_id")
        if not _is_valid_id(step_id):
            raise InvalidLabMetadataError(lab_id, f"step_id inválido: {step_id!r}")
        if not isinstance(raw.get("title"), str) or not raw["title"]:
            raise InvalidLabMetadataError(lab_id, "title ausente ou vazio", step_id)
        step_type = raw.get("type")
        if step_type not in STEP_TYPES:
            raise InvalidLabMetadataError(lab_id, f"type inválido: {step_type!r}", step_id)
        threshold = raw.get("hint_threshold", DEFAULT_HINT_THRESHOLD)
        if isinstance(threshold, bool) or not isinstance(threshold, int) or threshold < 1:
            raise InvalidLabMetadataError(
                lab_id, "hint_threshold deve ser inteiro >= 1", step_id
            )

        paths = raw.get("paths")
        unavailable = raw.get("unavailable_paths")

        if step_type != "task":
            if paths is not None or unavailable is not None:
                raise InvalidLabMetadataError(
                    lab_id,
                    "paths/unavailable_paths só são permitidos em steps do tipo task",
                    step_id,
                )
            return StepMetadata(step_id, raw["title"], step_type, threshold)

        if not isinstance(paths, list) or not paths:
            raise InvalidLabMetadataError(lab_id, "paths deve ser uma lista não vazia", step_id)
        if any(p not in VALID_PATHS for p in paths) or len(set(paths)) != len(paths):
            raise InvalidLabMetadataError(
                lab_id, f"paths deve conter somente {list(VALID_PATHS)} sem repetição", step_id
            )
        if unavailable is None:
            unavailable = {}
        if not isinstance(unavailable, dict):
            raise InvalidLabMetadataError(lab_id, "unavailable_paths deve ser um objeto", step_id)
        for trail, reason in unavailable.items():
            if trail not in VALID_PATHS:
                raise InvalidLabMetadataError(
                    lab_id, f"Trilha desconhecida em unavailable_paths: {trail!r}", step_id
                )
            if trail in paths:
                raise InvalidLabMetadataError(
                    lab_id, f"Trilha '{trail}' está em paths e em unavailable_paths", step_id
                )
            if not isinstance(reason, str) or not reason.strip():
                raise InvalidLabMetadataError(
                    lab_id, f"motivo vazio para a Trilha '{trail}' em unavailable_paths", step_id
                )
        for trail in VALID_PATHS:
            if trail not in paths and trail not in unavailable:
                raise InvalidLabMetadataError(
                    lab_id,
                    f"Trilha '{trail}' ausente de paths e sem motivo em unavailable_paths",
                    step_id,
                )
        return StepMetadata(step_id, raw["title"], step_type, threshold, list(paths), dict(unavailable))

    # ------------------------------------------------------------------
    # Consultas de metadados
    # ------------------------------------------------------------------

    def get_lab(self, lab_id: str) -> Optional[LabMetadata]:
        """Retorna o lab ou `None` se não existir."""
        if not isinstance(lab_id, str):
            return None
        return self._labs.get(lab_id)

    def get_all_labs(self) -> list[LabMetadata]:
        """Todos os labs, ordenados por `lab_id`."""
        return sorted(self._labs.values(), key=lambda lab: lab.lab_id)

    def get_step(self, lab_id: str, step_id: str) -> StepMetadata:
        """Retorna o step. Levanta `LabNotFoundError` ou `StepNotFoundError`."""
        lab = self.get_lab(lab_id)
        if lab is None:
            raise LabNotFoundError(f"Lab '{lab_id}' não encontrado.")
        for step in lab.steps:
            if step.step_id == step_id:
                return step
        raise StepNotFoundError(f"Step '{step_id}' não encontrado no lab '{lab_id}'.")

    # ------------------------------------------------------------------
    # Conteúdo
    # ------------------------------------------------------------------

    def _step_dir(self, lab_id: str, step_id: str) -> Path:
        # lab_id e step_id já foram confirmados no catálogo (formato validado na carga).
        return self._labs_dir / lab_id / "steps" / step_id

    def _read(self, lab_id: str, step_id: str, filename: str) -> str:
        file = self._step_dir(lab_id, step_id) / filename
        try:
            return file.read_text(encoding="utf-8")
        except OSError:
            raise StepNotFoundError(
                f"Arquivo de conteúdo '{filename}' não encontrado no step '{step_id}' "
                f"do lab '{lab_id}'."
            )

    def _task_step_and_path(self, lab_id: str, step_id: str, path: object) -> StepMetadata:
        step = self.get_step(lab_id, step_id)
        if step.type != "task":
            raise StepNotFoundError(
                f"Step '{step_id}' do lab '{lab_id}' não é do tipo task."
            )
        if path not in VALID_PATHS:
            raise InvalidPathError(
                f"Trilha inválida: {path!r}. Use 'console' ou 'cli'."
            )
        if path not in (step.paths or []):
            raise PathUnavailableError(path, (step.unavailable_paths or {}).get(path, ""))
        return step

    def get_step_content(self, lab_id: str, step_id: str, path: str) -> str:
        """Retorna `scenario.md`, o separador e o arquivo da Trilha escolhida.

        Raises:
            LabNotFoundError, StepNotFoundError (inclui step que não é task),
            InvalidPathError, PathUnavailableError.
        """
        self._task_step_and_path(lab_id, step_id, path)
        scenario = self._read(lab_id, step_id, "scenario.md")
        trail = self._read(lab_id, step_id, f"{path}.md")
        return scenario + CONTENT_SEPARATOR + trail

    def get_step_hint(self, lab_id: str, step_id: str, path: str) -> str:
        """Retorna a Dica Detalhada da Trilha (`hint-console.md` ou `hint-cli.md`)."""
        self._task_step_and_path(lab_id, step_id, path)
        return self._read(lab_id, step_id, f"hint-{path}.md")

    def get_step_single_content(self, lab_id: str, step_id: str) -> str:
        """Retorna `content.md` de steps que não são task (info, deploy, teardown, completion)."""
        step = self.get_step(lab_id, step_id)
        if step.type == "task":
            raise StepNotFoundError(
                f"Step '{step_id}' do lab '{lab_id}' é do tipo task e não tem content.md único."
            )
        return self._read(lab_id, step_id, "content.md")
