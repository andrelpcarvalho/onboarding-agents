"""Progresso dos tutorados para buddy e responsável (lê o Store, sem LLM)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from . import memory, profile
from .progress import snapshot
from .schemas import Escalation


@dataclass
class TuteeStatus:
    user_id: str
    role: str | None
    completed: str
    next_module: str | None
    to_review: list[str]
    quiz_module: str | None
    last_seen: datetime | None


def tutee_status(store, user_id: str) -> TuteeStatus:
    prof = profile.load(store, user_id)
    snap = snapshot(prof) if prof else {}
    seen = memory.last_seen(store, user_id)
    quiz = prof.get("quiz")
    return TuteeStatus(
        user_id=user_id, role=snap.get("role"), completed=snap.get("completed", "-"),
        next_module=snap.get("next_module"), to_review=snap.get("to_review", []),
        quiz_module=quiz["module_id"] if quiz else None,
        last_seen=datetime.fromisoformat(seen).astimezone() if seen else None,
    )


CATEGORY = {"rh": "RH", "juridico": "Jurídico", "saude": "Saúde", "conflito": "Conflito",
            "acesso": "Acesso", "outro": "Outro"}


def request_row(e: Escalation) -> str:
    flag = "URGENTE " if e.urgency == "alta" else ""
    status = "" if e.status == "open" else f"  [fechado por {e.closed_by}: {e.close_note}]"
    when = e.created_at.replace(tzinfo=UTC).astimezone()
    return (f"#{e.id:<4} {flag}{CATEGORY[e.category]:<9} {e.user_id:<18} "
            f"{when:%d/%m %H:%M}  {e.summary}{status}")
