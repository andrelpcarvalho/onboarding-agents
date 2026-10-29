"""Monta a base fixa usada pelos evals (evals/.fixture/catalog.db).

Os evals não podem depender do catálogo real (que muda com o uso). Aqui criamos:
- materiais APROVADOS dos 4 módulos de dev_salesforce, com o texto da base de
  conhecimento e um banco de 4 perguntas em que a correta é sempre a B (assim os
  casos de quiz respondem "B" e o resultado esperado é determinístico);
- a atribuição de cada usuário de eval (um por caso) à buddy Maria Eval e, quando o
  caso tem papel, ao papel (o Tutor lê o papel do catálogo, não da conversa).

Rode com as variáveis do `make eval` (ONBOARDING_CATALOG_DB apontando para a fixture).
"""

from __future__ import annotations

from build_evalsets import BUDDY, eval_role_assignments, eval_user_ids  # mesmo diretório

from onboarding_core.config import CATALOG_DB, KB_DIR
from onboarding_core.kb import split_front_matter
from onboarding_core.quiz_bank import parse_bank
from onboarding_core.storage import Catalog

ROLE = "dev_salesforce"
MODULES = {
    "cultura_empresa": "cultura.md",
    "acessos_ferramentas": "acessos_ferramentas.md",
    "seguranca_informacao": "seguranca.md",
    "pipeline_deploy": "pipeline_deploy.md",
}


def _bank(module_id: str) -> list[dict]:
    return [
        {"question": f"[{module_id}] Pergunta de checagem {i + 1}?",
         "options": [f"errada {i}a", f"certa {i}", f"errada {i}c", f"errada {i}d"],
         "correct_option": 1, "explanation": f"A alternativa B é a correta ({module_id})."}
        for i in range(4)
    ]


def main() -> None:
    if "fixture" not in str(CATALOG_DB):
        raise SystemExit(f"recusado: ONBOARDING_CATALOG_DB={CATALOG_DB} não é a fixture de eval")
    for p in CATALOG_DB.parent.glob(CATALOG_DB.name + "*"):
        p.unlink()
    cat = Catalog(CATALOG_DB)
    for module_id, kb_file in MODULES.items():
        _, text = split_front_matter((KB_DIR / kb_file).read_text(encoding="utf-8"))
        sections = [ln[3:].strip() for ln in text.splitlines() if ln.startswith("## ")]
        m = cat.save_draft(ROLE, module_id, module_id.replace("_", " ").title(), text,
                           [f"{kb_file}#{s}" for s in sections], quiz=parse_bank(_bank(module_id)))
        cat.approve(m.id, "eval")
    for user_id in eval_user_ids():
        cat.assign_buddy(user_id, *BUDDY, "eval")
    for user_id, role_id in eval_role_assignments().items():
        cat.assign_role(user_id, role_id, "eval")
    print(f"fixture pronta em {CATALOG_DB}")


if __name__ == "__main__":
    main()
