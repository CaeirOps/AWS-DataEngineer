"""Testes de unidade de scripts/check_dco.py (Requisitos 1.13 e 15.3).

Cada teste cria um repositório git temporário em tmp_path. O git é chamado
com -c user.name/user.email, sem tocar na configuração global.
"""

import importlib.util
import os
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


# --- Allowlist de bots (Dependabot), task 15I.3, Requisitos 15.13 e 15.14 ---

_BOT_NAME = "dependabot[bot]"
_BOT_EMAIL = "49699333+dependabot[bot]@users.noreply.github.com"
_BOT_SIGNOFF = "dependabot[bot] <support@github.com>"


def _commit_as(repo, subject, body, author_name, author_email):
    """Cria um commit vazio com autor via GIT_AUTHOR_* e corpo literal.

    O corpo é usado como veio, para testar linhas de Signed-off-by com
    espaços extras ou embutidas em outra linha.
    """
    env = dict(os.environ)
    env.update({
        "GIT_AUTHOR_NAME": author_name,
        "GIT_AUTHOR_EMAIL": author_email,
        # Sem configuração global ou do sistema, para o teste ser hermético
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_SYSTEM": os.devnull,
    })
    cmd = ["git", "-c", "user.name=Committer", "-c", "user.email=committer@example.com",
           "-c", "commit.gpgsign=false", "commit", "--allow-empty", "--cleanup=verbatim",
           "-m", subject + "\n\n" + body]
    subprocess.run(cmd, cwd=repo, env=env, capture_output=True, text=True,
                   encoding="utf-8", check=True)
    return _git(repo, "rev-parse", "HEAD")


def test_bot_dependabot_exato_aceito(repo, capsys):
    base = _commit(repo, "base")
    _commit_as(repo, "bump dep", "Signed-off-by: " + _BOT_SIGNOFF, _BOT_NAME, _BOT_EMAIL)
    code, out, _ = _run(capsys, base + "..HEAD")
    assert code == 0, out
    assert "OK (bot)" in out


def test_bot_dependabot_email_do_autor_com_outras_maiusculas(repo, capsys):
    base = _commit(repo, "base")
    _commit_as(repo, "bump dep", "Signed-off-by: " + _BOT_SIGNOFF,
               _BOT_NAME, "49699333+Dependabot[BOT]@Users.Noreply.GitHub.com")
    code, out, _ = _run(capsys, base + "..HEAD")
    assert code == 0, out
    assert "OK (bot)" in out


def test_bot_autor_dependabot_com_signoff_de_outra_identidade_falha(repo, capsys):
    base = _commit(repo, "base")
    _commit_as(repo, "bump dep", "Signed-off-by: Outro <outro@example.com>", _BOT_NAME, _BOT_EMAIL)
    code, out, _ = _run(capsys, base + "..HEAD")
    assert code == 1
    assert "FAIL" in out and "bump dep" in out
    assert "OK (bot)" not in out


def test_bot_signoff_do_dependabot_com_autor_humano_falha(repo, capsys):
    base = _commit(repo, "base")
    _commit_as(repo, "falso bot", "Signed-off-by: " + _BOT_SIGNOFF,
               "Humano", "humano@example.com")
    code, out, _ = _run(capsys, base + "..HEAD")
    assert code == 1
    assert "FAIL" in out and "falso bot" in out
    assert "OK (bot)" not in out


def test_bot_nome_dependabot_com_email_diferente_falha(repo, capsys):
    base = _commit(repo, "base")
    _commit_as(repo, "nome forjado", "Signed-off-by: " + _BOT_SIGNOFF,
               _BOT_NAME, "dependabot@example.com")
    code, out, _ = _run(capsys, base + "..HEAD")
    assert code == 1
    assert "FAIL" in out and "nome forjado" in out
    assert "OK (bot)" not in out


def test_bot_email_do_dependabot_com_outro_nome_falha(repo, capsys):
    base = _commit(repo, "base")
    _commit_as(repo, "email forjado", "Signed-off-by: " + _BOT_SIGNOFF,
               "Outro Nome", _BOT_EMAIL)
    code, out, _ = _run(capsys, base + "..HEAD")
    assert code == 1
    assert "FAIL" in out and "email forjado" in out
    assert "OK (bot)" not in out


def test_bot_signoff_com_dominio_estendido_falha(repo, capsys):
    base = _commit(repo, "base")
    _commit_as(repo, "dominio evil", "Signed-off-by: dependabot[bot] <support@github.com.evil>",
               _BOT_NAME, _BOT_EMAIL)
    code, out, _ = _run(capsys, base + "..HEAD")
    assert code == 1
    assert "FAIL" in out and "dominio evil" in out
    assert "OK (bot)" not in out


@pytest.mark.parametrize("linha", [
    # Espaços extras dentro da linha, no início e no fim
    "Signed-off-by:  dependabot[bot] <support@github.com>",
    "Signed-off-by: dependabot[bot]  <support@github.com>",
    " Signed-off-by: dependabot[bot] <support@github.com>",
    "Signed-off-by: dependabot[bot] <support@github.com> ",
    # Trailer como parte de outra linha (não pode casar por substring)
    "Co-authored-by: x Signed-off-by: dependabot[bot] <support@github.com>",
    "Signed-off-by: dependabot[bot] <support@github.com> e mais texto",
    "xSigned-off-by: dependabot[bot] <support@github.com>",
])
def test_bot_signoff_nao_casa_por_substring(repo, capsys, linha):
    base = _commit(repo, "base")
    _commit_as(repo, "variacao", linha, _BOT_NAME, _BOT_EMAIL)
    code, out, _ = _run(capsys, base + "..HEAD")
    assert code == 1, out
    assert "FAIL" in out
    assert "OK (bot)" not in out


def test_intervalo_misto_humano_e_dependabot_passa(repo, capsys):
    base = _commit(repo, "base")
    _commit(repo, "humano", "Autor <autor@example.com>")
    _commit_as(repo, "bump dep", "Signed-off-by: " + _BOT_SIGNOFF, _BOT_NAME, _BOT_EMAIL)
    code, out, _ = _run(capsys, base + "..HEAD")
    assert code == 0, out
    assert "OK (bot)" in out
    assert out.count("OK ") == 2
