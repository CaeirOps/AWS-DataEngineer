"""Simulado final (`mock-exam`): sorteio por domínio e correção (Requirement 18).

Funções puras, sem Flask e sem AWS. As questões vêm das Verificações de
conhecimento do catálogo, com id global `<lab_id>/<qid>`.

Regra de cotas (design.md, seção 5a), com `n = min(N, total)`:
1. `cota[d] = floor(n * peso[d] + 0,5)` com os pesos D1 0,34, D2 0,26,
   D3 0,22 e D4 0,18.
2. Se `soma(cotas) < n`, a diferença vai para o domínio de maior peso (D1).
   Se `soma(cotas) > n`, o excesso sai do domínio de menor peso com cota
   maior que zero (D4, depois D3...), para nenhum domínio grande ficar vazio.
3. Domínio sem questões suficientes fica com o que tem; a falta é completada
   pelos outros domínios na ordem dos pesos, e o ajuste é informado.
"""

import math
import random
from dataclasses import dataclass
from fractions import Fraction
from typing import Iterable, Optional

from app.quiz import Question, Quiz, normalize_answers, question_result, score_of

DOMAIN_WEIGHTS = (("D1", 0.34), ("D2", 0.26), ("D3", 0.22), ("D4", 0.18))
DOMAIN_ORDER = tuple(d for d, _ in DOMAIN_WEIGHTS)
DEFAULT_QUESTIONS = 65
MAX_QUESTIONS = 200
DEFAULT_DURATION_MINUTES = 130
MAX_ATTEMPTS = 20


@dataclass(frozen=True)
class PoolQuestion:
    global_id: str  # "<lab_id>/<qid>"
    lab_id: str
    question: Question

    @property
    def domain(self) -> str:
        return self.question.domain


def build_pool(quizzes: Iterable[Quiz]) -> dict[str, PoolQuestion]:
    """Banco de questões do catálogo, indexado pelo id global."""
    pool: dict[str, PoolQuestion] = {}
    for quiz in quizzes:
        for q in quiz.questions:
            gid = f"{quiz.lab_id}/{q.question_id}"
            pool[gid] = PoolQuestion(gid, quiz.lab_id, q)
    return pool


def target_quotas(n: int) -> dict[str, int]:
    """Cotas por domínio para `n` questões (passos 1 e 2 da regra)."""
    quotas = {d: math.floor(n * w + 0.5) for d, w in DOMAIN_WEIGHTS}
    diff = n - sum(quotas.values())
    if diff > 0:
        quotas[DOMAIN_ORDER[0]] += diff
    for d in reversed(DOMAIN_ORDER):
        while diff < 0 and quotas[d] > 0:
            quotas[d] -= 1
            diff += 1
    return quotas


def quotas_for(n: int, available: dict[str, int]) -> tuple[dict[str, int], bool]:
    """Cotas finais respeitando o que existe em cada domínio (passo 3).

    Returns:
        `(cotas, ajustado)`; `ajustado` indica que alguma cota mudou por falta
        de questões.
    """
    total = sum(available.get(d, 0) for d in DOMAIN_ORDER)
    n = min(n, total)
    quotas = target_quotas(n)
    adjusted = False
    missing = 0
    for d in DOMAIN_ORDER:
        have = available.get(d, 0)
        if quotas[d] > have:
            missing += quotas[d] - have
            quotas[d] = have
            adjusted = True
    for d in DOMAIN_ORDER:
        if missing == 0:
            break
        room = available.get(d, 0) - quotas[d]
        take = min(room, missing)
        quotas[d] += take
        missing -= take
    return quotas, adjusted


def select_questions(
    pool: dict[str, PoolQuestion], count: int, rng: Optional[random.Random] = None
) -> dict:
    """Sorteia uma tentativa sem repetição.

    Returns:
        `{question_ids, requested, by_domain, adjusted}`; os ids ficam em ordem
        embaralhada.
    """
    rng = rng or random.SystemRandom()
    by_domain: dict[str, list[str]] = {d: [] for d in DOMAIN_ORDER}
    for gid in sorted(pool):
        by_domain[pool[gid].domain].append(gid)
    quotas, adjusted = quotas_for(count, {d: len(v) for d, v in by_domain.items()})
    chosen: list[str] = []
    for d in DOMAIN_ORDER:
        chosen.extend(rng.sample(by_domain[d], quotas[d]))
    rng.shuffle(chosen)
    return {
        "question_ids": chosen,
        "requested": count,
        "by_domain": quotas,
        "adjusted": adjusted or len(chosen) < count,
    }


def public_attempt_questions(pool: dict[str, PoolQuestion], ids: list[str]) -> list[dict]:
    """Questões da tentativa como vão ao browser: sem gabarito, domínio nem explicação."""
    result = []
    for gid in ids:
        q = pool[gid].question
        result.append(
            {
                "id": gid,
                "type": q.type,
                "prompt": q.prompt,
                "options": [{"id": o.option_id, "text": o.text} for o in q.options],
                "select": q.select,
            }
        )
    return result


def grade_attempt(pool: dict[str, PoolQuestion], ids: list[str], answers: object) -> dict:
    """Corrige a tentativa. Questões removidas do catálogo depois do sorteio são ignoradas.

    Returns:
        `{score, right, total, by_domain: {D: {right, total, score}}, results}`.
    """
    present = [pool[gid] for gid in ids if gid in pool]
    # Reaproveita a validação do quiz com os ids globais como ids de questão.
    questions = [
        Question(p.global_id, p.question.type, p.domain, p.question.skills, p.question.prompt,
                 p.question.options, p.question.correct)
        for p in present
    ]
    selected = normalize_answers(questions, answers)
    results = []
    domains = {d: [0, 0] for d in DOMAIN_ORDER}
    for q in questions:
        r = question_result(q, selected[q.question_id])
        results.append(r)
        domains[q.domain][1] += 1
        domains[q.domain][0] += 1 if r["right"] else 0
    right = sum(1 for r in results if r["right"])
    return {
        "score": float(score_of(right, len(results))),
        "right": right,
        "total": len(results),
        "by_domain": {
            d: {"right": r, "total": t, "score": float(score_of(r, t)) if t else None}
            for d, (r, t) in domains.items()
        },
        "results": results,
    }


def score_fraction(right: int, total: int) -> Fraction:
    return score_of(right, total)
