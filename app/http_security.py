"""Proteção da API local contra CSRF e DNS rebinding (Requirement 13).

`register_request_guards` registra um `before_request` que valida, nesta ordem:
`Host` (toda requisição, exceto `GET /health`), e, em `POST`, `PUT` e `DELETE`,
`Origin`, `Content-Type` e o cabeçalho próprio `X-Workshop-Request`. A
allowlist usa a porta publicada ao browser, recebida em `WORKSHOP_PORT`.
Os valores recebidos nunca são repetidos nas mensagens de erro.
"""

import os
from typing import Mapping, Optional

from flask import Flask, request

from app.errors import (
    HostNotAllowedError,
    MissingWorkshopHeaderError,
    OriginNotAllowedError,
    UnsupportedMediaTypeError,
)

PORT_ENV = "WORKSHOP_PORT"
DEFAULT_PORT = "5000"
WORKSHOP_HEADER = "X-Workshop-Request"
WORKSHOP_HEADER_VALUE = "1"
MUTATING_METHODS = frozenset({"POST", "PUT", "DELETE"})
HEALTH_PATH = "/health"
LOCAL_HOSTS = ("127.0.0.1", "localhost")


def resolve_port(port: Optional[str] = None, env: Optional[Mapping[str, str]] = None) -> str:
    """Porta usada na allowlist: argumento, senão `WORKSHOP_PORT`, senão 5000.

    Valor que não seja numérico volta para a porta padrão.
    """
    env = os.environ if env is None else env
    value = str(port if port is not None else env.get(PORT_ENV, "")).strip()
    return value if value.isdigit() else DEFAULT_PORT


def allowed_hosts(port: str) -> frozenset:
    """Valores aceitos para `Host`."""
    return frozenset(f"{host}:{port}" for host in LOCAL_HOSTS)


def allowed_origins(port: str) -> frozenset:
    """Valores aceitos para `Origin`."""
    return frozenset(f"http://{host}:{port}" for host in LOCAL_HOSTS)


def _is_json_content_type(value: str) -> bool:
    """`application/json`, com parâmetros (como `charset`) permitidos."""
    media_type = value.split(";", 1)[0].strip().lower()
    return media_type == "application/json"


CONTENT_SECURITY_POLICY = (
    "default-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
)
SECURITY_HEADERS = {
    "Content-Security-Policy": CONTENT_SECURITY_POLICY,
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
}
API_PREFIX = "/api/"


def register_security_headers(app: Flask) -> None:
    """Registra um `after_request` que define os cabeçalhos de segurança.

    Os cabeçalhos valem para todas as respostas, inclusive erros e arquivos
    estáticos. As rotas `/api/*` recebem também `Cache-Control: no-store`.
    """

    @app.after_request
    def add_security_headers(response):
        for name, value in SECURITY_HEADERS.items():
            response.headers[name] = value
        if request.path.startswith(API_PREFIX):
            response.headers["Cache-Control"] = "no-store"
        return response


def register_request_guards(app: Flask, port: Optional[str] = None) -> None:
    """Registra a validação de `Host`, `Origin`, `Content-Type` e cabeçalho próprio."""
    register_security_headers(app)
    resolved = resolve_port(port)
    # Expõe a porta efetiva para quem precisa montar `Host` e `Origin` válidos.
    app.config["WORKSHOP_EFFECTIVE_PORT"] = resolved
    hosts = allowed_hosts(resolved)
    origins = allowed_origins(resolved)

    @app.before_request
    def guard_request():
        is_health = request.method == "GET" and request.path == HEALTH_PATH
        if not is_health and request.headers.get("Host", "").lower() not in hosts:
            raise HostNotAllowedError("Host não permitido.")

        if request.method not in MUTATING_METHODS:
            return None

        if request.headers.get("Origin") not in origins:
            raise OriginNotAllowedError("Origin ausente ou não permitido.")
        if not _is_json_content_type(request.headers.get("Content-Type", "")):
            raise UnsupportedMediaTypeError("Content-Type deve ser application/json.")
        if request.headers.get(WORKSHOP_HEADER) != WORKSHOP_HEADER_VALUE:
            raise MissingWorkshopHeaderError(
                f"Cabeçalho {WORKSHOP_HEADER} ausente ou inválido."
            )
        return None
