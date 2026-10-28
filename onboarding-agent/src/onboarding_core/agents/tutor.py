"""Tutor: agente conversacional que conduz o colaborador pela trilha do seu papel."""

from __future__ import annotations

import json
import os

from google.adk.agents import LlmAgent
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.tools import preload_memory
from google.genai import types

from .. import config
from ..tools import (
    answer_mission,
    answer_quiz,
    escalate_to_buddy,
    get_material,
    get_test_cpf,
    list_roles,
    log_gap,
    search_knowledge_base,
    set_my_role,
    start_mission,
    start_module,
    start_quiz,
)
from ..tools.progress import progress_snapshot
from . import prompts


def _tutor_instruction(ctx: ReadonlyContext) -> str:
    """Monta a instrução com o progresso já embutido (recalculado a cada chamada
    ao modelo). Evita as idas e voltas get_my_progress/list_roles no começo da
    conversa, que custavam ~2 chamadas ao LLM por mensagem inicial."""
    snapshot = progress_snapshot(ctx.state, ctx.user_id)
    if snapshot["role_id"] is None:
        snapshot["available_roles"] = list_roles()["roles"]
    return prompts.TUTOR.replace("<<CONTEXTO>>", json.dumps(snapshot, ensure_ascii=False))


def _generate_config() -> types.GenerateContentConfig | None:
    """Orçamento de raciocínio do Tutor (padrão 1024 tokens).

    Com 0 (sem thinking) a latência caía ~1s, mas os evals mostraram o modelo
    pulando tools e até afirmando ter buscado/registrado sem chamar nada (6-7/8
    nos evals de comportamento contra 8/8 com 1024). -1 = dinâmico; vazio = padrão
    do modelo. Meça com `make eval` antes de mudar."""
    budget = os.getenv("TUTOR_THINKING_BUDGET", "1024").strip()
    if not budget or not isinstance(config.model("tutor"), config.Gemini):
        return None
    return types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(thinking_budget=int(budget))
    )


async def _save_session_to_memory(callback_context) -> None:
    """Indexa a conversa na memória semântica de longo prazo (MemoryService).

    É idempotente: eventos já ingeridos não são duplicados. Sem MemoryService
    configurado, a chamada falha e é ignorada (o progresso estruturado em `user:`
    continua funcionando).
    """
    try:
        await callback_context.add_session_to_memory()
    except ValueError:
        pass


def build_tutor(name: str = "tutor") -> LlmAgent:
    return LlmAgent(
        name=name,
        model=config.model("tutor"),
        description="Tutor de onboarding que conduz o colaborador pela trilha do seu papel.",
        instruction=_tutor_instruction,
        generate_content_config=_generate_config(),
        tools=[
            set_my_role,
            start_module,
            get_material,
            start_quiz,
            answer_quiz,
            search_knowledge_base,
            log_gap,
            escalate_to_buddy,
            # Missões práticas (progresso e evidências por código; ver tools/missions.py).
            start_mission,
            answer_mission,
            get_test_cpf,
            # Traz lembranças relevantes de conversas anteriores para o contexto.
            preload_memory,
            # Curador fora do Tutor (TO-BE): material só vem do catálogo, nunca gerado
            # sob demanda durante a conversa com o colaborador.
        ],
        after_agent_callback=_save_session_to_memory,
    )
