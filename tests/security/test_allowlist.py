"""Property 13: Saida restrita a Allowlist (parte pura).

Testa o matcher que espelha o dstdomain do Squid e confere, por leitura, as
regras de gateway/squid.conf (deny all por ultimo; CONNECT somente na 443).
**Validates: Requirements 9.5, 9.6**
"""
import re
from pathlib import Path

from hypothesis import given, settings, strategies as st

from allowlist_matcher import carregar_allowlist, dominio_permitido

SQUID_CONF = Path(__file__).resolve().parents[2] / "gateway" / "squid.conf"
ENTRADAS = carregar_allowlist()

rotulo = st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789-", min_size=1, max_size=12).filter(
    lambda s: not s.startswith("-") and not s.endswith("-")
)
subdominios = st.lists(rotulo, min_size=0, max_size=3).map(lambda r: ".".join(r))
base_aws = st.sampled_from(["amazonaws.com", "api.aws"])


def _com_prefixo(prefixo: str, base: str) -> str:
    return f"{prefixo}.{base}" if prefixo else base


def test_allowlist_contem_entradas_esperadas():
    assert ENTRADAS == [".amazonaws.com", ".api.aws"]


@settings(max_examples=100)
@given(sub=subdominios, base=base_aws, caixa=st.booleans(), ponto_final=st.booleans())
def test_dominios_aws_sao_aceitos(sub, base, caixa, ponto_final):
    host = _com_prefixo(sub, base)
    host = host.upper() if caixa else host
    host = host + "." if ponto_final else host
    assert dominio_permitido(host, ENTRADAS)


@settings(max_examples=100)
@given(sub=subdominios, base=base_aws, extra=rotulo)
def test_sufixos_enganosos_sao_recusados(sub, base, extra):
    # Dominio AWS no inicio, mas o dominio registravel e outro.
    assert not dominio_permitido(_com_prefixo(sub, base) + f".{extra}.example", ENTRADAS)
    # Rotulo colado antes do sufixo (evilamazonaws.com) nao e subdominio.
    assert not dominio_permitido(_com_prefixo(sub, f"evil{base}"), ENTRADAS)
    assert not dominio_permitido(f"{extra}{base}", ENTRADAS)


def test_exemplos_enganosos_fixos():
    for host in [
        "amazonaws.com.evil.example",
        "evilamazonaws.com",
        "api.aws.attacker.io",
        "amazonaws.com.br",
        "example.com",
        "",
    ]:
        assert not dominio_permitido(host, ENTRADAS), host
    for host in ["s3.amazonaws.com", "AMAZONAWS.COM", "sts.us-east-1.amazonaws.com", "x.api.aws"]:
        assert dominio_permitido(host, ENTRADAS), host


@settings(max_examples=100)
@given(host=st.from_regex(r"[a-z0-9]{1,10}(\.[a-z0-9]{1,10}){0,3}\.[a-z]{2,6}", fullmatch=True))
def test_dominio_aleatorio_casa_somente_por_sufixo(host):
    esperado = any(host == b or host.endswith("." + b) for b in ("amazonaws.com", "api.aws"))
    assert dominio_permitido(host, ENTRADAS) == esperado


def _regras_squid() -> list:
    linhas = []
    for linha in SQUID_CONF.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if linha and not linha.startswith("#"):
            linhas.append(linha)
    return linhas


def test_squid_deny_all_e_a_ultima_regra_http_access():
    regras = [l for l in _regras_squid() if l.startswith("http_access ")]
    assert regras, "nenhuma regra http_access encontrada"
    assert regras[-1] == "http_access deny all"


def test_squid_connect_somente_porta_443_e_allowlist():
    linhas = _regras_squid()
    assert "acl SSL_ports port 443" in linhas
    assert "acl CONNECT method CONNECT" in linhas
    assert any(re.fullmatch(r'acl allowed_domains dstdomain "/etc/squid/allowlist\.txt"', l) for l in linhas)
    allow_connect = [l for l in linhas if l.startswith("http_access allow") and "CONNECT" in l]
    assert allow_connect == ["http_access allow CONNECT SSL_ports allowed_domains from_internal"]
    # Nenhuma outra porta e liberada para CONNECT.
    portas = [l for l in linhas if re.match(r"acl \S+ port ", l)]
    assert portas == ["acl SSL_ports port 443"]
