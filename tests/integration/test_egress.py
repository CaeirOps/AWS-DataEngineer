"""Property 13: Saida restrita a Allowlist (integracao em rede real).

Como executar (requer Docker e acesso a internet):
    docker compose up -d
    WORKSHOP_EGRESS_TEST=1 .venv/bin/python -m pytest tests/integration/test_egress.py -q -rs
    docker compose down

Ignorado se `docker` nao existir ou se WORKSHOP_EGRESS_TEST nao estiver definida.
Os testes rodam comandos dentro do container `workshop` (servico do compose).
**Validates: Requirements 9.5, 9.6**
"""
import shutil
import subprocess
import time

import pytest

import os

pytestmark = pytest.mark.skipif(
    shutil.which("docker") is None or not os.environ.get("WORKSHOP_EGRESS_TEST"),
    reason="requer docker e WORKSHOP_EGRESS_TEST definida (ver instrucoes no topo)",
)

# Script Python executado dentro do container: abre um tunel CONNECT pelo proxy
# e imprime a linha de status da resposta (ou ERRO:...).
_SCRIPT = (
    "import os,socket,sys,urllib.parse as u;"
    "p=u.urlparse(os.environ['HTTPS_PROXY']);"
    "s=socket.create_connection((p.hostname,p.port),timeout=10);"
    "h=sys.argv[1];"
    "s.sendall(f'CONNECT {h}:443 HTTP/1.1\\r\\nHost: {h}:443\\r\\n\\r\\n'.encode());"
    "print(s.recv(256).decode(errors='replace').splitlines()[0])"
)


def _connect(host: str) -> str:
    r = subprocess.run(
        ["docker", "compose", "exec", "-T", "workshop", "python", "-c", _SCRIPT, host],
        capture_output=True, text=True, timeout=60,
    )
    return (r.stdout + r.stderr).strip()


def _log_gateway() -> str:
    r = subprocess.run(
        ["docker", "compose", "exec", "-T", "gateway", "cat", "/var/log/squid/access.log"],
        capture_output=True, text=True, timeout=30,
    )
    return r.stdout


@pytest.mark.parametrize("host", ["sts.amazonaws.com", "s3.us-east-1.amazonaws.com"])
def test_dominio_aws_na_443_e_aceito(host):
    assert " 200 " in _connect(host) + " "


@pytest.mark.parametrize("host", ["example.com", "amazonaws.com.evil.example"])
def test_destino_fora_da_allowlist_falha_e_e_registrado(host):
    antes = time.time()
    resposta = _connect(host)
    assert " 200 " not in resposta + " "
    assert "403" in resposta
    time.sleep(1)
    linhas = [l for l in _log_gateway().splitlines() if host in l]
    assert linhas, "destino negado nao aparece no log do gateway"
    ultima = linhas[-1]
    # Formato squid: <epoch>.<ms> ... TCP_DENIED/403 ... CONNECT host:443
    assert "TCP_DENIED/403" in ultima
    assert float(ultima.split()[0]) >= antes - 5
