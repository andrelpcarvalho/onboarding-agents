"""Chat de terminal com o Tutor (LangGraph), com progresso e memória persistentes.

Uso:
    python scripts/chat.py --user joao.silva          # retoma a última conversa
    python scripts/chat.py --user joao.silva --new    # conversa nova (progresso mantido)
"""

from __future__ import annotations

import argparse
import warnings

from onboarding_lg.services import ask_stream, thread_for, tutor_app

warnings.filterwarnings("ignore")


def say(graph, user: str, thread: str, text: str) -> None:
    print("tutor> ", end="", flush=True)
    for chunk in ask_stream(graph, user, thread, text):
        print(chunk, end="", flush=True)
    print("\n")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--user", required=True, help="id estável do colaborador (ex.: login)")
    p.add_argument("--new", action="store_true", help="inicia uma nova conversa")
    args = p.parse_args()
    with tutor_app() as (graph, store):
        thread = thread_for(store, args.user, new=args.new)
        print(f"[thread {thread}] digite 'sair' para encerrar\n")
        say(graph, args.user, thread, "Olá!")
        while True:
            try:
                text = input("você> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if text.lower() in {"sair", "exit", "quit"}:
                break
            if text:
                say(graph, args.user, thread, text)


if __name__ == "__main__":
    main()
