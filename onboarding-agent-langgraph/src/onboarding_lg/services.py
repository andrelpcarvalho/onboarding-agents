"""Persistência (checkpointer + store em SQLite), threads por usuário e execução com streaming."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager

from langchain_core.messages import AIMessage, AIMessageChunk, ToolMessage
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.store.sqlite import SqliteStore

from .config import CHECKPOINT_DB, STORE_DB
from .db import connect, enable_wal
from .guardrails import prepare_user_message
from .profile import user_ns
from .tools.tutor_tools import TutorContext
from .tutor.graph import build_tutor_graph

THREADS_NS = "threads"


def open_store() -> SqliteStore:
    # O SqliteStore controla as próprias transações: precisa de autocommit.
    store = SqliteStore(connect(STORE_DB, check_same_thread=False, isolation_level=None))
    store.setup()
    return store


@contextmanager
def tutor_app():
    """Grafo do Tutor com conversas e perfil persistidos em `.lg/`."""
    enable_wal(CHECKPOINT_DB)
    saver = SqliteSaver(connect(CHECKPOINT_DB, check_same_thread=False))
    store = open_store()
    try:
        yield build_tutor_graph(checkpointer=saver, store=store), store
    finally:
        saver.conn.close()
        store.conn.close()


def thread_for(store, user_id: str, *, new: bool = False) -> str:
    """Retoma a última thread do usuário ou cria uma (o perfil vale para todas)."""
    item = store.get((THREADS_NS, user_ns(user_id)), "index")
    threads = item.value["threads"] if item else []
    if threads and not new:
        return threads[-1]
    thread_id = uuid.uuid4().hex
    store.put((THREADS_NS, user_ns(user_id)), "index", {"threads": [*threads, thread_id]})
    return thread_id


def threads_of(store, user_id: str) -> list[str]:
    item = store.get((THREADS_NS, user_ns(user_id)), "index")
    return item.value["threads"] if item else []


_TOOL_LABELS = {
    "set_my_role": "salvando seu papel", "get_material": "buscando material",
    "start_quiz": "preparando o quiz", "answer_quiz": "corrigindo",
    "search_knowledge_base": "consultando a base", "log_gap": "registrando dúvida",
    "escalate_to_buddy": "registrando pedido para o buddy",
    "ask_curator": "gerando material novo (pode levar ~1 min)",
}


def ask_stream(graph, user_id: str, thread_id: str, text: str) -> Iterator[str]:
    """Envia uma mensagem (já mascarada) e devolve a resposta em pedaços."""
    msg, _ = prepare_user_message(text)
    cfg = {"configurable": {"thread_id": thread_id}}
    for chunk, meta in graph.stream({"messages": [msg]}, cfg, context=TutorContext(user_id),
                                    stream_mode="messages"):
        node = meta.get("langgraph_node")
        if node == "agent" and isinstance(chunk, AIMessageChunk):
            for tc in chunk.tool_call_chunks or []:
                if tc.get("name"):
                    yield f"\n  [{_TOOL_LABELS.get(tc['name'], tc['name'])}...]\n"
            text = str(chunk.text)  # normaliza conteúdo em blocos (thinking do Gemini)
            if text:
                yield text


def ask(graph, user_id: str, thread_id: str, text: str) -> dict:
    """Versão sem streaming: devolve a resposta final e as tools chamadas no turno."""
    msg, _ = prepare_user_message(text)
    cfg = {"configurable": {"thread_id": thread_id}}
    before = len(graph.get_state(cfg).values.get("messages", [])) if graph.checkpointer else 0
    out = graph.invoke({"messages": [msg]}, cfg, context=TutorContext(user_id))
    turn = out["messages"][before:]
    tools = [{"name": tc["name"], "args": tc["args"]}
             for m in turn if isinstance(m, AIMessage) for tc in m.tool_calls]
    tool_results = [m.content for m in turn if isinstance(m, ToolMessage)]
    final = str(turn[-1].text) if turn and isinstance(turn[-1], AIMessage) else ""
    return {"answer": final, "tools": tools,
            "tool_results": tool_results}
