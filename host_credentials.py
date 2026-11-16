"""Obtem e valida as credenciais temporarias do profile AWS (roda no host).

Modulo compartilhado por `start.py` e `check_requirements.py`. Usa somente a
biblioteca padrao do Python (3.9+) e chama o `aws` CLI via subprocess, sem
shell. O stdout do CLI fica apenas em memoria: nunca e gravado em disco nem
repassado ao terminal. Valores de credenciais nunca aparecem em mensagens de
erro, em `repr` ou em logs.
"""

import json
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Dict, List, Tuple

COMMAND_TIMEOUT_S = 30
MAX_STDERR_CHARS = 300

SSO_HINT = (
    "Renove o login no host com `aws sso login --profile <profile>` "
    "(AWS IAM Identity Center) ou `aws login` e tente novamente."
)

# run(cmd) -> (returncode, stdout, stderr), igual ao check_requirements.py.
RunFn = Callable[[List[str]], Tuple[int, str, str]]

# Trechos que parecem credencial: access key ids, e sequencias longas
# tipicas de secret keys e session tokens.
_ACCESS_KEY_RE = re.compile(r"\b(?:AKIA|ASIA|AIDA|AROA)[A-Z0-9]{12,}\b")
_LONG_TOKEN_RE = re.compile(r"[A-Za-z0-9+/=_\-]{40,}")


class LongLivedCredentialsError(Exception):
    """Credencial sem SessionToken ou sem Expiration (longa duracao)."""


class CredentialsExportError(Exception):
    """Falha ao exportar credenciais (comando com erro ou saida invalida)."""


@dataclass(frozen=True)
class TempCredentials:
    access_key_id: str = field(repr=False)
    secret_access_key: str = field(repr=False)
    session_token: str = field(repr=False)
    expiration: datetime = field(repr=False)  # timezone-aware, UTC


def default_run(cmd: List[str]) -> Tuple[int, str, str]:
    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        timeout=COMMAND_TIMEOUT_S,
    )
    return proc.returncode, proc.stdout, proc.stderr


def _redact_stderr(stderr: str, secrets: List[str]) -> str:
    """Remove linhas que contenham valores conhecidos ou trechos com cara de credencial."""
    kept = []
    for line in (stderr or "").splitlines():
        line = line.strip()
        if not line:
            continue
        if any(s and s in line for s in secrets):
            continue
        if _ACCESS_KEY_RE.search(line) or _LONG_TOKEN_RE.search(line):
            continue
        kept.append(line)
    return " ".join(kept)[:MAX_STDERR_CHARS]


def _parse_expiration(raw: str) -> datetime:
    text = raw.strip()
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        # Python 3.9 nao aceita fracoes de segundo com tamanho arbitrario.
        match = re.match(r"^(.*?)(\.\d+)?([+-]\d{2}:\d{2})?$", text)
        if not match:
            raise
        base, _frac, offset = match.groups()
        parsed = datetime.fromisoformat(base + (offset or ""))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def export_credentials(profile: str, run: RunFn = default_run) -> TempCredentials:
    """Executa `aws configure export-credentials --profile <profile> --format process`.

    Levanta LongLivedCredentialsError se faltar SessionToken ou Expiration, e
    CredentialsExportError se o comando falhar ou a saida nao for JSON valido.
    """
    cmd = [
        "aws", "configure", "export-credentials",
        "--profile", profile,
        "--format", "process",
    ]
    try:
        code, out, err = run(cmd)
    except FileNotFoundError:
        raise CredentialsExportError(
            "comando 'aws' nao encontrado no PATH. Instale o AWS CLI v2."
        ) from None
    except subprocess.TimeoutExpired:
        raise CredentialsExportError(
            "tempo esgotado ao exportar as credenciais do profile '%s'. %s"
            % (profile, SSO_HINT.replace("<profile>", profile))
        ) from None
    except OSError:
        raise CredentialsExportError(
            "nao foi possivel executar o AWS CLI para o profile '%s'." % profile
        ) from None

    hint = SSO_HINT.replace("<profile>", profile)

    if code != 0:
        detail = _redact_stderr(err, [])
        raise CredentialsExportError(
            "falha ao exportar credenciais do profile '%s'%s. %s"
            % (profile, " (%s)" % detail if detail else "", hint)
        )

    try:
        data = json.loads(out)
    except (ValueError, TypeError):
        raise CredentialsExportError(
            "saida inesperada ao exportar credenciais do profile '%s' "
            "(JSON invalido). %s" % (profile, hint)
        ) from None
    if not isinstance(data, dict):
        raise CredentialsExportError(
            "saida inesperada ao exportar credenciais do profile '%s'. %s"
            % (profile, hint)
        )

    def _text(key: str) -> str:
        value = data.get(key)
        return value.strip() if isinstance(value, str) else ""

    access_key = _text("AccessKeyId")
    secret_key = _text("SecretAccessKey")
    token = _text("SessionToken")
    expiration_raw = _text("Expiration")

    if not access_key or not secret_key:
        raise CredentialsExportError(
            "o profile '%s' nao devolveu AccessKeyId e SecretAccessKey. %s"
            % (profile, hint)
        )
    if not token or not expiration_raw:
        raise LongLivedCredentialsError(
            "o profile '%s' usa credenciais de longa duracao (sem SessionToken "
            "ou sem Expiration), que o workshop recusa. Use credenciais "
            "temporarias: AWS IAM Identity Center (SSO) ou `aws login`. %s"
            % (profile, hint)
        )

    try:
        expiration = _parse_expiration(expiration_raw)
    except ValueError:
        raise CredentialsExportError(
            "campo Expiration em formato inesperado para o profile '%s'. %s"
            % (profile, hint)
        ) from None

    return TempCredentials(
        access_key_id=access_key,
        secret_access_key=secret_key,
        session_token=token,
        expiration=expiration,
    )


def to_environment(creds: TempCredentials) -> Dict[str, str]:
    """Variaveis de ambiente entregues ao docker compose (pass-through)."""
    return {
        "AWS_ACCESS_KEY_ID": creds.access_key_id,
        "AWS_SECRET_ACCESS_KEY": creds.secret_access_key,
        "AWS_SESSION_TOKEN": creds.session_token,
        "WORKSHOP_CREDENTIALS_EXPIRATION": creds.expiration.strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
    }
