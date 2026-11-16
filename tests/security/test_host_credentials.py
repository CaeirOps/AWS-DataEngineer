"""Testes de unidade de `host_credentials.py` (task 15D.7).

Os valores abaixo sao claramente ficticios e nao casam com as regras do
gitleaks (nao usam os prefixos AKIA/ASIA nem sequencias longas de secret).

**Validates: Requirements 1.5, 1.14, 1.15**
"""

import json
import subprocess
from datetime import datetime, timezone

import pytest

import host_credentials as hc

AK = "fake-access-key-id"
SK = "fake-secret-key"
TOKEN = "fake-session-token"
VALORES = (AK, SK, TOKEN)
# Montado em tempo de execucao para nao casar com o gitleaks no codigo-fonte.
CHAVE_ACESSO = "AK" + "IA" + "ABCDEFGHIJKLMNOP"


def _saida(**over):
    data = {
        "Version": 1,
        "AccessKeyId": AK,
        "SecretAccessKey": SK,
        "SessionToken": TOKEN,
        "Expiration": "2030-01-02T03:04:05Z",
    }
    data.update(over)
    return json.dumps({k: v for k, v in data.items() if v is not None})


def _run_com(out="", code=0, err=""):
    chamadas = []

    def run(cmd):
        chamadas.append(list(cmd))
        return code, out, err

    return run, chamadas


def test_sucesso_devolve_credenciais_e_comando_previsto():
    run, chamadas = _run_com(_saida())
    creds = hc.export_credentials("meu", run)
    assert chamadas == [[
        "aws", "configure", "export-credentials",
        "--profile", "meu", "--format", "process",
    ]]
    assert creds.access_key_id == AK
    assert creds.secret_access_key == SK
    assert creds.session_token == TOKEN
    assert creds.expiration == datetime(2030, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


@pytest.mark.parametrize("campo", ["SessionToken", "Expiration"])
def test_longa_duracao_e_recusada(campo):
    run, _ = _run_com(_saida(**{campo: None}))
    with pytest.raises(hc.LongLivedCredentialsError) as exc:
        hc.export_credentials("meu", run)
    assert not any(v in str(exc.value) for v in VALORES)


def test_falha_do_cli_filtra_stderr_com_segredos():
    err = (
        "Unable to locate credentials\n"
        + CHAVE_ACESSO + "\n"
        "%s\n" % ("A" * 50)
    )
    run, _ = _run_com(code=255, err=err)
    with pytest.raises(hc.CredentialsExportError) as exc:
        hc.export_credentials("meu", run)
    msg = str(exc.value)
    assert "Unable to locate credentials" in msg
    assert CHAVE_ACESSO not in msg
    assert "A" * 50 not in msg
    assert "meu" in msg


def test_stderr_e_truncado():
    run, _ = _run_com(code=1, err="erro " * 200)
    with pytest.raises(hc.CredentialsExportError) as exc:
        hc.export_credentials("meu", run)
    assert len(str(exc.value)) < 300 + 400


@pytest.mark.parametrize("saida", ["nao e json", "", "[1, 2]", "null"])
def test_saida_invalida(saida):
    run, _ = _run_com(saida)
    with pytest.raises(hc.CredentialsExportError):
        hc.export_credentials("meu", run)


def test_sem_chaves_de_acesso():
    run, _ = _run_com(_saida(AccessKeyId=None))
    with pytest.raises(hc.CredentialsExportError):
        hc.export_credentials("meu", run)


def test_expiration_invalida():
    run, _ = _run_com(_saida(Expiration="amanha"))
    with pytest.raises(hc.CredentialsExportError) as exc:
        hc.export_credentials("meu", run)
    assert not any(v in str(exc.value) for v in VALORES)


def test_expiration_com_fracao_e_offset_vira_utc():
    run, _ = _run_com(_saida(Expiration="2030-01-02T04:04:05.1234567+01:00"))
    creds = hc.export_credentials("meu", run)
    # A fracao e preservada (truncada em microssegundos); o fuso vira UTC.
    assert creds.expiration.replace(microsecond=0) == datetime(
        2030, 1, 2, 3, 4, 5, tzinfo=timezone.utc
    )
    assert creds.expiration.utcoffset().total_seconds() == 0


@pytest.mark.parametrize(
    "exc",
    [
        FileNotFoundError("aws"),
        subprocess.TimeoutExpired(["aws"], 30),
        PermissionError("negado"),
    ],
)
def test_excecoes_do_subprocess_viram_erro_de_exportacao(exc):
    def run(cmd):
        raise exc

    with pytest.raises(hc.CredentialsExportError):
        hc.export_credentials("meu", run)


def test_repr_nao_expoe_valores():
    run, _ = _run_com(_saida())
    creds = hc.export_credentials("meu", run)
    texto = repr(creds) + str(creds)
    assert not any(v in texto for v in VALORES)
    assert "2030" not in texto


def test_to_environment_tem_as_quatro_variaveis():
    run, _ = _run_com(_saida())
    env = hc.to_environment(hc.export_credentials("meu", run))
    assert env == {
        "AWS_ACCESS_KEY_ID": AK,
        "AWS_SECRET_ACCESS_KEY": SK,
        "AWS_SESSION_TOKEN": TOKEN,
        "WORKSHOP_CREDENTIALS_EXPIRATION": "2030-01-02T03:04:05Z",
    }
