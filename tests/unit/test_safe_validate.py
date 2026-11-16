"""Testes de propriedade para `_safe_validate` e `dispatch_step`.

Feature: aws-data-engineer-workshop
Property 8: Validador retorna ValidationResult para qualquer exceção AWS
"""

from botocore.exceptions import (
    ClientError,
    NoCredentialsError,
    TokenRetrievalError,
    UnauthorizedSSOTokenError,
)
from hypothesis import given, settings, strategies as st

from app.models import ValidationResult
from app.validators.base import (
    CREDENTIAL_ERROR_CODES,
    CREDENTIAL_HINT,
    GENERIC_ERROR_MESSAGE,
    _safe_validate,
    dispatch_step,
)

# Texto simples, sem caracteres de controle, para códigos e mensagens
_texto = st.text(
    alphabet=st.characters(blacklist_categories=("Cc", "Cs")),
    min_size=1,
    max_size=40,
).filter(lambda s: s.strip() != "")

_codigos = st.one_of(st.sampled_from(CREDENTIAL_ERROR_CODES), _texto)


def _lanca(exc):
    """Cria um validador decorado que sempre lança `exc`."""

    @_safe_validate
    def validador(session, context):
        raise exc

    return validador


@settings(max_examples=100)
@given(code=_codigos, msg=_texto)
def test_client_error_vira_validation_result(code, msg):
    """**Validates: Requirements 5.3, 5.6**"""
    exc = ClientError({"Error": {"Code": code, "Message": msg}}, "Op")
    result = _lanca(exc)(None, {})

    assert isinstance(result, ValidationResult)
    assert result.passed is False
    assert result.message
    assert code in result.message
    assert msg in result.message
    # Sugestão de credencial presente se e somente se o código for de credencial
    assert (CREDENTIAL_HINT in result.message) == (code in CREDENTIAL_ERROR_CODES)


@settings(max_examples=100)
@given(
    exc=st.sampled_from(
        [
            NoCredentialsError(),
            UnauthorizedSSOTokenError(),
            TokenRetrievalError(provider="sso", error_msg="falhou"),
        ]
    )
)
def test_erros_de_credencial_botocore(exc):
    """**Validates: Requirements 5.3, 5.6**"""
    result = _lanca(exc)(None, {})

    assert isinstance(result, ValidationResult)
    assert result.passed is False
    assert type(exc).__name__ in result.message
    assert CREDENTIAL_HINT in result.message


def test_excecao_inesperada_vira_mensagem_generica(caplog):
    result = _lanca(ValueError("segredo interno"))(None, {})

    assert result.passed is False
    assert result.message == GENERIC_ERROR_MESSAGE
    assert "Traceback" not in result.message
    assert "segredo interno" not in result.message


def test_dispatch_step_desconhecido():
    result = dispatch_step({}, None, {"step_id": "nao-existe"})

    assert result.passed is False
    assert "nao-existe" in result.message


def test_dispatch_step_conhecido_e_protegido():
    def ok(session, context):
        return ValidationResult(passed=True, message="ok")

    def falha(session, context):
        raise RuntimeError("boom")

    validadores = {"a": ok, "b": falha}
    assert dispatch_step(validadores, None, {"step_id": "a"}).passed is True
    assert dispatch_step(validadores, None, {"step_id": "b"}).message == GENERIC_ERROR_MESSAGE


def test_wraps_preserva_nome():
    @_safe_validate
    def meu_validador(session, context):
        """Documentação."""
        return ValidationResult(passed=True, message="ok")

    assert meu_validador.__name__ == "meu_validador"
    assert meu_validador.__doc__ == "Documentação."
