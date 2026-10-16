"""Lembranças de longo prazo no Store do LangGraph (equivale ao MemoryService do ADK).

Cada turno (pergunta + resposta) vira um item em ("memories", user_id). A busca é por
palavra-chave, como o SqliteMemoryService do ADK. Para busca semântica, crie o
SqliteStore/PostgresStore com `index={"embed": ..., "dims": ...}` e troque `recall`
por `store.search(ns, query=...)`.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from langgraph.store.base import BaseStore

from .kb import _tokens
from .profile import user_ns

NS = "memories"
MAX_SCAN = 300


def remember(store: BaseStore, user_id: str, user_text: str, answer: str) -> None:
    store.put((NS, user_ns(user_id)), uuid.uuid4().hex, {
        "at": datetime.now(UTC).isoformat(timespec="seconds"),
        "user": user_text[:1000], "assistant": answer[:1500],
    })


def recall(store: BaseStore, user_id: str, query: str, k: int = 3) -> list[dict]:
    """Turnos antigos mais parecidos com a mensagem atual (por palavras em comum)."""
    q = _tokens(query)
    if not q:
        return []
    scored = []
    for item in store.search((NS, user_ns(user_id)), limit=MAX_SCAN):
        v = item.value
        score = len(q & _tokens(v.get("user", "") + " " + v.get("assistant", "")))
        if score:
            scored.append((score, v["at"], v))
    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [v for _, _, v in scored[:k]]


def last_seen(store: BaseStore, user_id: str) -> str | None:
    items = store.search((NS, user_ns(user_id)), limit=MAX_SCAN)
    return max((i.value["at"] for i in items), default=None)


def forget(store: BaseStore, user_id: str) -> int:
    items = store.search((NS, user_ns(user_id)), limit=10_000)
    for i in items:
        store.delete((NS, user_ns(user_id)), i.key)
    return len(items)
