"""Fábrica de serviços persistentes (sessão + memória) e helper de execução."""

from __future__ import annotations

from collections.abc import AsyncIterator

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import LlmCallsLimitExceededError
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.apps import App
from google.adk.memory import SqliteMemoryService
from google.adk.runners import Runner
from google.adk.sessions.sqlite_session_service import SqliteSessionService
from google.genai import types

from .config import APP_NAME, MAX_LLM_CALLS, MEMORY_DB, SESSIONS_DB
from .db import prepare_databases
from .guardrails import default_plugins


def build_runner(agent: BaseAgent, app_name: str = APP_NAME) -> Runner:
    """Runner com sessão e memória em SQLite (banco do MVP, ver db.py).

    Ao escalar para mais de uma instância, troque por
    DatabaseSessionService(db_url="postgresql+asyncpg://...") e
    VertexAiMemoryBankService(...), sem mudar os agentes.
    """
    prepare_databases()
    return Runner(
        app=App(name=app_name, root_agent=agent, plugins=default_plugins()),
        session_service=SqliteSessionService(db_path=str(SESSIONS_DB)),
        memory_service=SqliteMemoryService(db_path=MEMORY_DB),
    )


async def get_or_create_session(runner: Runner, user_id: str, *, new: bool = False) -> str:
    """Retoma a sessão mais recente do usuário (ou cria uma).

    Mesmo numa sessão nova, o estado `user:*` (papel e progresso) é carregado.
    """
    svc = runner.session_service
    if not new:
        resp = await svc.list_sessions(app_name=runner.app_name, user_id=user_id)
        if resp.sessions:
            return max(resp.sessions, key=lambda s: s.last_update_time).id
    session = await svc.create_session(app_name=runner.app_name, user_id=user_id)
    return session.id


async def ask(runner: Runner, user_id: str, session_id: str, text: str) -> str:
    """Envia uma mensagem e devolve a resposta final do agente raiz."""
    msg = types.Content(role="user", parts=[types.Part(text=text)])
    final = ""
    run_config = RunConfig(max_llm_calls=MAX_LLM_CALLS)
    async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=msg,
                                        run_config=run_config):
        if event.content and event.content.parts and event.is_final_response():
            final = "".join(p.text or "" for p in event.content.parts) or final
    return final


_TOOL_LABELS = {
    "start_module": "abrindo módulo",
    "get_material": "buscando material",
    "start_quiz": "preparando o quiz",
    "answer_quiz": "corrigindo",
    "propose_escalation": "preparando pedido para o buddy",
    "confirm_escalation": "registrando pedido para o buddy",
    "search_knowledge_base": "consultando a base",
    "log_gap": "registrando dúvida",
    "start_mission": "abrindo a missão",
    "answer_mission": "conferindo",
    "get_test_cpf": "buscando CPF de teste",
}


async def ask_stream(runner: Runner, user_id: str, session_id: str, text: str) -> AsyncIterator[str]:
    """Como `ask`, mas devolve o texto em pedaços conforme o modelo gera (SSE),
    mais avisos curtos quando o agente chama uma tool."""
    msg = types.Content(role="user", parts=[types.Part(text=text)])
    run_config = RunConfig(streaming_mode=StreamingMode.SSE, max_llm_calls=MAX_LLM_CALLS)
    try:
        async for event in runner.run_async(
            user_id=user_id, session_id=session_id, new_message=msg, run_config=run_config
        ):
            if not (event.content and event.content.parts):
                continue
            for part in event.content.parts:
                if part.function_call and not event.partial:
                    label = _TOOL_LABELS.get(part.function_call.name, part.function_call.name)
                    yield f"\n  [{label}...]\n"
                # No modo SSE os pedaços chegam com partial=True e no fim vem um evento
                # agregado com o texto inteiro, que não reimprimimos.
                elif part.text and event.partial and not part.thought:
                    yield part.text
    except LlmCallsLimitExceededError:
        yield ("\nNão consegui concluir esta resposta. Pode repetir a mensagem com outras "
               "palavras? Se continuar, fale com o seu buddy.")
