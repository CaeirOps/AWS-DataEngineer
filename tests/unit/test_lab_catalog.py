"""Testes de unidade do LabCatalog (conteúdo, dica por Trilha e validação de metadata)."""

import json
from pathlib import Path

import pytest

from app.errors import (
    InvalidPathError,
    LabNotFoundError,
    PathUnavailableError,
    StepNotFoundError,
)
from app.lab_catalog import CONTENT_SEPARATOR, InvalidLabMetadataError, LabCatalog
from tests.fixtures import NO_INFRA_FIELDS


# ----------------------------------------------------------------------
# Helpers para montar labs em tmp_path
# ----------------------------------------------------------------------


def task_step(step_id="t1", **extra):
    step = {
        "step_id": step_id,
        "title": "Tarefa",
        "type": "task",
        "paths": ["console", "cli"],
    }
    step.update(extra)
    return step


def info_step(step_id="i1", **extra):
    step = {"step_id": step_id, "title": "Info", "type": "info"}
    step.update(extra)
    return step


def make_metadata(lab_id="lab-a", steps=None, **extra):
    meta = {
        "lab_id": lab_id,
        "title": f"Lab {lab_id}",
        "description": "Descrição",
        "difficulty": "iniciante",
        "estimated_duration_minutes": 30,
        "estimated_cost_usd": 0.5,
        "cost_disclaimer": "Estimativa",
        "dea_domains": ["1"],
        "dea_tasks": ["1.1"],
        "services": ["Amazon S3"],
        **NO_INFRA_FIELDS,
        "prerequisites": {},
        "steps": steps if steps is not None else [task_step(), info_step()],
    }
    meta.update(extra)
    return meta


def write_lab(labs_dir: Path, meta: dict, dir_name=None) -> Path:
    lab_dir = labs_dir / (dir_name or meta["lab_id"])
    lab_dir.mkdir(parents=True, exist_ok=True)
    (lab_dir / "metadata.json").write_text(json.dumps(meta), encoding="utf-8")
    return lab_dir


def write_files(lab_dir: Path, step_id: str, files: dict) -> None:
    step_dir = lab_dir / "steps" / step_id
    step_dir.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        (step_dir / name).write_text(text, encoding="utf-8")


@pytest.fixture
def catalog(tmp_path):
    lab_dir = write_lab(tmp_path, make_metadata())
    write_files(
        lab_dir,
        "t1",
        {
            "scenario.md": "CENARIO",
            "console.md": "PASSOS CONSOLE",
            "cli.md": "PASSOS CLI",
            "hint-console.md": "DICA CONSOLE",
            "hint-cli.md": "DICA CLI",
        },
    )
    write_files(lab_dir, "i1", {"content.md": "CONTEUDO INFO"})
    return LabCatalog(str(tmp_path))


# ----------------------------------------------------------------------
# Conteúdo e dica por Trilha
# ----------------------------------------------------------------------


@pytest.mark.parametrize("path,expected", [("console", "PASSOS CONSOLE"), ("cli", "PASSOS CLI")])
def test_step_content_is_scenario_separator_trail(catalog, path, expected):
    content = catalog.get_step_content("lab-a", "t1", path)
    assert content == "CENARIO" + CONTENT_SEPARATOR + expected


@pytest.mark.parametrize("path,expected", [("console", "DICA CONSOLE"), ("cli", "DICA CLI")])
def test_step_hint_returns_trail_hint(catalog, path, expected):
    assert catalog.get_step_hint("lab-a", "t1", path) == expected


@pytest.mark.parametrize("path", ["", "portal", "CLI", None])
def test_invalid_path_raises(catalog, path):
    with pytest.raises(InvalidPathError):
        catalog.get_step_content("lab-a", "t1", path)
    with pytest.raises(InvalidPathError):
        catalog.get_step_hint("lab-a", "t1", path)


def test_unavailable_path_raises_with_reason(tmp_path):
    step = task_step(paths=["console"], unavailable_paths={"cli": "Sem API para isso"})
    lab_dir = write_lab(tmp_path, make_metadata(steps=[step]))
    write_files(lab_dir, "t1", {"scenario.md": "S", "console.md": "C"})
    catalog = LabCatalog(str(tmp_path))

    with pytest.raises(PathUnavailableError) as exc:
        catalog.get_step_content("lab-a", "t1", "cli")
    assert exc.value.reason == "Sem API para isso"
    assert "Sem API para isso" in str(exc.value)
    with pytest.raises(PathUnavailableError):
        catalog.get_step_hint("lab-a", "t1", "cli")


def test_task_methods_reject_non_task_step(catalog):
    with pytest.raises(StepNotFoundError):
        catalog.get_step_content("lab-a", "i1", "console")
    with pytest.raises(StepNotFoundError):
        catalog.get_step_hint("lab-a", "i1", "cli")


def test_missing_content_file_raises_step_not_found(tmp_path):
    lab_dir = write_lab(tmp_path, make_metadata())
    write_files(lab_dir, "t1", {"scenario.md": "S"})  # sem console.md
    catalog = LabCatalog(str(tmp_path))
    with pytest.raises(StepNotFoundError):
        catalog.get_step_content("lab-a", "t1", "console")


# ----------------------------------------------------------------------
# Steps que não são task
# ----------------------------------------------------------------------


def test_single_content_for_non_task_step(catalog):
    assert catalog.get_step_single_content("lab-a", "i1") == "CONTEUDO INFO"


def test_single_content_rejects_task_step(catalog):
    with pytest.raises(StepNotFoundError):
        catalog.get_step_single_content("lab-a", "t1")


# ----------------------------------------------------------------------
# Ids inválidos e path traversal
# ----------------------------------------------------------------------


def test_unknown_lab_raises(catalog):
    assert catalog.get_lab("nope") is None
    with pytest.raises(LabNotFoundError):
        catalog.get_step("nope", "t1")
    with pytest.raises(LabNotFoundError):
        catalog.get_step_content("nope", "t1", "cli")


def test_unknown_step_raises(catalog):
    with pytest.raises(StepNotFoundError):
        catalog.get_step("lab-a", "nope")
    with pytest.raises(StepNotFoundError):
        catalog.get_step_single_content("lab-a", "nope")


def test_path_traversal_ids_are_rejected(tmp_path, catalog):
    (tmp_path / "x").mkdir()
    (tmp_path / "x" / "content.md").write_text("segredo")
    assert catalog.get_lab("../x") is None
    with pytest.raises(LabNotFoundError):
        catalog.get_step_single_content("../x", "i1")
    with pytest.raises(StepNotFoundError):
        catalog.get_step_single_content("lab-a", "../x")
    with pytest.raises(StepNotFoundError):
        catalog.get_step_content("lab-a", "../x", "cli")


def test_metadata_with_traversal_ids_is_rejected(tmp_path):
    write_lab(tmp_path, make_metadata(lab_id="../x"), dir_name="lab-a")
    with pytest.raises(InvalidLabMetadataError):
        LabCatalog(str(tmp_path))


def test_metadata_with_traversal_step_id_is_rejected(tmp_path):
    write_lab(tmp_path, make_metadata(steps=[info_step(step_id="../x")]))
    with pytest.raises(InvalidLabMetadataError):
        LabCatalog(str(tmp_path))


# ----------------------------------------------------------------------
# Catálogo vazio e ordenação
# ----------------------------------------------------------------------


def test_missing_labs_dir_gives_empty_catalog(tmp_path):
    catalog = LabCatalog(str(tmp_path / "inexistente"))
    assert catalog.get_all_labs() == []


def test_empty_labs_dir_gives_empty_catalog(tmp_path):
    assert LabCatalog(str(tmp_path)).get_all_labs() == []


def test_get_all_labs_sorted_by_lab_id(tmp_path):
    for lab_id in ["lab-c", "lab-a", "lab-b"]:
        write_lab(tmp_path, make_metadata(lab_id=lab_id))
    ids = [lab.lab_id for lab in LabCatalog(str(tmp_path)).get_all_labs()]
    assert ids == ["lab-a", "lab-b", "lab-c"]


# ----------------------------------------------------------------------
# metadata.json inconsistente é rejeitado na carga
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "step",
    [
        task_step(paths=[]),  # paths vazio
        task_step(paths=["console"]),  # cli ausente sem motivo
        task_step(paths=["console", "cli"], unavailable_paths={"cli": "motivo"}),  # em ambos
        task_step(paths=["console"], unavailable_paths={"cli": "   "}),  # motivo vazio
        task_step(paths=["console"], unavailable_paths={"cli": ""}),  # motivo vazio
        info_step(paths=["console"]),  # paths em step não task
        info_step(unavailable_paths={"cli": "motivo"}),  # unavailable em step não task
    ],
)
def test_inconsistent_step_metadata_is_rejected(tmp_path, step):
    write_lab(tmp_path, make_metadata(steps=[step]))
    with pytest.raises(InvalidLabMetadataError) as exc:
        LabCatalog(str(tmp_path))
    assert exc.value.lab_id == "lab-a"
    assert exc.value.step_id == step["step_id"]


def test_lab_id_differing_from_dir_name_is_rejected(tmp_path):
    write_lab(tmp_path, make_metadata(lab_id="lab-a"), dir_name="lab-b")
    with pytest.raises(InvalidLabMetadataError):
        LabCatalog(str(tmp_path))


def test_valid_unavailable_path_is_loaded(tmp_path):
    step = task_step(paths=["console"], unavailable_paths={"cli": "Sem suporte"})
    write_lab(tmp_path, make_metadata(steps=[step]))
    loaded = LabCatalog(str(tmp_path)).get_step("lab-a", "t1")
    assert loaded.paths == ["console"]
    assert loaded.unavailable_paths == {"cli": "Sem suporte"}
