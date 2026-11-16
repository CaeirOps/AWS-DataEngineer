"""Matcher puro que espelha a semantica de `acl dstdomain` do Squid.

Vive em tests/ porque so reproduz o Squid; nao faz parte da aplicacao.
Regras reproduzidas:
- entrada com ponto inicial (".amazonaws.com") casa o proprio dominio e
  qualquer subdominio;
- entrada sem ponto inicial casa somente o dominio exato;
- comparacao sem diferenciar maiusculas e minusculas;
- um ponto final do destino (FQDN) e ignorado;
- nunca casa por substring: a correspondencia e por sufixo em fronteira de rotulo.
"""
from pathlib import Path

ALLOWLIST = Path(__file__).resolve().parents[2] / "gateway" / "allowlist.txt"


def carregar_allowlist(caminho: Path = ALLOWLIST) -> list:
    """Le o arquivo ignorando linhas vazias e comentarios."""
    entradas = []
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if linha and not linha.startswith("#"):
            entradas.append(linha.lower())
    return entradas


def dominio_permitido(host: str, entradas: list) -> bool:
    """True se `host` casa alguma entrada, como o dstdomain do Squid."""
    h = host.strip().lower().rstrip(".")
    if not h:
        return False
    for e in entradas:
        if e.startswith("."):
            base = e[1:]
            if h == base or h.endswith(e):
                return True
        elif h == e:
            return True
    return False
