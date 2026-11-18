"""Modelos de dados da plataforma (dataclasses)."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ValidationResult:
    """Resultado da validação de um step contra o estado real da AWS."""

    passed: bool
    message: str
    hint: Optional[str] = None


@dataclass
class StepMetadata:
    """Metadados de um step, conforme `metadata.json` do módulo.

    `paths`, `unavailable_paths`, `optional` e `cost_note` são usados somente
    em steps do tipo `task`. `pass_score` é usado somente em steps `quiz`.
    """

    step_id: str
    title: str
    type: str  # info | deploy | task | quiz | teardown | completion
    hint_threshold: int = 3
    paths: Optional[list[str]] = None  # "console" e/ou "cli"
    unavailable_paths: Optional[dict[str, str]] = None  # trilha -> motivo
    skills: list[str] = field(default_factory=list)  # ids "N.N.N" da Matriz de cobertura
    optional: bool = False  # Prática opcional (só task)
    cost_note: Optional[str] = None  # aviso de custo reforçado da Prática opcional
    pass_score: Optional[float] = None  # nota mínima do quiz (0 < x <= 1)

    @property
    def required(self) -> bool:
        """Step que conta para a conclusão do módulo: task não opcional ou quiz."""
        return (self.type == "task" and not self.optional) or self.type == "quiz"


@dataclass
class LabMetadata:
    """Metadados de um módulo (lab), conforme `metadata.json`.

    `estimated_cost_usd` é legado e não é exibido (19.4); fica `None` quando
    o metadata não o declara. `cost_notice` vazio significa sem aviso.
    """

    lab_id: str
    title: str
    description: str
    difficulty: str  # iniciante | intermediario | avancado
    estimated_duration_minutes: int
    estimated_cost_usd: Optional[float]
    cost_disclaimer: str
    dea_domains: list[str]
    dea_tasks: list[str]
    services: list[str]
    prerequisites: dict
    steps: list[StepMetadata]
    residual_resources: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    has_infrastructure: bool = True
    cost_notice: dict = field(default_factory=dict)  # {"services": [{"name", "pricing_url"}]}
