"""Visão geral do responsável pelo piloto: o que está pendente em cada fila.

Uso:
    python scripts/inbox.py          # ou: make inbox
"""

from __future__ import annotations

import asyncio
from collections import Counter

from onboarding_core.reports import known_users, request_row
from onboarding_core.storage import get_catalog


def main() -> None:
    cat = get_catalog()
    open_req = cat.list_escalations("open")
    orphan = [e for e in open_req if e.buddy_id is None]
    per_buddy = Counter(e.buddy_id for e in open_req if e.buddy_id)
    urgent = sum(e.urgency == "alta" for e in open_req)

    print(f"Pedidos abertos: {len(open_req)}" + (f" ({urgent} URGENTE)" if urgent else ""))
    for buddy_id, n in per_buddy.most_common():
        print(f"   {buddy_id:<18} {n}   -> scripts/buddy.py requests --buddy {buddy_id}")
    if orphan:
        print(f"   SEM BUDDY          {len(orphan)}   (atribua um buddy ao tutorado ou atenda você)")
        for e in orphan:
            print("      " + request_row(e))

    users = asyncio.run(known_users())
    assigned = {a.user_id for a in cat.list_assignments()}
    without = [u for u in users if u not in assigned]
    print(f"Tutorados sem buddy atribuído: {len(without)}"
          + (f"   ({', '.join(without[:8])}{'...' if len(without) > 8 else ''})" if without else ""))
    print(f"Rascunhos aguardando revisão: {len(cat.list_by_status('draft'))}"
          "   -> scripts/approve.py list")
    print(f"Lacunas abertas: {len(cat.list_open_gaps())}   -> scripts/approve.py gaps")


if __name__ == "__main__":
    main()
