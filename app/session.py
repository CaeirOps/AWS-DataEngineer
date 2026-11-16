"""Estado da sessão de credenciais temporárias (Requirement 12).

O `start.py` exporta `WORKSHOP_CREDENTIALS_EXPIRATION` (ISO 8601) ao container.
Este módulo calcula, no servidor, quanto tempo resta e classifica a sessão em
`valid`, `expiring` (600 s ou menos) ou `expired`. Nunca lê nem devolve valores
de credenciais.

Comportamento sem a variável: falha fechada (12.3). Variável ausente, vazia ou
inválida resulta em `expired`, `expires_at = None` e `seconds_remaining = 0`, e
as rotas que chamam a AWS são recusadas. Testes e `create_app(config)` injetam
`session_env` e `session_clock` para controlar o estado sem tocar `os.environ`.
"""

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Mapping, Optional

from app.errors import SessionExpiredError

EXPIRATION_ENV = "WORKSHOP_CREDENTIALS_EXPIRATION"
EXPIRING_THRESHOLD_S = 600
REFRESH_COMMAND = "python start.py --refresh"


@dataclass(frozen=True)
class SessionState:
    """Estado da sessão: `valid`, `expiring` ou `expired`."""

    expires_at: Optional[str]
    seconds_remaining: int
    status: str

    def to_dict(self) -> dict:
        return {
            "expires_at": self.expires_at,
            "seconds_remaining": self.seconds_remaining,
            "status": self.status,
        }


def utcnow() -> datetime:
    """Instante atual em UTC com fuso."""
    return datetime.now(timezone.utc)


def _parse_expiration(raw: Optional[str]) -> Optional[datetime]:
    """Converte ISO 8601 em datetime com fuso; `None` se ausente ou inválido.

    Valores sem fuso são tratados como UTC. O sufixo `Z` é aceito.
    """
    if not raw or not raw.strip():
        return None
    text = raw.strip()
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def get_session_state(
    env: Mapping[str, str] = os.environ,
    now: Callable[[], datetime] = utcnow,
) -> SessionState:
    """Calcula o estado da sessão a partir de `WORKSHOP_CREDENTIALS_EXPIRATION`."""
    expires = _parse_expiration(env.get(EXPIRATION_ENV))
    if expires is None:
        return SessionState(expires_at=None, seconds_remaining=0, status="expired")
    current = now()
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    remaining = max(0, int((expires - current).total_seconds()))
    if remaining <= 0:
        status = "expired"
    elif remaining <= EXPIRING_THRESHOLD_S:
        status = "expiring"
    else:
        status = "valid"
    return SessionState(
        expires_at=expires.strftime("%Y-%m-%dT%H:%M:%SZ"),
        seconds_remaining=remaining,
        status=status,
    )


def require_active_session(
    env: Mapping[str, str] = os.environ,
    now: Callable[[], datetime] = utcnow,
) -> None:
    """Levanta `SessionExpiredError` se a sessão está expirada."""
    if get_session_state(env, now).status == "expired":
        raise SessionExpiredError(
            "Sessão AWS expirada. Renove o login no host e execute "
            f"`{REFRESH_COMMAND}`."
        )
