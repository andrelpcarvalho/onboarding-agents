"""Curador em batch (LangGraph): gera rascunho (texto + banco de perguntas) por módulo.

Uso:
    python scripts/curate_role.py dev_salesforce
    python scripts/curate_role.py dev_salesforce --module pipeline_deploy --feedback "..."
    python scripts/curate_role.py dev_salesforce --missing-only --pause 30
"""

from __future__ import annotations

import argparse
import sys
import time
import warnings

from onboarding_lg.curator.graph import curate
from onboarding_lg.roles import get_role
from onboarding_lg.storage import get_catalog

warnings.filterwarnings("ignore")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("role_id")
    p.add_argument("--module")
    p.add_argument("--missing-only", action="store_true")
    p.add_argument("--feedback", help="observações do revisor que o Curador deve atender")
    p.add_argument("--pause", type=float, default=5.0)
    args = p.parse_args()
    role = get_role(args.role_id) or sys.exit(f"papel desconhecido: {args.role_id}")
    failed = []
    for i, m in enumerate(x for x in role.modules if not args.module or x.id == args.module):
        if args.missing_only and get_catalog().get_latest(role.id, m.id, approved_only=False):
            print(f"= {m.id}: já tem material, pulando")
            continue
        if i:
            time.sleep(args.pause)
        print(f"> {m.id}: gerando...")
        try:
            r = curate(role.id, m.id, args.feedback)
        except Exception as e:  # noqa: BLE001 - segue para o próximo módulo
            r = {"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}
        if r.get("ok"):
            auto = "aprovado" if r["auto_review_approved"] else "NÃO aprovado (veja a nota)"
            print(f"  material #{r['material_id']} v{r['version']}, {r['quiz_questions']} perguntas; "
                  f"revisão automática: {auto}")
            if r.get("invalid_citations"):
                print(f"  citações descartadas (não existem na base): {r['invalid_citations']}")
        else:
            failed.append(m.id)
            print(f"  ! falhou: {r.get('error')}")
    print("\nRevise e aprove com: python scripts/approve.py list")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
