#!/usr/bin/env python3
"""Verifica a assinatura DCO (Signed-off-by) nos commits de um intervalo.

Uso:
    python scripts/check_dco.py base..head

Regras:
- Cada commit precisa de uma linha `Signed-off-by: Nome <email>`.
- O e-mail da linha precisa ser igual ao e-mail do autor do commit
  (comparação sem diferenciar maiúsculas de minúsculas).
- Merge commits (mais de um pai) são ignorados.

Código de saída: 0 se todos os commits estão assinados, 1 se algum falha,
2 para erro de uso ou falha ao executar o git.
Somente biblioteca padrão; o git é chamado sem shell.
"""

import argparse
import re
import subprocess
import sys

# Separadores de campo e de registro que não aparecem em mensagens de commit
_FIELD = "\x1f"
_RECORD = "\x1e"

_SIGNOFF_RE = re.compile(r"^Signed-off-by:[ \t]+(\S.*?)[ \t]+<([^<>\s]+)>[ \t]*$", re.MULTILINE)


def _git_log(rev_range):
    """Retorna a lista de commits do intervalo como dicionários."""
    fmt = _FIELD.join(["%H", "%P", "%ae", "%an", "%s", "%B"]) + _RECORD
    cmd = ["git", "log", "--format=" + fmt, rev_range, "--"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", check=False)
    except OSError as exc:
        raise RuntimeError("não foi possível executar o git: %s" % exc)
    if result.returncode != 0:
        raise RuntimeError("git log falhou: %s" % result.stderr.strip())

    commits = []
    for record in result.stdout.split(_RECORD):
        record = record.strip("\n")
        if not record:
            continue
        sha, parents, email, name, subject, body = record.split(_FIELD, 5)
        commits.append(
            {
                "sha": sha,
                "parents": parents.split(),
                "author_email": email,
                "author_name": name,
                "subject": subject,
                "body": body,
            }
        )
    return commits


def check_commit(commit):
    """Retorna (ok, motivo) para um commit."""
    signoffs = _SIGNOFF_RE.findall(commit["body"])
    if not signoffs:
        return False, "sem linha Signed-off-by: Nome <email>"
    author = commit["author_email"].strip().lower()
    for _name, email in signoffs:
        if email.strip().lower() == author:
            return True, "ok"
    return False, "e-mail do Signed-off-by difere do autor (%s)" % commit["author_email"]


def main(argv=None):
    parser = argparse.ArgumentParser(description="Verifica Signed-off-by (DCO) em um intervalo de commits.")
    parser.add_argument("range", help="intervalo de commits, por exemplo base..head")
    args = parser.parse_args(argv)

    # Evita que o valor seja interpretado como opção do git
    if args.range.startswith("-"):
        print("erro: intervalo inválido: %s" % args.range, file=sys.stderr)
        return 2

    try:
        commits = _git_log(args.range)
    except RuntimeError as exc:
        print("erro: %s" % exc, file=sys.stderr)
        return 2

    if not commits:
        print("Nenhum commit no intervalo %s." % args.range)
        return 0

    failed = 0
    for commit in commits:
        short = commit["sha"][:7]
        if len(commit["parents"]) > 1:
            print("SKIP %s merge commit ignorado: %s" % (short, commit["subject"]))
            continue
        ok, reason = check_commit(commit)
        if ok:
            print("OK   %s %s" % (short, commit["subject"]))
        else:
            failed += 1
            print("FAIL %s %s: %s" % (short, commit["subject"], reason))

    if failed:
        print("\n%d commit(s) sem DCO válido. Use `git commit -s` ou `git rebase --signoff`." % failed)
        return 1
    print("\nTodos os commits do intervalo têm DCO válido.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
