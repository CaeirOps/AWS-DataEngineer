"""Validador de exemplo do lab fictício `lab-example` (somente testes)."""

from app.models import ValidationResult
from app.validators.base import _safe_validate, dispatch_step

BUCKET_PREFIX = "workshop-example"


@_safe_validate
def _validate_bucket_created(session, ctx: dict) -> ValidationResult:
    prefix = ctx.get("bucket_prefix", BUCKET_PREFIX)
    buckets = session.client("s3").list_buckets().get("Buckets", [])
    matching = [b["Name"] for b in buckets if b["Name"].startswith(prefix)]
    if not matching:
        return ValidationResult(
            passed=False,
            message=f"Nenhum bucket com prefixo '{prefix}' encontrado.",
            hint="Confira o prefixo do nome e a Region do bucket.",
        )
    return ValidationResult(passed=True, message=f"Bucket '{matching[0]}' encontrado.")


STEP_VALIDATORS = {
    "step-03": _validate_bucket_created,
    "step-04": _validate_bucket_created,
}


def validate_step(boto3_session, context: dict) -> ValidationResult:
    return dispatch_step(STEP_VALIDATORS, boto3_session, context)
