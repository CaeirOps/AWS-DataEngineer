"""Executa a suíte de testes JavaScript (node --test) dentro do pytest."""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.skipif(shutil.which("node") is None, reason="node não está instalado")
def test_js_suite_passes():
    result = subprocess.run(
        # No Node 23, passar o diretório é tratado como arquivo; usa-se glob.
        ["node", "--test", "tests/js/**/*.test.mjs"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
