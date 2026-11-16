"""Contrato base dos validadores de labs.

Define o tipo de `validate_step`, o decorator `_safe_validate` que converte
exceções em `ValidationResult(passed=False)` e o helper `dispatch_step`
reutilizado por cada `labXX.py`.
"""

import functools
import logging
from typing import Any, Callable, Mapping, Protocol

from botocore.exceptions import (
    ClientError,
    NoCredentialsError,
    TokenRetrievalError,
    UnauthorizedSSOTokenError,
)

from app.models import ValidationResult

logger = logging.getLogger(__name__)

CREDENTIAL_ERROR_CODES = (
    "ExpiredToken",
    "ExpiredTokenException",
    "InvalidClientTokenId",
    "UnrecognizedClientException",
    "InvalidSignatureException",
)
CREDENTIAL_HINT = "Verifique as credenciais AWS do profile em uso."
GENERIC_ERROR_MESSAGE = "Erro inesperado durante a validação."


class ValidateStep(Protocol):
    """Contrato de `validate_step` de cada lab.

    Recebe a sessão boto3 e o `context` (sem a chave `path`) e retorna um
    `ValidationResult`, sem propagar exceções.
    """

    def __call__(self, boto3_session: Any, context: dict) -> ValidationResult: ...


StepValidator = Callable[[Any, dict], ValidationResult]


def _credential_message(code: str, original: str) -> str:
    """Monta a mensagem com código e texto originais mais a sugestão."""
    return f"{code}: {original}. {CREDENTIAL_HINT}"


def _safe_validate(fn: StepValidator) -> StepValidator:
    """Decorator que converte exceções AWS e inesperadas em `ValidationResult`."""

    @functools.wraps(fn)
    def wrapper(session: Any, context: dict) -> ValidationResult:
        try:
            return fn(session, context)
        except (NoCredentialsError, UnauthorizedSSOTokenError, TokenRetrievalError) as e:
            return ValidationResult(
                passed=False,
                message=_credential_message(type(e).__name__, str(e)),
            )
        except ClientError as e:
            error = e.response.get("Error", {})
            code = error.get("Code", "Unknown")
            message = error.get("Message", str(e))
            if code in CREDENTIAL_ERROR_CODES:
                return ValidationResult(
                    passed=False, message=_credential_message(code, message)
                )
            return ValidationResult(passed=False, message=f"{code}: {message}")
        except Exception:
            logger.exception("Erro inesperado no validador %s", fn.__name__)
            return ValidationResult(passed=False, message=GENERIC_ERROR_MESSAGE)

    return wrapper


def dispatch_step(
    step_validators: Mapping[str, StepValidator],
    boto3_session: Any,
    context: dict,
) -> ValidationResult:
    """Despacha para a função do step em `context["step_id"]`.

    Step desconhecido retorna `passed=False`. O dispatch também é protegido
    por `_safe_validate`.
    """
    step_id = context.get("step_id")
    validator_fn = step_validators.get(step_id)
    if validator_fn is None:
        return ValidationResult(passed=False, message=f"Step {step_id} desconhecido.")
    return _safe_validate(validator_fn)(boto3_session, context)
