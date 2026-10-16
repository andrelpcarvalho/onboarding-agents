"""Dados de um tutorado: consultar ou apagar (recomeçar teste / pedido LGPD).

Uso:
    python scripts/user_data.py show  joao.silva
    python scripts/user_data.py reset joao.silva            # progresso, conversas e memória
    python scripts/user_data.py reset joao.silva --forget   # + lacunas, pedidos e atribuição de buddy

Pare o `make web` / `make chat` antes de apagar. Faça `make backup` se tiver dúvida.
"""

from __future__ import annotations

import argparse
import asyncio
import sqlite3

from onboarding_core.config import APP_NAME, MEMORY_DB, SESSIONS_DB
from onboarding_core.db import connect
from onboarding_core.reports import tutee_status
from onboarding_core.storage import get_catalog


def _count(db, sql: str, user_id: str) -> int:
    if not db.exists():
        return 0
    with connect(db) as c:
        try:
            return c.execute(sql, (user_id,)).fetchone()[0]
        except sqlite3.OperationalError:  # tabela ainda não criada
            return 0


def show(user_id: str) -> None:
    s = asyncio.run(tutee_status(user_id))
    cat = get_catalog()
    a = cat.get_assignment(user_id)
    print(f"tutorado: {user_id}")
    print(f"  papel: {s.role or '-'} · concluídos: {s.completed} · próximo: {s.next_module or '-'}")
    print(f"  revisar: {', '.join(s.to_review) or '-'} · quiz em andamento: {s.quiz_module or '-'}")
    print(f"  último acesso: {s.last_seen:%d/%m %H:%M}" if s.last_seen else "  nunca entrou")
    print(f"  buddy: {a.buddy_name} ({a.buddy_contact})" if a else "  buddy: não atribuído")
    print(f"  sessões: {_count(SESSIONS_DB, 'SELECT COUNT(*) FROM sessions WHERE user_id=?', user_id)}"
          f" · trechos na memória: "
          f"{_count(MEMORY_DB, 'SELECT COUNT(*) FROM memory_events WHERE user_id=?', user_id)}"
          f" · pedidos ao buddy: {len([e for e in cat.list_escalations(None) if e.user_id == user_id])}")


def reset(user_id: str, forget: bool) -> None:
    with connect(SESSIONS_DB) as c:
        c.execute("PRAGMA foreign_keys=ON")
        n = c.execute("DELETE FROM sessions WHERE app_name=? AND user_id=?",
                      (APP_NAME, user_id)).rowcount
        c.execute("DELETE FROM user_states WHERE app_name=? AND user_id=?", (APP_NAME, user_id))
    if MEMORY_DB.exists():
        with connect(MEMORY_DB) as c:
            c.execute("DELETE FROM memory_events WHERE user_id=?", (user_id,))
    print(f"apagados: {n} sessão(ões), progresso e memória de {user_id}")
    if forget:
        cat = get_catalog()
        with connect(cat.db_path) as c:
            for table in ("gaps", "escalations"):
                c.execute(f"DELETE FROM {table} WHERE user_id=?", (user_id,))
        cat.unassign_buddy(user_id)
        print("apagados também: lacunas, pedidos ao buddy e atribuição de buddy")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("show").add_argument("user_id")
    sp = sub.add_parser("reset")
    sp.add_argument("user_id")
    sp.add_argument("--forget", action="store_true", help="apaga tudo ligado ao usuário")
    args = p.parse_args()
    if args.cmd == "show":
        show(args.user_id)
    else:
        reset(args.user_id, args.forget)


if __name__ == "__main__":
    main()
