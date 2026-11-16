"""Testes de propriedade para os modelos de dados e a hierarquia de erros.

**Feature: aws-data-engineer-workshop, Property 9: Todos os steps de todos os
labs têm campos obrigatórios**
**Validates: Requirements 4.1, 7.1**

A verificação contra o catálogo real fica na Parte 3 do plano. Aqui os testes
usam as dataclasses de `app/models.py` com dados gerados.
"""

import dataclasses

from hypothesis import given, strategies as st

from app import errors
from app.errors import PathUnavailableError, WorkshopError
from app.models import LabMetadata, StepMetadata

TRILHAS = ["console", "cli"]
TIPOS = ["info", "deploy", "task", "teardown", "completion"]

texto = st.text(min_size=1, max_size=40).filter(lambda s: s.strip() != "")
ids = st.from_regex(r"[a-z][a-z0-9-]{0,19}", fullmatch=True)


@st.composite
def steps_task(draw):
    """Step `task` válido: `paths` não vazio e trilhas ausentes com motivo."""
    paths = draw(st.lists(st.sampled_from(TRILHAS), min_size=1, max_size=2, unique=True))
    ausentes = [t for t in TRILHAS if t not in paths]
    unavailable = {t: draw(texto) for t in ausentes}
    return StepMetadata(
        step_id=draw(ids),
        title=draw(texto),
        type="task",
        hint_threshold=draw(st.integers(min_value=1, max_value=10)),
        paths=paths,
        unavailable_paths=unavailable or None,
    )


@st.composite
def steps_outros(draw):
    """Step de tipo diferente de `task`: sem `paths`/`unavailable_paths`."""
    return StepMetadata(
        step_id=draw(ids),
        title=draw(texto),
        type=draw(st.sampled_from([t for t in TIPOS if t != "task"])),
        hint_threshold=draw(st.integers(min_value=1, max_value=10)),
    )


steps = st.one_of(steps_task(), steps_outros())


@st.composite
def labs(draw):
    return LabMetadata(
        lab_id=draw(ids),
        title=draw(texto),
        description=draw(texto),
        difficulty=draw(st.sampled_from(["iniciante", "intermediario", "avancado"])),
        estimated_duration_minutes=draw(st.integers(min_value=1, max_value=600)),
        estimated_cost_usd=draw(st.floats(min_value=0, max_value=100, allow_nan=False)),
        cost_disclaimer=draw(texto),
        dea_domains=draw(st.lists(st.sampled_from(["D1", "D2", "D3", "D4"]), min_size=1, unique=True)),
        dea_tasks=draw(st.lists(texto, min_size=1, max_size=4)),
        services=draw(st.lists(texto, min_size=1, max_size=3)),
        prerequisites=draw(st.dictionaries(texto, texto, max_size=3)),
        steps=draw(st.lists(steps, min_size=1, max_size=8)),
    )


@given(steps)
def test_step_tem_campos_obrigatorios_e_trilhas_coerentes(step):
    """Property 9: campos obrigatórios não nulos e regras de trilha por tipo."""
    assert step.step_id and step.title and step.type
    assert step.hint_threshold is not None
    if step.type == "task":
        assert step.paths  # não vazio
        assert set(step.paths) <= set(TRILHAS)
        unavailable = step.unavailable_paths or {}
        for trilha in TRILHAS:
            if trilha not in step.paths:
                assert unavailable.get(trilha)  # motivo não vazio
            else:
                assert trilha not in unavailable
    else:
        assert step.paths is None
        assert step.unavailable_paths is None


@given(labs())
def test_lab_tem_campos_obrigatorios(lab):
    """Property 9: todo campo do lab e de seus steps é não nulo."""
    for campo in dataclasses.fields(LabMetadata):
        assert getattr(lab, campo.name) is not None
    assert lab.steps
    for step in lab.steps:
        for campo in ("step_id", "title", "type", "hint_threshold"):
            assert getattr(step, campo) is not None
    assert lab.residual_resources == []  # padrão independente entre instâncias


def test_step_hint_threshold_padrao_e_3():
    step = StepMetadata(step_id="s1", title="t", type="info")
    assert step.hint_threshold == 3


def _subclasses(base):
    for sub in base.__subclasses__():
        yield sub
        yield from _subclasses(sub)


def test_toda_subclasse_de_workshop_error_define_code_e_status():
    subclasses = list(_subclasses(WorkshopError))
    assert subclasses
    codes = set()
    for cls in subclasses:
        assert isinstance(cls.code, str) and cls.code
        assert isinstance(cls.http_status, int) and 400 <= cls.http_status < 600
        codes.add(cls.code)
    assert len(codes) == len(subclasses)  # codes únicos
    assert errors.InvalidPathError.http_status == 400
    assert errors.PathUnavailableError.http_status == 409


@given(st.sampled_from(TRILHAS), texto)
def test_path_unavailable_inclui_motivo_na_mensagem(trilha, motivo):
    erro = PathUnavailableError(trilha, motivo)
    assert motivo in str(erro)
    assert trilha in str(erro)
    assert erro.reason == motivo
