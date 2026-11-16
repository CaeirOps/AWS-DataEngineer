"""Testes de unidade de scripts/check_dco.py (Requisitos 1.13 e 15.3).

Cada teste cria um repositório git temporário em tmp_path. O git é chamado
com -c user.name/user.email, sem tocar na configuração global.
"""

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_dco.py"
_spec = importlib.util.spec_from_file_location("check_dco", _SCRIPT)
check_dco = importlib.util.module_from_spec(_spec)
sys.modules["check_dco"] = check_dco
_spec.loader.exec_module(check_dco)


def _git(repo, *args, name="Autor", email="autor@example.com"):
    """Executa git no repositório sem shell e sem config global."""
    cmd = ["git", "-c", "user.name=" + name, "-c", "user.email=" + email,
           "-c", "commit.gpgsign=false", *args]
    result = subprocess.run(cmd, cwd=repo, capture_output=True, text=True,
                            encoding="utf-8", check=True)
    return result.stdout.strip()


def _commit(repo, subject, signoff=None, name="Autor", email="autor@example.com"):
    """Cria um commit vazio, opcionalmente com linha Signed-off-by."""
    message = subject
    if signoff is not None:
        message += "\n\nSigned-off-by: " + signoff
    _git(repo, "commit", "--allow-empty", "-m", message, name=name, email=email)
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path, monkeypatch):
    _git(tmp_path, "init", "-q")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _run(capsys, rng):
    code = check_dco.main([rng])
    out = capsys.readouterr()
    return code, out.out, out.err


def test_todos_assinados(repo, capsys):
    base = _commit(repo, "base")
    _commit(repo, "um", "Autor <autor@example.com>")
    _commit(repo, "dois", "Autor <autor@example.com>")
    code, out, _ = _run(capsys, base + "..HEAD")
    assert code == 0
    assert out.count("OK ") == 2


def test_commit_sem_signoff_falha_e_e_listado(repo, capsys):
    base = _commit(repo, "base")
    _commit(repo, "assinado", "Autor <autor@example.com>")
    _commit(repo, "sem assinatura")
    code, out, _ = _run(capsys, base + "..HEAD")
    assert code == 1
    assert "FAIL" in out and "sem assinatura" in out
    assert "assinado" in out


def test_email_do_signoff_diferente_do_autor(repo, capsys):
    base = _commit(repo, "base")
    _commit(repo, "outro email", "Autor <outro@example.com>")
    code, out, _ = _run(capsys, base + "..HEAD")
    assert code == 1
    assert "difere do autor" in out


def test_diferenca_de_maiusculas_aceita(repo, capsys):
    base = _commit(repo, "base")
    _commit(repo, "caixa", "Autor <AUTOR@Example.COM>")
    code, _, _ = _run(capsys, base + "..HEAD")
    assert code == 0


def test_merge_commit_ignorado(repo, capsys):
    base = _commit(repo, "base")
    _git(repo, "checkout", "-q", "-b", "a")
    _commit(repo, "em a", "Autor <autor@example.com>")
    _git(repo, "checkout", "-q", "-b", "b", base)
    _commit(repo, "em b", "Autor <autor@example.com>")
    _git(repo, "checkout", "-q", "a")
    # Merge sem Signed-off-by: deve ser ignorado
    _git(repo, "merge", "--no-ff", "-m", "merge sem assinatura", "b")
    code, out, _ = _run(capsys, base + "..HEAD")
    assert code == 0
    assert "SKIP" in out and "merge sem assinatura" in out


def test_intervalo_invalido_retorna_2(repo, capsys):
    _commit(repo, "base")
    code, _, err = _run(capsys, "naoexiste..HEAD")
    assert code == 2
    assert "erro" in err


def test_intervalo_iniciado_com_hifen_rejeitado(repo, capsys):
    _commit(repo, "base")
    # O argparse já recusa "--all" como opção desconhecida (saída 2)
    with pytest.raises(SystemExit) as exc:
        check_dco.main(["--all"])
    assert exc.value.code == 2
    capsys.readouterr()
    # Com "--" o valor chega ao script, que precisa rejeitá-lo por conta própria
    code = check_dco.main(["--", "--all"])
    assert code == 2
    assert "intervalo inválido" in capsys.readouterr().err


def test_caracteres_especiais_sem_execucao_de_shell(repo, capsys):
    base = _commit(repo, "base")
    name = "O'Brien; $(touch pwned) `touch pwned2` & |"
    # E-mail sem espaços, pois o formato do sign-off não os admite
    email = "a+b$(touch${IFS}pwned3)@example.com"
    _commit(repo, "especial; $(touch pwned4)", "%s <%s>" % (name, email),
            name=name, email=email)
    code, out, err = _run(capsys, base + "..HEAD")
    assert code == 0, out + err
    assert "OK" in out
    # Nenhum comando embutido pode ter sido executado
    assert not list(Path(repo).glob("pwned*"))
