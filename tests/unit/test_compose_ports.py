"""Property 14: Porta publicada somente em loopback.

Renderiza o docker-compose.yml sem Docker (parse do YAML com substituicao
de variaveis) e verifica o isolamento de portas.

**Validates: Requirements 9.1, 1.9**
"""
import re
from pathlib import Path

import yaml
from hypothesis import given, settings, strategies as st

COMPOSE = Path(__file__).resolve().parents[2] / "docker-compose.yml"
_VAR = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}")


def substituir(texto: str, env: dict) -> str:
    """Substitui ${VAR:-padrao} e ${VAR} (variavel vazia ou ausente usa o padrao)."""
    def troca(m):
        valor = env.get(m.group(1))
        if valor:
            return valor
        return m.group(2) if m.group(2) is not None else ""
    return _VAR.sub(troca, texto)


def renderizar(env: dict) -> dict:
    return yaml.safe_load(substituir(COMPOSE.read_text(encoding="utf-8"), env))


def portas_publicadas(config: dict) -> list:
    """Lista (servico, porta_publicada_str) de todas as portas publicadas."""
    return [
        (nome, str(p))
        for nome, svc in config["services"].items()
        for p in (svc.get("ports") or [])
    ]


# None representa a variavel ausente (padrao 5000)
porta_env = st.one_of(st.none(), st.integers(min_value=1, max_value=65535))


@settings(max_examples=100)
@given(porta=porta_env)
def test_porta_publicada_somente_em_loopback(porta):
    # HOME e usado nos volumes; AWS_PROFILE e irrelevante aqui
    env = {"HOME": "/home/usuario"}
    if porta is not None:
        env["WORKSHOP_PORT"] = str(porta)
    esperada = str(porta if porta is not None else 5000)

    config = renderizar(env)
    publicadas = portas_publicadas(config)

    # Exatamente uma porta publicada no total, e no gateway
    assert len(publicadas) == 1
    servico, mapeamento = publicadas[0]
    assert servico == "gateway"

    # Formato IP:host:container, vinculado a loopback
    ip, host, container = mapeamento.split(":")
    assert ip == "127.0.0.1"
    assert host == esperada
    assert container == "8080"

    # O workshop nao publica nem expoe portas ao host
    assert not config["services"]["workshop"].get("ports")


def test_variavel_vazia_usa_padrao_5000():
    config = renderizar({"HOME": "/h", "WORKSHOP_PORT": ""})
    assert portas_publicadas(config) == [("gateway", "127.0.0.1:5000:8080")]
