"""Container sem ~/.aws e so com as variaveis de credencial previstas (15D.12).

Como executar (requer Docker):
    WORKSHOP_CONTAINER_TEST=1 WORKSHOP_PORT=5050 .venv/bin/python -m pytest \
        tests/security/test_container_credentials.py -q -rs

Ignorado se `docker` nao existir ou se WORKSHOP_CONTAINER_TEST nao estiver definida.
Usa credenciais FICTICIAS, passadas somente pelo ambiente do subprocesso.
**Validates: Requirements 9.3, 14.6**
"""
import json
import os
import shutil
import subprocess
import time

import pytest

pytestmark = pytest.mark.skipif(
    shutil.which("docker") is None or not os.environ.get("WORKSHOP_CONTAINER_TEST"),
    reason="requer docker e WORKSHOP_CONTAINER_TEST definida (ver instrucoes no topo)",
)

_RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Valores ficticios: so estes podem aparecer nas mensagens do teste
_FICTICIAS = {
    "AWS_ACCESS_KEY_ID": "AKIAFICTICIO0000TEST",
    "AWS_SECRET_ACCESS_KEY": "segredo-ficticio-apenas-para-teste",
    "AWS_SESSION_TOKEN": "token-ficticio-apenas-para-teste",
    "WORKSHOP_CREDENTIALS_EXPIRATION": "2099-01-01T00:00:00Z",
}


def _compose(*args, env=None, timeout=300):
    return subprocess.run(
        ["docker", "compose", *args],
        cwd=_RAIZ, env=env, capture_output=True, text=True, timeout=timeout,
    )


def _ambiente():
    env = dict(os.environ)
    # AWS_PROFILE no host nao deve vazar para o container
    env["AWS_PROFILE"] = "perfil-que-nao-deve-passar"
    env.update(_FICTICIAS)
    return env


@pytest.fixture(scope="module")
def container():
    env = _ambiente()
    try:
        r = _compose("up", "-d", "--build", env=env, timeout=900)
        assert r.returncode == 0, f"docker compose up falhou: {r.stderr[-1500:]}"
        # Aguarda o container workshop ficar em execucao
        cid = ""
        for _ in range(60):
            cid = _compose("ps", "-q", "workshop", env=env).stdout.strip()
            if cid:
                estado = subprocess.run(
                    ["docker", "inspect", "-f", "{{.State.Running}}", cid],
                    capture_output=True, text=True,
                ).stdout.strip()
                if estado == "true":
                    break
            time.sleep(1)
        assert cid, "container workshop nao iniciou"
        inspecao = json.loads(
            subprocess.run(["docker", "inspect", cid], capture_output=True,
                           text=True, check=True).stdout
        )[0]
        yield {"env": env, "inspect": inspecao}
    finally:
        # Sempre derruba, mesmo em falha
        _compose("down", env=env, timeout=120)


def _exec(container, *cmd):
    return _compose("exec", "-T", "workshop", *cmd, env=container["env"], timeout=60)


def test_diretorios_aws_nao_existem(container):
    script = (
        "import os;"
        "print([p for p in (os.path.expanduser('~/.aws'), '/root/.aws', '/home/workshop/.aws')"
        " if os.path.exists(p)])"
    )
    r = _exec(container, "python", "-c", script)
    assert r.returncode == 0
    assert r.stdout.strip() == "[]"


def test_somente_volume_progress(container):
    montagens = container["inspect"]["Mounts"]
    do_host = [m["Destination"] for m in montagens if m["Type"] in ("bind", "volume")]
    assert do_host == ["/app/progress"], f"volumes inesperados: {do_host}"


def test_variaveis_de_credencial_batem_com_as_ficticias(container):
    script = "import os,json;print(json.dumps(dict(os.environ)))"
    r = _exec(container, "python", "-c", script)
    assert r.returncode == 0
    amb = json.loads(r.stdout)
    for nome, valor in _FICTICIAS.items():
        assert amb.get(nome) == valor, f"{nome} ausente ou diferente da ficticia"
    assert amb.get("AWS_SHARED_CREDENTIALS_FILE") == "/dev/null"
    assert amb.get("AWS_CONFIG_FILE") == "/dev/null"
    assert amb.get("AWS_EC2_METADATA_DISABLED") == "true"
    assert "AWS_PROFILE" not in amb


def test_processo_nao_root(container):
    r = _exec(container, "id", "-u")
    assert r.returncode == 0
    assert r.stdout.strip() != "0"
    # PID 1 tambem nao e root
    assert container["inspect"]["Config"]["User"].split(":")[0] not in ("", "0", "root")


def test_rootfs_somente_leitura(container):
    r = _exec(container, "python", "-c", "open('/arquivo_de_teste','w')")
    assert r.returncode != 0
    assert "Read-only file system" in r.stderr
    assert container["inspect"]["HostConfig"]["ReadonlyRootfs"] is True


def test_cap_drop_all_e_no_new_privileges(container):
    host = container["inspect"]["HostConfig"]
    assert host["CapDrop"] == ["ALL"]
    assert "no-new-privileges:true" in host["SecurityOpt"] or \
        "no-new-privileges" in host["SecurityOpt"]
