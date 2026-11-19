"""Verificação de conhecimento: formato, correção, rotas e progresso (task 15N.4).

**Property 23: O gabarito nunca chega ao browser antes da resposta**
**Property 24: A nota é calculada corretamente para escolha única e múltipla**
**Validates: Requirements 17.1, 17.2, 17.3, 17.4, 17.5, 17.6**
"""

import copy
import json
from fractions import Fraction

import pytest
from hypothesis import given, settings, strategies as st

from app.errors import InvalidAnswerError
from app.lab_catalog import LabCatalog
from app.models import LabMetadata, StepMetadata
from app.progress_store import ProgressStore
from app.quiz import QuizFormatError, grade, parse_quiz, public_questions
from app.server import create_app
from tests.fixtures import LABS_FIXTURE_DIR, THEORY_LAB_ID
from tests.fixtures.http_client import workshop_client

SKILLS = ["1.1.1", "1.1.2"]


def option(oid):
    return {"id": oid, "text": f"Texto {oid}", "explanation": f"Explicação {oid}"}


def single(qid="q1", correct="a", **extra):
    q = {
        "id": qid, "type": "single", "domain": "D1", "skills": ["1.1.1"],
        "prompt": "Pergunta?", "options": [option(k) for k in "abcd"], "correct": [correct],
    }
    q.update(extra)
    return q


def multiple(qid="m1", n=5, correct=("a", "b"), **extra):
    q = {
        "id": qid, "type": "multiple", "domain": "D2", "skills": ["1.1.2"],
        "prompt": "Marque duas.", "options": [option(k) for k in "abcdefgh"[:n]],
        "correct": list(correct),
    }
    q.update(extra)
    return q


def parse(questions, pass_score=0.7):
    return parse_quiz({"questions": questions}, "lab-a", "s1", pass_score, SKILLS)


# ----------------------------------------------------------------------
# Formato (17.1)
# ----------------------------------------------------------------------


def test_valid_quiz_parses():
    quiz = parse([single(), multiple()])
    assert [q.question_id for q in quiz.questions] == ["q1", "m1"]
    assert quiz.questions[1].select == 2


@pytest.mark.parametrize(
    "question",
    [
        single(options=[option(k) for k in "abc"]),
        single(options=[option(k) for k in "abcde"]),
        single(correct=None) | {"correct": []},
        single() | {"correct": ["a", "b"]},
        multiple(n=4),
        multiple(correct=("a",)),
        multiple(correct=tuple("abcde")),
        single(correct="z"),
        single() | {"correct": ["a", "a"]},
        single() | {"type": "true_false"},
        single() | {"domain": "D5"},
        single() | {"skills": []},
        single() | {"skills": ["4.1.1"]},
        single() | {"skills": ["1.1.1", "1.1.1"]},
        single() | {"prompt": "  "},
        single() | {"id": "../q"},
        single() | {"extra": 1},
        single() | {"options": [option("a"), option("a"), option("b"), option("c")]},
        single() | {"options": [option(k) for k in "abc"] + [{"id": "d", "text": "", "explanation": "x"}]},
        single() | {"options": [option(k) for k in "abc"] + [{"id": "d", "text": "x"}]},
    ],
)
def test_invalid_question_rejected(question):
    with pytest.raises(QuizFormatError):
        parse([question])


@pytest.mark.parametrize("data", [[], {}, {"questions": []}, {"questions": [single()], "x": 1}])
def test_invalid_root_rejected(data):
    with pytest.raises(QuizFormatError):
        parse_quiz(data, "lab-a", "s1", 0.7, SKILLS)


def test_duplicate_question_ids_rejected_within_and_across_quizzes():
    with pytest.raises(QuizFormatError):
        parse([single("q1"), single("q1")])
    taken = set()
    parse_quiz({"questions": [single("q1")]}, "lab-a", "s1", 0.7, SKILLS, taken)
    with pytest.raises(QuizFormatError):
        parse_quiz({"questions": [single("q1")]}, "lab-a", "s2", 0.7, SKILLS, taken)


# ----------------------------------------------------------------------
# Correção (17.3, 17.4)
# ----------------------------------------------------------------------


def test_multiple_requires_exact_set():
    quiz = parse([multiple(correct=("a", "c"))])
    assert grade(quiz, {"m1": ["a", "c"]})["right"] == 1
    assert grade(quiz, {"m1": ["c", "a"]})["right"] == 1
    for wrong in (["a"], ["a", "b"], ["a", "c", "d"], []):
        assert grade(quiz, {"m1": wrong})["right"] == 0


def test_unanswered_counts_as_wrong():
    result = grade(parse([single("q1"), single("q2")]), {"q1": ["a"]})
    assert (result["right"], result["total"], result["score"]) == (1, 2, 0.5)
    assert result["results"][1]["selected"] == []


@pytest.mark.parametrize(
    "answers",
    [None, [], "a", {"q9": ["a"]}, {"q1": "a"}, {"q1": ["z"]}, {"q1": ["a", "a"]}, {"q1": [1]}],
)
def test_invalid_answers_rejected(answers):
    with pytest.raises(InvalidAnswerError):
        grade(parse([single()]), answers)


def test_pass_score_uses_exact_arithmetic():
    questions = [single(f"q{i}") for i in range(10)]
    answers = {f"q{i}": ["a"] for i in range(7)}
    assert grade(parse(questions, 0.7), answers)["passed"] is True
    answers.pop("q6")
    assert grade(parse(questions, 0.7), answers)["passed"] is False


# ----------------------------------------------------------------------
# Property 23 e 24 com quizzes gerados
# ----------------------------------------------------------------------

LETTERS = "abcdefgh"


@st.composite
def quizzes(draw):
    count = draw(st.integers(1, 8))
    questions = []
    for i in range(count):
        if draw(st.booleans()):
            correct = draw(st.sampled_from("abcd"))
            questions.append(single(f"q{i}", correct))
        else:
            n = draw(st.integers(5, 8))
            k = draw(st.integers(2, n - 1))
            correct = draw(st.lists(st.sampled_from(LETTERS[:n]), min_size=k, max_size=k, unique=True))
            questions.append(multiple(f"q{i}", n, correct))
    pass_score = draw(st.sampled_from([0.5, 0.6, 0.7, 0.75, 0.8, 1.0]))
    return parse(questions, pass_score), questions


@st.composite
def quiz_and_answers(draw):
    quiz, raw = draw(quizzes())
    answers = {}
    for q in raw:
        if draw(st.integers(0, 4)) == 0:
            continue  # sem resposta
        ids = [o["id"] for o in q["options"]]
        if draw(st.booleans()):
            answers[q["id"]] = list(q["correct"])
        else:
            answers[q["id"]] = draw(st.lists(st.sampled_from(ids), unique=True, max_size=len(ids)))
    return quiz, raw, answers


@settings(max_examples=200, deadline=None)
@given(quizzes())
def test_property_23_public_questions_never_leak_answers(generated):
    quiz, raw = generated
    public = public_questions(quiz)
    text = json.dumps(public)
    assert "correct" not in text and "explanation" not in text.lower()
    for q in public:
        assert set(q) == {"id", "type", "prompt", "options", "select"}
        for o in q["options"]:
            assert set(o) == {"id", "text"}
    for q, original in zip(public, raw):
        # O único dado ligado ao gabarito é quantas marcar, como no exame.
        assert q["select"] == len(original["correct"])
        assert [o["id"] for o in q["options"]] == [o["id"] for o in original["options"]]


@settings(max_examples=300, deadline=None)
@given(quiz_and_answers())
def test_property_24_score_is_exact_set_match(data):
    quiz, raw, answers = data
    result = grade(quiz, answers)
    expected_right = sum(
        1 for q in raw if set(answers.get(q["id"], [])) == set(q["correct"])
    )
    assert result["right"] == expected_right
    assert result["score"] == float(Fraction(expected_right, len(raw)))
    assert result["passed"] == (Fraction(expected_right, len(raw)) >= Fraction(str(quiz.pass_score)))
    for r, q in zip(result["results"], raw):
        assert r["right"] == (set(answers.get(q["id"], [])) == set(q["correct"]))


@settings(max_examples=100, deadline=None)
@given(st.lists(st.tuples(st.floats(0, 1), st.booleans()), min_size=1, max_size=12))
def test_property_24_passed_never_regresses(attempts):
    import tempfile
    from pathlib import Path

    lab = LabMetadata(
        lab_id="lab-q", title="t", description="d", difficulty="iniciante",
        estimated_duration_minutes=1, estimated_cost_usd=None, cost_disclaimer="",
        dea_domains=["D1"], dea_tasks=["1.1"], services=["Amazon S3"], prerequisites={},
        steps=[StepMetadata("q", "Quiz", "quiz", pass_score=0.7)],
    )
    with tempfile.TemporaryDirectory() as tmp:
        store = ProgressStore(str(Path(tmp) / "p.json"))
        ever_passed = False
        for n, (score, passed) in enumerate(attempts, start=1):
            saved = store.record_quiz_attempt("lab-q", "q", score, passed, lab)
            ever_passed = ever_passed or passed
            assert saved["step_status"] == ("passed" if ever_passed else "failed")
            assert saved["attempt_count"] == n
            assert saved["last_score"] == score
            assert saved["best_score"] == max(s for s, _ in attempts[:n])
            assert saved["lab_status"] == ("completed" if ever_passed else "in_progress")


# ----------------------------------------------------------------------
# Catálogo e rotas (17.2, 17.3, 17.6)
# ----------------------------------------------------------------------


@pytest.fixture
def env(tmp_path):
    def no_aws():
        raise AssertionError("o quiz não pode chamar a AWS")

    store = ProgressStore(str(tmp_path / "progress.json"))
    app = create_app(
        {
            "labs_dir": str(LABS_FIXTURE_DIR),
            "progress_store": store,
            "session_factory": no_aws,
            "static_folder": str(tmp_path / "static"),
            # Sessão expirada: o quiz não depende dela.
            "session_env": {"WORKSHOP_CREDENTIALS_EXPIRATION": "2000-01-01T00:00:00Z"},
        }
    )
    return {"client": workshop_client(app), "store": store}


URL = f"/api/labs/{THEORY_LAB_ID}/steps/step-02/quiz"


def test_get_quiz_has_no_answer_key(env):
    resp = env["client"].get(URL)
    assert resp.status_code == 200
    body = resp.get_json()
    raw = json.loads((LABS_FIXTURE_DIR / THEORY_LAB_ID / "steps/step-02/quiz.json").read_text())
    text = resp.get_data(as_text=True)
    assert '"correct"' not in text and "explanation" not in text
    for q in raw["questions"]:
        for o in q["options"]:
            assert o["explanation"] not in text
    assert body["pass_score"] == 0.7 and body["attempts"] == 0 and body["status"] == "not_visited"
    assert body["questions"][0]["select"] == 1


def test_post_grades_records_and_completes_module(env):
    c = env["client"]
    wrong = c.post(URL, json={"answers": {"q1": ["a"]}}).get_json()
    assert wrong["score"] == 0 and wrong["passed"] is False
    assert wrong["step_status"] == "failed" and wrong["attempts"] == 1
    assert wrong["results"][0]["correct"] == ["b"]
    assert all(o["explanation"] for o in wrong["results"][0]["options"])
    right = c.post(URL, json={"answers": {"q1": ["b"]}}).get_json()
    assert right["passed"] is True and right["step_status"] == "passed"
    assert right["best_score"] == 1.0 and right["attempts"] == 2
    assert right["lab_status"] == "completed"
    again = c.post(URL, json={"answers": {}}).get_json()
    assert again["passed"] is False and again["step_status"] == "passed"  # não regride
    assert again["last_score"] == 0 and again["best_score"] == 1.0
    detail = c.get(f"/api/labs/{THEORY_LAB_ID}").get_json()
    quiz_step = next(s for s in detail["steps"] if s["type"] == "quiz")
    assert quiz_step["best_score"] == 1.0 and quiz_step["attempts"] == 3


@pytest.mark.parametrize("body", [{"answers": {"q1": ["z"]}}, {"answers": {"q9": ["a"]}}, {"answers": "b"}, {}])
def test_post_invalid_answer_returns_400_and_does_not_count(env, body):
    resp = env["client"].post(URL, json=body)
    assert resp.status_code == 400
    assert resp.get_json()["code"] == "INVALID_ANSWER"
    assert env["store"].get_lab_progress(THEORY_LAB_ID)["steps"] == {}


@pytest.mark.parametrize("url", [
    "/api/labs/lab-example/steps/step-03/quiz",
    f"/api/labs/{THEORY_LAB_ID}/steps/nao-existe/quiz",
    "/api/labs/nao-existe/steps/step-02/quiz",
])
def test_quiz_routes_on_non_quiz_steps_return_404(env, url):
    assert env["client"].get(url).status_code == 404
    assert env["client"].post(url, json={"answers": {}}).status_code == 404


def test_post_requires_request_guards(env):
    resp = env["client"].post(URL, json={"answers": {}}, headers={"X-Workshop-Request": ""})
    assert resp.status_code == 403


def test_catalog_rejects_module_with_invalid_quiz(tmp_path):
    import shutil

    labs = tmp_path / "labs"
    shutil.copytree(LABS_FIXTURE_DIR / THEORY_LAB_ID, labs / THEORY_LAB_ID)
    file = labs / THEORY_LAB_ID / "steps/step-02/quiz.json"
    data = json.loads(file.read_text())
    bad = copy.deepcopy(data)
    bad["questions"][0]["correct"] = ["b", "c"]
    file.write_text(json.dumps(bad))
    from app.lab_catalog import InvalidLabMetadataError

    with pytest.raises(InvalidLabMetadataError, match="quiz.json"):
        LabCatalog(str(labs))


def test_get_all_quizzes_lists_fixture_quizzes():
    ids = [(q.lab_id, q.step_id) for q in LabCatalog(str(LABS_FIXTURE_DIR)).get_all_quizzes()]
    assert ids == [("lab-example", "step-08"), (THEORY_LAB_ID, "step-02")]
