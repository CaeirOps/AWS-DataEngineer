"""Mascara valores de credenciais AWS em textos de resposta e de log.

O erro original da AWS deve chegar ao usuário. Se ele repetir o valor de uma
credencial do ambiente, só esse valor é trocado por `MASK`; o resto da
mensagem fica intacto.
"""

import logging
import os
import traceback
from typing import Any, Mapping, Optional

MASK = "***"
CREDENTIAL_ENV_VARS = ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN")
# Valores curtos demais trocariam trechos comuns de texto por engano.
MIN_SECRET_LENGTH = 8


def mask_credentials(text: Any, env: Optional[Mapping[str, str]] = None) -> Any:
    """Troca valores de credenciais do ambiente por `MASK`. Não-texto passa direto."""
    if not isinstance(text, str) or not text:
        return text
    env = os.environ if env is None else env
    secrets = sorted(
        {env.get(name, "") for name in CREDENTIAL_ENV_VARS}, key=len, reverse=True
    )
    for secret in secrets:
        if len(secret) >= MIN_SECRET_LENGTH:
            text = text.replace(secret, MASK)
    return text


def mask_json(value: Any, env: Optional[Mapping[str, str]] = None) -> Any:
    """Aplica `mask_credentials` a todas as strings (chaves e valores) de um JSON."""
    if isinstance(value, str):
        return mask_credentials(value, env)
    if isinstance(value, list):
        return [mask_json(v, env) for v in value]
    if isinstance(value, dict):
        return {mask_json(k, env): mask_json(v, env) for k, v in value.items()}
    return value


def log_exception(logger: logging.Logger, message: str, *args: Any) -> None:
    """Como `logger.exception`, mas com a mensagem e o traceback já mascarados."""
    try:
        message = message % args if args else message
    except (TypeError, ValueError):
        pass
    detail = mask_credentials(traceback.format_exc())
    logger.error("%s\n%s", mask_credentials(message), detail)
