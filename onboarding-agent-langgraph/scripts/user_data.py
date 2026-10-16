"""Dados de um tutorado: consultar ou apagar (recomeçar teste / pedido LGPD).

Uso:
    python scripts/user_data.py show  joao.silva
    python scripts/user_data.py reset joao.silva            # perfil, conversas e lembranças
    python scripts/user_data.py reset joao.silva --forget   # + lacunas, pedidos e buddy
"""

from __future__ import annotations

import argparse

from langgraph.checkpoint.sqlite import SqliteSaver

from onboarding_lg import memory, profile
from onboarding_lg.config import CHECKPOINT_DB
from onboarding_lg.db import connect
from onboarding_lg.profile import user_ns
from onboarding_lg.reports import tutee_status
from onboarding_lg.services import THREADS_NS, open_store, threads_of
from onboarding_lg.storage import get_catalog


def show(user_id: str) -> None:
    store = open_store()
    s = tutee_status(store, user_id)
    cat = get_catalog()
    a = cat.get_assignment(user_id)
    print(f"tutorado: {user_id}")
    print(f"  papel: {s.role or '-'} · concluídos: {s.completed} · próximo: {s.next_module or '-'}")
    print(f"  revisar: {', '.join(s.to_review) or '-'} · quiz em andamento: {s.quiz_module or '-'}")
    print(f"  último acesso: {s.last_seen:%d/%m %H:%M}" if s.last_seen else "  nunca entrou")
    print(f"  buddy: {a.buddy_name} ({a.buddy_contact})" if a else "  buddy: não atribuído")
    n_mem = len(store.search((memory.NS, user_ns(user_id)), limit=10_000))
    n_req = len([e for e in cat.list_escalations(None) if e.user_id == user_id])
    print(f"  conversas: {len(threads_of(store, user_id))} · lembranças: {n_mem} · pedidos: {n_req}")


def reset(user_id: str, forget: bool) -> None:
    store = open_store()
    threads = threads_of(store, user_id)
    saver = SqliteSaver(connect(CHECKPOINT_DB, check_same_thread=False))
    for t in threads:
        saver.delete_thread(t)
    store.delete((THREADS_NS, user_ns(user_id)), "index")
    profile.delete(store, user_id)
    n = memory.forget(store, user_id)
    print(f"apagados: {len(threads)} conversa(s), perfil e {n} lembrança(s) de {user_id}")
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
    sp.add_argument("--forget", action="store_true")
    args = p.parse_args()
    show(args.user_id) if args.cmd == "show" else reset(args.user_id, args.forget)


if __name__ == "__main__":
    main()
