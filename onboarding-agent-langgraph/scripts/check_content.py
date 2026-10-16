"""Valida papéis (data/roles) e base de conhecimento (data/kb) antes de gerar materiais.

Uso:
    python scripts/check_content.py        # ou: make check

Sai com código 1 se houver erro. Avisos não bloqueiam.
"""

from __future__ import annotations

import sys

import yaml
from pydantic import ValidationError

from onboarding_lg import kb
from onboarding_lg.config import KB_DIR, ROLES_DIR
from onboarding_lg.schemas import Role


def check_kb(errors: list[str], warnings: list[str]) -> None:
    files = sorted(KB_DIR.glob("*.md"))
    if not files:
        errors.append(f"nenhum documento em {KB_DIR}")
    for f in files:
        text = f.read_text(encoding="utf-8")
        if "\n## " not in "\n" + text:
            warnings.append(f"kb/{f.name}: sem seções '## '; o arquivo inteiro vira uma única fonte")
        if "TODO" in text:
            warnings.append(f"kb/{f.name}: contém TODO")
    print(f"base de conhecimento: {len(files)} arquivo(s), {len(kb.load_chunks())} seção(ões) citáveis")


def check_role(path, errors: list[str], warnings: list[str], seen_ids: set[str]) -> None:
    name = f"roles/{path.name}"
    try:
        role = Role.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    except yaml.YAMLError as e:
        errors.append(f"{name}: YAML inválido (indentação?): {e}")
        return
    except ValidationError as e:
        for err in e.errors():
            loc = ".".join(str(x) for x in err["loc"])
            errors.append(f"{name}: campo '{loc}': {err['msg']}")
        return

    if path.stem != role.id:
        errors.append(f"{name}: o nome do arquivo deve ser igual ao id ('{role.id}.yaml')")
    if role.id in seen_ids:
        errors.append(f"{name}: id '{role.id}' repetido em outro arquivo")
    seen_ids.add(role.id)
    if not role.modules:
        errors.append(f"{name}: nenhum módulo")

    raw = path.read_text(encoding="utf-8")
    if "TODO" in raw:
        errors.append(f"{name}: ainda tem TODO para preencher")

    ids: list[str] = []
    for m in role.modules:
        where = f"{name} › {m.id}"
        if m.id in ids:
            errors.append(f"{where}: id de módulo repetido")
        for pre in m.prerequisites:
            if pre not in ids:
                errors.append(
                    f"{where}: pré-requisito '{pre}' não existe ou vem depois na lista"
                )
        ids.append(m.id)
        if not m.objectives:
            errors.append(f"{where}: sem objetivos (o quiz é baseado neles)")
        if not m.kb_tags:
            errors.append(f"{where}: sem kb_tags (o Curador não sabe o que buscar)")
        elif not kb.search(" ".join(m.kb_tags)):
            errors.append(f"{where}: kb_tags {m.kb_tags} não encontram nada em data/kb/")
        else:
            missing = [t for t in m.kb_tags if not kb.has_term(t)]
            if missing:
                warnings.append(f"{where}: tags sem resultado na base: {missing}")
    print(f"papel {role.id}: {len(role.modules)} módulo(s)")


def main() -> None:
    errors: list[str] = []
    warnings: list[str] = []
    check_kb(errors, warnings)
    seen: set[str] = set()
    for path in sorted(ROLES_DIR.glob("*.yaml")):
        check_role(path, errors, warnings, seen)

    for w in warnings:
        print(f"  aviso: {w}")
    for e in errors:
        print(f"  ERRO:  {e}")
    if errors:
        print(f"\n{len(errors)} erro(s). Corrija antes de rodar o Curador.")
        sys.exit(1)
    print("\ntudo certo ✓")


if __name__ == "__main__":
    main()
