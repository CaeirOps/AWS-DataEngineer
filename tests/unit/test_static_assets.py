"""Smoke tests dos arquivos estaticos (Requisito 8.2).

Property 11: arquivos estaticos nao referenciam URLs externas.

Excecao explicita: o renderizador Markdown (`markdown.js`) pode gerar links
`http(s)` a partir do conteudo dos labs. Isso e um link navegavel, nao um
recurso carregado. Por isso a verificacao em JS olha apenas `import`,
`import()` e `fetch`, e nao atribuicoes de `href` geradas pelo Markdown.

**Validates: Requirements 8.2**
"""
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from app.server import create_app
from tests.fixtures.http_client import workshop_client

STATIC = Path(__file__).resolve().parents[2] / "app" / "static"
JS_FILES = sorted((STATIC / "js").glob("*.js"))
ALL_FILES = sorted(p for p in STATIC.rglob("*") if p.is_file())

EXTERNAL = re.compile(r"^\s*(?:https?:)?//|^\s*(?:https?|ftp|wss?):", re.I)

ATTR_RE = re.compile(r"""\b(?:src|href)\s*=\s*(["'])(.*?)\1""", re.I | re.S)
CSS_URL_RE = re.compile(r"""url\(\s*(["']?)(.*?)\1\s*\)""", re.I | re.S)
CSS_IMPORT_RE = re.compile(r"""@import\s+(?:url\()?\s*(["'])(.*?)\1""", re.I)
IMPORT_FROM_RE = re.compile(r"""^\s*(?:import|export)\b[^;'"]*?\bfrom\s*(["'])(.*?)\1""", re.M)
IMPORT_BARE_RE = re.compile(r"""^\s*import\s*(["'])(.*?)\1""", re.M)
IMPORT_DYN_RE = re.compile(r"""\bimport\s*\(\s*(["'`])(.*?)\1""")
FETCH_RE = re.compile(r"""\bfetch\s*\(\s*(["'`])(.*?)\1""")


def _text(path):
    return path.read_text(encoding="utf-8")


def _js_specifiers(source):
    found = []
    for rx in (IMPORT_FROM_RE, IMPORT_BARE_RE, IMPORT_DYN_RE):
        found += [m.group(2) for m in rx.finditer(source)]
    return found


def _refs(path):
    """Referencias carregaveis de um arquivo estatico."""
    text = _text(path)
    if path.suffix == ".html":
        return [m.group(2) for m in ATTR_RE.finditer(text)]
    if path.suffix == ".css":
        return [m.group(2) for m in CSS_URL_RE.finditer(text)] + [
            m.group(2) for m in CSS_IMPORT_RE.finditer(text)
        ]
    if path.suffix == ".js":
        return _js_specifiers(text) + [m.group(2) for m in FETCH_RE.finditer(text)]
    return []


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("static")
    labs = tmp / "labs"
    labs.mkdir()
    app = create_app(
        {"labs_dir": str(labs), "progress_file": str(tmp / "progress.json")}
    )
    return workshop_client(app)


def test_existem_arquivos_estaticos():
    assert (STATIC / "index.html").is_file()
    assert JS_FILES and list((STATIC / "css").glob("*.css"))


@pytest.mark.parametrize("path", ALL_FILES, ids=lambda p: str(p.relative_to(STATIC)))
def test_property_11_sem_urls_externas(path):
    for ref in _refs(path):
        assert not EXTERNAL.match(ref), f"{path.name}: referencia externa '{ref}'"


def test_detector_pega_urls_externas():
    # Garante que o detector nao e vazio: exemplos externos sao reconhecidos.
    assert EXTERNAL.match("https://cdn.example.com/x.js")
    assert EXTERNAL.match("//cdn.example.com/x.js")
    assert not EXTERNAL.match("/static/js/app.js")
    assert not EXTERNAL.match("./dom.js")


def _resolve_imports(entry):
    """Fecho transitivo de imports locais a partir de `entry`."""
    seen, queue, missing = set(), [entry], []
    while queue:
        current = queue.pop()
        if current in seen:
            continue
        seen.add(current)
        for spec in _js_specifiers(_text(current)):
            target = (current.parent / spec).resolve()
            if not target.is_file():
                missing.append((current.name, spec))
            else:
                queue.append(target)
    return seen, missing


def test_imports_de_app_js_existem():
    seen, missing = _resolve_imports((STATIC / "js" / "app.js").resolve())
    assert not missing, f"imports inexistentes: {missing}"
    js_dir = (STATIC / "js").resolve()
    assert all(p.parent == js_dir for p in seen)
    assert len(seen) > 1


def test_index_html_referencia_arquivos_servidos_com_200(client):
    refs = _refs(STATIC / "index.html")
    local = [r for r in refs if r.startswith("/static/")]
    assert local, "index.html deveria referenciar arquivos em /static/"
    for ref in local:
        assert (STATIC / ref[len("/static/"):]).is_file(), f"nao existe: {ref}"
        response = client.get(ref)
        assert response.status_code == 200, f"{ref} retornou {response.status_code}"
        response.close()


@pytest.mark.parametrize("path", ALL_FILES, ids=lambda p: str(p.relative_to(STATIC)))
def test_sem_em_dash(path):
    assert "\u2014" not in _text(path)


@pytest.mark.skipif(shutil.which("node") is None, reason="node nao disponivel")
@pytest.mark.parametrize("path", JS_FILES, ids=lambda p: p.name)
def test_node_check_sintaxe(path):
    # O codigo vai por stdin como ES module: `node --check arquivo.js` trataria
    # o arquivo como CommonJS e rejeitaria `import`.
    result = subprocess.run(
        ["node", "--input-type=module", "--check"],
        input=_text(path),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
