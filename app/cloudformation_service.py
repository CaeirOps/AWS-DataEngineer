"""Serviço de deploy, teardown e consulta de status das stacks CloudFormation.

Cada lab tem uma stack chamada `workshop-<lab_id>`, criada a partir de
`<labs_dir>/<lab_id>/cloudformation/stack.yaml`. O serviço não mantém estado
de polling: cada chamada a `get_status` executa `describe_stacks`.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from botocore.exceptions import (
    BotoCoreError,
    ClientError,
    NoCredentialsError,
    TokenRetrievalError,
    UnauthorizedSSOTokenError,
)

from app.errors import (
    CredentialsError,
    CredentialsMissingError,
    LabNotFoundError,
    NoInfrastructureError,
    PermissionsError,
    StackDeployError,
    StackNotFoundError,
    WorkshopError,
)
from app.lab_catalog import LabCatalog
from app.models import LabMetadata
from app.redaction import log_exception
from app.validation_service import default_session_factory
from app.validators.base import CREDENTIAL_ERROR_CODES, _credential_message

logger = logging.getLogger(__name__)

SessionFactory = Callable[[], Any]

PROJECT_TAG = "aws-data-engineer-workshop"
STACK_NAME_PREFIX = "workshop-"
# Limite do CloudFormation para `TemplateBody` enviado direto na chamada.
MAX_TEMPLATE_BYTES = 51200
PERMISSION_ERROR_CODES = ("AccessDenied", "AccessDeniedException", "UnauthorizedOperation")

IN_PROGRESS_SUFFIX = "_IN_PROGRESS"
FAILURE_STATES = (
    "CREATE_FAILED",
    "ROLLBACK_COMPLETE",
    "ROLLBACK_FAILED",
    "DELETE_FAILED",
    "UPDATE_FAILED",
    "UPDATE_ROLLBACK_COMPLETE",
    "UPDATE_ROLLBACK_FAILED",
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _iso(value: Any) -> str:
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            value = value.astimezone(timezone.utc)
        return value.strftime("%Y-%m-%dT%H:%M:%SZ")
    return _utc_now_iso()


def _is_missing_stack(error: ClientError) -> bool:
    """`describe_stacks` de stack inexistente retorna ValidationError."""
    err = error.response.get("Error", {})
    return err.get("Code") == "ValidationError" and "does not exist" in err.get("Message", "")


class CloudFormationService:
    """Gerencia o deploy, o teardown e o status das stacks dos labs."""

    def __init__(
        self,
        lab_catalog: LabCatalog,
        session_factory: Optional[SessionFactory] = None,
    ):
        self._catalog = lab_catalog
        self._session_factory = session_factory or default_session_factory

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def deploy(self, lab_id: str, lab_metadata: Optional[LabMetadata] = None) -> dict:
        """Inicia a criação da stack do lab.

        Se a stack já existir, não a recria e retorna o status atual. Em falha
        de criação a stack passa por rollback e o motivo fica disponível em
        `get_status` (obtido de `describe_stack_events`).

        Raises:
            LabNotFoundError: lab inexistente.
            StackDeployError: template ausente, grande demais ou erro da AWS.
            CredentialsError, CredentialsMissingError, PermissionsError: ver `_translate`.
        """
        self._require_lab(lab_id, lab_metadata)
        stack_name = self._get_stack_name(lab_id)
        template = self._read_template(lab_id)

        def run() -> dict:
            cfn = self._client()
            existing = self._describe_or_none(cfn, stack_name)
            if existing is not None:
                return self._existing_response(stack_name, existing)
            try:
                cfn.create_stack(
                    StackName=stack_name,
                    TemplateBody=template,
                    Capabilities=self._capabilities(template),
                    OnFailure="ROLLBACK",
                    Tags=[
                        {"Key": "Project", "Value": PROJECT_TAG},
                        {"Key": "Lab", "Value": lab_id},
                    ],
                )
            except ClientError as exc:
                if exc.response.get("Error", {}).get("Code") == "AlreadyExistsException":
                    current = self._describe_or_none(cfn, stack_name)
                    if current is not None:
                        return self._existing_response(stack_name, current)
                raise
            return {
                "stack_name": stack_name,
                "status": "CREATE_IN_PROGRESS",
                "message": "Stack iniciada. Aguarde o provisionamento.",
            }

        return self._call(run, deploy=True)

    def teardown(self, lab_id: str) -> dict:
        """Inicia a exclusão da stack e retorna os `residual_resources` do lab.

        Pode ser chamado em qualquer estado (6.7). Stack inexistente não é
        erro: retorna `DELETE_COMPLETE`. Se a exclusão já estiver em andamento,
        não a reinicia. Se a AWS recusar a exclusão no estado atual, retorna o
        status atual com a explicação, sem levantar erro.
        """
        lab = self._require_lab(lab_id, None)
        stack_name = self._get_stack_name(lab_id)
        residual = list(lab.residual_resources)

        def run() -> dict:
            cfn = self._client()
            existing = self._describe_or_none(cfn, stack_name)
            if existing is None:
                return self._teardown_response(
                    stack_name,
                    "DELETE_COMPLETE",
                    residual,
                    "Stack não encontrada. Nada a excluir.",
                )
            status = existing["StackStatus"]
            if status == "DELETE_IN_PROGRESS":
                return self._teardown_response(
                    stack_name, status, residual, "Exclusão da stack já em andamento."
                )
            try:
                cfn.delete_stack(StackName=stack_name)
            except ClientError as exc:
                if exc.response.get("Error", {}).get("Code") == "ValidationError":
                    reason = exc.response["Error"].get("Message", "")
                    return self._teardown_response(
                        stack_name,
                        status,
                        residual,
                        f"Não foi possível iniciar a exclusão no estado {status}: {reason}",
                    )
                raise
            return self._teardown_response(
                stack_name, "DELETE_IN_PROGRESS", residual, "Exclusão da stack iniciada."
            )

        return self._call(run)

    def get_status(self, lab_id: str) -> dict:
        """Consulta `describe_stacks` e retorna status, motivo e outputs.

        Em estados de falha, `status_reason` vem do primeiro evento `*_FAILED`
        (em ordem cronológica) de `describe_stack_events`.

        Raises:
            LabNotFoundError: lab inexistente.
            StackNotFoundError: a stack não existe.
        """
        self._require_lab(lab_id, None)
        stack_name = self._get_stack_name(lab_id)

        def run() -> dict:
            cfn = self._client()
            stack = self._describe_or_none(cfn, stack_name)
            if stack is None:
                raise StackNotFoundError(f"Stack '{stack_name}' não encontrada.")
            status = stack["StackStatus"]
            reason = None
            if status in FAILURE_STATES:
                reason = self._failure_reason(cfn, stack_name, status) or stack.get(
                    "StackStatusReason"
                )
            outputs = {
                o["OutputKey"]: o.get("OutputValue", "") for o in stack.get("Outputs", [])
            }
            return {
                "stack_name": stack_name,
                "status": status,
                "status_reason": reason,
                "outputs": outputs,
                "last_updated": _iso(stack.get("LastUpdatedTime") or stack.get("CreationTime")),
            }

        return self._call(run)

    # ------------------------------------------------------------------
    # Auxiliares
    # ------------------------------------------------------------------

    def _get_stack_name(self, lab_id: str) -> str:
        return f"{STACK_NAME_PREFIX}{lab_id}"

    def _get_template_path(self, lab_id: str):
        return self._catalog.labs_dir / lab_id / "cloudformation" / "stack.yaml"

    def _require_lab(self, lab_id: str, lab_metadata: Optional[LabMetadata]) -> LabMetadata:
        """Lab existente e com infraestrutura; checado antes de criar cliente boto3."""
        lab = lab_metadata or self._catalog.get_lab(lab_id)
        if lab is None:
            raise LabNotFoundError(f"Lab '{lab_id}' não encontrado.")
        if not lab.has_infrastructure:
            raise NoInfrastructureError(
                f"O módulo '{lab_id}' não tem infraestrutura: não há stack para criar, "
                "consultar ou excluir."
            )
        return lab

    def _read_template(self, lab_id: str) -> str:
        path = self._get_template_path(lab_id)
        try:
            body = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise StackDeployError(
                f"Template CloudFormation do lab '{lab_id}' não encontrado: {exc}"
            )
        if len(body.encode("utf-8")) > MAX_TEMPLATE_BYTES:
            raise StackDeployError(
                f"Template do lab '{lab_id}' excede {MAX_TEMPLATE_BYTES} bytes, "
                "limite do envio direto ao CloudFormation."
            )
        return body

    @staticmethod
    def _capabilities(template: str) -> list[str]:
        """Pede as capabilities de IAM somente se o template declara recursos IAM."""
        if "AWS::IAM::" in template:
            return ["CAPABILITY_IAM", "CAPABILITY_NAMED_IAM"]
        return []

    def _client(self):
        return self._session_factory().client("cloudformation")

    @staticmethod
    def _describe_or_none(cfn: Any, stack_name: str) -> Optional[dict]:
        try:
            stacks = cfn.describe_stacks(StackName=stack_name).get("Stacks", [])
        except ClientError as exc:
            if _is_missing_stack(exc):
                return None
            raise
        return stacks[0] if stacks else None

    @staticmethod
    def _existing_response(stack_name: str, stack: dict) -> dict:
        status = stack["StackStatus"]
        if status.endswith(IN_PROGRESS_SUFFIX):
            message = "A stack já existe e está em andamento. Aguarde a conclusão."
        elif status in FAILURE_STATES:
            message = (
                f"A stack já existe no estado {status}. Consulte o status para ver o "
                "motivo, finalize o lab (teardown) e faça o deploy novamente."
            )
        else:
            message = "A stack já existe. Nenhuma ação foi executada."
        return {"stack_name": stack_name, "status": status, "message": message}

    @staticmethod
    def _teardown_response(
        stack_name: str, status: str, residual: list[str], message: str
    ) -> dict:
        return {
            "stack_name": stack_name,
            "status": status,
            "residual_resources": residual,
            "message": message,
        }

    @staticmethod
    def _failure_reason(cfn: Any, stack_name: str, stack_status: str) -> Optional[str]:
        """Motivo do primeiro evento `*_FAILED` em ordem cronológica.

        A API retorna os eventos do mais novo para o mais antigo, e a causa
        raiz é o evento mais antigo. Em `DELETE_FAILED` só entram eventos de
        exclusão; nos demais estados eles são ignorados.
        """
        try:
            paginator = cfn.get_paginator("describe_stack_events")
            events: list[dict] = []
            for page in paginator.paginate(StackName=stack_name):
                events.extend(page.get("StackEvents", []))
        except ClientError:
            log_exception(logger, "Falha ao ler eventos da stack %s", stack_name)
            return None
        want_delete = stack_status == "DELETE_FAILED"
        for event in reversed(events):
            event_status = event.get("ResourceStatus", "")
            if not event_status.endswith("_FAILED"):
                continue
            if (event_status == "DELETE_FAILED") != want_delete:
                continue
            reason = event.get("ResourceStatusReason")
            if reason:
                resource = event.get("LogicalResourceId", "")
                return f"{resource}: {reason}" if resource else reason
        return None

    def _call(self, fn: Callable[[], dict], deploy: bool = False) -> dict:
        """Executa `fn` convertendo exceções boto3 nas exceções da plataforma."""
        try:
            return fn()
        except WorkshopError:
            raise
        except (UnauthorizedSSOTokenError, TokenRetrievalError) as exc:
            raise CredentialsError(_credential_message(type(exc).__name__, str(exc)))
        except NoCredentialsError as exc:
            raise CredentialsMissingError(_credential_message(type(exc).__name__, str(exc)))
        except ClientError as exc:
            err = exc.response.get("Error", {})
            code = err.get("Code", "Unknown")
            message = err.get("Message", str(exc))
            if code in CREDENTIAL_ERROR_CODES:
                raise CredentialsError(_credential_message(code, message))
            if code in PERMISSION_ERROR_CODES:
                raise PermissionsError(f"{code}: {message}")
            error_cls = StackDeployError if deploy else WorkshopError
            raise error_cls(f"Erro AWS ({code}): {message}")
        except BotoCoreError as exc:
            error_cls = StackDeployError if deploy else WorkshopError
            raise error_cls(f"{type(exc).__name__}: {exc}")
