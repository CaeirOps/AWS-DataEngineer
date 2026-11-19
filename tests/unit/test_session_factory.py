"""Fábrica de sessão boto3 da plataforma (hotfix v0.2.1).

Sem `AWS_PROFILE`, a sessão não pode exigir um profile: no container os
arquivos de configuração são `/dev/null` e as credenciais vêm do ambiente.
Valores fictícios.
"""

import boto3
import pytest
from botocore.exceptions import ProfileNotFound

from app.validation_service import default_session_factory

FICTICIAS = {
    "AWS_ACCESS_KEY_ID": "AKIAFICTICIO0000TEST",
    "AWS_SECRET_ACCESS_KEY": "segredo-ficticio-apenas-para-teste",
    "AWS_SESSION_TOKEN": "token-ficticio-apenas-para-teste",
}


@pytest.fixture
def ambiente_do_container(monkeypatch):
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.delenv("AWS_DEFAULT_PROFILE", raising=False)
    monkeypatch.setenv("AWS_CONFIG_FILE", "/dev/null")
    monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", "/dev/null")
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    for nome, valor in FICTICIAS.items():
        monkeypatch.setenv(nome, valor)


def test_sem_profile_usa_as_credenciais_do_ambiente(ambiente_do_container):
    creds = default_session_factory().get_credentials()
    assert creds.method == "env"
    assert creds.access_key == FICTICIAS["AWS_ACCESS_KEY_ID"]
    assert creds.token == FICTICIAS["AWS_SESSION_TOKEN"]


def test_profile_nomeado_ainda_e_respeitado(ambiente_do_container, monkeypatch):
    monkeypatch.setenv("AWS_PROFILE", "perfil-inexistente")
    with pytest.raises(ProfileNotFound):
        default_session_factory()


def test_comportamento_antigo_falhava_no_container(ambiente_do_container):
    """Documenta a causa: nomear o profile default sem arquivo de configuração falha."""
    with pytest.raises(ProfileNotFound):
        boto3.Session(profile_name="default")
