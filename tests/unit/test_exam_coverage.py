"""Testes da Matriz de cobertura do exame (Property 26, Requirements 10.2 a 10.4 e 20.2)."""
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MATRIX = ROOT / "docs" / "exam-coverage.json"
SKILL_ID = re.compile(r"^[1-4]\.[1-5]\.(\d+)$")
EXPECTED_MODULES = [f"lab-{n:02d}" for n in range(19)]


@pytest.fixture(scope="module")
def data():
    with open(MATRIX, encoding="utf-8") as fh:
        return json.load(fh)


def test_origem_e_metadados(data):
    assert data["source"].startswith("https://docs.aws.amazon.com/aws-certification/")
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", data["retrieved_at"])
    assert data["exam"] == "DEA-C01"


def test_modulos_planejados(data):
    assert list(data["modules"]) == EXPECTED_MODULES
    assert all(title.strip() for title in data["modules"].values())


def test_skills_tem_formato_e_ids_unicos(data):
    ids = [s["id"] for s in data["skills"]]
    assert len(ids) == len(set(ids)), "id de skill duplicado"
    for skill in data["skills"]:
        assert SKILL_ID.match(skill["id"]), skill["id"]
        assert skill["domain"] == "D" + skill["id"][0]
        assert skill["task"] == skill["id"][:3]
        assert skill["task"] in data["tasks"], skill["id"]
        assert skill["text"].strip()
        assert "\u2014" not in skill["text"]


def test_skills_sao_sequenciais_por_task(data):
    by_task = {}
    for skill in data["skills"]:
        by_task.setdefault(skill["task"], []).append(int(skill["id"].split(".")[2]))
    for task, numbers in by_task.items():
        assert numbers == list(range(1, len(numbers) + 1)), f"lacuna na task {task}"
    assert set(by_task) == set(data["tasks"])


def test_toda_skill_tem_modulo_existente(data):
    for skill in data["skills"]:
        assert skill["modules"], f"skill sem módulo: {skill['id']}"
        assert len(skill["modules"]) == len(set(skill["modules"]))
        unknown = set(skill["modules"]) - set(data["modules"])
        assert not unknown, f"{skill['id']} cita módulo inexistente: {unknown}"


def test_todo_modulo_cobre_ao_menos_uma_skill(data):
    covered = {m for s in data["skills"] for m in s["modules"]}
    assert covered == set(data["modules"])


def test_cobre_os_quatro_dominios(data):
    assert {s["domain"] for s in data["skills"]} == {"D1", "D2", "D3", "D4"}


def _existing_modules():
    labs = ROOT / "labs"
    return sorted(p for p in labs.glob("lab-*/metadata.json")) if labs.is_dir() else []


@pytest.mark.parametrize("metadata", _existing_modules(), ids=lambda p: p.parent.name)
def test_metadata_existente_confere_com_a_matriz(data, metadata):
    meta = json.loads(metadata.read_text(encoding="utf-8"))
    lab_id = meta["lab_id"]
    expected = {s["id"] for s in data["skills"] if lab_id in s["modules"]}
    assert set(meta.get("skills", [])) == expected, f"{lab_id} diverge da Matriz"


def test_relatorio_sem_skills_orfas(capsys):
    import importlib.util

    spec = importlib.util.spec_from_file_location("coverage_report", ROOT / "scripts" / "coverage_report.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.main([]) == 0
    assert "sem módulo: 0" in capsys.readouterr().out
    assert module.main(["lab-99"]) == 1
