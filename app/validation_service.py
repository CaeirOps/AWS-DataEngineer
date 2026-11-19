"""Serviço que orquestra validadores de labs e o `ProgressStore`.

Fluxo de `validate`: confirma lab e step, cria a sessão boto3, carrega o
validador do lab, executa `validate_step` com um `context` sem a chave
`path` (11.4), grava o resultado no progresso e monta a resposta da API.
Não há limite de tentativas (5.4).
"""

import importlib
import os
import re
from typing import Any, Callable, Optional

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.errors import StepNotFoundError
from app.lab_catalog import LabCatalog
from app.models import ValidationResult
from app.progress_store import ProgressStore
from app.validators.base import CREDENTIAL_HINT, _safe_validate

SessionFactory = Callable[[], Any]
ValidatorLoader = Callable[[str], Optional[Callable[[Any, dict], ValidationResult]]]

_LAB_NUMBER_RE = re.compile(r"^lab-(\d+)$")


def default_session_factory() -> boto3.Session:
    """Cria a sessão boto3 da plataforma.

    No container não há `AWS_PROFILE` e os arquivos de configuração apontam
    para `/dev/null`: as credenciais temporárias chegam por variável de
    ambiente (15D). Por isso a sessão só usa um profile nomeado quando
    `AWS_PROFILE` está definida; sem ela, segue a cadeia padrão do SDK, que
    lê `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` e `AWS_SESSION_TOKEN`.
    """
    profile = os.environ.get("AWS_PROFILE")
    return boto3.Session(profile_name=profile) if profile else boto3.Session()


def default_validator_loader(lab_id: str):
    """Importa `app.validators.labNN` e retorna seu `validate_step`.

    Exemplo: `lab-01` -> `app.validators.lab01`. Retorna `None` se o módulo
    do lab ainda não existe.
    """
    match = _LAB_NUMBER_RE.match(lab_id)
    if not match:
        return None
    module_name = f"app.validators.lab{int(match.group(1)):02d}"
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        if exc.name == module_name:
            return None
        raise
    return getattr(module, "validate_step", None)


class ValidationService:
    """Executa validações de steps e atualiza o progresso."""

    def __init__(
        self,
        lab_catalog: LabCatalog,
        progress_store: ProgressStore,
        session_factory: Optional[SessionFactory] = None,
        validator_loader: Optional[ValidatorLoader] = None,
    ):
        self._catalog = lab_catalog
        self._progress = progress_store
        self._session_factory = session_factory or default_session_factory
        self._validator_loader = validator_loader or default_validator_loader

    def validate(self, lab_id: str, step_id: str, context: Optional[dict] = None) -> dict:
        """Valida um step e retorna a resposta de `POST /api/validate`.

        Args:
            lab_id: id do lab.
            step_id: id do step (deve ser do tipo `task`).
            context: parâmetros extras da requisição. A chave `path` é
                descartada, de modo que o resultado não dependa da Trilha.

        Raises:
            LabNotFoundError: lab inexistente.
            StepNotFoundError: step inexistente ou que não é do tipo `task`.
        """
        step = self._catalog.get_step(lab_id, step_id)
        if step.type != "task":
            raise StepNotFoundError(
                f"Step '{step_id}' do lab '{lab_id}' não é validável (tipo {step.type})."
            )
        lab = self._catalog.get_lab(lab_id)

        previous = (
            self._progress.get_lab_progress(lab_id)["steps"].get(step_id, {}).get("attempts", 0)
        )
        ctx = {k: v for k, v in (context or {}).items() if k != "path"}
        ctx.update(step_id=step_id, lab_id=lab_id, attempt_count=previous + 1)

        result = self._run_validator(lab_id, ctx)

        self._progress.update_step(
            lab_id,
            step_id,
            "passed" if result.passed else "failed",
            lab_metadata=lab,
        )
        step_progress = self._progress.get_lab_progress(lab_id)["steps"][step_id]
        attempts = step_progress["attempts"]
        show_hint = attempts >= step.hint_threshold
        return {
            "passed": result.passed,
            "message": result.message,
            "hint": result.hint if (show_hint and not result.passed) else None,
            "step_status": step_progress["status"],
            "show_hint_button": show_hint,
            "attempt_count": attempts,
        }

    def _run_validator(self, lab_id: str, ctx: dict) -> ValidationResult:
        """Cria a sessão, carrega e executa o validador; nunca propaga exceções AWS."""
        try:
            session = self._session_factory()
        except (BotoCoreError, ClientError) as exc:
            return ValidationResult(
                passed=False,
                message=f"{type(exc).__name__}: {exc}. {CREDENTIAL_HINT}",
            )
        validate_step = self._validator_loader(lab_id)
        if validate_step is None:
            return ValidationResult(
                passed=False,
                message=f"Validador do lab '{lab_id}' não disponível.",
            )
        return _safe_validate(validate_step)(session, ctx)
