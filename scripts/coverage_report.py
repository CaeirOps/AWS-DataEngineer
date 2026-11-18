"""Relatório da Matriz de cobertura do exame DEA-C01.

Lê `docs/exam-coverage.json` e mostra quantas skills cada módulo cobre,
quantas skills cada domínio tem e quais skills ficam sem módulo.
Usa somente a biblioteca padrão do Python.

Uso:
    python scripts/coverage_report.py              # resumo por módulo e domínio
    python scripts/coverage_report.py lab-03       # skills de um módulo
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

MATRIX = Path(__file__).resolve().parents[1] / "docs" / "exam-coverage.json"


def load(path=MATRIX):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def by_module(data):
    result = defaultdict(list)
    for skill in data["skills"]:
        for module in skill["modules"]:
            result[module].append(skill["id"])
    return result


def main(argv=None, out=sys.stdout):
    argv = sys.argv[1:] if argv is None else argv
    data = load()
    mods = by_module(data)
    if argv:
        module = argv[0]
        if module not in data["modules"]:
            print(f"Módulo desconhecido: {module}", file=out)
            return 1
        print(f"{module} {data['modules'][module]}", file=out)
        texts = {s["id"]: s["text"] for s in data["skills"]}
        for sid in mods.get(module, []):
            print(f"  {sid}  {texts[sid]}", file=out)
        return 0

    print("Skills por módulo:", file=out)
    for module, title in data["modules"].items():
        print(f"  {module}  {len(mods.get(module, [])):3d}  {title}", file=out)
    print("Skills por domínio:", file=out)
    domains = defaultdict(int)
    for skill in data["skills"]:
        domains[skill["domain"]] += 1
    for domain in sorted(domains):
        print(f"  {domain}  {domains[domain]:3d}", file=out)
    orphans = [s["id"] for s in data["skills"] if not s["modules"]]
    print(f"Total: {len(data['skills'])} skills, sem módulo: {len(orphans)}", file=out)
    for sid in orphans:
        print(f"  sem módulo: {sid}", file=out)
    return 1 if orphans else 0


if __name__ == "__main__":
    sys.exit(main())
