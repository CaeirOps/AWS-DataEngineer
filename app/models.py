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
    """Metadados de um step, conforme `metadata.json` do lab.

    `paths` e `unavailable_paths` são usados somente em steps do tipo `task`.
    """

    step_id: str
    title: str
    type: str  # info | deploy | task | teardown | completion
    hint_threshold: int = 3
    paths: Optional[list[str]] = None  # "console" e/ou "cli"
    unavailable_paths: Optional[dict[str, str]] = None  # trilha -> motivo


@dataclass
class LabMetadata:
    """Metadados de um lab, conforme `metadata.json`."""

    lab_id: str
    title: str
    description: str
    difficulty: str  # iniciante | intermediario | avancado
    estimated_duration_minutes: int
    estimated_cost_usd: float
    cost_disclaimer: str
    dea_domains: list[str]
    dea_tasks: list[str]
    services: list[str]
    prerequisites: dict
    steps: list[StepMetadata]
    residual_resources: list[str] = field(default_factory=list)
