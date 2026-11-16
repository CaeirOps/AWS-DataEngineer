"""Cliente de teste Flask com `Host`, `Origin` e cabeçalhos válidos (Requirement 13).

Use `workshop_client(app)` no lugar de `app.test_client()`. Cabeçalhos passados
explicitamente em cada chamada têm precedência, então testes de recusa podem
sobrescrevê-los.
"""

from flask.testing import FlaskClient

DEFAULT_PORT = "5000"
PORT = DEFAULT_PORT  # compatibilidade com testes que fixam a porta no config


def base_url_for(app) -> str:
    """URL base com a porta efetiva do app, independente do ambiente."""
    port = app.config.get("WORKSHOP_EFFECTIVE_PORT", DEFAULT_PORT)
    return f"http://localhost:{port}"


def valid_headers(app) -> dict:
    """Cabeçalhos exigidos em `POST`, `PUT` e `DELETE`."""
    return {"Origin": base_url_for(app), "X-Workshop-Request": "1"}


class WorkshopClient(FlaskClient):
    """Cliente que injeta `base_url` e cabeçalhos válidos por padrão."""

    def open(self, *args, **kwargs):
        kwargs.setdefault("base_url", base_url_for(self.application))
        return super().open(*args, **kwargs)

    def post(self, *args, **kwargs):
        return super().post(*args, **self._with_headers(kwargs))

    def put(self, *args, **kwargs):
        return super().put(*args, **self._with_headers(kwargs))

    def delete(self, *args, **kwargs):
        return super().delete(*args, **self._with_headers(kwargs))

    def _with_headers(self, kwargs: dict) -> dict:
        headers = {**valid_headers(self.application), **(kwargs.get("headers") or {})}
        kwargs["headers"] = headers
        # Sem corpo, o Flask não define Content-Type; o guard exige JSON.
        if kwargs.get("json") is None and "data" not in kwargs:
            kwargs.pop("json", None)
            kwargs["headers"].setdefault("Content-Type", "application/json")
        return kwargs


def workshop_client(app) -> WorkshopClient:
    """Cliente de teste com cabeçalhos válidos para a API local."""
    app.test_client_class = WorkshopClient
    return app.test_client()
