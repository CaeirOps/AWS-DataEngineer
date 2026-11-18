"""Catálogo de labs carregado a partir dos `metadata.json`.

Estrutura esperada em disco (ver design.md, seção Lab Content):

    <labs_dir>/<lab_id>/metadata.json
    <labs_dir>/<lab_id>/steps/<step_id>/content.md          (steps que não são task)
    <labs_dir>/<lab_id>/steps/<step_id>/scenario.md         (steps task)
    <labs_dir>/<lab_id>/steps/<step_id>/{console,cli}.md    (instruções por Trilha)
    <labs_dir>/<lab_id>/steps/<step_id>/hint-{console,cli}.md
    <labs_dir>/<lab_id>/steps/<step_id>/quiz.json           (steps quiz)
    <labs_dir>/<lab_id>/cloudformation/stack.yaml           (só com infraestrutura)

Os `skills` declarados precisam existir na Matriz de cobertura
(`docs/exam-coverage.json`, ver design.md seção 5a).
"""

import json
import os
import re
from pathlib import Path
from urllib.parse import urlsplit
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
STEP_TYPES = ("info", "deploy", "task", "quiz", "teardown", "completion")
CONTENT_SEPARATOR = "\n\n---\n\n"
DEFAULT_HINT_THRESHOLD = 3
DEFAULT_PASS_SCORE = 0.7
PRICING_URL_PREFIX = "https://aws.amazon.com/"
PRICING_HOST = "aws.amazon.com"
ENV_COVERAGE_FILE = "WORKSHOP_COVERAGE_FILE"

_SKILL_RE = re.compile(r"^[1-9]\.[1-9]\.[1-9][0-9]?$")
# Caracteres proibidos em `pricing_url`: espaços, controle e barra invertida.
_URL_FORBIDDEN_RE = re.compile(r"[\s\x00-\x1f\x7f\\]")

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


def default_coverage_file() -> str:
    """Matriz de cobertura: `WORKSHOP_COVERAGE_FILE` ou `docs/exam-coverage.json`."""
    env = os.environ.get(ENV_COVERAGE_FILE)
    if env:
        return env
    return str(Path(__file__).resolve().parent.parent / "docs" / "exam-coverage.json")


def _is_valid_id(value: object) -> bool:
    return isinstance(value, str) and _ID_RE.match(value) is not None


class LabCatalog:
    """Carrega e consulta os labs. Instanciado uma vez por processo."""

    def __init__(self, labs_dir: Optional[str] = None, coverage_file: Optional[str] = None):
        self._labs_dir = Path(labs_dir if labs_dir is not None else default_labs_dir())
        self._coverage_file = Path(
            coverage_file if coverage_file is not None else default_coverage_file()
        )
        self._matrix_skills: Optional[frozenset[str]] = None
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

        for key in ("title", "description", "difficulty"):
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
        if isinstance(duration, bool) or not isinstance(duration, int):
            raise InvalidLabMetadataError(lab_id, "estimated_duration_minutes deve ser inteiro")

        # Campos legados: aceitos, mas não obrigatórios (19.4: USD não é exibido).
        cost = raw.get("estimated_cost_usd")
        if cost is not None and (isinstance(cost, bool) or not isinstance(cost, (int, float))):
            raise InvalidLabMetadataError(lab_id, "estimated_cost_usd deve ser numérico")
        disclaimer = raw.get("cost_disclaimer", "")
        if not isinstance(disclaimer, str):
            raise InvalidLabMetadataError(lab_id, "cost_disclaimer deve ser texto")

        prerequisites = raw.get("prerequisites", {})
        if not isinstance(prerequisites, dict):
            raise InvalidLabMetadataError(lab_id, "prerequisites deve ser um objeto")
        residual = raw.get("residual_resources", [])
        if not isinstance(residual, list):
            raise InvalidLabMetadataError(lab_id, "residual_resources deve ser uma lista")

        skills = self._parse_skills(lab_id, raw.get("skills"), None, required=True)
        has_infra = raw.get("has_infrastructure", True)
        if not isinstance(has_infra, bool):
            raise InvalidLabMetadataError(lab_id, "has_infrastructure deve ser booleano")
        cost_notice = self._parse_cost_notice(lab_id, raw.get("cost_notice"), has_infra)

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
            outside = [s for s in step.skills if s not in skills]
            if outside:
                raise InvalidLabMetadataError(
                    lab_id, f"skills do step fora dos skills do módulo: {outside}", step.step_id
                )
            if step.type == "quiz":
                self._check_quiz_file(lab_id, step.step_id)
            steps.append(step)

        self._check_infrastructure(lab_id, has_infra, steps)

        return LabMetadata(
            lab_id=lab_id,
            title=raw["title"],
            description=raw["description"],
            difficulty=raw["difficulty"],
            estimated_duration_minutes=duration,
            estimated_cost_usd=None if cost is None else float(cost),
            cost_disclaimer=disclaimer,
            dea_domains=list(raw["dea_domains"]),
            dea_tasks=list(raw["dea_tasks"]),
            services=list(services),
            prerequisites=prerequisites,
            steps=steps,
            residual_resources=list(residual),
            skills=skills,
            has_infrastructure=has_infra,
            cost_notice=cost_notice,
        )

    # ------------------------------------------------------------------
    # Regras dos campos de módulo (Requirements 6.8, 19.3, 20.3)
    # ------------------------------------------------------------------

    def _matrix(self, lab_id: str) -> frozenset[str]:
        """Ids das skills da Matriz de cobertura, lidos uma vez (fail-closed)."""
        if self._matrix_skills is None:
            try:
                with open(self._coverage_file, encoding="utf-8") as fh:
                    data = json.load(fh)
                ids = frozenset(s["id"] for s in data["skills"])
            except (OSError, ValueError, KeyError, TypeError) as exc:
                raise InvalidLabMetadataError(
                    lab_id,
                    f"Matriz de cobertura indisponível em '{self._coverage_file}': {exc}",
                )
            self._matrix_skills = ids
        return self._matrix_skills

    def _parse_skills(
        self, lab_id: str, value: object, step_id: Optional[str], required: bool
    ) -> list[str]:
        if value is None and not required:
            return []
        if not isinstance(value, list) or not value:
            raise InvalidLabMetadataError(
                lab_id, "skills deve ser uma lista não vazia de ids 'N.N.N'", step_id
            )
        if any(not isinstance(s, str) or not _SKILL_RE.match(s) for s in value):
            raise InvalidLabMetadataError(
                lab_id, f"skills com id fora do formato 'N.N.N': {value!r}", step_id
            )
        if len(set(value)) != len(value):
            raise InvalidLabMetadataError(lab_id, "skills com id repetido", step_id)
        unknown = [s for s in value if s not in self._matrix(lab_id)]
        if unknown:
            raise InvalidLabMetadataError(
                lab_id, f"skills ausentes da Matriz de cobertura: {unknown}", step_id
            )
        return list(value)

    @staticmethod
    def _valid_pricing_url(url: object) -> bool:
        """`https://aws.amazon.com/...` sem userinfo, porta, espaço ou barra invertida."""
        if not isinstance(url, str) or not url.startswith(PRICING_URL_PREFIX):
            return False
        if _URL_FORBIDDEN_RE.search(url):
            return False
        parts = urlsplit(url)
        return parts.scheme == "https" and parts.netloc == PRICING_HOST

    def _parse_cost_notice(self, lab_id: str, value: object, has_infra: bool) -> dict:
        if value is None:
            if has_infra:
                raise InvalidLabMetadataError(
                    lab_id, "cost_notice é obrigatório em módulo com infraestrutura"
                )
            return {}
        if not isinstance(value, dict) or set(value) != {"services"}:
            raise InvalidLabMetadataError(
                lab_id, "cost_notice deve ser um objeto apenas com 'services'"
            )
        services = value["services"]
        if not isinstance(services, list) or not services:
            raise InvalidLabMetadataError(
                lab_id, "cost_notice.services deve ser uma lista não vazia"
            )
        result = []
        for item in services:
            if not isinstance(item, dict) or set(item) != {"name", "pricing_url"}:
                raise InvalidLabMetadataError(
                    lab_id, "cada item de cost_notice.services deve ter só 'name' e 'pricing_url'"
                )
            name = item["name"]
            if not isinstance(name, str) or not name.strip():
                raise InvalidLabMetadataError(lab_id, "cost_notice.services[].name vazio")
            if not self._valid_pricing_url(item["pricing_url"]):
                raise InvalidLabMetadataError(
                    lab_id,
                    f"pricing_url deve começar com '{PRICING_URL_PREFIX}': "
                    f"{item['pricing_url']!r}",
                )
            result.append({"name": name, "pricing_url": item["pricing_url"]})
        return {"services": result}

    def _check_quiz_file(self, lab_id: str, step_id: str) -> None:
        """`quiz.json` existe e tem `questions` não vazio (formato completo na 15N)."""
        file = self._labs_dir / lab_id / "steps" / step_id / "quiz.json"
        try:
            with open(file, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError) as exc:
            raise InvalidLabMetadataError(lab_id, f"quiz.json ausente ou inválido: {exc}", step_id)
        questions = data.get("questions") if isinstance(data, dict) else None
        if not isinstance(questions, list) or not questions:
            raise InvalidLabMetadataError(
                lab_id, "quiz.json deve ter 'questions' como lista não vazia", step_id
            )

    def _check_infrastructure(
        self, lab_id: str, has_infra: bool, steps: list[StepMetadata]
    ) -> None:
        stack = (self._labs_dir / lab_id / "cloudformation" / "stack.yaml").is_file()
        types = {s.type for s in steps}
        if has_infra:
            if not stack:
                raise InvalidLabMetadataError(
                    lab_id, "has_infrastructure é true, mas cloudformation/stack.yaml não existe"
                )
            for kind in ("deploy", "teardown"):
                if kind not in types:
                    raise InvalidLabMetadataError(
                        lab_id, f"has_infrastructure é true, mas não há step '{kind}'"
                    )
            return
        if stack:
            raise InvalidLabMetadataError(
                lab_id, "has_infrastructure é false, mas cloudformation/stack.yaml existe"
            )
        for kind in ("deploy", "teardown"):
            if kind in types:
                raise InvalidLabMetadataError(
                    lab_id, f"has_infrastructure é false, mas há step '{kind}'"
                )

    def _parse_step(self, lab_id: str, raw: object) -> StepMetadata:
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
        skills = self._parse_skills(lab_id, raw.get("skills"), step_id, required=False)

        if "pass_score" in raw and step_type != "quiz":
            raise InvalidLabMetadataError(
                lab_id, "pass_score só é permitido em steps do tipo quiz", step_id
            )
        if step_type != "task":
            for key in ("optional", "cost_note"):
                if key in raw:
                    raise InvalidLabMetadataError(
                        lab_id, f"{key} só é permitido em steps do tipo task", step_id
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
            pass_score = None
            if step_type == "quiz":
                pass_score = raw.get("pass_score", DEFAULT_PASS_SCORE)
                if (
                    isinstance(pass_score, bool)
                    or not isinstance(pass_score, (int, float))
                    or not 0 < pass_score <= 1
                ):
                    raise InvalidLabMetadataError(
                        lab_id, "pass_score deve ser número maior que 0 e até 1", step_id
                    )
            return StepMetadata(
                step_id, raw["title"], step_type, threshold, skills=skills, pass_score=pass_score
            )

        optional = raw.get("optional", False)
        if not isinstance(optional, bool):
            raise InvalidLabMetadataError(lab_id, "optional deve ser booleano", step_id)
        cost_note = raw.get("cost_note")
        if optional:
            if not isinstance(cost_note, str) or not cost_note.strip():
                raise InvalidLabMetadataError(
                    lab_id, "Prática opcional exige cost_note não vazio", step_id
                )
        elif cost_note is not None:
            raise InvalidLabMetadataError(
                lab_id, "cost_note só é permitido em step com optional: true", step_id
            )

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
        return StepMetadata(
            step_id,
            raw["title"],
            step_type,
            threshold,
            list(paths),
            dict(unavailable),
            skills=skills,
            optional=optional,
            cost_note=cost_note if optional else None,
        )

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
        """Retorna `content.md` de steps info, deploy, teardown e completion."""
        step = self.get_step(lab_id, step_id)
        if step.type in ("task", "quiz"):
            raise StepNotFoundError(
                f"Step '{step_id}' do lab '{lab_id}' é do tipo {step.type} e não tem "
                "content.md único."
            )
        return self._read(lab_id, step_id, "content.md")
