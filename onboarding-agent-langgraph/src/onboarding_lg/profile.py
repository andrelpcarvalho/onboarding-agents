"""Perfil do colaborador no Store do LangGraph (equivale ao estado `user:*` do ADK).

O Store é a memória entre threads (conversas): tudo aqui vale para todas as
conversas do mesmo user_id. Chaves do perfil:
  role_id, progress {module_id: ModuleProgress}, current_module,
  material_loaded, quiz (referências do quiz em andamento, sem gabarito)
"""

from __future__ import annotations

from typing import Any

from langgraph.store.base import BaseStore

NS = "profile"


def user_ns(user_id: str) -> str:
    """Rótulo de namespace para um user_id.

    O Store do LangGraph não aceita ponto em rótulos de namespace, e logins como
    `joao.silva` têm ponto: codificamos de forma reversível (% e . viram %25 e %2E).
    """
    return user_id.replace("%", "%25").replace(".", "%2E")


def from_user_ns(label: str) -> str:
    return label.replace("%2E", ".").replace("%25", "%")


def load(store: BaseStore, user_id: str) -> dict[str, Any]:
    item = store.get((NS, user_ns(user_id)), "data")
    return dict(item.value) if item else {}


def save(store: BaseStore, user_id: str, profile: dict[str, Any]) -> None:
    store.put((NS, user_ns(user_id)), "data", profile)


def known_users(store: BaseStore) -> list[str]:
    return sorted(from_user_ns(ns[1])
                  for ns in store.list_namespaces(prefix=(NS,), limit=10_000) if len(ns) > 1)


def delete(store: BaseStore, user_id: str) -> None:
    store.delete((NS, user_ns(user_id)), "data")
