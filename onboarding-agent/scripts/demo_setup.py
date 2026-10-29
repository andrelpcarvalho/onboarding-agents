"""Prepara a demo da PoC com dados SIMULADOS, sem tocar nos dados de uso normal.

Uso (via Makefile, que aponta os bancos para .adk/demo/):
    make demo-setup                 # recria catálogo, sessões e memória da demo
    make demo-chat                  # conversa como demo.ana (dev_salesforce)
    make demo-chat USER_ID=demo.bruno

O que monta (de data/demo/materiais.yaml):
- materiais APROVADOS de todos os módulos dos dois papéis, com o texto das seções da
  base e um banco de perguntas fiel a ela;
- papel e buddy atribuídos aos usuários de demo (como o responsável faria).
"""

from __future__ import annotations

import sys

import yaml

from onboarding_core import kb
from onboarding_core.config import CATALOG_DB, DATA_DIR, MEMORY_DB, SESSIONS_DB
from onboarding_core.quiz_bank import parse_bank, validate_bank
from onboarding_core.roles import load_roles
from onboarding_core.storage import Catalog

DEMO = DATA_DIR / "demo" / "materiais.yaml"


def material_md(titulo: str, fontes: list[str]) -> str:
    """Texto de estudo montado das seções da base, cada uma com a sua fonte."""
    parts = [f"# {titulo}", "", "_Material simulado para a PoC do curso._", ""]
    for src in fontes:
        text = kb.section(src)
        if text is None:
            raise SystemExit(f"fonte inexistente na base: {src}")
        parts += [f"## {src.split('#', 1)[1]}", text, f"[{src}]", ""]
    parts += ["## Para saber mais", *[f"- [{s}]" for s in fontes]]
    return "\n".join(parts)


def main() -> None:
    if ".adk/demo" not in str(CATALOG_DB).replace("\\", "/"):
        sys.exit(f"recusado: ONBOARDING_CATALOG_DB={CATALOG_DB} não é o catálogo de demo "
                 "(use `make demo-setup`)")
    for db in (CATALOG_DB, SESSIONS_DB, MEMORY_DB):
        db.parent.mkdir(parents=True, exist_ok=True)
        for p in db.parent.glob(db.name + "*"):
            p.unlink()
    data = yaml.safe_load(DEMO.read_text(encoding="utf-8"))
    mods, cat = data["modulos"], Catalog(CATALOG_DB)

    n = 0
    for role in load_roles().values():
        for m in role.modules:
            spec = mods.get(m.id)
            if spec is None:
                sys.exit(f"{role.id}/{m.id}: módulo sem material simulado em {DEMO.name}")
            bank = parse_bank(spec["perguntas"])
            if err := validate_bank(bank):
                sys.exit(f"{m.id}: {err}")
            mat = cat.save_draft(role.id, m.id, spec["titulo"],
                                 material_md(spec["titulo"], spec["fontes"]), spec["fontes"],
                                 quiz=bank)
            cat.approve(mat.id, "demo.revisor")
            n += 1

    for u in data["usuarios_demo"]:
        cat.assign_role(u["user_id"], u["papel"], "demo.responsavel")
        b = u["buddy"]
        cat.assign_buddy(u["user_id"], b["id"], b["nome"], b["contato"], "demo.responsavel")

    users = ", ".join(f"{u['user_id']} ({u['papel']})" for u in data["usuarios_demo"])
    print(f"demo pronta: {n} materiais aprovados; usuários: {users}")
    print("próximo passo: make demo-chat   (ou make demo-chat USER_ID=demo.bruno)")


if __name__ == "__main__":
    main()
