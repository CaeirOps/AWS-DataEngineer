"""Testes de política do repositório: workflows, CODEOWNERS, documentação, ADRs e arquivos do Kiro."""

import glob
import re
from pathlib import Path

import pytest
import yaml

RAIZ = Path(__file__).resolve().parents[2]
WORKFLOWS = sorted((RAIZ / ".github" / "workflows").glob("*.yml"))
CODEOWNERS = RAIZ / ".github" / "CODEOWNERS"
DOCUMENTOS = [
    RAIZ / "README.md",
    RAIZ / "SECURITY.md",
    RAIZ / "CONTRIBUTING.md",
    RAIZ / ".github" / "pull_request_template.md",
]

# Caminhos sensíveis que precisam ter dono no CODEOWNERS.
CAMINHOS_SENSIVEIS = [
    "/docker-compose.yml",
    "/Dockerfile",
    "/.dockerignore",
    "/start.py",
    "/check_requirements.py",
    "/host_credentials.py",
    "/gateway/",
    "/app/server.py",
    "/app/session.py",
    "/app/http_security.py",
    "/app/validators/base.py",
    "/requirements.in",
    "/requirements*.txt",
    "/scripts/",
    "/.github/",
    "/.gitleaks.toml",
    "/tests/security/",
    "/tests/fixtures/http_client.py",
    "/LICENSE*",
    "/NOTICE",
    "/SECURITY.md",
    "/.kiro/",
    "/docs/adr/",
]

SHA_40 = re.compile(r"^[0-9a-f]{40}$")
INTERPOLACAO_EVENTO = re.compile(r"\$\{\{\s*github\.event\.")
EM_DASH = "\u2014"
PADROES_CREDENCIAL_AWS = [
    re.compile(r"\b(AKIA|ASIA)[0-9A-Z]{16}\b"),
    re.compile(r"(?i)aws_secret_access_key\s*[=:]\s*['\"]?[A-Za-z0-9/+=]{40}\b"),
    re.compile(r"(?i)aws_session_token\s*[=:]\s*['\"]?[A-Za-z0-9/+=]{100,}"),
]
TERMOS_ADMINISTRATIVOS = [
    re.compile(r"(?i)\bruleset"),
    re.compile(r"(?i)branch protection"),
    re.compile(r"(?i)Settings\s*(>|&gt;|→)\s*Actions"),
]


def _carregar(caminho: Path) -> dict:
    return yaml.safe_load(caminho.read_text(encoding="utf-8"))


def _jobs(caminho: Path) -> dict:
    return _carregar(caminho).get("jobs") or {}


def _passos(caminho: Path):
    for nome, job in _jobs(caminho).items():
        for passo in job.get("steps") or []:
            yield nome, passo


def test_existem_workflows():
    assert WORKFLOWS, "nenhum workflow encontrado em .github/workflows"


@pytest.mark.parametrize("wf", WORKFLOWS, ids=lambda p: p.name)
def test_sem_gatilhos_perigosos(wf):
    dados = _carregar(wf)
    # PyYAML interpreta a chave "on" como booleano True.
    gatilhos = dados.get("on", dados.get(True))
    nomes = gatilhos if isinstance(gatilhos, (list, dict)) else [gatilhos]
    assert "pull_request_target" not in nomes
    assert "workflow_run" not in nomes


@pytest.mark.parametrize("wf", WORKFLOWS, ids=lambda p: p.name)
def test_permissions_no_topo_e_sem_write_all(wf):
    dados = _carregar(wf)
    assert "permissions" in dados, "permissions deve ser definido no topo"
    assert dados["permissions"] != "write-all"
    assert "write-all" not in wf.read_text(encoding="utf-8")


@pytest.mark.parametrize("wf", WORKFLOWS, ids=lambda p: p.name)
def test_permissions_de_job_restritas(wf):
    for nome, job in _jobs(wf).items():
        perms = job.get("permissions")
        if perms is None:
            continue
        assert isinstance(perms, dict), f"{nome}: permissions de job deve ser mapa"
        for chave, valor in perms.items():
            if (chave, valor) in (("security-events", "write"), ("actions", "read")):
                assert wf.name == "codeql.yml", f"{nome}: {chave}: {valor} só no CodeQL"
            else:
                assert valor in ("read", "none"), f"{nome}: {chave}: {valor} não permitido"


@pytest.mark.parametrize("wf", WORKFLOWS, ids=lambda p: p.name)
def test_actions_externas_fixadas_por_sha(wf):
    for nome, passo in _passos(wf):
        uses = passo.get("uses")
        if not uses or uses.startswith("./"):
            continue
        assert "@" in uses, f"{nome}: {uses} sem versão"
        ref = uses.rsplit("@", 1)[1]
        assert SHA_40.match(ref), f"{nome}: {uses} não está fixado por SHA de 40 hex"


@pytest.mark.parametrize("wf", WORKFLOWS, ids=lambda p: p.name)
def test_checkout_sem_persistir_credenciais(wf):
    for nome, passo in _passos(wf):
        if str(passo.get("uses", "")).startswith("actions/checkout@"):
            valor = (passo.get("with") or {}).get("persist-credentials")
            assert valor is False, f"{nome}: checkout sem persist-credentials: false"


@pytest.mark.parametrize("wf", WORKFLOWS, ids=lambda p: p.name)
def test_sem_referencia_a_secrets(wf):
    assert not re.search(r"\bsecrets\.", wf.read_text(encoding="utf-8"))


@pytest.mark.parametrize("wf", WORKFLOWS, ids=lambda p: p.name)
def test_sem_interpolacao_de_evento_em_run(wf):
    for nome, passo in _passos(wf):
        run = passo.get("run")
        if run:
            assert not INTERPOLACAO_EVENTO.search(run), (
                f"{nome}: interpolação direta de github.event.* em run (use env)"
            )


@pytest.mark.parametrize("wf", WORKFLOWS, ids=lambda p: p.name)
def test_todo_job_tem_timeout(wf):
    for nome, job in _jobs(wf).items():
        assert "timeout-minutes" in job, f"{nome}: sem timeout-minutes"


def _regras_codeowners():
    regras = {}
    for linha in CODEOWNERS.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#"):
            continue
        partes = linha.split()
        regras[partes[0]] = partes[1:]
    return regras


def test_codeowners_cobre_caminhos_sensiveis():
    regras = _regras_codeowners()
    for caminho in CAMINHOS_SENSIVEIS:
        assert regras.get(caminho), f"{caminho} sem dono no CODEOWNERS"
        assert all(dono.startswith("@") for dono in regras[caminho])


def test_codeowners_caminhos_existem():
    for padrao in _regras_codeowners():
        if padrao == "*":
            continue
        relativo = padrao.lstrip("/")
        achados = glob.glob(str(RAIZ / relativo))
        assert achados, f"caminho citado no CODEOWNERS não existe: {padrao}"


def test_dependabot_cobre_tres_ecossistemas():
    dados = yaml.safe_load((RAIZ / ".github" / "dependabot.yml").read_text(encoding="utf-8"))
    ecossistemas = {u["package-ecosystem"] for u in dados["updates"]}
    assert len(ecossistemas) >= 3


@pytest.mark.parametrize("doc", DOCUMENTOS, ids=lambda p: p.name)
def test_documentos_existem(doc):
    assert doc.is_file()


@pytest.mark.parametrize("doc", DOCUMENTOS, ids=lambda p: p.name)
def test_documentos_sem_em_dash_credenciais_ou_instrucoes_admin(doc):
    texto = doc.read_text(encoding="utf-8")
    assert EM_DASH not in texto, "em dash encontrado"
    for padrao in PADROES_CREDENCIAL_AWS:
        assert not padrao.search(texto), f"padrão de credencial AWS: {padrao.pattern}"
    for padrao in TERMOS_ADMINISTRATIVOS:
        assert not padrao.search(texto), f"instrução administrativa: {padrao.pattern}"


SECAO_GITFLOW = "Fluxo de trabalho (gitflow)"
ANCORA_GITFLOW = "#fluxo-de-trabalho-gitflow"
RECOMENDA_MERGE_ERRADO = [
    re.compile(r"(?i)(use|usar|usa|escolha|prefira|recomend\w+|fa[çc]a)\s+(o\s+)?(\*)?(squash|merge commit)"),
    re.compile(r"(?i)squash (and|e) merge"),
    re.compile(r"(?i)git merge\b"),
]


def test_readme_tem_secao_gitflow_completa():
    texto = (RAIZ / "README.md").read_text(encoding="utf-8")
    assert re.search(rf"(?m)^#+\s+{re.escape(SECAO_GITFLOW)}\s*$", texto)
    for item in ("`main`", "`release/vX.Y.Z`", "`hotfix/vX.Y.Z`", "`lab/NN-<descricao>`",
                 "rebase and merge", "git commit -s", "Conventional Commits", "`vX.Y.Z`"):
        assert item in texto, f"README sem {item} na seção de gitflow"


@pytest.mark.parametrize(
    "doc",
    [RAIZ / "CONTRIBUTING.md", RAIZ / ".github" / "pull_request_template.md"],
    ids=lambda p: p.name,
)
def test_documentos_referenciam_secao_gitflow(doc):
    texto = doc.read_text(encoding="utf-8")
    assert ANCORA_GITFLOW in texto
    assert "release" in texto


def test_template_de_pr_indica_branch_base():
    texto = (RAIZ / ".github" / "pull_request_template.md").read_text(encoding="utf-8")
    assert "release ativa" in texto and "`main`" in texto


@pytest.mark.parametrize("doc", DOCUMENTOS, ids=lambda p: p.name)
def test_documentos_nao_recomendam_squash_nem_merge_commit(doc):
    texto = doc.read_text(encoding="utf-8")
    for padrao in RECOMENDA_MERGE_ERRADO:
        assert not padrao.search(texto), f"recomenda método de merge não suportado: {padrao.pattern}"


def test_dependabot_ignora_major_e_minor_do_python():
    dados = yaml.safe_load((RAIZ / ".github" / "dependabot.yml").read_text(encoding="utf-8"))
    regras = [
        r
        for u in dados["updates"]
        if u["package-ecosystem"] == "docker"
        for r in u.get("ignore", [])
        if r.get("dependency-name") == "python"
    ]
    assert regras, "docker sem regra de ignore para python"
    tipos = set(regras[0]["update-types"])
    assert {"version-update:semver-major", "version-update:semver-minor"} <= tipos


# ---------------------------------------------------------------- ADRs e Kiro

ADR_DIR = RAIZ / "docs" / "adr"
ADRS = sorted(ADR_DIR.glob("[0-9][0-9][0-9][0-9]-*.md"))
STEERING_DO_PROJETO = RAIZ / ".kiro" / "steering" / "projeto.md"
# Arquivos de contexto escritos pelo projeto. O aws-rules.md vem do AWS Agent
# Toolkit, em inglês, e fica fora das regras de redação.
CONTEXTO = [ADR_DIR / "README.md", *ADRS, STEERING_DO_PROJETO]
ID_DE_CONTA = re.compile(r"(?<![0-9])[0-9]{12}(?![0-9])")
CAMINHOS_KIRO_PROIBIDOS = (".kiro/hooks/", ".kiro/settings/")
STEERING_LOCAL = ".kiro/steering/local-"


def _arquivos_versionados() -> list[str]:
    import subprocess

    saida = subprocess.run(
        ["git", "ls-files"], cwd=RAIZ, capture_output=True, text=True, check=True
    ).stdout
    return saida.splitlines()


def test_existem_adrs_e_steering_do_projeto():
    assert ADRS, "nenhum ADR em docs/adr/"
    assert STEERING_DO_PROJETO.is_file()


@pytest.mark.parametrize("arquivo", CONTEXTO, ids=lambda p: p.name)
def test_contexto_sem_dados_sensiveis_nem_em_dash(arquivo):
    """ADRs e steering são públicos e lidos por agentes: nada de credencial ou ID de conta."""
    texto = arquivo.read_text(encoding="utf-8")
    assert EM_DASH not in texto, "em dash encontrado"
    for padrao in PADROES_CREDENCIAL_AWS:
        assert not padrao.search(texto), f"padrão de credencial AWS: {padrao.pattern}"
    assert not ID_DE_CONTA.search(texto), "número de 12 dígitos (possível ID de conta AWS)"
    for padrao in TERMOS_ADMINISTRATIVOS + RECOMENDA_MERGE_ERRADO:
        assert not padrao.search(texto), f"termo não permitido: {padrao.pattern}"


def test_indice_de_adrs_lista_todos_e_numeracao_unica():
    indice = (ADR_DIR / "README.md").read_text(encoding="utf-8")
    numeros = [a.name[:4] for a in ADRS]
    assert len(numeros) == len(set(numeros)), "número de ADR repetido"
    for adr in ADRS:
        assert f"]({adr.name})" in indice, f"{adr.name} não está no índice"


@pytest.mark.parametrize("adr", ADRS, ids=lambda p: p.name)
def test_adr_tem_as_secoes_do_modelo(adr):
    texto = adr.read_text(encoding="utf-8")
    assert texto.startswith(f"# ADR-{adr.name[:4]}:")
    for secao in ("- **Status:**", "- **Data:**", "## Contexto", "## Decisão",
                  "## Alternativas rejeitadas", "## Consequências"):
        assert secao in texto, f"{adr.name} sem {secao!r}"


def test_hooks_e_configuracoes_do_kiro_nao_sao_versionados():
    """Hooks e MCP executam comandos na máquina de quem abre o projeto."""
    proibidos = [f for f in _arquivos_versionados() if f.startswith(CAMINHOS_KIRO_PROIBIDOS + (STEERING_LOCAL,))]
    assert proibidos == [], f"arquivos do Kiro que não podem ser versionados: {proibidos}"
    ignorados = (RAIZ / ".gitignore").read_text(encoding="utf-8").splitlines()
    for caminho in (*CAMINHOS_KIRO_PROIBIDOS, f"{STEERING_LOCAL}*.md"):
        assert caminho in ignorados, f"{caminho} fora do .gitignore"
