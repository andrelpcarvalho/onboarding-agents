"""Expõe o Curador como agente isolado via protocolo A2A (Agent2Agent).

Uso:
    python scripts/serve_a2a.py            # http://localhost:8001
O agent card fica em /.well-known/agent-card.json. Outro agente ADK pode consumi-lo com
RemoteA2aAgent(name="curador", agent_card="http://localhost:8001/.well-known/agent-card.json").
"""

from __future__ import annotations

import argparse

import uvicorn
from google.adk.a2a.utils.agent_to_a2a import to_a2a

from curator_agent.agent import build_agent


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="localhost")
    p.add_argument("--port", type=int, default=8001)
    a = p.parse_args()
    uvicorn.run(to_a2a(build_agent(), host=a.host, port=a.port), host=a.host, port=a.port)


if __name__ == "__main__":
    main()
