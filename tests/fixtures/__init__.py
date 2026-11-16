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
