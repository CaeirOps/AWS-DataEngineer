"""Politica estatica de seguranca do Dockerfile, do compose e das dependencias.

Nao usa Docker: le os arquivos e verifica as regras.
**Validates: Requirements 9.3, 14.1, 14.2, 14.3, 14.4, 14.5, 14.6**
"""
import re
from pathlib import Path

import pytest

# Reaproveita o helper de renderizacao (parse + substituicao de variaveis)
from test_compose_ports import renderizar

RAIZ = Path(__file__).resolve().parents[2]
DOCKERFILE = RAIZ / "Dockerfile"
DOCKERIGNORE = RAIZ / ".dockerignore"
REQ_TXT = RAIZ / "requirements.txt"
REQ_IN = RAIZ / "requirements.in"

DIGEST = re.compile(r"@sha256:[0-9a-f]{64}$")
SERVICOS = ("workshop", "gateway")


def _compose() -> dict:
    return renderizar({"HOME": "/home/usuario"})


def _instrucoes_dockerfile() -> list:
    """Retorna (INSTRUCAO, argumentos) juntando linhas continuadas com barra."""
    texto = DOCKERFILE.read_text(encoding="utf-8").replace("\\\n", " ")
    saida = []
    for linha in texto.splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#"):
            continue
        instr, _, args = linha.partition(" ")
        saida.append((instr.upper(), args.strip()))
    return saida


# ---------------------------------------------------------------- Dockerfile


def test_from_fixado_por_digest():
    froms = [a for i, a in _instrucoes_dockerfile() if i == "FROM"]
    assert froms
    for arg in froms:
        imagem = arg.split()[0]
        assert DIGEST.search(imagem), f"FROM sem digest: {imagem}"


def test_user_nao_root_antes_do_cmd():
    instrs = _instrucoes_dockerfile()
    idx_cmd = max(n for n, (i, _) in enumerate(instrs) if i == "CMD")
    users = [(n, a) for n, (i, a) in enumerate(instrs) if i == "USER"]
    assert users, "USER ausente"
    n, valor = [u for u in users if u[0] < idx_cmd][-1]
    uid = valor.split(":")[0]
    assert uid not in ("root", "0")


def test_sem_add_de_url_remota():
    for instr, args in _instrucoes_dockerfile():
        if instr == "ADD":
            assert not re.search(r"https?://|ftp://", args), args


def test_pip_install_com_hashes_e_sem_cache():
    pips = [a for i, a in _instrucoes_dockerfile() if i == "RUN" and "pip install" in a]
    assert pips
    for cmd in pips:
        assert "--require-hashes" in cmd
        assert "--no-cache-dir" in cmd


def test_dockerignore_exclui_itens_sensiveis():
    linhas = {
        l.strip()
        for l in DOCKERIGNORE.read_text(encoding="utf-8").splitlines()
        if l.strip() and not l.startswith("#")
    }
    for item in (".git", ".venv", "tests", "progress", ".aws"):
        assert item in linhas, f".dockerignore sem {item}"
    assert ".env" in linhas and ".env.*" in linhas


# ------------------------------------------------------------------- Compose


def test_imagem_do_gateway_fixada_por_digest():
    imagem = _compose()["services"]["gateway"]["image"]
    assert DIGEST.search(imagem), imagem


@pytest.mark.parametrize("nome", SERVICOS)
def test_hardening_nos_dois_servicos(nome):
    svc = _compose()["services"][nome]
    assert svc.get("read_only") is True
    assert "ALL" in (svc.get("cap_drop") or [])
    assert "no-new-privileges:true" in (svc.get("security_opt") or [])
    assert svc.get("mem_limit")
    assert svc.get("pids_limit")
    assert not svc.get("privileged")


def test_cap_add_do_gateway_restrito():
    cap_add = set(_compose()["services"]["gateway"].get("cap_add") or [])
    assert cap_add <= {"SETUID", "SETGID"}


def test_volumes_nao_expoem_host_sensivel():
    proibidos = ("/.aws", "/.ssh", "/.config", "/.docker", "docker.sock", "/home", "/Users", "${HOME}")
    for nome, svc in _compose()["services"].items():
        for vol in svc.get("volumes") or []:
            origem = str(vol).split(":")[0]
            # Somente caminhos relativos ao projeto (./...) sao aceitos
            assert origem.startswith("./"), f"{nome}: volume {vol}"
            assert not origem.startswith("/") and not origem.startswith("~")
            assert not any(p in str(vol) for p in proibidos), f"{nome}: volume {vol}"


def test_workshop_isolado():
    svc = _compose()["services"]["workshop"]
    assert not svc.get("ports")
    assert not svc.get("privileged")
    assert svc.get("network_mode") != "host"
    uid = str(svc["user"]).split(":")[0]
    assert uid not in ("", "root", "0")
    # Sem perfil de credenciais: so as variaveis esperadas
    assert "AWS_PROFILE" not in {str(e).split("=")[0] for e in svc["environment"]}


def test_credenciais_sem_valor_literal():
    nomes = {"AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN", "WORKSHOP_CREDENTIALS_EXPIRATION"}
    for nome, svc in _compose()["services"].items():
        env = svc.get("environment") or []
        if isinstance(env, dict):
            env = [k if v is None else f"{k}={v}" for k, v in env.items()]
        for item in env:
            chave, sep, valor = str(item).partition("=")
            if chave in nomes:
                assert not sep and not valor, f"{nome}: {chave} com valor literal"


def test_rede_interna():
    redes = _compose()["networks"]
    assert redes["workshop-internal"]["internal"] is True
    assert "workshop-internal" in _compose()["services"]["workshop"]["networks"]


# -------------------------------------------------------------- Dependencias


def _blocos_requirements() -> dict:
    """Mapeia pacote -> lista de hashes em requirements.txt (pip-compile)."""
    texto = REQ_TXT.read_text(encoding="utf-8").replace("\\\n", " ")
    blocos = {}
    for linha in texto.splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#"):
            continue
        m = re.match(r"^([A-Za-z0-9_.\-]+)(==\S+)?\s*(.*)$", linha)
        assert m, linha
        assert m.group(2), f"pacote sem pin ==: {linha}"
        blocos[m.group(1).lower()] = re.findall(r"--hash=sha256:[0-9a-f]{64}", m.group(3))
    return blocos


def test_requirements_pinado_com_hash():
    blocos = _blocos_requirements()
    assert blocos
    for pacote, hashes in blocos.items():
        assert hashes, f"{pacote} sem --hash=sha256"


def test_requirements_in_coincide_com_dependencias_diretas():
    diretas = {}
    for linha in REQ_IN.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if linha and not linha.startswith("#"):
            nome, _, versao = linha.partition("==")
            diretas[nome.lower()] = versao
    blocos = _blocos_requirements()
    texto = REQ_TXT.read_text(encoding="utf-8")
    # Toda dependencia direta esta no lock (com a mesma versao) e vem de requirements.in
    for nome, versao in diretas.items():
        assert nome in blocos, f"{nome} ausente de requirements.txt"
        assert f"{nome}=={versao}" in texto
    # O lock marca como "via -r requirements.in" exatamente as dependencias diretas
    no_lock = set()
    atual = None
    for linha in REQ_TXT.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^([A-Za-z0-9_.\-]+)==", linha)
        if m:
            atual = m.group(1).lower()
        elif "# via -r requirements.in" in linha and atual:
            no_lock.add(atual)
    assert no_lock == set(diretas)
