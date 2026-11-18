"""Fixtures de teste: lab de exemplo e validador de exemplo."""

import importlib.util
from pathlib import Path
from typing import Callable, Optional

FIXTURES_DIR = Path(__file__).resolve().parent
LABS_FIXTURE_DIR = FIXTURES_DIR / "labs"
EXAMPLE_LAB_ID = "lab-example"


def example_validator_loader(lab_id: str) -> Optional[Callable]:
    """Carregador de validadores para `ValidationService(validator_loader=...)`.

    Retorna `validate_step` do validador de exemplo para `lab-example` e
    `None` para qualquer outro lab. O módulo fica fora de `app/validators/`.
    """
    if lab_id != EXAMPLE_LAB_ID:
        return None
    spec = importlib.util.spec_from_file_location(
        "tests_fixtures_lab_example", FIXTURES_DIR / "validators" / "lab_example.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.validate_step

THEORY_LAB_ID = "lab-theory"

# Campos mínimos de um módulo sem infraestrutura (Requirement 20), para os
# testes que montam um `metadata.json` próprio em `tmp_path`.
NO_INFRA_FIELDS = {"skills": ["1.1.1"], "has_infrastructure": False}

# Campos mínimos de um módulo com infraestrutura. O teste precisa criar
# `cloudformation/stack.yaml` (ver `write_stack`) e os steps deploy e teardown.
INFRA_FIELDS = {
    "skills": ["1.1.1"],
    "has_infrastructure": True,
    "cost_notice": {
        "services": [{"name": "Amazon S3", "pricing_url": "https://aws.amazon.com/s3/pricing/"}]
    },
}
MINIMAL_TEMPLATE = (
    "AWSTemplateFormatVersion: '2010-09-09'\n"
    "Resources:\n  Handle:\n    Type: AWS::CloudFormation::WaitConditionHandle\n"
)


def write_stack(lab_dir, template: str = MINIMAL_TEMPLATE) -> None:
    """Cria `<lab_dir>/cloudformation/stack.yaml`."""
    stack_dir = Path(lab_dir) / "cloudformation"
    stack_dir.mkdir(parents=True, exist_ok=True)
    (stack_dir / "stack.yaml").write_text(template, encoding="utf-8")
