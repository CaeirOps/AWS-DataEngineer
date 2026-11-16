#!/usr/bin/env python3
"""Pre-validacao dos pre-requisitos do workshop (roda no host).

Usa somente a biblioteca padrao do Python e subprocess para chamar `docker`
e `aws`. Nao usa boto3. Execute antes de `python start.py`.

Codigos de saida: 0 (todos os pre-requisitos ok) ou 1 (ao menos uma falha).
"""

import json
import os
import re
import socket
import subprocess
import sys
from typing import Callable, Dict, List, Optional, Tuple

DEFAULT_PROFILE = "default"
DEFAULT_PORT = 5000
COMMAND_TIMEOUT_S = 30

MIN_DOCKER_MAJOR = 20
MIN_COMPOSE_MAJOR = 2
MIN_AWS_CLI_MAJOR = 2

# run(cmd) -> (returncode, stdout, stderr). Pode lancar OSError (comando
# inexistente) ou subprocess.TimeoutExpired.
RunFn = Callable[[List[str]], Tuple[int, str, str]]
# port_checker(port) -> None se livre, ou texto com o motivo se ocupada.
PortChecker = Callable[[int], Optional[str]]

Result = Dict[str, str]


def default_run(cmd: List[str]) -> Tuple[int, str, str]:
    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        timeout=COMMAND_TIMEOUT_S,
    )
    return proc.returncode, proc.stdout, proc.stderr


def default_port_checker(port: int) -> Optional[str]:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", port))
    except OSError as exc:
        return str(exc)
    finally:
        sock.close()
    return None


def parse_major(text: str) -> Optional[int]:
    """Extrai a versao major do primeiro trecho 'N.N' ou 'N' encontrado."""
    match = re.search(r"(\d+)(?:\.\d+)*", text or "")
    return int(match.group(1)) if match else None


def _failure(prerequisite: str, found: str, fix: str, status: str = "missing") -> Result:
    return {
        "prerequisite": prerequisite,
        "status": status,
        "found": found,
        "fix": fix,
    }


def _first_line(text: str, limit: int = 200) -> str:
    for line in (text or "").splitlines():
        line = line.strip()
        if line:
            return line[:limit]
    return ""


def _safe_run(run: RunFn, cmd: List[str]) -> Tuple[Optional[Tuple[int, str, str]], str]:
    """Executa o comando; retorna (resultado, erro). Erro vazio se executou."""
    try:
        return run(cmd), ""
    except FileNotFoundError:
        return None, "comando '%s' nao encontrado no PATH" % cmd[0]
    except subprocess.TimeoutExpired:
        return None, "tempo esgotado ao executar '%s'" % " ".join(cmd[:2])
    except OSError as exc:
        return None, str(exc)


def check_docker(run: RunFn) -> Optional[Result]:
    name = "Docker >= %d com daemon ativo" % MIN_DOCKER_MAJOR
    fix_install = "Instale ou atualize o Docker: https://docs.docker.com/engine/install/"
    res, err = _safe_run(run, ["docker", "version", "--format", "{{.Server.Version}}"])
    if res is None:
        return _failure(name, err, fix_install)
    code, out, stderr = res
    if code != 0:
        detail = _first_line(stderr) or "codigo de saida %d" % code
        return _failure(
            name,
            "daemon nao responde (%s)" % detail,
            "Inicie o Docker Desktop (ou o servico docker) e aguarde o daemon ficar ativo.",
            status="not_running",
        )
    version = out.strip()
    major = parse_major(version)
    if major is None or major < MIN_DOCKER_MAJOR:
        return _failure(name, version or "versao desconhecida", fix_install, status="outdated")
    return None


def check_compose(run: RunFn) -> Optional[Result]:
    name = "Docker Compose v%d" % MIN_COMPOSE_MAJOR
    fix = "Instale o plugin Docker Compose v2: https://docs.docker.com/compose/install/"
    res, err = _safe_run(run, ["docker", "compose", "version", "--short"])
    if res is None:
        return _failure(name, err, fix)
    code, out, stderr = res
    if code != 0:
        detail = _first_line(stderr) or "codigo de saida %d" % code
        return _failure(name, "plugin 'docker compose' indisponivel (%s)" % detail, fix)
    version = out.strip()
    major = parse_major(version)
    if major is None or major < MIN_COMPOSE_MAJOR:
        return _failure(name, version or "versao desconhecida", fix, status="outdated")
    return None


def check_aws_cli(run: RunFn) -> Optional[Result]:
    name = "AWS CLI >= %d" % MIN_AWS_CLI_MAJOR
    fix = "Instale ou atualize o AWS CLI v2: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
    res, err = _safe_run(run, ["aws", "--version"])
    if res is None:
        return _failure(name, err, fix)
    code, out, stderr = res
    # O AWS CLI v1 escreve a versao em stderr; o v2 em stdout.
    text = _first_line(out) or _first_line(stderr)
    if code != 0:
        return _failure(name, text or "codigo de saida %d" % code, fix)
    match = re.search(r"aws-cli/(\d+(?:\.\d+)*)", text)
    major = int(match.group(1).split(".")[0]) if match else parse_major(text)
    if major is None or major < MIN_AWS_CLI_MAJOR:
        return _failure(name, text or "versao desconhecida", fix, status="outdated")
    return None


def check_credentials(run: RunFn, profile: str) -> Optional[Result]:
    name = "Credenciais AWS validas (profile '%s')" % profile
    cmd = ["aws", "sts", "get-caller-identity", "--profile", profile, "--output", "json"]
    res, err = _safe_run(run, cmd)
    if res is None:
        return _failure(name, err, "Instale o AWS CLI v2 e configure o profile.")
    code, out, stderr = res
    if code != 0:
        detail = _first_line(stderr) or "codigo de saida %d" % code
        return _failure(
            name,
            detail,
            "Configure ou renove as credenciais do profile '%s' (por exemplo "
            "`aws configure --profile %s` ou `aws sso login --profile %s`) "
            "e defina AWS_PROFILE se usar outro profile." % (profile, profile, profile),
            status="invalid",
        )
    try:
        json.loads(out)
    except ValueError:
        return _failure(
            name,
            "resposta inesperada do sts",
            "Verifique o profile '%s' com `aws sts get-caller-identity --profile %s`." % (profile, profile),
            status="invalid",
        )
    return None


def check_port(port: int, port_checker: PortChecker) -> Optional[Result]:
    name = "Porta %d livre em 127.0.0.1" % port
    reason = port_checker(port)
    if reason is None:
        return None
    hint = ""
    if port == 5000 and sys.platform == "darwin":
        hint = " No macOS, o AirPlay Receiver costuma ocupar a porta 5000."
    return _failure(
        name,
        "porta ocupada (%s)" % reason,
        "Libere a porta ou escolha outra, por exemplo `WORKSHOP_PORT=5050 python check_requirements.py`.%s" % hint,
        status="in_use",
    )


def read_port(env: Dict[str, str]) -> Tuple[Optional[int], str]:
    raw = env.get("WORKSHOP_PORT", "").strip()
    if not raw:
        return DEFAULT_PORT, ""
    if raw.isdigit() and 1 <= int(raw) <= 65535:
        return int(raw), ""
    return None, raw


def run_checks(
    env: Optional[Dict[str, str]] = None,
    run: RunFn = default_run,
    port_checker: PortChecker = default_port_checker,
) -> List[Result]:
    """Executa todas as verificacoes e retorna a lista de falhas (vazia se ok)."""
    env = os.environ if env is None else env
    profile = env.get("AWS_PROFILE", "").strip() or DEFAULT_PROFILE
    failures: List[Result] = []

    checks = [
        check_docker(run),
        check_compose(run),
        check_aws_cli(run),
        check_credentials(run, profile),
    ]

    port, invalid = read_port(env)
    if port is None:
        checks.append(
            _failure(
                "WORKSHOP_PORT valida",
                invalid,
                "Defina WORKSHOP_PORT com um numero entre 1 e 65535 (padrao: %d)." % DEFAULT_PORT,
                status="invalid",
            )
        )
    else:
        checks.append(check_port(port, port_checker))

    for result in checks:
        if result is not None:
            failures.append(result)
    return failures


def format_failures(failures: List[Result]) -> str:
    lines = ["Pre-requisitos nao atendidos:", ""]
    for item in failures:
        lines.append("[FALHA] %s" % item["prerequisite"])
        lines.append("  Encontrado: %s" % item["found"])
        lines.append("  Como corrigir: %s" % item["fix"])
        lines.append("")
    return "\n".join(lines).rstrip()


def main(
    env: Optional[Dict[str, str]] = None,
    run: RunFn = default_run,
    port_checker: PortChecker = default_port_checker,
    out=None,
) -> int:
    out = out or sys.stdout
    failures = run_checks(env, run, port_checker)
    if failures:
        out.write(format_failures(failures) + "\n")
        return 1
    out.write("Todos os pre-requisitos foram atendidos. Execute: python start.py\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
