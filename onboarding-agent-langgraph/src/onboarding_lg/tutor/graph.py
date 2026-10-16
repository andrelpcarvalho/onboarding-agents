"""Tutor como StateGraph explícito.

    START → quiz_gate → agent ─┬─(tool_calls)→ tools → agent
                               └─(resposta)──→ guard_output → remember → END

- `quiz_gate`: com um quiz em andamento, corrige a mensagem do colaborador POR CÓDIGO
  antes do modelo rodar, e o modelo só comunica o resultado. Na versão ADK isso
  dependia de o modelo lembrar de chamar `answer_quiz` (e os evals pegaram falhas).

- `agent`: monta o prompt com o progresso (Store), o buddy (catálogo) e lembranças
  relevantes, e chama o Gemini com as tools.
- `tools`: ToolNode; as tools leem/gravam o perfil no Store via ToolRuntime.
- `guard_output`: mascara CPF/cartão na resposta (substitui a mensagem pelo id).
- `remember`: grava o turno nas lembranças de longo prazo.

Persistência: o checkpointer guarda a THREAD (conversa); o Store guarda o que é do
USUÁRIO (perfil e lembranças), compartilhado por todas as threads dele.
"""

from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.tools import tool
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, ToolRuntime
from langgraph.runtime import Runtime

from .. import config, memory, profile
from ..curator.graph import curate
from ..guardrails import redact_ai_message
from ..progress import snapshot
from ..prompts import TUTOR
from ..roles import load_roles
from ..tools.tutor_tools import TUTOR_TOOLS, TutorContext, grade_answer


class TutorState(MessagesState):
    quiz_feedback: dict[str, Any] | None  # resultado do quiz_gate neste turno


@tool
def ask_curator(module_id: str, runtime: ToolRuntime[TutorContext]) -> dict:
    """Pede ao Curador o material de um módulo que ainda não tem material (leva ~1 min).
    O resultado é um rascunho não revisado; depois chame get_material.

    Args:
        module_id: id do módulo.
    """
    prof = profile.load(runtime.store, runtime.context.user_id)
    if not prof.get("role_id"):
        return {"ok": False, "error": "papel do colaborador não definido"}
    return curate(prof["role_id"], module_id)


TOOLS = [*TUTOR_TOOLS, ask_curator]


def _last_human_text(state: MessagesState) -> str:
    for m in reversed(state["messages"]):
        if m.type == "human":
            return str(m.text)
    return ""


def quiz_gate(state: TutorState, runtime: Runtime[TutorContext]) -> dict:
    """Determinístico: se há quiz em andamento, corrige a última mensagem do colaborador."""
    uid = runtime.context.user_id
    prof = profile.load(runtime.store, uid)
    if not prof.get("quiz"):
        return {"quiz_feedback": None}
    last = next((m for m in reversed(state["messages"]) if m.type == "human"), None)
    result = grade_answer(prof, last.id if last else None, str(last.text) if last else "")
    profile.save(runtime.store, uid, prof)
    return {"quiz_feedback": result}


def agent(state: TutorState, runtime: Runtime[TutorContext]) -> dict:
    uid = runtime.context.user_id
    snap = snapshot(profile.load(runtime.store, uid), uid)
    if state.get("quiz_feedback"):
        snap["quiz_feedback_deste_turno"] = state["quiz_feedback"]
    if snap["role_id"] is None:
        snap["available_roles"] = [{"id": r.id, "title": r.title, "description": r.description}
                                   for r in load_roles().values()]
    memories = memory.recall(runtime.store, uid, _last_human_text(state))
    if memories:
        snap["lembrancas_de_conversas_anteriores"] = memories
    system = SystemMessage(TUTOR.replace("<<CONTEXTO>>", json.dumps(snap, ensure_ascii=False)))
    model = config.llm("tutor").bind_tools(TOOLS)
    return {"messages": [model.invoke([system, *state["messages"]])]}


def route_after_agent(state: MessagesState) -> str:
    last = state["messages"][-1]
    return "tools" if isinstance(last, AIMessage) and last.tool_calls else "guard_output"


def guard_output(state: MessagesState) -> dict:
    masked = redact_ai_message(state["messages"][-1])
    return {"messages": [masked]} if masked else {}


def remember(state: MessagesState, runtime: Runtime[TutorContext]) -> dict:
    text = str(state["messages"][-1].text)  # normaliza conteúdo em blocos
    if text:
        memory.remember(runtime.store, runtime.context.user_id, _last_human_text(state), text)
    return {}


def build_tutor_graph(checkpointer=None, store=None):
    g = StateGraph(TutorState, context_schema=TutorContext)
    g.add_node("quiz_gate", quiz_gate)
    g.add_node("agent", agent)
    g.add_node("tools", ToolNode(TOOLS))
    g.add_node("guard_output", guard_output)
    g.add_node("remember", remember)
    g.add_edge(START, "quiz_gate")
    g.add_edge("quiz_gate", "agent")
    g.add_conditional_edges("agent", route_after_agent, ["tools", "guard_output"])
    g.add_edge("tools", "agent")
    g.add_edge("guard_output", "remember")
    g.add_edge("remember", END)
    return g.compile(checkpointer=checkpointer, store=store)
