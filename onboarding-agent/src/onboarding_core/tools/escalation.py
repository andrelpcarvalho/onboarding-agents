"""Encaminhamento ao buddy: grava na caixa de entrada (scripts/inbox.py).

Consentimento por código, no mesmo padrão do quiz e da missão:
- `propose_escalation` só PREPARA o pedido (resumo mascarado no estado) e devolve o
  que o Tutor deve perguntar;
- `confirm_escalation` não recebe argumentos: lê a mensagem do colaborador DEPOIS da
  proposta e só registra com um "sim" explícito. O modelo não consegue consentir
  pelo colaborador.

Sem webhook no MVP: o buddy/responsável consulta com `make inbox`.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from google.adk.tools import ToolContext

from ..pii import redact_text
from ..roles import get_role
from ..storage import get_catalog
from . import state_keys as K
from .progress import buddy_info
from .quiz import _last_user_message

MAX_PER_DAY = 3
Category = Literal["rh", "juridico", "saude", "conflito", "acesso", "outro"]
YES = ["sim", "pode", "pode registrar", "pode sim", "quero", "registra", "registre", "ok",
       "claro", "por favor", "manda", "pode mandar", "beleza", "isso"]
NO = ["nao", "agora nao", "deixa", "melhor nao", "prefiro nao", "cancela"]


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    return re.sub(r"\s+", " ", "".join(c for c in s if not unicodedata.combining(c))).strip()


def _has(terms: list[str], text: str) -> bool:
    t = _norm(text)
    return any(re.search(rf"\b{re.escape(_norm(x))}\b", t) for x in terms)


def _limit_reached(user_id: str) -> bool:
    since = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=1)
    return get_catalog().count_recent_escalations(user_id, since) >= MAX_PER_DAY


def propose_escalation(
    category: Category,
    summary: str,
    tool_context: ToolContext,
    urgency: Literal["normal", "alta"] = "normal",
) -> dict:
    """Prepara (NÃO registra) um pedido de ajuda para o buddy humano do colaborador.
    Depois pergunte se ele quer que o pedido seja registrado e, na resposta dele,
    chame confirm_escalation.

    Args:
        category: rh, juridico, saude, conflito, acesso (acesso/ferramenta bloqueada) ou outro.
        summary: 1-2 frases com o assunto, SEM detalhes sensíveis (o buddy conversa
            pessoalmente com o colaborador depois).
        urgency: "alta" só se houver impedimento de trabalhar ou risco; senão "normal".
    """
    user_id = tool_context.user_id
    if _limit_reached(user_id):
        return {"ok": False, "error": "limite diário de encaminhamentos atingido; "
                "oriente o colaborador a procurar o buddy diretamente"}
    event_id, _ = _last_user_message(tool_context)
    pending = {"category": category, "urgency": urgency,
               "summary": redact_text(summary.strip())[:500],
               "proposed_after_event": event_id,
               "at": datetime.now(UTC).isoformat(timespec="seconds")}
    tool_context.state[K.PENDING_ESCALATION] = pending
    role_id = tool_context.state.get(K.ROLE_ID)
    return {"ok": True, "status": "awaiting_consent", "summary": pending["summary"],
            "buddy": buddy_info(user_id, get_role(role_id) if role_id else None),
            "next_step": "pergunte se o colaborador quer que este pedido seja registrado para "
            "o buddy e PARE; na próxima mensagem dele, chame confirm_escalation"}


def confirm_escalation(tool_context: ToolContext) -> dict:
    """Registra o pedido preparado por propose_escalation SE o colaborador disse sim.
    Não recebe argumentos: lê a última mensagem dele. Chame logo após ele responder
    à pergunta sobre registrar o pedido."""
    state = tool_context.state
    pending = state.get(K.PENDING_ESCALATION)
    if not pending:
        return {"ok": False, "error": "não há pedido preparado",
                "next_step": "se o colaborador quer ajuda do buddy, chame propose_escalation"}
    event_id, text = _last_user_message(tool_context)
    if event_id == pending["proposed_after_event"]:
        return {"ok": False, "status": "awaiting_consent",
                "error": "o colaborador ainda não respondeu à pergunta",
                "next_step": "pergunte se ele quer registrar o pedido e aguarde a resposta"}
    if _has(NO, text):
        state[K.PENDING_ESCALATION] = None
        return {"ok": True, "status": "declined",
                "next_step": "respeite a decisão; lembre o contato direto do buddy"}
    if not _has(YES, text):
        return {"ok": False, "status": "unclear",
                "next_step": "pergunte de novo, pedindo um sim ou não"}
    state[K.PENDING_ESCALATION] = None
    return _register(tool_context.user_id, state, pending["category"], pending["summary"],
                     pending["urgency"])


def escalate_to_buddy(
    category: Category,
    summary: str,
    tool_context: ToolContext,
    urgency: Literal["normal", "alta"] = "normal",
) -> dict:
    """Registra o pedido direto. NÃO é exposta ao modelo (o Tutor usa propose/confirm);
    fica para scripts e testes.

    Args:
        category: categoria do pedido.
        summary: resumo sem detalhes sensíveis.
        urgency: normal ou alta.
    """
    return _register(tool_context.user_id, tool_context.state, category,
                     redact_text(summary.strip())[:500], urgency)


def _register(user_id: str, state: Any, category: str, summary: str, urgency: str) -> dict:
    catalog = get_catalog()
    if _limit_reached(user_id):
        return {"ok": False, "error": "limite diário de encaminhamentos atingido; "
                "oriente o colaborador a procurar o buddy diretamente"}

    role_id = state.get(K.ROLE_ID)
    role = get_role(role_id) if role_id else None
    assignment = catalog.get_assignment(user_id)
    esc = catalog.create_escalation(
        user_id=user_id,
        role_id=role_id,
        category=category,
        urgency=urgency,
        summary=summary,
        buddy_id=assignment.buddy_id if assignment else None,
    )
    return {
        "ok": True,
        "status": "registered",
        "escalation_id": esc.id,
        "buddy": buddy_info(user_id, role),
        "note": "registrado na lista de pedidos do buddy (ou do responsável, se não houver "
        "buddy atribuído); não há notificação automática, então indique também o contato",
    }
