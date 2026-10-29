"""Valida papéis (data/roles), missões (data/missions) e base (data/kb) antes de gerar materiais.

Uso:
    python scripts/check_content.py        # ou: make check

Sai com código 1 se houver erro. Avisos não bloqueiam.
"""

from __future__ import annotations

import re
import sys

import yaml
from pydantic import ValidationError

from onboarding_core import kb
from onboarding_core.config import KB_DIR, MISSIONS_DIR, ROLES_DIR
from onboarding_core.roles import load_roles
from onboarding_core.schemas import Mission, Role

KNOWN_HELPERS = {"get_test_cpf"}


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


def check_missions(errors: list[str], warnings: list[str]) -> None:
    sources = kb.valid_sources()
    missions: dict[str, Mission] = {}
    for path in sorted(MISSIONS_DIR.glob("*.yaml")):
        name = f"missions/{path.name}"
        try:
            m = Mission.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
        except (yaml.YAMLError, ValidationError) as e:
            errors.append(f"{name}: inválido: {e}")
            continue
        if path.stem != m.id:
            errors.append(f"{name}: o nome do arquivo deve ser igual ao id ('{m.id}.yaml')")
        if m.status != "approved":
            warnings.append(f"{name}: status '{m.status}' (não aparece para o colaborador)")
        for step in m.steps:
            for h in step.helpers:
                if h not in KNOWN_HELPERS:
                    errors.append(f"{name} › {step.id}: helper desconhecido '{h}'")
            for cp in step.checkpoints:
                where = f"{name} › {step.id} › {cp.id}"
                for src in [*cp.explain, *([cp.fallback_source] if cp.fallback_source else [])]:
                    if src not in sources:
                        errors.append(f"{where}: fonte '{src}' não existe em data/kb/")
                if not cp.ask:
                    warnings.append(f"{where}: sem `ask` (pergunta que fecha a mensagem do Tutor)")
                if cp.pattern:
                    try:
                        re.compile(cp.pattern)
                    except re.error as e:
                        errors.append(f"{where}: regex inválida: {e}")
        missions[m.id] = m
    modules = {mod.id for r in load_roles().values() for mod in r.modules}
    for m in missions.values():
        for pre in m.prerequisites:
            if pre not in missions and pre not in modules:
                errors.append(f"missions/{m.id}.yaml: pré-requisito '{pre}' não existe")
    for r in load_roles().values():
        for mid in r.missions:
            if mid not in missions:
                errors.append(f"roles/{r.id}.yaml: missão '{mid}' não existe em data/missions/")
    print(f"missões: {len(missions)} arquivo(s)")


def main() -> None:
    errors: list[str] = []
    warnings: list[str] = []
    check_kb(errors, warnings)
    seen: set[str] = set()
    for path in sorted(ROLES_DIR.glob("*.yaml")):
        check_role(path, errors, warnings, seen)
    check_missions(errors, warnings)

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
