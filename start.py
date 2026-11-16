#!/usr/bin/env python3
"""Inicializa o workshop (roda no host).

Usa somente a biblioteca padrao do Python. Executa `docker compose up -d --build`,
aguarda o /health responder e abre o browser. Em caso de timeout, imprime um
diagnostico e mantem os containers no ar.

As credenciais temporarias do profile sao exportadas no host e entregues ao
`docker compose` somente pelo ambiente do subprocesso (nunca por arquivo nem
pela linha de comando). Nada de credencial e impresso: so a hora de expiracao.
Com `--refresh`, exporta de novo e recria apenas o servico `workshop`.

Volume de progresso: `progress/` e criado no host se nao existir, sem `chmod 777`
e sem `sudo`. O container roda como UID/GID 10001 por padrao. No Linux o bind
mount respeita as permissoes do host, entao exportamos `WORKSHOP_UID` e
`WORKSHOP_GID` do usuario atual no ambiente do `docker compose` (o compose deve
usar `user: "${WORKSHOP_UID:-10001}:${WORKSHOP_GID:-10001}"`); assim o diretorio,
que pertence a esse usuario, fica gravavel. Se o usuario for root (UID 0), mantem
10001 para nao rodar o container como root. No macOS (Docker Desktop) e nos demais
sistemas o bind mount e gravavel independentemente do UID, entao mantem 10001.

Codigos de saida: 0 (workshop no ar) ou 1 (falha ao subir ou timeout de health).
"""

import os
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import host_credentials

DEFAULT_PROFILE = "default"
DEFAULT_PORT = 5000
# UID/GID fixos do usuario nao root definido no Dockerfile.
CONTAINER_UID = 10001
CONTAINER_GID = 10001
DEFAULT_PROGRESS_DIR = Path(__file__).resolve().parent / "progress"
POLL_INTERVAL_S = 2
TIMEOUT_S = 60
# O build pode baixar a imagem base e dependencias; o limite e generoso.
UP_TIMEOUT_S = 1800
DIAG_TIMEOUT_S = 60

# run(cmd) -> (returncode, stdout, stderr). Pode lancar OSError ou
# subprocess.TimeoutExpired. Quando `env` e informado (somente no `compose up`),
# ele e o ambiente completo do subprocesso.
RunFn = Callable[[List[str]], Tuple[int, str, str]]


def default_run(
    cmd: List[str],
    timeout: int = UP_TIMEOUT_S,
    env: Optional[Dict[str, str]] = None,
) -> Tuple[int, str, str]:
    proc = subprocess.run(
        cmd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        timeout=timeout,
    )
    return proc.returncode, proc.stdout, proc.stderr


def read_port(env: Dict[str, str]) -> Tuple[Optional[int], str]:
    """Retorna (porta, valor_invalido). Porta e None se o valor for invalido."""
    raw = env.get("WORKSHOP_PORT", "").strip()
    if not raw:
        return DEFAULT_PORT, ""
    if raw.isdigit() and 1 <= int(raw) <= 65535:
        return int(raw), ""
    return None, raw


def read_profile(env: Dict[str, str]) -> str:
    return env.get("AWS_PROFILE", "").strip() or DEFAULT_PROFILE


def container_user(
    platform: str = sys.platform,
    getuid: Optional[Callable[[], int]] = None,
    getgid: Optional[Callable[[], int]] = None,
) -> Tuple[int, int]:
    """UID/GID com que o container deve rodar para gravar em `progress/`."""
    if platform.startswith("linux"):
        getuid = getuid or getattr(os, "getuid", None)
        getgid = getgid or getattr(os, "getgid", None)
        if getuid and getgid:
            uid, gid = getuid(), getgid()
            if uid != 0:
                return uid, gid
    return CONTAINER_UID, CONTAINER_GID


def ensure_progress_dir(path: Path) -> None:
    """Cria `progress/` se nao existir (permissoes padrao do usuario)."""
    path.mkdir(parents=True, exist_ok=True)


def _first_line(text: str, limit: int = 300) -> str:
    for line in (text or "").splitlines():
        line = line.strip()
        if line:
            return line[:limit]
    return ""


def health_url(port: int) -> str:
    return "http://127.0.0.1:%d/health" % port


def workshop_url(port: int) -> str:
    return "http://127.0.0.1:%d" % port


def wait_for_health(
    port: int,
    timeout_s: float = TIMEOUT_S,
    interval_s: float = POLL_INTERVAL_S,
    opener=urllib.request.urlopen,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> bool:
    """Retorna True se /health responder 200 antes do timeout."""
    deadline = clock() + timeout_s
    url = health_url(port)
    while True:
        try:
            resp = opener(url, timeout=3)
            try:
                status = getattr(resp, "status", None)
                if status is None:
                    status = resp.getcode()
            finally:
                close = getattr(resp, "close", None)
                if close:
                    close()
            if status == 200:
                return True
        except Exception:
            # Conexao recusada, reset, timeout, HTTP 5xx: tenta de novo.
            pass
        if clock() + interval_s > deadline:
            return False
        sleep(interval_s)


def default_port_checker(port: int) -> Optional[str]:
    """None se a porta esta livre em 127.0.0.1, ou o motivo se ocupada."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", port))
    except OSError as exc:
        return str(exc)
    finally:
        sock.close()
    return None


def _run_text(run: RunFn, cmd: List[str]) -> str:
    try:
        code, out, err = run(cmd)
    except FileNotFoundError:
        return "(comando '%s' nao encontrado)" % cmd[0]
    except subprocess.TimeoutExpired:
        return "(tempo esgotado ao executar '%s')" % " ".join(cmd[:3])
    except OSError as exc:
        return "(falha ao executar: %s)" % exc
    text = (out or "").rstrip()
    if err and err.strip():
        text = (text + "\n" + err.rstrip()).strip()
    if code != 0:
        text = (text + "\n(codigo de saida %d)" % code).strip()
    return text or "(sem saida)"


def build_diagnostics(
    port: int,
    run: RunFn = default_run,
    port_checker: Callable[[int], Optional[str]] = default_port_checker,
    platform: str = sys.platform,
) -> str:
    """Monta o texto de diagnostico apos o timeout do health check."""
    lines: List[str] = []
    lines.append("O workshop nao respondeu em %s dentro de %d s." % (health_url(port), TIMEOUT_S))
    lines.append("")
    lines.append("== docker compose ps ==")
    lines.append(_run_text(run, ["docker", "compose", "ps"]))
    lines.append("")
    lines.append("== docker compose logs --tail 50 workshop gateway ==")
    lines.append(_run_text(run, ["docker", "compose", "logs", "--tail", "50", "workshop", "gateway"]))
    lines.append("")
    lines.append("== Porta %d em 127.0.0.1 ==" % port)
    busy = port_checker(port)
    if busy is None:
        lines.append("Livre neste momento (nenhum outro processo a ocupa).")
    else:
        lines.append("Ocupada: %s" % busy)
        lines.append(
            "Se o gateway nao conseguiu publicar a porta, outro processo a esta usando."
        )
    lines.append("")
    lines.append("== Causas comuns ==")
    if port == DEFAULT_PORT and platform == "darwin":
        lines.append(
            "- AirPlay Receiver do macOS ocupa a porta 5000. Use outra porta: "
            "WORKSHOP_PORT=5050 python start.py"
        )
    elif busy is not None:
        lines.append(
            "- Porta %d ocupada. Use outra porta, por exemplo: WORKSHOP_PORT=5050 python start.py" % port
        )
    lines.append("- Docker Desktop sem memoria suficiente (aumente em Settings > Resources).")
    lines.append("- Erro de import na aplicacao: procure um traceback nos logs do servico workshop acima.")
    lines.append(
        "- Sessao expirada ou variaveis de credenciais ausentes no container: renove o "
        "login no host (`aws sso login --profile <profile>` ou `aws login`) e execute "
        "`python start.py --refresh`."
    )
    lines.append("")
    lines.append("Os containers continuam no ar para inspecao.")
    lines.append("Para encerrar e remover os containers: docker compose down")
    return "\n".join(lines)


def mask_credentials(text: str, env: Dict[str, str]) -> str:
    """Troca valores de credenciais do `env` por `***`, mantendo o resto do texto.

    A saida do docker pode repetir variaveis do ambiente do subprocesso.
    """
    for name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
        value = env.get(name, "")
        if len(value) >= 8:
            text = text.replace(value, "***")
    return text


UP_CMD = ["docker", "compose", "up", "-d", "--build"]
REFRESH_CMD = ["docker", "compose", "up", "-d", "--force-recreate", "--no-deps", "workshop"]


def compose_up(run: RunFn, out, env: Dict[str, str], cmd: List[str] = UP_CMD) -> bool:
    """Executa o comando `docker compose up` com `env`. Retorna True em sucesso."""
    out.write("Subindo os containers (%s)...\n" % " ".join(cmd))
    try:
        code, _stdout, stderr = run(list(cmd), env=env)
    except FileNotFoundError:
        out.write(
            "Erro: o comando 'docker' nao foi encontrado. Instale o Docker: "
            "https://docs.docker.com/engine/install/\n"
        )
        return False
    except subprocess.TimeoutExpired:
        out.write("Erro: 'docker compose up' excedeu o tempo limite.\n")
        return False
    except OSError as exc:
        out.write("Erro ao executar o Docker: %s\n" % exc)
        return False
    if code != 0:
        detail = (stderr or "").strip()
        out.write("Erro: '%s' falhou (codigo %d).\n" % (" ".join(cmd), code))
        if detail:
            tail = "\n".join(detail.splitlines()[-15:])
            out.write(mask_credentials(tail, env) + "\n")
        out.write(
            "Verifique se o Docker esta instalado e com o daemon ativo "
            "(Docker Desktop aberto) e rode `python check_requirements.py`.\n"
        )
        return False
    return True


def main(
    env: Optional[Dict[str, str]] = None,
    run: RunFn = default_run,
    opener=urllib.request.urlopen,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
    browser_open: Callable[[str], object] = webbrowser.open,
    port_checker: Callable[[int], Optional[str]] = default_port_checker,
    out=None,
    argv: Optional[List[str]] = None,
    export: Callable[[str], "host_credentials.TempCredentials"] = host_credentials.export_credentials,
    progress_dir: Path = DEFAULT_PROGRESS_DIR,
    platform: str = sys.platform,
    getuid: Optional[Callable[[], int]] = None,
    getgid: Optional[Callable[[], int]] = None,
) -> int:
    out = out or sys.stdout
    env = os.environ if env is None else env
    args = sys.argv[1:] if argv is None else argv
    unknown = [a for a in args if a != "--refresh"]
    if unknown:
        out.write("Erro: argumento desconhecido '%s'. Uso: python start.py [--refresh]\n" % unknown[0])
        return 1
    refresh = "--refresh" in args

    port, invalid = read_port(env)
    if port is None:
        out.write(
            "Erro: WORKSHOP_PORT invalida ('%s'). Use um numero entre 1 e 65535 "
            "(padrao: %d).\n" % (invalid, DEFAULT_PORT)
        )
        return 1
    profile = read_profile(env)
    out.write("Profile AWS: %s | Porta: %d\n" % (profile, port))

    # Exporta antes de qualquer `docker compose`: falha ou credencial de longa
    # duracao interrompe aqui. Nenhum valor de credencial e impresso.
    try:
        creds = export(profile)
    except (host_credentials.LongLivedCredentialsError, host_credentials.CredentialsExportError) as exc:
        out.write("Erro: %s\n" % exc)
        return 1
    out.write(
        "Sessao AWS valida ate %s (UTC).\n"
        % creds.expiration.strftime("%Y-%m-%d %H:%M:%S")
    )

    try:
        ensure_progress_dir(Path(progress_dir))
    except OSError as exc:
        out.write("Erro: nao foi possivel criar o diretorio '%s': %s\n" % (progress_dir, exc))
        return 1
    uid, gid = container_user(platform, getuid, getgid)

    # Credenciais so no ambiente do subprocesso: sem .env, sem disco, sem argv.
    child_env = dict(os.environ)
    child_env.update(env)
    child_env["WORKSHOP_PORT"] = str(port)
    child_env["WORKSHOP_UID"] = str(uid)
    child_env["WORKSHOP_GID"] = str(gid)
    child_env.update(host_credentials.to_environment(creds))

    if not compose_up(run, out, child_env, REFRESH_CMD if refresh else UP_CMD):
        return 1

    out.write("Aguardando o workshop ficar saudavel em %s ...\n" % health_url(port))
    if wait_for_health(port, TIMEOUT_S, POLL_INTERVAL_S, opener, clock, sleep):
        url = workshop_url(port)
        out.write("Workshop no ar: %s\n" % url)
        try:
            browser_open(url)
        except Exception:
            out.write("Nao foi possivel abrir o browser automaticamente. Abra a URL acima.\n")
        return 0

    out.write(mask_credentials(build_diagnostics(port, run, port_checker), child_env) + "\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())
