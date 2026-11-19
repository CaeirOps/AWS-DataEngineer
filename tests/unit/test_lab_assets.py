"""Rota de imagens locais do módulo (task 15M.3).

**Property 27: Imagens do conteúdo são sempre locais** (lado do servidor)
**Validates: Requirements 4.8, 8.2**
"""

import os
import shutil
from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st

from app.errors import AssetNotFoundError
from app.http_security import ASSET_CONTENT_SECURITY_POLICY, CONTENT_SECURITY_POLICY
from app.lab_catalog import LabCatalog
from app.server import create_app
from tests.fixtures import LABS_FIXTURE_DIR
from tests.fixtures.http_client import workshop_client

LAB = "lab-example"
ASSETS = LABS_FIXTURE_DIR / LAB / "assets"
NAME_RULE = r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}\.(svg|png)$"


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("assets")
    app = create_app(
        {
            "labs_dir": str(LABS_FIXTURE_DIR),
            "progress_file": str(tmp / "progress.json"),
            "static_folder": str(tmp / "static"),
            "session_factory": lambda: (_ for _ in ()).throw(AssertionError("sem AWS")),
        }
    )
    return workshop_client(app)


def url(name, lab=LAB):
    return f"/api/labs/{lab}/assets/{name}"


@pytest.mark.parametrize(
    "name,mimetype", [("fluxo.svg", "image/svg+xml"), ("icone.png", "image/png")]
)
def test_serves_local_asset_with_type_and_security_headers(client, name, mimetype):
    resp = client.get(url(name))
    assert resp.status_code == 200
    assert resp.mimetype == mimetype
    assert resp.data == (ASSETS / name).read_bytes()
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["Content-Security-Policy"] == ASSET_CONTENT_SECURITY_POLICY
    assert "sandbox" in resp.headers["Content-Security-Policy"]
    assert resp.headers["Content-Disposition"] == "inline"
    assert resp.headers["Cache-Control"] == "no-store"


def test_percent_encoded_dot_is_the_same_name(client):
    """`%2E` é decodificado antes da rota: é o próprio `fluxo.svg`."""
    assert client.get(url("fluxo%2Esvg")).data == (ASSETS / "fluxo.svg").read_bytes()


def test_other_routes_keep_default_csp(client):
    assert client.get("/api/labs").headers["Content-Security-Policy"] == CONTENT_SECURITY_POLICY


@pytest.mark.parametrize(
    "name",
    [
        "inexistente.svg",
        "fluxo.SVG",
        "fluxo.svg.html",
        "fluxo.gif",
        "fluxo",
        ".svg",
        "-fluxo.svg",
        "..%2Fmetadata.json",
        "..%2F..%2Fmetadata.json",
        "%2E%2E%2Fmetadata.json",
        "fluxo.svg%00.png",
        "fluxo.svg%3Fx",
        "a" * 65 + ".svg",
    ],
)
def test_invalid_or_missing_names_return_404(client, name):
    resp = client.get(url(name))
    assert resp.status_code == 404
    body = resp.get_json()
    assert body["code"] in ("ASSET_NOT_FOUND", "NOT_FOUND")
    assert "Imagem" in body["message"] or body["code"] == "NOT_FOUND"


@pytest.mark.parametrize("path", ["../metadata.json", "../../lab-theory/metadata.json", "sub/fluxo.svg"])
def test_multi_segment_paths_never_reach_files(client, path):
    resp = client.get(url(path))
    assert resp.status_code == 404
    assert b"lab_id" not in resp.data


def test_unknown_lab_returns_404(client):
    resp = client.get(url("fluxo.svg", lab="lab-inexistente"))
    assert resp.status_code == 404
    assert resp.get_json()["code"] == "LAB_NOT_FOUND"


def test_module_without_assets_dir_returns_404(client):
    assert client.get(url("fluxo.svg", lab="lab-theory")).get_json()["code"] == "ASSET_NOT_FOUND"


@pytest.fixture
def copied_labs(tmp_path):
    labs = tmp_path / "labs"
    shutil.copytree(LABS_FIXTURE_DIR, labs)
    return labs


def test_symlink_escaping_assets_dir_is_refused(copied_labs, tmp_path):
    secret = tmp_path / "segredo.svg"
    secret.write_text("<svg/>", encoding="utf-8")
    os.symlink(secret, copied_labs / LAB / "assets" / "fora.svg")
    os.symlink(copied_labs / LAB / "metadata.json", copied_labs / LAB / "assets" / "meta.png")
    catalog = LabCatalog(str(copied_labs))
    for name in ("fora.svg", "meta.png"):
        with pytest.raises(AssetNotFoundError):
            catalog.get_asset(LAB, name)


def test_symlink_inside_assets_dir_is_refused(copied_labs):
    """Mesmo apontando para outro arquivo de `assets/`, link simbólico não é servido."""
    assets = copied_labs / LAB / "assets"
    (assets / "pagina.html").write_text("<script>alert(1)</script>", encoding="utf-8")
    os.symlink(assets / "pagina.html", assets / "atalho.svg")
    os.symlink(assets / "fluxo.svg", assets / "copia.svg")
    catalog = LabCatalog(str(copied_labs))
    for name in ("atalho.svg", "copia.svg"):
        with pytest.raises(AssetNotFoundError):
            catalog.get_asset(LAB, name)


def test_directory_with_asset_name_is_refused(copied_labs):
    (copied_labs / LAB / "assets" / "pasta.svg").mkdir()
    with pytest.raises(AssetNotFoundError):
        LabCatalog(str(copied_labs)).get_asset(LAB, "pasta.svg")


@settings(max_examples=300, deadline=None)
@given(
    name=st.one_of(
        st.text(max_size=30),
        st.sampled_from(["fluxo.svg", "icone.png", "../metadata.json", "..", ".", ""]),
        st.from_regex(NAME_RULE, fullmatch=True),
    )
)
def test_property_27_route_only_serves_svg_or_png_inside_assets(name):
    """Para qualquer nome, só sai arquivo .svg/.png de `labs/<lab_id>/assets/`."""
    catalog = LabCatalog(str(LABS_FIXTURE_DIR))
    try:
        path, mimetype = catalog.get_asset(LAB, name)
    except AssetNotFoundError:
        return
    assert path.parent == ASSETS.resolve()
    assert path.suffix in (".svg", ".png")
    assert mimetype == {".svg": "image/svg+xml", ".png": "image/png"}[path.suffix]
    assert name in {"fluxo.svg", "icone.png"}
