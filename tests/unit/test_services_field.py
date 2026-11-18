"""Testes de unidade do campo `services` (catálogo e API). Requisito 5.7."""
import json
from pathlib import Path

import pytest

from app.lab_catalog import InvalidLabMetadataError, LabCatalog
from app.server import create_app
from tests.fixtures.http_client import workshop_client
from tests.fixtures import NO_INFRA_FIELDS

FIXTURE_LABS = Path(__file__).resolve().parent.parent / "fixtures" / "labs"


def _metadata(**overrides):
    meta = {
        "lab_id": "lab-a",
        "title": "Lab A",
        "description": "Descrição",
        "difficulty": "beginner",
        "estimated_duration_minutes": 30,
        "estimated_cost_usd": 0.5,
        "cost_disclaimer": "Custo estimado.",
        "dea_domains": ["Domain 1"],
        "dea_tasks": ["1.1"],
        "services": ["Amazon S3"],
        **NO_INFRA_FIELDS,
        "steps": [{"step_id": "i1", "title": "Info", "type": "info"}],
    }
    meta.update(overrides)
    return meta


def _write_lab(tmp_path, meta, drop=()):
    lab_dir = tmp_path / meta["lab_id"]
    lab_dir.mkdir(parents=True)
    for key in drop:
        meta.pop(key, None)
    (lab_dir / "metadata.json").write_text(json.dumps(meta), encoding="utf-8")
    return tmp_path


def test_valid_services_loaded(tmp_path):
    catalog = LabCatalog(str(_write_lab(tmp_path, _metadata(services=["Amazon S3", "AWS Glue"]))))
    assert catalog.get_lab("lab-a").services == ["Amazon S3", "AWS Glue"]


def test_missing_services_rejected(tmp_path):
    _write_lab(tmp_path, _metadata(), drop=("services",))
    with pytest.raises(InvalidLabMetadataError):
        LabCatalog(str(tmp_path))


@pytest.mark.parametrize(
    "value",
    [[], "Amazon S3", None, {"a": "b"}, 3, [1], [None], [""], ["   "], ["Amazon S3", ""], ["Amazon S3", 2]],
)
def test_invalid_services_rejected(tmp_path, value):
    _write_lab(tmp_path, _metadata(services=value))
    with pytest.raises(InvalidLabMetadataError):
        LabCatalog(str(tmp_path))


def test_fixture_lab_example_loads_with_services():
    catalog = LabCatalog(str(FIXTURE_LABS))
    lab = catalog.get_lab("lab-example")
    assert lab is not None
    assert lab.services == ["Amazon S3", "AWS CloudFormation"]


def test_api_returns_services(tmp_path):
    progress_file = tmp_path / "progress.json"
    app = create_app({"labs_dir": str(FIXTURE_LABS), "progress_file": str(progress_file)})
    client = workshop_client(app)

    listing = client.get("/api/labs").get_json()
    item = next(x for x in listing["labs"] if x["lab_id"] == "lab-example")
    assert item["services"] == ["Amazon S3", "AWS CloudFormation"]

    detail = client.get("/api/labs/lab-example").get_json()
    assert detail["services"] == ["Amazon S3", "AWS CloudFormation"]
