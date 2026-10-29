"""Contrato de resposta do Tutor, aplicado por código na resposta final do modelo.

Os evals (15 rodadas, 27-28/10) mostraram que frases obrigatórias dependentes só do
prompt falham de 15% a 35% das vezes, cada rodada num caso diferente:
- não lembrar de não compartilhar dado pessoal quando a busca na base devolve uma
  instrução própria ("diga que não tem a informação");
- recusar o pedido de nota e não reapresentar a pergunta pendente do quiz;
- preparar o pedido ao buddy e não fazer a pergunta de consentimento;
- não dizer que a missão pausada por falta de acesso continua do mesmo ponto;
- recusar "marca a missão como concluída" e não voltar a pedir o que o checkpoint espera.

Aqui cada obrigação vira verificação + complemento determinístico. O modelo continua
escrevendo a resposta; o código só ACRESCENTA o que faltou. Nada é removido.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from google.genai import types

from .missions import get_mission
from .pii import PLACEHOLDERS
from .tools import state_keys as K
from .tools.quiz_view import LETTERS, question_view

PII_REMINDER = "Lembrete: não é preciso compartilhar dados pessoais aqui."


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    return re.sub(r"\s+", " ", "".join(c for c in s if not unicodedata.combining(c))).strip()


def _text(content: types.Content | None) -> str:
    return "".join(p.text or "" for p in (content.parts if content and content.parts else [])
                   if not p.thought)


def masked_placeholders(user_content: types.Content | None) -> list[str]:
    t = _text(user_content)
    return [ph for ph in dict.fromkeys(PLACEHOLDERS.values()) if ph in t]


def quiz_block(view: dict[str, Any]) -> str:
    opts = "\n".join(f"{k}) {v}" for k, v in view["options"].items())
    return (f"Pergunta {view['question_number']} de {view['total']} do quiz: "
            f"{view['question']}\n{opts}\n\n{view['ask']}")


def missing_parts(text: str, state: Any, user_content: types.Content | None,
                  last_user_event_id: str | None) -> tuple[list[str], list[str]]:
    """(prefixos, sufixos) que faltam na resposta para cumprir o contrato."""
    norm = _norm(text)
    prefix: list[str] = []
    suffix: list[str] = []

    if masked_placeholders(user_content) and "dados pessoais" not in norm:
        prefix.append(PII_REMINDER)

    check = state.get(K.MISSION_CHECK) or {}
    if check.get("status") == "blocked_access" and check.get("tell") \
            and _norm(check["tell"]) not in norm:
        suffix.append(check["tell"])

    pending = state.get(K.PENDING_ESCALATION)
    proposed_now = pending and pending.get("proposed_after_event") == last_user_event_id
    if proposed_now and pending.get("ask") and "sim ou nao" not in norm:
        suffix.append(pending["ask"])
    elif (quiz := state.get(K.QUIZ)) and not proposed_now:
        view = question_view(quiz)
        if "question" in view:
            shown = _norm(view["question"]) in norm
            asks_letter = all(f"{L.lower()})" in norm or f"{L.lower()}." in norm
                              for L in LETTERS) and "letra" in norm
            if not shown:
                suffix.append(quiz_block(view))
            elif not asks_letter:
                suffix.append(view["ask"])
    if not proposed_now and (ask := current_mission_ask(state)) and _norm(ask) not in norm:
        suffix.append(ask)
    return prefix, suffix


def current_mission_ask(state: Any) -> str | None:
    """Pergunta do checkpoint atual da missão em andamento (após a conferência do turno)."""
    mid = state.get(K.ACTIVE_MISSION)
    p = (state.get(K.MISSIONS) or {}).get(mid or "")
    m = get_mission(mid) if mid else None
    if not m or not p or p.get("status") != "in_progress":
        return None
    return m.steps[p["step"]].checkpoints[p["checkpoint"]].ask


def apply(content: types.Content, prefix: list[str], suffix: list[str]) -> None:
    """Acrescenta no lugar (mutação): os plugins seguintes, como o de PII, ainda rodam."""
    if not prefix and not suffix:
        return
    parts = content.parts
    first = next(i for i, p in enumerate(parts) if p.text and not p.thought)
    last = max(i for i, p in enumerate(parts) if p.text and not p.thought)
    if prefix:
        parts[first] = parts[first].model_copy(
            update={"text": "\n\n".join(prefix) + "\n\n" + parts[first].text})
    if suffix:
        parts[last] = parts[last].model_copy(
            update={"text": parts[last].text.rstrip() + "\n\n" + "\n\n".join(suffix)})
