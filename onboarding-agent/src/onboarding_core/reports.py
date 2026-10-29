"""Leitura do progresso dos tutorados para buddy e responsável (sem LLM)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from google.adk.sessions.sqlite_session_service import SqliteSessionService

from .config import APP_NAME, SESSIONS_DB
from .schemas import Escalation
from .tools import state_keys as K
from .tools.progress import progress_snapshot, sync_role


@dataclass
class TuteeStatus:
    user_id: str
    role: str | None
    completed: str
    next_module: str | None
    to_review: list[str]
    quiz_module: str | None
    last_seen: datetime | None
    # mission_id -> {"status", "evidence"}; evidências sem o CPF de teste
    missions: dict[str, dict] = field(default_factory=dict)


async def known_users() -> list[str]:
    """Todos os userIds que já conversaram com o Tutor."""
    svc = SqliteSessionService(db_path=str(SESSIONS_DB))
    resp = await svc.list_sessions(app_name=APP_NAME)
    return sorted({s.user_id for s in resp.sessions})


async def tutee_status(user_id: str) -> TuteeStatus:
    svc = SqliteSessionService(db_path=str(SESSIONS_DB))
    resp = await svc.list_sessions(app_name=APP_NAME, user_id=user_id)
    if not resp.sessions:
        state: dict = {}
        sync_role(state, user_id)
        snap = progress_snapshot(state)
        return TuteeStatus(user_id, snap.get("role"), snap.get("completed", "-"),
                           snap.get("next_module"), [], None, None)
    latest = max(resp.sessions, key=lambda s: s.last_update_time)
    # get_session mescla o estado `user:*` (progresso) no estado da sessão
    session = await svc.get_session(app_name=APP_NAME, user_id=user_id, session_id=latest.id)
    state = dict(session.state) if session else {}
    # papel = atribuição atual do responsável, mesmo que o tutorado ainda não tenha
    # conversado desde a mudança (o estado da sessão só sincroniza na próxima mensagem)
    sync_role(state, user_id)
    snap = progress_snapshot(state)
    quiz = snap.get("quiz_in_progress")
    missions = {
        mid: {"status": p.get("status"),
              "evidence": {k: v for k, v in p.get("evidence", {}).items() if k != "test_cpf"}}
        for mid, p in (state.get(K.MISSIONS) or {}).items()
    }
    return TuteeStatus(
        user_id=user_id,
        role=snap.get("role"),
        completed=snap.get("completed", "-"),
        next_module=snap.get("next_module"),
        to_review=snap.get("to_review", []),
        quiz_module=quiz["module_id"] if quiz else None,
        last_seen=datetime.fromtimestamp(latest.last_update_time, UTC).astimezone(),
        missions=missions,
    )


CATEGORY = {"rh": "RH", "juridico": "Jurídico", "saude": "Saúde", "conflito": "Conflito",
            "acesso": "Acesso", "outro": "Outro"}


def request_row(e: Escalation) -> str:
    """Uma linha legível de um pedido encaminhado ao buddy."""
    flag = "URGENTE " if e.urgency == "alta" else ""
    status = "" if e.status == "open" else f"  [fechado por {e.closed_by}: {e.close_note}]"
    when = e.created_at.replace(tzinfo=UTC).astimezone()  # gravado em UTC, exibido no fuso local
    return (f"#{e.id:<4} {flag}{CATEGORY[e.category]:<9} {e.user_id:<18} "
            f"{when:%d/%m %H:%M}  {e.summary}{status}")
