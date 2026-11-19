"""Simulado final: sorteio, correção, rotas e histórico (task 15P.3).

**Property 25: O Simulado respeita os pesos dos domínios e não repete questões**
**Property 23** (parte do Simulado): `POST /api/mock-exam` não entrega gabarito.
**Validates: Requirements 7.4, 18.1, 18.2, 18.3, 18.5**
"""

import json
import random

import pytest
from hypothesis import given, settings, strategies as st

from app.mock_exam import (
    DOMAIN_ORDER,
    PoolQuestion,
    grade_attempt,
    quotas_for,
    select_questions,
    target_quotas,
)
from app.progress_store import MOCK_EXAM_MAX_ATTEMPTS, ProgressStore
from app.quiz import Option, Question
from app.server import create_app
from tests.fixtures import LABS_FIXTURE_DIR
from tests.fixtures.http_client import workshop_client


def make_question(qid, domain, correct=("a",)):
    options = tuple(Option(k, f"Texto {k}", f"Explicação {k}") for k in "abcd")
    return Question(qid, "single", domain, ("1.1.1",), f"Pergunta {qid}?", options, frozenset(correct))


def make_pool(counts):
    pool = {}
    for domain, n in counts.items():
        for i in range(n):
            gid = f"lab-{domain.lower()}/q{i}"
            pool[gid] = PoolQuestion(gid, f"lab-{domain.lower()}", make_question(f"q{i}", domain))
    return pool


# ----------------------------------------------------------------------
# Regra de cotas
# ----------------------------------------------------------------------


def test_default_65_follows_exam_weights():
    assert target_quotas(65) == {"D1": 22, "D2": 17, "D3": 14, "D4": 12}
    assert target_quotas(100) == {"D1": 34, "D2": 26, "D3": 22, "D4": 18}


@pytest.mark.parametrize("n,expected", [(1, (1, 0, 0, 0)), (3, (1, 1, 1, 0)), (4, (1, 1, 1, 1))])
def test_rounding_edges(n, expected):
    assert tuple(target_quotas(n)[d] for d in DOMAIN_ORDER) == expected


def test_shortage_is_filled_in_weight_order_and_reported():
    quotas, adjusted = quotas_for(65, {"D1": 50, "D2": 50, "D3": 5, "D4": 50})
    assert adjusted is True
    assert quotas == {"D1": 31, "D2": 17, "D3": 5, "D4": 12}


@settings(max_examples=300, deadline=None)
@given(n=st.integers(1, 250))
def test_quotas_sum_to_n_and_never_negative(n):
    quotas = target_quotas(n)
    assert sum(quotas.values()) == n
    assert all(v >= 0 for v in quotas.values())
    for d, w in zip(DOMAIN_ORDER, (0.34, 0.26, 0.22, 0.18)):
        assert abs(quotas[d] - n * w) < 2


@settings(max_examples=300, deadline=None)
@given(
    counts=st.fixed_dictionaries({d: st.integers(0, 40) for d in DOMAIN_ORDER}),
    n=st.integers(1, 200),
    seed=st.integers(0, 2**32 - 1),
)
def test_property_25_weights_and_no_repetition(counts, n, seed):
    pool = make_pool(counts)
    total = sum(counts.values())
    if total == 0:
        return
    selection = select_questions(pool, n, random.Random(seed))
    ids = selection["question_ids"]
    assert len(ids) == len(set(ids)) == min(n, total)
    assert all(gid in pool for gid in ids)
    actual = {d: sum(1 for gid in ids if pool[gid].domain == d) for d in DOMAIN_ORDER}
    assert actual == selection["by_domain"]
    expected = target_quotas(min(n, total))
    if all(counts[d] >= expected[d] for d in DOMAIN_ORDER):
        assert actual == expected
        assert sum(expected.values()) == min(n, total)


# ----------------------------------------------------------------------
# Correção
# ----------------------------------------------------------------------


def test_grade_by_domain_and_ignores_removed_questions():
    pool = make_pool({"D1": 2, "D2": 1, "D3": 0, "D4": 1})
    ids = sorted(pool) + ["lab-x/removida"]
    answers = {"lab-d1/q0": ["a"], "lab-d1/q1": ["b"], "lab-d4/q0": ["a"]}
    result = grade_attempt(pool, ids, answers)
    assert (result["right"], result["total"], result["score"]) == (2, 4, 0.5)
    assert result["by_domain"]["D1"] == {"right": 1, "total": 2, "score": 0.5}
    assert result["by_domain"]["D2"] == {"right": 0, "total": 1, "score": 0.0}
    assert result["by_domain"]["D3"] == {"right": 0, "total": 0, "score": None}
    assert result["by_domain"]["D4"]["score"] == 1.0


# ----------------------------------------------------------------------
# Rotas e Progress Store
# ----------------------------------------------------------------------


@pytest.fixture
def env(tmp_path):
    def no_aws():
        raise AssertionError("o Simulado não pode chamar a AWS")

    store = ProgressStore(str(tmp_path / "progress.json"))
    app = create_app(
        {
            "labs_dir": str(LABS_FIXTURE_DIR),
            "progress_store": store,
            "session_factory": no_aws,
            "static_folder": str(tmp_path / "static"),
            "session_env": {"WORKSHOP_CREDENTIALS_EXPIRATION": "2000-01-01T00:00:00Z"},
        }
    )
    return {"client": workshop_client(app), "store": store}


def raw_questions():
    result = {}
    for lab, step in (("lab-example", "step-08"), ("lab-theory", "step-02")):
        data = json.loads((LABS_FIXTURE_DIR / lab / "steps" / step / "quiz.json").read_text())
        for q in data["questions"]:
            result[f"{lab}/{q['id']}"] = q
    return result


def test_info_lists_pool_and_defaults(env):
    body = env["client"].get("/api/mock-exam").get_json()
    assert body["available"] == 2
    assert body["available_by_domain"] == {"D1": 1, "D2": 1, "D3": 0, "D4": 0}
    assert (body["default_count"], body["duration_minutes"]) == (65, 130)
    assert body["attempts"] == []


def test_start_has_no_answer_key_and_reports_adjustment(env):
    resp = env["client"].post("/api/mock-exam", json={})
    body = resp.get_json()
    assert resp.status_code == 200
    text = resp.get_data(as_text=True)
    assert '"correct"' not in text and "explanation" not in text and '"domain"' not in text
    for q in raw_questions().values():
        for o in q["options"]:
            assert o["explanation"] not in text
    assert {q["id"] for q in body["questions"]} == set(raw_questions())
    assert body["adjusted"] is True and body["message"]
    assert len(body["attempt_id"]) == 32


def test_submit_grades_by_domain_records_history_and_cannot_repeat(env):
    c = env["client"]
    attempt = c.post("/api/mock-exam", json={"count": 2}).get_json()
    raw = raw_questions()
    answers = {gid: raw[gid]["correct"] for gid in raw if gid.startswith("lab-theory")}
    resp = c.post(f"/api/mock-exam/{attempt['attempt_id']}/submit", json={"answers": answers})
    body = resp.get_json()
    assert resp.status_code == 200
    assert (body["right"], body["total"], body["score"]) == (1, 2, 0.5)
    assert body["by_domain"]["D1"]["score"] == 1.0 and body["by_domain"]["D2"]["score"] == 0.0
    assert all(o["explanation"] for r in body["results"] for o in r["options"])
    history = c.get("/api/mock-exam").get_json()["attempts"]
    assert history[0]["attempt_id"] == attempt["attempt_id"] and history[0]["finished_at"]
    assert "question_ids" not in history[0]
    again = c.post(f"/api/mock-exam/{attempt['attempt_id']}/submit", json={"answers": {}})
    assert again.status_code == 409 and again.get_json()["code"] == "MOCK_EXAM_ALREADY_SUBMITTED"


@pytest.mark.parametrize("attempt_id", ["0" * 32, "nao-existe", "../x"])
def test_submit_unknown_attempt_returns_404(env, attempt_id):
    resp = env["client"].post(f"/api/mock-exam/{attempt_id}/submit", json={"answers": {}})
    assert resp.status_code == 404


@pytest.mark.parametrize("count", [0, -1, 201, "65", True, 2.5])
def test_start_invalid_count_returns_400(env, count):
    resp = env["client"].post("/api/mock-exam", json={"count": count})
    assert resp.status_code == 400 and resp.get_json()["code"] == "INVALID_PAYLOAD"


def test_submit_invalid_answer_returns_400_and_keeps_attempt_open(env):
    c = env["client"]
    attempt = c.post("/api/mock-exam", json={}).get_json()
    gid = attempt["questions"][0]["id"]
    resp = c.post(f"/api/mock-exam/{attempt['attempt_id']}/submit", json={"answers": {gid: ["zz"]}})
    assert resp.status_code == 400 and resp.get_json()["code"] == "INVALID_ANSWER"
    ok = c.post(f"/api/mock-exam/{attempt['attempt_id']}/submit", json={"answers": {}})
    assert ok.status_code == 200


def test_empty_catalog_returns_unavailable(tmp_path):
    app = create_app(
        {
            "labs_dir": str(tmp_path / "vazio"),
            "progress_file": str(tmp_path / "p.json"),
            "static_folder": str(tmp_path / "static"),
        }
    )
    resp = workshop_client(app).post("/api/mock-exam", json={})
    assert resp.status_code == 409 and resp.get_json()["code"] == "MOCK_EXAM_UNAVAILABLE"


def test_store_keeps_only_last_20_attempts(tmp_path):
    store = ProgressStore(str(tmp_path / "p.json"))
    for i in range(MOCK_EXAM_MAX_ATTEMPTS + 5):
        store.create_mock_attempt(f"{i:032x}", ["lab-a/q1"])
    attempts = store.get_mock_attempts()
    assert len(attempts) == 20
    assert attempts[0]["attempt_id"] == f"{5:032x}"
    assert store.get_progress()["labs"] == {}


def test_mock_exam_page_serves_spa(env, tmp_path):
    resp = env["client"].get("/mock-exam")
    assert resp.status_code == 404  # sem index.html no static de teste
    assert resp.get_json()["message"].startswith("Frontend")
