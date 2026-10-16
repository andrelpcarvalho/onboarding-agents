"""Modo batch do Curador: gera rascunhos de todos os módulos de um papel.

Uso:
    python scripts/curate_role.py dev_salesforce
    python scripts/curate_role.py dev_salesforce --module pipeline_deploy
    python scripts/curate_role.py dev_salesforce --missing-only   # retoma após falha
    python scripts/curate_role.py dev_salesforce --pause 30         # cota apertada (429)
    python scripts/curate_role.py dev_salesforce --module pipeline_deploy \
        --feedback "explicar melhor quem aprova a GMUD; tom menos técnico"
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from google.adk.runners import InMemoryRunner

from onboarding_core.agents import build_curator
from onboarding_core.roles import get_role
from onboarding_core.services import ask
from onboarding_core.storage import get_catalog


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("role_id")
    parser.add_argument("--module", help="gera só este módulo")
    parser.add_argument("--missing-only", action="store_true",
                        help="pula módulos que já têm material (rascunho ou aprovado)")
    parser.add_argument("--feedback",
                        help="observações do revisor que o Curador deve atender")
    parser.add_argument("--pause", type=float, default=10.0,
                        help="segundos de pausa entre módulos (alivia a cota do Vertex)")
    args = parser.parse_args()

    role = get_role(args.role_id)
    if role is None:
        sys.exit(f"papel desconhecido: {args.role_id}")

    modules = [m for m in role.modules if not args.module or m.id == args.module]
    catalog = get_catalog()
    failed: list[str] = []
    for i, m in enumerate(modules):
        if args.missing_only and catalog.get_latest(role.id, m.id, approved_only=False):
            print(f"= {m.id}: já tem material, pulando")
            continue
        if i:
            await asyncio.sleep(args.pause)
        # Um runner/sessão por módulo: estado (outline/draft) não vaza entre módulos.
        runner = InMemoryRunner(agent=build_curator(), app_name="curator_batch")
        session = await runner.session_service.create_session(
            app_name=runner.app_name, user_id="curator-batch"
        )
        print(f"> {m.id}: gerando...")
        request = f"role_id={role.id} module_id={m.id}"
        if args.feedback:
            request += f"\nObservações do revisor: {args.feedback}"
        try:
            reply = await ask(runner, "curator-batch", session.id, request)
        except Exception as e:  # noqa: BLE001 - segue para o próximo módulo
            failed.append(m.id)
            print(f"  ! falhou: {type(e).__name__}: {str(e).strip().splitlines()[-1][:200]}")
            continue
        print(f"  {reply.strip()}")

    if failed:
        print(f"\nFalharam: {', '.join(failed)}. Rode de novo com --missing-only para retomar.")
    print("\nRevise e aprove com: python scripts/approve.py list")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
