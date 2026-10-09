"""Chat de terminal com o Tutor, com progresso e memória persistentes.

Uso:
    python scripts/chat.py --user joao.silva          # retoma a última sessão
    python scripts/chat.py --user joao.silva --new    # sessão nova (progresso mantido)
"""

from __future__ import annotations

import argparse
import asyncio
import warnings

from onboarding_core.agents import build_tutor
from onboarding_core.services import ask_stream, build_runner, get_or_create_session

# Avisos [EXPERIMENTAL] do ADK (emitidos em runtime) poluem o chat; não afetam o funcionamento.
warnings.filterwarnings("ignore", message=r"\[EXPERIMENTAL\]")


async def _say(runner, user_id: str, session_id: str, text: str) -> None:
    print("tutor> ", end="", flush=True)
    async for chunk in ask_stream(runner, user_id, session_id, text):
        print(chunk, end="", flush=True)
    print("\n")


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", required=True, help="id estável do colaborador (ex.: e-mail)")
    parser.add_argument("--new", action="store_true", help="inicia uma nova sessão")
    args = parser.parse_args()

    runner = build_runner(build_tutor())
    session_id = await get_or_create_session(runner, args.user, new=args.new)
    print(f"[sessão {session_id}] digite 'sair' para encerrar\n")

    await _say(runner, args.user, session_id, "Olá!")
    while True:
        try:
            text = input("você> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if text.lower() in {"sair", "exit", "quit"}:
            break
        if text:
            await _say(runner, args.user, session_id, text)


if __name__ == "__main__":
    asyncio.run(main())
