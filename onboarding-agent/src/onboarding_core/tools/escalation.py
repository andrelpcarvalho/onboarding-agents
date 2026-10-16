"""Encaminhamento ao buddy: grava na caixa de entrada (scripts/inbox.py).

Sem webhook no MVP: o buddy/responsável consulta com `make inbox`.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal

from google.adk.tools import ToolContext

from ..pii import redact_text
from ..roles import get_role
from ..storage import get_catalog
from . import state_keys as K
from .progress import buddy_info

MAX_PER_DAY = 3


def escalate_to_buddy(
    category: Literal["rh", "juridico", "saude", "conflito", "acesso", "outro"],
    summary: str,
    tool_context: ToolContext,
    urgency: Literal["normal", "alta"] = "normal",
) -> dict:
    """Registra um pedido de ajuda para o buddy humano do colaborador. Use SOMENTE
    depois que o colaborador concordar em ser encaminhado.

    Args:
        category: rh, juridico, saude, conflito, acesso (acesso/ferramenta bloqueada) ou outro.
        summary: 1-2 frases com o assunto, SEM detalhes sensíveis (o buddy conversa
            pessoalmente com o colaborador depois).
        urgency: "alta" só se houver impedimento de trabalhar ou risco; senão "normal".
    """
    catalog = get_catalog()
    user_id = tool_context.user_id
    since = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=1)
    if catalog.count_recent_escalations(user_id, since) >= MAX_PER_DAY:
        return {"ok": False, "error": "limite diário de encaminhamentos atingido; "
                "oriente o colaborador a procurar o buddy diretamente"}

    role_id = tool_context.state.get(K.ROLE_ID)
    role = get_role(role_id) if role_id else None
    assignment = catalog.get_assignment(user_id)
    esc = catalog.create_escalation(
        user_id=user_id,
        role_id=role_id,
        category=category,
        urgency=urgency,
        summary=redact_text(summary.strip())[:500],
        buddy_id=assignment.buddy_id if assignment else None,
    )
    return {
        "ok": True,
        "escalation_id": esc.id,
        "buddy": buddy_info(user_id, role),
        "note": "registrado na lista de pedidos do buddy (ou do responsável, se não houver "
        "buddy atribuído); não há notificação automática, então indique também o contato",
    }
