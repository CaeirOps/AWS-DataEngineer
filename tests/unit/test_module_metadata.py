"""Testes das regras de metadata de módulo (task 15L).

Cobrem `skills`, `has_infrastructure`, `cost_notice`, `optional`/`cost_note`
e steps `quiz` no LabCatalog, a exposição na API, a resposta
`NO_INFRASTRUCTURE` e a regra de conclusão do módulo.
Valida: Requirements 4.4, 5.8, 6.8, 19.2, 19.3, 20.3.
"""

import json
from pathlib import Path

import pytest

from app.cloudformation_service import CloudFormationService
from app.errors import NoInfrastructureError, StepRequiresValidationError
from app.lab_catalog import DEFAULT_PASS_SCORE, InvalidLabMetadataError, LabCatalog
from app.progress_store import ProgressStore
from app.server import create_app
from tests.fixtures import LABS_FIXTURE_DIR, THEORY_LAB_ID
from tests.fixtures.http_client import workshop_client

PRICING_S3 = {"name": "Amazon S3", "pricing_url": "https://aws.amazon.com/s3/pricing/"}
QUIZ = {"questions": [{"id": "q1"}]}


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def task(step_id="t1", **extra):
    step = {"step_id": step_id, "title": "Tarefa", "type": "task", "paths": ["console", "cli"]}
    step.update(extra)
    return step


def step(step_id, step_type, **extra):
    data = {"step_id": step_id, "title": step_id, "type": step_type}
    data.update(extra)
    return data


def infra_steps():
    return [step("d1", "deploy"), task(), step("x1", "teardown"), step("c1", "completion")]


def module(steps=None, drop=(), **extra):
    meta = {
        "lab_id": "lab-a",
        "title": "Módulo A",
        "description": "d",
        "difficulty": "iniciante",
        "estimated_duration_minutes": 30,
        "dea_domains": ["D1"],
        "dea_tasks": ["1.1"],
        "services": ["Amazon S3"],
        "skills": ["1.1.1", "1.1.2"],
        "cost_notice": {"services": [PRICING_S3]},
        "steps": steps if steps is not None else infra_steps(),
    }
    meta.update(extra)
    for key in drop:
        meta.pop(key, None)
    return meta


def write(tmp_path, meta, stack=True, quizzes=None, quiz_body=QUIZ):
    lab_dir = tmp_path / meta["lab_id"]
    lab_dir.mkdir(parents=True, exist_ok=True)
    (lab_dir / "metadata.json").write_text(json.dumps(meta), encoding="utf-8")
    if stack:
        (lab_dir / "cloudformation").mkdir(exist_ok=True)
        (lab_dir / "cloudformation" / "stack.yaml").write_text(
            "Resources: {}\n", encoding="utf-8"
        )
    for qid in quizzes or ():
        qdir = lab_dir / "steps" / qid
        qdir.mkdir(parents=True, exist_ok=True)
        body = quiz_body if isinstance(quiz_body, str) else json.dumps(quiz_body)
        (qdir / "quiz.json").write_text(body, encoding="utf-8")
    return tmp_path


def load(tmp_path, meta, **kwargs):
    return LabCatalog(str(write(tmp_path, meta, **kwargs)))


def rejected(tmp_path, meta, match=None, **kwargs):
    with pytest.raises(InvalidLabMetadataError, match=match):
        load(tmp_path, meta, **kwargs)


# ----------------------------------------------------------------------
# skills
# ----------------------------------------------------------------------


def test_module_valid_loads_new_fields(tmp_path):
    lab = load(tmp_path, module()).get_lab("lab-a")
    assert lab.skills == ["1.1.1", "1.1.2"]
    assert lab.has_infrastructure is True
    assert lab.cost_notice == {"services": [PRICING_S3]}
    assert lab.estimated_cost_usd is None
    assert lab.cost_disclaimer == ""


@pytest.mark.parametrize(
    "value", [None, [], "1.1.1", ["1.1"], ["1.1.1.1"], ["a.b.c"], [1], ["1.1.1", "1.1.1"]]
)
def test_module_skills_invalid_rejected(tmp_path, value):
    meta = module(skills=value) if value is not None else module(drop=("skills",))
    rejected(tmp_path, meta, "skills")


def test_module_skill_absent_from_matrix_rejected(tmp_path):
    rejected(tmp_path, module(skills=["9.9.9"]), "Matriz")


def test_step_skills_must_be_subset_of_module(tmp_path):
    steps = infra_steps()
    steps[1]["skills"] = ["1.1.2"]
    assert load(tmp_path, module(steps=steps)).get_step("lab-a", "t1").skills == ["1.1.2"]
    steps[1]["skills"] = ["1.1.3"]
    rejected(tmp_path / "b", module(steps=steps), "skills")


def test_custom_coverage_file_is_used(tmp_path):
    matrix = tmp_path / "matrix.json"
    matrix.write_text(json.dumps({"skills": [{"id": "1.1.1"}]}), encoding="utf-8")
    labs = write(tmp_path / "labs", module(skills=["1.1.1"]))
    assert LabCatalog(str(labs), coverage_file=str(matrix)).get_lab("lab-a").skills == ["1.1.1"]
    with pytest.raises(InvalidLabMetadataError, match="Matriz"):
        LabCatalog(str(write(tmp_path / "labs2", module())), coverage_file=str(matrix))


def test_missing_coverage_file_fails_closed(tmp_path):
    labs = write(tmp_path / "labs", module())
    with pytest.raises(InvalidLabMetadataError, match="Matriz"):
        LabCatalog(str(labs), coverage_file=str(tmp_path / "nao-existe.json"))


def test_empty_catalog_does_not_need_matrix(tmp_path):
    assert LabCatalog(str(tmp_path), coverage_file=str(tmp_path / "x.json")).get_all_labs() == []


# ----------------------------------------------------------------------
# has_infrastructure
# ----------------------------------------------------------------------


@pytest.mark.parametrize("value", ["true", 1, None, []])
def test_has_infrastructure_must_be_boolean(tmp_path, value):
    rejected(tmp_path, module(has_infrastructure=value), "has_infrastructure")


def test_infrastructure_requires_stack_file(tmp_path):
    rejected(tmp_path, module(), "stack.yaml", stack=False)


@pytest.mark.parametrize("missing", ["deploy", "teardown"])
def test_infrastructure_requires_deploy_and_teardown(tmp_path, missing):
    steps = [s for s in infra_steps() if s["type"] != missing]
    rejected(tmp_path, module(steps=steps), missing)


def test_no_infrastructure_rejects_stack_file(tmp_path):
    meta = module(has_infrastructure=False, steps=[task()], drop=("cost_notice",))
    rejected(tmp_path, meta, "stack.yaml")


@pytest.mark.parametrize("kind", ["deploy", "teardown"])
def test_no_infrastructure_rejects_deploy_and_teardown(tmp_path, kind):
    meta = module(has_infrastructure=False, steps=[task(), step("s9", kind)], drop=("cost_notice",))
    rejected(tmp_path, meta, kind, stack=False)


def test_no_infrastructure_module_loads_without_cost_notice(tmp_path):
    meta = module(has_infrastructure=False, steps=[task()], drop=("cost_notice",))
    lab = load(tmp_path, meta, stack=False).get_lab("lab-a")
    assert lab.has_infrastructure is False
    assert lab.cost_notice == {}


# ----------------------------------------------------------------------
# cost_notice
# ----------------------------------------------------------------------


def test_cost_notice_required_with_infrastructure(tmp_path):
    rejected(tmp_path, module(drop=("cost_notice",)), "cost_notice")


@pytest.mark.parametrize(
    "notice",
    [
        "texto",
        {},
        {"services": []},
        {"services": "Amazon S3"},
        {"services": [PRICING_S3], "usd": 1.0},
        {"services": [{"name": "", "pricing_url": PRICING_S3["pricing_url"]}]},
        {"services": [{"name": "Amazon S3"}]},
        {"services": [{**PRICING_S3, "extra": 1}]},
    ],
)
def test_cost_notice_invalid_shape_rejected(tmp_path, notice):
    rejected(tmp_path, module(cost_notice=notice), "cost_notice")


@pytest.mark.parametrize(
    "url",
    [
        "http://aws.amazon.com/s3/pricing/",
        "https://aws.amazon.com.evil.example/s3/pricing/",
        "https://evil.example/https://aws.amazon.com/",
        "https://user@aws.amazon.com/s3/pricing/",
        "https://aws.amazon.com:8443/s3/pricing/",
        "https://calculator.aws/#/estimate",
        "https://aws.amazon.com",
        "https://aws.amazon.com/s3/pricing/\n",
        "https://aws.amazon.com/s3 pricing/",
        "https://aws.amazon.com/s3\\pricing/",
        "javascript:alert(1)",
        "",
        42,
    ],
)
def test_cost_notice_pricing_url_must_be_aws_https(tmp_path, url):
    notice = {"services": [{"name": "Amazon S3", "pricing_url": url}]}
    rejected(tmp_path, module(cost_notice=notice), "pricing_url")


def test_legacy_cost_fields_still_accepted(tmp_path):
    lab = load(
        tmp_path, module(estimated_cost_usd=0.5, cost_disclaimer="Aviso livre.")
    ).get_lab("lab-a")
    assert lab.estimated_cost_usd == 0.5
    assert lab.cost_disclaimer == "Aviso livre."


@pytest.mark.parametrize("field,value", [("estimated_cost_usd", "0.5"), ("cost_disclaimer", 3)])
def test_legacy_cost_fields_still_type_checked(tmp_path, field, value):
    rejected(tmp_path, module(**{field: value}), field)


# ----------------------------------------------------------------------
# optional e cost_note
# ----------------------------------------------------------------------


def test_optional_task_with_cost_note_loads(tmp_path):
    steps = infra_steps() + [task("t2", optional=True, cost_note="Cobra por hora.")]
    s = load(tmp_path, module(steps=steps)).get_step("lab-a", "t2")
    assert s.optional is True and s.cost_note == "Cobra por hora."
    assert s.required is False


@pytest.mark.parametrize("note", [None, "", "   ", 3])
def test_optional_task_requires_cost_note(tmp_path, note):
    extra = {"optional": True}
    if note is not None:
        extra["cost_note"] = note
    rejected(tmp_path, module(steps=infra_steps() + [task("t2", **extra)]), "cost_note")


@pytest.mark.parametrize("value", ["true", 1, None])
def test_optional_must_be_boolean(tmp_path, value):
    steps = infra_steps() + [task("t2", optional=value, cost_note="x")]
    rejected(tmp_path, module(steps=steps), "optional")


@pytest.mark.parametrize("kind", ["info", "deploy", "teardown", "completion"])
def test_optional_only_on_task(tmp_path, kind):
    steps = infra_steps() + [step("s9", kind, optional=True, cost_note="x")]
    rejected(tmp_path, module(steps=steps), "optional")


def test_cost_note_without_optional_rejected(tmp_path):
    steps = infra_steps() + [task("t2", cost_note="x")]
    rejected(tmp_path, module(steps=steps), "cost_note")


# ----------------------------------------------------------------------
# quiz
# ----------------------------------------------------------------------


def test_quiz_step_loads_with_default_pass_score(tmp_path):
    steps = infra_steps() + [step("q1", "quiz")]
    s = load(tmp_path, module(steps=steps), quizzes=["q1"]).get_step("lab-a", "q1")
    assert s.pass_score == DEFAULT_PASS_SCORE == 0.7
    assert s.required is True


@pytest.mark.parametrize("score", [0.5, 1, 1.0])
def test_quiz_pass_score_valid(tmp_path, score):
    steps = infra_steps() + [step("q1", "quiz", pass_score=score)]
    assert load(tmp_path, module(steps=steps), quizzes=["q1"]).get_step("lab-a", "q1").pass_score == score


@pytest.mark.parametrize("score", [0, -0.1, 1.01, "0.7", True, None])
def test_quiz_pass_score_invalid(tmp_path, score):
    steps = infra_steps() + [step("q1", "quiz", pass_score=score)]
    rejected(tmp_path, module(steps=steps), "pass_score", quizzes=["q1"])


def test_quiz_requires_quiz_file(tmp_path):
    rejected(tmp_path, module(steps=infra_steps() + [step("q1", "quiz")]), "quiz.json")


@pytest.mark.parametrize("body", ["{inválido", "[]", {"questions": []}, {"questions": "x"}, {}])
def test_quiz_file_must_be_valid(tmp_path, body):
    steps = infra_steps() + [step("q1", "quiz")]
    rejected(tmp_path, module(steps=steps), "quiz.json", quizzes=["q1"], quiz_body=body)


@pytest.mark.parametrize("field", ["paths", "optional", "cost_note"])
def test_quiz_rejects_task_fields(tmp_path, field):
    value = {"paths": ["console"], "optional": True, "cost_note": "x"}[field]
    steps = infra_steps() + [step("q1", "quiz", **{field: value})]
    rejected(tmp_path, module(steps=steps), field, quizzes=["q1"])


@pytest.mark.parametrize("kind", ["info", "task"])
def test_pass_score_only_on_quiz(tmp_path, kind):
    base = task("s9") if kind == "task" else step("s9", kind)
    base["pass_score"] = 0.7
    rejected(tmp_path, module(steps=infra_steps() + [base]), "pass_score")


# ----------------------------------------------------------------------
# Fixtures lab-example e lab-theory
# ----------------------------------------------------------------------


def test_fixture_catalog_loads_both_modules():
    catalog = LabCatalog(str(LABS_FIXTURE_DIR))
    example = catalog.get_lab("lab-example")
    theory = catalog.get_lab(THEORY_LAB_ID)
    assert example.has_infrastructure and example.cost_notice["services"]
    assert any(s.optional for s in example.steps)
    assert any(s.type == "quiz" for s in example.steps)
    assert theory.has_infrastructure is False
    assert {s.type for s in theory.steps} == {"info", "quiz", "completion"}


# ----------------------------------------------------------------------
# API
# ----------------------------------------------------------------------


@pytest.fixture
def api(tmp_path):
    calls = []

    def session_factory():
        calls.append(1)
        raise AssertionError("módulo sem infraestrutura não pode criar sessão boto3")

    store = ProgressStore(str(tmp_path / "progress.json"))
    app = create_app(
        {
            "labs_dir": str(LABS_FIXTURE_DIR),
            "progress_store": store,
            "session_factory": session_factory,
            "static_folder": str(tmp_path / "static"),
            "session_env": {"WORKSHOP_CREDENTIALS_EXPIRATION": "2999-01-01T00:00:00Z"},
        }
    )
    return {"client": workshop_client(app), "calls": calls, "store": store}


def test_api_lists_new_fields_without_usd(api):
    labs = {l["lab_id"]: l for l in api["client"].get("/api/labs").get_json()["labs"]}
    for lab in labs.values():
        assert "estimated_cost_usd" not in lab
        assert lab["skills"]
    assert labs["lab-example"]["has_infrastructure"] is True
    assert labs["lab-example"]["cost_notice"]["services"][0]["pricing_url"].startswith(
        "https://aws.amazon.com/"
    )
    assert labs[THEORY_LAB_ID]["has_infrastructure"] is False
    assert labs[THEORY_LAB_ID]["cost_notice"] == {}


def test_api_lab_detail_exposes_step_fields(api):
    body = api["client"].get("/api/labs/lab-example").get_json()
    assert "estimated_cost_usd" not in body
    assert body["skills"] and body["has_infrastructure"] is True
    steps = {s["step_id"]: s for s in body["steps"]}
    optional = [s for s in steps.values() if s.get("optional")]
    assert optional and all(s["cost_note"] for s in optional)
    quiz = [s for s in steps.values() if s["type"] == "quiz"]
    assert quiz and quiz[0]["pass_score"] == 0.7
    assert "content" not in quiz[0]  # o conteúdo do quiz vem das rotas de quiz
    for s in steps.values():
        assert isinstance(s["skills"], list)
        if s["type"] != "task":
            assert "optional" not in s and "cost_note" not in s


@pytest.mark.parametrize(
    "method,url,body",
    [
        ("post", f"/api/deploy/{THEORY_LAB_ID}", None),
        ("post", f"/api/teardown/{THEORY_LAB_ID}", {"confirm": True}),
        ("post", f"/api/teardown/{THEORY_LAB_ID}", {}),
        ("get", f"/api/stack-status/{THEORY_LAB_ID}", None),
    ],
)
def test_stack_routes_return_no_infrastructure(api, method, url, body):
    client = api["client"]
    resp = client.get(url) if method == "get" else client.post(url, json=body or {})
    assert resp.status_code == 409
    assert resp.get_json()["code"] == "NO_INFRASTRUCTURE"
    assert api["calls"] == []


def test_cloudformation_service_rejects_without_client():
    catalog = LabCatalog(str(LABS_FIXTURE_DIR))

    def factory():
        raise AssertionError("não deveria criar cliente boto3")

    service = CloudFormationService(catalog, session_factory=factory)
    for call in (service.deploy, service.teardown, service.get_status):
        with pytest.raises(NoInfrastructureError):
            call(THEORY_LAB_ID)


def test_quiz_step_cannot_be_completed_by_visit(api):
    resp = api["client"].post(f"/api/labs/{THEORY_LAB_ID}/steps/step-02/visit", json={})
    assert resp.status_code == 409
    assert resp.get_json()["code"] == "STEP_REQUIRES_VALIDATION"


def test_store_mark_visited_rejects_quiz(tmp_path):
    lab = LabCatalog(str(LABS_FIXTURE_DIR)).get_lab(THEORY_LAB_ID)
    with pytest.raises(StepRequiresValidationError):
        ProgressStore(str(tmp_path / "p.json")).mark_visited(THEORY_LAB_ID, "step-02", lab)


# ----------------------------------------------------------------------
# Conclusão
# ----------------------------------------------------------------------


def test_theory_module_completes_when_quiz_passes(tmp_path):
    lab = LabCatalog(str(LABS_FIXTURE_DIR)).get_lab(THEORY_LAB_ID)
    store = ProgressStore(str(tmp_path / "p.json"))
    store.mark_visited(THEORY_LAB_ID, "step-01", lab)
    assert store.get_lab_progress(THEORY_LAB_ID)["status"] == "in_progress"
    store.update_step(THEORY_LAB_ID, "step-02", "passed", lab_metadata=lab)
    assert store.get_lab_progress(THEORY_LAB_ID)["status"] == "completed"


def test_example_module_completes_without_optional_task(tmp_path):
    lab = LabCatalog(str(LABS_FIXTURE_DIR)).get_lab("lab-example")
    store = ProgressStore(str(tmp_path / "p.json"))
    required = [s.step_id for s in lab.steps if s.required]
    for sid in required[:-1]:
        store.update_step("lab-example", sid, "passed", lab_metadata=lab)
        assert store.get_lab_progress("lab-example")["status"] == "in_progress"
    store.update_step("lab-example", required[-1], "passed", lab_metadata=lab)
    assert store.get_lab_progress("lab-example")["status"] == "completed"
