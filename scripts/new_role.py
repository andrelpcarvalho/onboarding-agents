"""Cria o arquivo de um papel novo a partir de um modelo comentado.

Uso:
    python scripts/new_role.py analista_qa "Analista de QA"
    python scripts/new_role.py analista_qa "Analista de QA" --from dev_salesforce   # copia módulos
"""

from __future__ import annotations

import argparse
import re
import sys

import yaml

from onboarding_core.config import ROLES_DIR

TEMPLATE = """\
# Papel: {title}
# Depois de editar, valide com:  make check
# E gere os materiais com:       make curate ROLE={id}

id: {id}                      # identificador único, minúsculo, sem espaço (não mude depois de usar)
title: {title}
description: >-               # 1 frase: o que essa pessoa faz na empresa
  TODO descreva o papel em uma frase.
buddy_contact: "TODO canal ou pessoa de apoio (ex.: #onboarding-qa no Slack)"

modules:
{modules}"""

MODULE_EXAMPLE = """\
  - id: cultura_empresa       # único dentro do papel
    title: Cultura e forma de trabalhar
    objectives:               # o que a pessoa deve saber ao final (vira o quiz)
      - Entender os valores da empresa e como eles aparecem no dia a dia
      - Conhecer os rituais do time
    kb_tags: [cultura, valores, rituais]   # palavras que aparecem nos docs de data/kb/
    prerequisites: []         # ids de módulos que precisam vir antes
    estimated_minutes: 20

  - id: TODO_segundo_modulo
    title: TODO título
    objectives:
      - TODO objetivo 1
    kb_tags: [TODO]
    prerequisites: [cultura_empresa]
    estimated_minutes: 30
"""


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("id", help="ex.: analista_qa")
    p.add_argument("title", help='ex.: "Analista de QA"')
    p.add_argument("--from", dest="from_role", help="copia os módulos de um papel existente")
    args = p.parse_args()

    if not re.fullmatch(r"[a-z][a-z0-9_]*", args.id):
        sys.exit("id deve ter só letras minúsculas, números e _ (ex.: analista_qa)")
    target = ROLES_DIR / f"{args.id}.yaml"
    if target.exists():
        sys.exit(f"{target} já existe")

    modules = MODULE_EXAMPLE
    if args.from_role:
        src = ROLES_DIR / f"{args.from_role}.yaml"
        if not src.exists():
            sys.exit(f"papel de origem não encontrado: {src}")
        data = yaml.safe_load(src.read_text(encoding="utf-8"))
        dumped = yaml.safe_dump(data["modules"], allow_unicode=True, sort_keys=False)
        modules = "".join(f"  {line}\n" for line in dumped.splitlines())

    target.write_text(TEMPLATE.format(id=args.id, title=args.title, modules=modules), encoding="utf-8")
    print(f"criado: {target.relative_to(ROLES_DIR.parents[1])}")
    print("Próximos passos: edite os TODO, rode `make check` e depois `make curate ROLE=" + args.id + "`.")


if __name__ == "__main__":
    main()
