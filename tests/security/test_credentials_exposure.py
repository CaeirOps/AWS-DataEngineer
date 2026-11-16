"""Property 20: credenciais nunca aparecem em respostas nem em logs.

**Validates: Requirements 1.5, 5.6, 9.3, 12.1**

Gera valores fictícios de `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` e
`AWS_SESSION_TOKEN` (montados em tempo de execução, sem literais que casem com
o gitleaks), injeta no ambiente do app e exercita todas as rotas, inclusive
erros forçados (validador que lança exceção com o segredo, `ClientError` com o
token na mensagem, exceção inesperada). Verifica corpo e cabeçalhos das
respostas, logs capturados em nível DEBUG e o `progress.json`. No host,
verifica `host_credentials` e `start.py` (saída, erro e `repr`).
"""

import io
import json
import logging
import os
import string
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

import pytest
from botocore.exceptions import ClientError
from hypothesis import HealthCheck, assume, given, settings, strategies as st

import host_credentials
import start
from app.redaction import MASK
from app.server import create_app
from tests.fixtures import EXAMPLE_LAB_ID, LABS_FIXTURE_DIR
from tests.fixtures.http_client import workshop_client

LAB = EXAMPLE_LAB_ID
PORT = "5000"
ENV_NAMES = ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN")

# --- Estratégias -----------------------------------------------------------

_BASE64 = string.ascii_letters + string.digits + "+/="
_KEY_CHARS = string.ascii_uppercase + string.digits

# Prefixo montado em tempo de execução para não casar com o gitleaks.
_key_ids = st.builds(
    lambda prefix, tail: prefix + tail,
    st.sampled_from(["AK" + "IA", "AS" + "IA"]),
    st.text(alphabet=_KEY_CHARS, min_size=16, max_size=16),
)
_long = st.text(alphabet=_BASE64, min_size=40, max_size=120)


@st.composite
def credentials(draw):
    """Retorna (access_key_id, secret_access_key, session_token) distintos."""
    values = (draw(_key_ids), draw(_long), draw(_long))
    assume(len(set(values)) == 3)
    # Nenhum valor pode estar contido em outro nem em texto fixo da aplicação.
    for a in values:
        assume(all(a == b or a not in b for b in values))
        assume(a not in "application/json workshop lab-example Introdução")
    return values


def _env_for(values) -> dict:
    return dict(zip(ENV_NAMES, values))


# --- Fakes de AWS ----------------------------------------------------------


def _client_error(code: str, message: str, op: str = "Op") -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": message}}, op)


class FailingClient:
    """Cliente AWS cujas chamadas levantam `ClientError` com o token."""

    def __init__(self, token: str):
        self.token = token

    def __getattr__(self, name):
        def call(*args, **kwargs):
            raise _client_error("SomeAwsError", f"falha com token {self.token} no pedido")

        return call

    def get_paginator(self, name):
        raise _client_error("SomeAwsError", f"paginador {self.token}")


class FailingSession:
    def __init__(self, token: str):
        self.token = token

    def client(self, name, **kwargs):
        return FailingClient(self.token)


def _validator_loader(mode: str, secret: str, token: str):
    """Carregador que simula cada modo de falha do validador."""

    def loader(lab_id):
        if mode == "loader_boom":
            raise RuntimeError(f"erro inesperado com {secret}")

        def validate_step(session, context):
            if mode == "raise_secret":
                raise ValueError(f"valor secreto {secret} vazou")
            if mode == "client_error":
                raise _client_error("SomeAwsError", f"mensagem da AWS com {token}")
            session.client("s3").list_buckets()

        return validate_step

    return loader


# --- Execução do app -------------------------------------------------------

AWS_POSTS = (
    f"/api/validate/{LAB}/step-03",
    f"/api/deploy/{LAB}",
    f"/api/teardown/{LAB}",
)


def _all_requests(client, validate_mode_paths=()):
    """Exercita todas as rotas e retorna as respostas."""
    responses = []
    gets = [
        "/",
        "/health",
        f"/lab/{LAB}",
        f"/lab/{LAB}/step-03",
        "/api/labs",
        f"/api/labs/{LAB}",
        "/api/labs/nao-existe",
        f"/api/labs/{LAB}/steps/step-03/content?path=cli",
        f"/api/labs/{LAB}/steps/step-03/content?path=invalido",
        f"/api/labs/{LAB}/steps/step-03/hint?path=console",
        "/api/progress",
        "/api/session",
        f"/api/stack-status/{LAB}",
        "/rota-inexistente",
    ]
    for path in gets:
        responses.append(client.get(path))
    responses.append(client.post(f"/api/labs/{LAB}/steps/step-01/visit", json={}))
    responses.append(client.put("/api/progress", json={"language": "pt"}))
    responses.append(client.put("/api/progress", data="nao-json"))
    responses.append(client.post(f"/api/validate/{LAB}/step-03", json={"context": {}}))
    responses.append(client.post(f"/api/validate/{LAB}/step-01", json={}))
    responses.append(client.post(f"/api/deploy/{LAB}", json={}))
    responses.append(client.post(f"/api/teardown/{LAB}", json={}))
    responses.append(client.post(f"/api/teardown/{LAB}", json={"confirm": True}))
    # Requisição recusada pelos guards.
    responses.append(client.post("/api/progress", json={}, headers={"Origin": "http://x"}))
    return responses


def _build_app(tmp: Path, session_factory, loader):
    progress_file = tmp / "progress" / "progress.json"
    app = create_app(
        {
            "labs_dir": str(LABS_FIXTURE_DIR),
            "progress_file": str(progress_file),
            "session_factory": session_factory,
            "validator_loader": loader,
            "session_env": {"WORKSHOP_CREDENTIALS_EXPIRATION": "2999-01-01T00:00:00Z"},
            "workshop_port": PORT,
        }
    )
    return app, progress_file


def _assert_no_secret(secrets, responses, caplog, progress_file):
    for resp in responses:
        body = resp.get_data(as_text=True)
        headers = "\n".join(f"{k}: {v}" for k, v in resp.headers.items())
        for secret in secrets:
            assert secret not in body, "segredo no corpo"
            assert secret not in headers, "segredo nos cabeçalhos"
    log_text = caplog.text + "\n".join(r.getMessage() for r in caplog.records)
    for secret in secrets:
        assert secret not in log_text, "segredo nos logs"
    if progress_file.exists():
        content = progress_file.read_text(encoding="utf-8")
        for secret in secrets:
            assert secret not in content, "segredo no progress.json"


@settings(
    max_examples=15,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    values=credentials(),
    mode=st.sampled_from(["raise_secret", "client_error", "aws_call", "loader_boom"]),
    factory_kind=st.sampled_from(["failing_session", "factory_error", "factory_boom"]),
)
def test_rotas_e_erros_nao_expoem_credenciais(values, mode, factory_kind, caplog):
    """Property 20: nenhuma rota, erro ou log repete os valores de credenciais."""
    key_id, secret, token = values

    if factory_kind == "failing_session":
        def session_factory():
            return FailingSession(token)
    elif factory_kind == "factory_error":
        def session_factory():
            raise _client_error("SomeAwsError", f"sessao falhou {token}")
    else:
        def session_factory():
            raise RuntimeError(f"fábrica quebrada {key_id} {secret}")

    caplog.clear()
    with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(
        os.environ, _env_for(values)
    ), caplog.at_level(logging.DEBUG):
        app, progress_file = _build_app(
            Path(tmp), session_factory, _validator_loader(mode, secret, token)
        )
        app.config["PROPAGATE_EXCEPTIONS"] = False
        client = workshop_client(app)
        responses = _all_requests(client)
        # O progresso é gravado por visita e por validação.
        _assert_no_secret(values, responses, caplog, progress_file)
        assert progress_file.exists()


def test_erro_original_da_aws_aparece_com_o_valor_mascarado(tmp_path, caplog):
    """O erro da AWS chega ao usuário; só o valor da credencial é mascarado."""
    token = "tok" + "en" + "A1b2C3d4E5f6G7h8I9j0"
    values = ("AK" + "IA" + "ABCDEFGHIJKLMNOP", "sec" + "ret" + "X" * 40, token)
    with mock.patch.dict(os.environ, _env_for(values)):
        app, _ = _build_app(
            tmp_path,
            lambda: FailingSession(token),
            _validator_loader("client_error", values[1], token),
        )
        client = workshop_client(app)
        body = client.post(f"/api/validate/{LAB}/step-03", json={"context": {}}).get_json()
        assert f"SomeAwsError: mensagem da AWS com {MASK}" in body["message"]
        assert token not in json.dumps(body)

        deploy = client.post(f"/api/deploy/{LAB}", json={}).get_json()
        assert deploy["error"] is True
        assert f"falha com token {MASK} no pedido" in deploy["message"]
        assert token not in json.dumps(deploy)


def test_rotas_limpas_mantem_corpo_original(tmp_path):
    """Sem credenciais na resposta, o corpo não é alterado."""
    with mock.patch.dict(os.environ, _env_for(("AK" + "IA" + "A" * 16, "s" * 40, "t" * 40))):
        app, _ = _build_app(tmp_path, lambda: FailingSession("x"), _validator_loader("aws_call", "s", "t"))
        response = workshop_client(app).get("/api/session")
        assert response.status_code == 200
        assert set(response.get_json()) == {"expires_at", "seconds_remaining", "status"}


# --- Host: host_credentials e start.py ------------------------------------


def _export_json(values) -> str:
    key_id, secret, token = values
    return json.dumps(
        {
            "Version": 1,
            "AccessKeyId": key_id,
            "SecretAccessKey": secret,
            "SessionToken": token,
            "Expiration": "2030-01-02T03:04:05Z",
        }
    )


@settings(max_examples=25, deadline=None)
@given(values=credentials(), stderr_kind=st.sampled_from(["echo", "split"]))
def test_host_credentials_nao_expoe_valores(values, stderr_kind):
    """`host_credentials`: mensagens, `repr` e `str` nunca contêm os valores."""
    key_id, secret, token = values

    # Sucesso: o repr de TempCredentials não traz valores.
    creds = host_credentials.export_credentials(
        "p", run=lambda cmd: (0, _export_json(values), "")
    )
    assert creds.session_token == token
    for text in (repr(creds), str(creds)):
        assert all(v not in text for v in values)

    # Falha do CLI com stderr que repete os valores.
    stderr = f"erro\nAccessKeyId={key_id}\nSecretAccessKey={secret}\ntoken {token}\n"
    with pytest.raises(host_credentials.CredentialsExportError) as err:
        host_credentials.export_credentials("p", run=lambda cmd: (1, "", stderr))
    assert all(v not in str(err.value) for v in values)

    # JSON inválido que contém os valores, e credencial de longa duração.
    broken = _export_json(values)[:-3]
    with pytest.raises(host_credentials.CredentialsExportError) as err:
        host_credentials.export_credentials("p", run=lambda cmd: (0, broken, ""))
    assert all(v not in str(err.value) for v in values)

    long_lived = json.dumps({"AccessKeyId": key_id, "SecretAccessKey": secret})
    with pytest.raises(host_credentials.LongLivedCredentialsError) as err:
        host_credentials.export_credentials("p", run=lambda cmd: (0, long_lived, ""))
    assert all(v not in str(err.value) for v in values)


@settings(
    max_examples=25,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(values=credentials(), compose_ok=st.booleans())
def test_start_nao_imprime_credenciais(values, compose_ok, capsys):
    """`start.py`: a saída padrão e o erro padrão nunca contêm os valores."""
    key_id, secret, token = values
    echo = f"env AWS_ACCESS_KEY_ID={key_id} AWS_SECRET_ACCESS_KEY={secret} AWS_SESSION_TOKEN={token}"

    def export(profile):
        return host_credentials.export_credentials(
            profile, run=lambda cmd: (0, _export_json(values), "")
        )

    def run(cmd, env=None):
        if cmd[:3] == ["docker", "compose", "up"]:
            # O docker repete o ambiente no stderr ao falhar.
            return (0, "", "") if compose_ok else (1, "", echo)
        return 0, echo, echo

    class Clock:
        now = 0.0

        def clock(self):
            return self.now

        def sleep(self, s):
            self.now += s

    clk = Clock()
    with tempfile.TemporaryDirectory() as tmp:
        code = start.main(
            env={"AWS_PROFILE": "p", **_env_for(values)},
            run=run,
            opener=mock.Mock(side_effect=ConnectionRefusedError("x")),
            clock=clk.clock,
            sleep=clk.sleep,
            browser_open=lambda url: True,
            port_checker=lambda port: None,
            argv=[],
            export=export,
            progress_dir=Path(tmp) / "progress",
        )
        assert code == 1
        created = [p for p in Path(tmp).rglob("*") if p.is_file()]
        assert created == []  # nenhum arquivo criado em disco

    captured = capsys.readouterr()
    for text in (captured.out, captured.err):
        assert all(v not in text for v in values)
    assert "Sessao AWS valida" in captured.out
