"""Testes de unidade das rotas de Trilha (console/cli) do servidor.

Valida: 11.1, 11.3, 11.4, 11.5, 11.6.
"""

import json

import pytest

from app.lab_catalog import LabCatalog
from app.models import ValidationResult
from app.progress_store import ProgressStore
from app.server import create_app
from tests.fixtures.http_client import workshop_client
from app.validation_service import ValidationService
from tests.fixtures import INFRA_FIELDS, write_stack

LAB = "lab-01"


def _build_labs(root):
    """Monta um catálogo mínimo em `root` (um módulo com infraestrutura, steps info e task)."""
    lab_dir = root / LAB
    meta = {
        "lab_id": LAB,
        "title": "Lab de teste",
        "description": "desc",
        "difficulty": "easy",
        "estimated_duration_minutes": 10,
        "estimated_cost_usd": 0.1,
        "cost_disclaimer": "estimativa",
        "dea_domains": ["1"],
        "dea_tasks": ["1.1"],
        "services": ["Amazon S3"],
        **INFRA_FIELDS,
        "steps": [
            {"step_id": "intro", "title": "Intro", "type": "info"},
            {"step_id": "deploy", "title": "Deploy", "type": "deploy"},
            {
                "step_id": "both",
                "title": "Ambas",
                "type": "task",
                "paths": ["console", "cli"],
            },
            {
                "step_id": "console-only",
                "title": "Só console",
                "type": "task",
                "paths": ["console"],
                "unavailable_paths": {"cli": "sem suporte na CLI"},
            },
        ],
    }
    meta["steps"].append({"step_id": "teardown", "title": "Teardown", "type": "teardown"})
    lab_dir.mkdir(parents=True)
    write_stack(lab_dir)
    (lab_dir / "metadata.json").write_text(json.dumps(meta), encoding="utf-8")
    steps = lab_dir / "steps"
    (steps / "intro").mkdir(parents=True)
    (steps / "intro" / "content.md").write_text("# Intro", encoding="utf-8")
    for sid in ("deploy", "teardown"):
        (steps / sid).mkdir(parents=True)
        (steps / sid / "content.md").write_text(f"# {sid}", encoding="utf-8")
    for sid, trails in (("both", ("console", "cli")), ("console-only", ("console",))):
        d = steps / sid
        d.mkdir(parents=True)
        (d / "scenario.md").write_text("CENARIO", encoding="utf-8")
        for t in trails:
            (d / f"{t}.md").write_text(f"INSTR-{t}", encoding="utf-8")
            (d / f"hint-{t}.md").write_text(f"DICA-{t}", encoding="utf-8")


@pytest.fixture
def env(tmp_path):
    labs = tmp_path / "labs"
    _build_labs(labs)
    progress_file = tmp_path / "progress" / "progress.json"
    catalog = LabCatalog(str(labs))
    store = ProgressStore(str(progress_file))
    contexts = []

    def fake_validator(session, ctx):
        contexts.append(dict(ctx))
        return ValidationResult(passed=True, message="ok")

    def fake_session():
        return object()

    validation = ValidationService(
        catalog,
        store,
        session_factory=fake_session,
        validator_loader=lambda lab_id: fake_validator,
    )
    app = create_app(
        {
            "catalog": catalog,
            "progress_store": store,
            "validation_service": validation,
            "session_factory": fake_session,
            "session_env": {"WORKSHOP_CREDENTIALS_EXPIRATION": "2999-01-01T00:00:00Z"},
        }
    )
    return {
        "client": workshop_client(app),
        "store": store,
        "file": progress_file,
        "contexts": contexts,
    }


# ----------------------------------------------------------------------
# GET /api/labs/<lab_id>
# ----------------------------------------------------------------------


def test_get_lab_returns_paths_and_unavailable_paths(env):
    data = env["client"].get(f"/api/labs/{LAB}").get_json()
    steps = {s["step_id"]: s for s in data["steps"]}
    assert steps["both"]["paths"] == ["console", "cli"]
    assert steps["both"]["unavailable_paths"] == {}
    assert steps["console-only"]["paths"] == ["console"]
    assert steps["console-only"]["unavailable_paths"] == {"cli": "sem suporte na CLI"}
    # Steps que não são task não expõem paths
    assert "paths" not in steps["intro"]


# ----------------------------------------------------------------------
# content e hint
# ----------------------------------------------------------------------


@pytest.mark.parametrize("trail", ["console", "cli"])
def test_content_and_hint_return_trail_content(env, trail):
    c = env["client"]
    content = c.get(f"/api/labs/{LAB}/steps/both/content?path={trail}")
    assert content.status_code == 200
    md = content.get_json()["markdown"]
    assert "CENARIO" in md and f"INSTR-{trail}" in md

    hint = c.get(f"/api/labs/{LAB}/steps/both/hint?path={trail}")
    assert hint.status_code == 200
    assert hint.get_json()["hint"] == f"DICA-{trail}"


@pytest.mark.parametrize("kind", ["content", "hint"])
@pytest.mark.parametrize("query", ["", "?path=", "?path=powershell"])
def test_missing_or_invalid_path_returns_invalid_path(env, kind, query):
    resp = env["client"].get(f"/api/labs/{LAB}/steps/both/{kind}{query}")
    assert resp.status_code == 400
    assert resp.get_json()["code"] == "INVALID_PATH"


@pytest.mark.parametrize("kind", ["content", "hint"])
def test_unavailable_path_returns_conflict_with_reason(env, kind):
    resp = env["client"].get(f"/api/labs/{LAB}/steps/console-only/{kind}?path=cli")
    body = resp.get_json()
    assert resp.status_code == 409
    assert body["code"] == "PATH_UNAVAILABLE"
    assert "sem suporte na CLI" in body["message"]


# ----------------------------------------------------------------------
# PUT /api/progress
# ----------------------------------------------------------------------


@pytest.mark.parametrize("trail", ["console", "cli"])
def test_put_progress_persists_valid_path(env, trail):
    c = env["client"]
    resp = c.put("/api/progress", json={"preferences": {"path": trail}})
    assert resp.status_code == 200
    assert resp.get_json()["preferences"]["path"] == trail
    assert c.get("/api/progress").get_json()["preferences"]["path"] == trail
    saved = json.loads(env["file"].read_text(encoding="utf-8"))
    assert saved["preferences"]["path"] == trail


def test_put_progress_invalid_path_returns_invalid_path(env):
    resp = env["client"].put("/api/progress", json={"preferences": {"path": "bash"}})
    assert resp.status_code == 400
    assert resp.get_json()["code"] == "INVALID_PATH"


def test_progress_without_preferences_defaults_to_console(env):
    env["file"].parent.mkdir(parents=True, exist_ok=True)
    env["file"].write_text(
        json.dumps({"schema_version": "1.0", "last_updated": "x", "labs": {}}),
        encoding="utf-8",
    )
    data = env["client"].get("/api/progress").get_json()
    assert data["preferences"] == {"path": "console"}
    assert env["store"].get_preferred_path() == "console"


# ----------------------------------------------------------------------
# POST /api/validate
# ----------------------------------------------------------------------


def test_validate_discards_path_and_result_is_same_for_both_trails(env):
    c = env["client"]
    results = []
    for trail in ("console", "cli"):
        resp = c.post(
            f"/api/validate/{LAB}/both",
            json={"path": trail, "context": {"path": trail, "extra": 1}},
        )
        assert resp.status_code == 200
        body = resp.get_json()
        body.pop("attempt_count")  # varia entre chamadas por contagem de tentativas
        results.append(body)
    assert results[0] == results[1]
    assert len(env["contexts"]) == 2
    for ctx in env["contexts"]:
        assert "path" not in ctx
        assert ctx["extra"] == 1


# ----------------------------------------------------------------------
# Efeitos colaterais e teardown
# ----------------------------------------------------------------------


def test_content_hint_and_put_do_not_change_step_progress(env):
    c = env["client"]
    c.post(f"/api/validate/{LAB}/both", json={})
    before = env["store"].get_lab_progress(LAB)["steps"]

    c.get(f"/api/labs/{LAB}/steps/both/content?path=cli")
    c.get(f"/api/labs/{LAB}/steps/both/hint?path=console")
    c.put("/api/progress", json={"preferences": {"path": "cli"}})

    after = env["store"].get_lab_progress(LAB)["steps"]
    assert after == before
    assert after["both"]["attempts"] == 1


@pytest.mark.parametrize("body", [None, {}, {"confirm": False}, {"confirm": "true"}])
def test_teardown_without_confirm_returns_400(env, body):
    resp = env["client"].post(f"/api/teardown/{LAB}", json=body)
    assert resp.status_code == 400
    assert resp.get_json()["code"] == "INVALID_PAYLOAD"
