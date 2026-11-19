"""Verificação de conhecimento: formato do `quiz.json` e correção (Requirement 17).

Funções puras, sem Flask e sem AWS. O `LabCatalog` usa `parse_quiz` na carga;
as rotas usam `public_questions` (sem gabarito) e `grade` (correção).

Regras do formato (design.md, seção 5a):
- `single`: exatamente 4 alternativas e 1 correta.
- `multiple`: 5 ou mais alternativas e 2 ou mais corretas, sem todas corretas.
- ids de questão únicos no módulo e ids de alternativa únicos na questão.
- `domain` entre D1 e D4; `skills` não vazio e contido nos `skills` do módulo.
"""

import re
from dataclasses import dataclass
from fractions import Fraction
from typing import Iterable, Optional

from app.errors import InvalidAnswerError

DOMAINS = ("D1", "D2", "D3", "D4")
QUESTION_TYPES = ("single", "multiple")
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,31}$")
_QUESTION_KEYS = {"id", "type", "domain", "skills", "prompt", "options", "correct"}
_OPTION_KEYS = {"id", "text", "explanation"}


class QuizFormatError(ValueError):
    """`quiz.json` fora do formato; a mensagem diz qual questão e por quê."""


@dataclass(frozen=True)
class Option:
    option_id: str
    text: str
    explanation: str


@dataclass(frozen=True)
class Question:
    question_id: str
    type: str
    domain: str
    skills: tuple[str, ...]
    prompt: str
    options: tuple[Option, ...]
    correct: frozenset[str]

    @property
    def select(self) -> int:
        """Quantas alternativas marcar (informado no enunciado, como no exame)."""
        return len(self.correct)


@dataclass(frozen=True)
class Quiz:
    lab_id: str
    step_id: str
    pass_score: float
    questions: tuple[Question, ...]


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _parse_question(raw: object, module_skills: frozenset[str]) -> Question:
    if not isinstance(raw, dict):
        raise QuizFormatError("cada questão deve ser um objeto")
    qid = raw.get("id")
    if not isinstance(qid, str) or not _ID_RE.match(qid):
        raise QuizFormatError(f"id de questão inválido: {qid!r}")
    where = f"questão '{qid}'"
    extra = set(raw) - _QUESTION_KEYS
    if extra:
        raise QuizFormatError(f"{where}: campos desconhecidos {sorted(extra)}")
    qtype = raw.get("type")
    if qtype not in QUESTION_TYPES:
        raise QuizFormatError(f"{where}: type deve ser 'single' ou 'multiple'")
    if raw.get("domain") not in DOMAINS:
        raise QuizFormatError(f"{where}: domain deve ser D1, D2, D3 ou D4")
    skills = raw.get("skills")
    if not isinstance(skills, list) or not skills or any(not isinstance(s, str) for s in skills):
        raise QuizFormatError(f"{where}: skills deve ser uma lista não vazia")
    if len(set(skills)) != len(skills):
        raise QuizFormatError(f"{where}: skills com id repetido")
    outside = [s for s in skills if s not in module_skills]
    if outside:
        raise QuizFormatError(f"{where}: skills fora dos skills do módulo: {outside}")
    if not _text(raw.get("prompt")):
        raise QuizFormatError(f"{where}: prompt vazio")

    raw_options = raw.get("options")
    if not isinstance(raw_options, list):
        raise QuizFormatError(f"{where}: options deve ser uma lista")
    options = []
    seen: set[str] = set()
    for opt in raw_options:
        if not isinstance(opt, dict) or set(opt) != _OPTION_KEYS:
            raise QuizFormatError(f"{where}: cada alternativa tem só id, text e explanation")
        oid = opt["id"]
        if not isinstance(oid, str) or not _ID_RE.match(oid) or oid in seen:
            raise QuizFormatError(f"{where}: id de alternativa inválido ou repetido: {oid!r}")
        if not _text(opt["text"]) or not _text(opt["explanation"]):
            raise QuizFormatError(f"{where}: alternativa '{oid}' com text ou explanation vazio")
        seen.add(oid)
        options.append(Option(oid, opt["text"], opt["explanation"]))

    correct = raw.get("correct")
    if (
        not isinstance(correct, list)
        or any(not isinstance(c, str) for c in correct)
        or len(set(correct)) != len(correct)
    ):
        raise QuizFormatError(f"{where}: correct deve ser uma lista de ids sem repetição")
    unknown = [c for c in correct if c not in seen]
    if unknown:
        raise QuizFormatError(f"{where}: correct cita alternativas inexistentes: {unknown}")
    if qtype == "single" and (len(options) != 4 or len(correct) != 1):
        raise QuizFormatError(f"{where}: escolha única exige 4 alternativas e 1 correta")
    if qtype == "multiple" and (
        len(options) < 5 or len(correct) < 2 or len(correct) >= len(options)
    ):
        raise QuizFormatError(
            f"{where}: múltipla escolha exige 5 ou mais alternativas e 2 ou mais "
            "corretas, sem todas corretas"
        )
    return Question(
        qid, qtype, raw["domain"], tuple(skills), raw["prompt"], tuple(options), frozenset(correct)
    )


def parse_quiz(
    data: object,
    lab_id: str,
    step_id: str,
    pass_score: float,
    module_skills: Iterable[str],
    taken_ids: Optional[set[str]] = None,
) -> Quiz:
    """Valida o conteúdo de um `quiz.json` já lido como JSON.

    `taken_ids` acumula os ids de questão do módulo, para recusar repetição
    entre steps `quiz` do mesmo módulo (ids globais `<lab_id>/<qid>`).

    Raises:
        QuizFormatError: com o motivo.
    """
    if not isinstance(data, dict) or set(data) != {"questions"}:
        raise QuizFormatError("o objeto raiz deve ter só 'questions'")
    raw_questions = data["questions"]
    if not isinstance(raw_questions, list) or not raw_questions:
        raise QuizFormatError("'questions' deve ser uma lista não vazia")
    skills = frozenset(module_skills)
    taken = taken_ids if taken_ids is not None else set()
    questions = []
    for raw in raw_questions:
        question = _parse_question(raw, skills)
        if question.question_id in taken:
            raise QuizFormatError(f"id de questão repetido no módulo: '{question.question_id}'")
        taken.add(question.question_id)
        questions.append(question)
    return Quiz(lab_id, step_id, pass_score, tuple(questions))


def public_question(question: Question) -> dict:
    """Questão como vai ao browser antes da resposta: sem gabarito e sem explicações."""
    return {
        "id": question.question_id,
        "type": question.type,
        "prompt": question.prompt,
        "options": [{"id": o.option_id, "text": o.text} for o in question.options],
        "select": question.select,
    }


def public_questions(quiz: Quiz) -> list[dict]:
    return [public_question(q) for q in quiz.questions]


def normalize_answers(questions: Iterable[Question], answers: object) -> dict[str, frozenset[str]]:
    """Confere `{qid: [ids]}` contra as questões. Questão ausente vira resposta vazia.

    Raises:
        InvalidAnswerError: formato inválido, questão ou alternativa inexistente.
    """
    by_id = {q.question_id: q for q in questions}
    if not isinstance(answers, dict):
        raise InvalidAnswerError('Corpo inválido. Esperado: {"answers": {"<questão>": ["<alternativa>"]}}.')
    result = {qid: frozenset() for qid in by_id}
    for qid, selected in answers.items():
        question = by_id.get(qid)
        if question is None:
            raise InvalidAnswerError("Resposta para uma questão que não existe neste quiz.")
        if (
            not isinstance(selected, list)
            or any(not isinstance(s, str) for s in selected)
            or len(set(selected)) != len(selected)
        ):
            raise InvalidAnswerError("Cada resposta deve ser uma lista de alternativas sem repetição.")
        valid = {o.option_id for o in question.options}
        if any(s not in valid for s in selected):
            raise InvalidAnswerError("Resposta com alternativa que não existe na questão.")
        result[qid] = frozenset(selected)
    return result


def score_of(right: int, total: int) -> Fraction:
    return Fraction(right, total) if total else Fraction(0)


def reaches(score: Fraction, pass_score: float) -> bool:
    """`score >= pass_score` em aritmética exata (0,7 não vira 0,69999...)."""
    return score >= Fraction(str(pass_score))


def question_result(question: Question, selected: frozenset[str]) -> dict:
    """Resultado de uma questão, com gabarito e explicações (só depois da resposta)."""
    return {
        "id": question.question_id,
        "type": question.type,
        "domain": question.domain,
        "prompt": question.prompt,
        "correct": sorted(question.correct),
        "selected": sorted(selected),
        "right": selected == question.correct,
        "options": [
            {"id": o.option_id, "text": o.text, "explanation": o.explanation}
            for o in question.options
        ],
    }


def grade(quiz: Quiz, answers: object) -> dict:
    """Corrige uma tentativa. Questão certa só se o conjunto marcado é igual ao correto.

    Returns:
        `{score, passed, right, total, results}`; `score` é float entre 0 e 1.
    """
    selected = normalize_answers(quiz.questions, answers)
    results = [question_result(q, selected[q.question_id]) for q in quiz.questions]
    right = sum(1 for r in results if r["right"])
    score = score_of(right, len(results))
    return {
        "score": float(score),
        "passed": reaches(score, quiz.pass_score),
        "right": right,
        "total": len(results),
        "results": results,
    }
