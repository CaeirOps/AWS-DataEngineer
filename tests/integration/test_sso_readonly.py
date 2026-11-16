"""Teste de integracao: credenciais SSO / `aws login` com ~/.aws montado em :ro.

Verifica se o botocore, dentro do container, falha ao gravar o token renovado
no cache quando o volume e somente-leitura, e se o erro chega como texto
original da AWS em vez de um traceback.

Requisitos para executar: Docker e um profile SSO (ou `aws login`) real.
O teste e ignorado (skip) quando `WORKSHOP_SSO_TEST_PROFILE` nao esta definida
ou o comando `docker` nao existe.

Como executar:

    aws sso login --profile X          # sessao valida
    WORKSHOP_SSO_TEST_PROFILE=X \\
        .venv/bin/python -m pytest tests/integration/test_sso_readonly.py -q -rs

Para o caso de sessao expirada, informe tambem um profile com token expirado
(por exemplo, apos `aws sso logout`):

    WORKSHOP_SSO_TEST_EXPIRED_PROFILE=Y

Sem essa variavel, o teste de sessao expirada e ignorado.

Requirements: 5.6, 9.3, 1.12
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PROFILE = os.environ.get("WORKSHOP_SSO_TEST_PROFILE")
EXPIRED_PROFILE = os.environ.get("WORKSHOP_SSO_TEST_EXPIRED_PROFILE")

if not PROFILE:
    pytest.skip("WORKSHOP_SSO_TEST_PROFILE nao definida", allow_module_level=True)
if shutil.which("docker") is None:
    pytest.skip("comando docker nao encontrado", allow_module_level=True)

# Roda dentro do container, com o mesmo codigo de credenciais do botocore
# usado pelos validadores.
_SCRIPT = """
import sys, boto3
from botocore.exceptions import ClientError, BotoCoreError
try:
    ident = boto3.Session().client("sts").get_caller_identity()
    print("OK", ident["Arn"])
except (ClientError, BotoCoreError) as e:
    print("AWSERROR", type(e).__name__, e)
    sys.exit(3)
"""


def _run(*args, **kw):
    return subprocess.run(args, capture_output=True, text=True, cwd=REPO_ROOT, **kw)


def _snapshot(path: Path):
    return sorted((str(p), p.stat().st_mtime_ns) for p in path.rglob("*") if p.is_file())


@pytest.fixture(scope="module")
def image_id():
    build = _run("docker", "compose", "build", "workshop", timeout=900)
    assert build.returncode == 0, build.stderr
    # `compose images -q` devolve um ID que `docker run` nao resolve com o
    # containerd image store. Usa o nome da imagem construida: o unico de
    # `config --images` que nao e a imagem fixa de outro servico.
    images = _run("docker", "compose", "config", "--images").stdout.split()
    cfg = json.loads(_run("docker", "compose", "config", "--format", "json").stdout)
    pinned = {s["image"] for s in cfg["services"].values() if s.get("image")}
    built = [i for i in images if i not in pinned]
    assert len(built) == 1, f"imagem do workshop nao encontrada: {images}"
    return built[0]


def _run_in_container(image_id, profile):
    aws_dir = Path.home() / ".aws"
    # `docker run` direto na rede padrao: o objetivo e o volume :ro, nao o proxy.
    return _run(
        "docker", "run", "--rm",
        "-v", f"{aws_dir}:/root/.aws:ro",
        "-e", f"AWS_PROFILE={profile}",
        "-e", "AWS_DEFAULT_REGION=" + os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
        "--entrypoint", "python",
        image_id, "-c", _SCRIPT,
        timeout=180,
    )


def test_valid_session_with_readonly_aws_dir(image_id):
    before = _snapshot(Path.home() / ".aws")
    res = _run_in_container(image_id, PROFILE)
    after = _snapshot(Path.home() / ".aws")
    print(f"profile={PROFILE} rc={res.returncode}\n{res.stdout}\n{res.stderr}")
    assert "Traceback" not in res.stderr
    assert res.returncode == 0 and res.stdout.startswith("OK"), res.stdout + res.stderr
    assert before == after, "~/.aws foi alterado"


def test_expired_session_reports_original_aws_error(image_id):
    if not EXPIRED_PROFILE:
        pytest.skip("WORKSHOP_SSO_TEST_EXPIRED_PROFILE nao definida")
    res = _run_in_container(image_id, EXPIRED_PROFILE)
    print(f"profile={EXPIRED_PROFILE} rc={res.returncode}\n{res.stdout}\n{res.stderr}")
    assert "Traceback" not in res.stderr
    assert res.stdout.startswith("AWSERROR"), res.stdout + res.stderr
    assert "Read-only file system" not in res.stdout + res.stderr
