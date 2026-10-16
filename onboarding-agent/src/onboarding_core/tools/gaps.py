"""Backlog de lacunas: perguntas que o Tutor não conseguiu responder com o
material disponível. É o canal de feedback Tutor -> Curador."""

from __future__ import annotations

from google.adk.tools import ToolContext

from ..pii import redact_text
from ..storage import get_catalog
from . import state_keys as K


def log_gap(question: str, tool_context: ToolContext, module_id: str | None = None) -> dict:
    """Registra uma pergunta do colaborador que não pôde ser respondida com o
    material ou a base de conhecimento.

    Args:
        question: a pergunta, reescrita de forma clara e sem dados pessoais.
        module_id: módulo relacionado, se houver.
    """
    gap = get_catalog().log_gap(
        user_id=tool_context.user_id,
        question=redact_text(question),
        role_id=tool_context.state.get(K.ROLE_ID),
        module_id=module_id or tool_context.state.get(K.CURRENT_MODULE),
    )
    return {"ok": True, "gap_id": gap.id}


def list_open_gaps(role_id: str | None = None) -> dict:
    """Lista lacunas abertas reportadas pelo Tutor, opcionalmente filtradas por papel.

    Args:
        role_id: filtra por papel (opcional).
    """
    gaps = get_catalog().list_open_gaps(role_id)
    return {
        "gaps": [
            {"id": g.id, "role_id": g.role_id, "module_id": g.module_id, "question": g.question}
            for g in gaps
        ]
    }
