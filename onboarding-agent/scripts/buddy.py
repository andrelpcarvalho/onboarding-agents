"""Comandos do buddy (acompanhar tutorados e atender pedidos) e da atribuição de buddies.

Buddy:
    python scripts/buddy.py tutees   --buddy maria.souza        # meus tutorados e progresso
    python scripts/buddy.py requests --buddy maria.souza        # meus pedidos abertos
    python scripts/buddy.py requests --buddy maria.souza --all  # inclui fechados
    python scripts/buddy.py close 4 --by maria.souza --note "conversamos no Slack"

Responsável (atribuição de papel e buddy):
    python scripts/buddy.py assign joao.silva --role dev_salesforce --buddy maria.souza \\
        --name "Maria Souza" --contact "@maria.souza no Slack" --by andre
    python scripts/buddy.py role joao.silva dev_salesforce --by andre   # só o papel
    python scripts/buddy.py assignments [--buddy maria.souza]
    python scripts/buddy.py unassign joao.silva
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from onboarding_core.reports import request_row, tutee_status
from onboarding_core.roles import load_roles
from onboarding_core.storage import get_catalog


def _check_role(role_id: str) -> None:
    if role_id not in load_roles():
        sys.exit(f"papel desconhecido: {role_id}. Válidos: {', '.join(sorted(load_roles()))}")


async def cmd_tutees(buddy_id: str) -> None:
    cat = get_catalog()
    assigned = cat.list_assignments(buddy_id)
    if not assigned:
        print(f"nenhum tutorado atribuído a {buddy_id}")
        return
    open_by_user: dict[str, int] = {}
    for e in cat.list_escalations("open", buddy_id=buddy_id):
        open_by_user[e.user_id] = open_by_user.get(e.user_id, 0) + 1
    print(f"{'tutorado':<18} {'papel':<28} {'feitos':<7} {'próximo':<22} {'revisar':<22} "
          f"{'último acesso':<14} pedidos")
    for a in assigned:
        s = await tutee_status(a.user_id)
        seen = f"{s.last_seen:%d/%m %H:%M}" if s.last_seen else "nunca entrou"
        nxt = f"quiz: {s.quiz_module}" if s.quiz_module else (s.next_module or "-")
        print(f"{s.user_id:<18} {(s.role or '-')[:27]:<28} {s.completed:<7} {nxt[:21]:<22} "
              f"{(', '.join(s.to_review) or '-')[:21]:<22} {seen:<14} "
              f"{open_by_user.get(a.user_id, 0)}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("tutees", help="meus tutorados e o progresso").add_argument(
        "--buddy", required=True)
    sp = sub.add_parser("requests", help="pedidos encaminhados pelo Tutor")
    sp.add_argument("--buddy", required=True)
    sp.add_argument("--all", action="store_true")
    sp = sub.add_parser("close", help="fecha um pedido")
    sp.add_argument("id", type=int)
    sp.add_argument("--by", required=True)
    sp.add_argument("--note", required=True, help="o que foi feito (sem conteúdo sensível)")

    sp = sub.add_parser("role", help="(responsável) define o papel (trilha) de um tutorado")
    sp.add_argument("user_id")
    sp.add_argument("role_id")
    sp.add_argument("--by", required=True)

    sp = sub.add_parser("assign", help="(responsável) define o buddy (e o papel) de um tutorado")
    sp.add_argument("user_id")
    sp.add_argument("--role", help="papel do tutorado, ex.: dev_salesforce")
    sp.add_argument("--buddy", required=True, help="login do buddy, ex.: maria.souza")
    sp.add_argument("--name", required=True, help="nome que o Tutor mostra")
    sp.add_argument("--contact", required=True, help='ex.: "@maria.souza no Slack"')
    sp.add_argument("--by", required=True)
    sub.add_parser("assignments", help="(responsável) lista atribuições").add_argument("--buddy")
    sub.add_parser("unassign", help="(responsável) remove atribuição").add_argument("user_id")
    args = p.parse_args()

    cat = get_catalog()
    if args.cmd == "tutees":
        asyncio.run(cmd_tutees(args.buddy))
    elif args.cmd == "requests":
        items = cat.list_escalations(None if args.all else "open", buddy_id=args.buddy)
        print("\n".join(request_row(e) for e in items) or "nenhum pedido aberto")
    elif args.cmd == "close":
        try:
            cat.close_escalation(args.id, args.by, args.note)
        except KeyError as e:
            sys.exit(str(e).strip("'\""))
        print(f"pedido #{args.id} fechado")
    elif args.cmd == "role":
        _check_role(args.role_id)
        r = cat.assign_role(args.user_id, args.role_id, args.by)
        print(f"{r.user_id}: papel {r.role_id}. Vale a partir da próxima mensagem.")
    elif args.cmd == "assign":
        if args.role:
            _check_role(args.role)
            cat.assign_role(args.user_id, args.role, args.by)
            print(f"{args.user_id}: papel {args.role}.")
        a = cat.assign_buddy(args.user_id, args.buddy, args.name, args.contact, args.by)
        print(f"{a.user_id} -> {a.buddy_name} ({a.buddy_contact}). Vale a partir da próxima mensagem.")
        orphans = [e for e in cat.list_escalations("open", unassigned=True) if e.user_id == a.user_id]
        if orphans:
            print(f"Atenção: {len(orphans)} pedido(s) antigo(s) deste tutorado estão sem buddy; "
                  "veja em `make inbox`.")
    elif args.cmd == "assignments":
        rows = cat.list_assignments(args.buddy)
        for a in rows:
            r = cat.get_role_assignment(a.user_id)
            print(f"{a.user_id:<20} -> {a.buddy_id:<16} {a.buddy_name} ({a.buddy_contact})"
                  f"  papel: {r.role_id if r else 'NÃO ATRIBUÍDO'}")
        if not rows:
            print("nenhuma atribuição")
    elif args.cmd == "unassign":
        print("removido" if cat.unassign_buddy(args.user_id) else "não havia atribuição")


if __name__ == "__main__":
    main()
