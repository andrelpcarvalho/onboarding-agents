"""Tools de progresso do colaborador (gravam no estado `user:` da sessão)."""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from datetime import UTC, datetime
from typing import Any

from google.adk.tools import ToolContext

from ..config import PASS_SCORE
from ..roles import get_role, load_roles
from ..schemas import ModuleProgress, Role
from ..storage import get_catalog
from . import state_keys as K
from .quiz_view import public_quiz_view


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _progress(tool_context: ToolContext) -> dict[str, dict]:
    return dict(tool_context.state.get(K.PROGRESS) or {})


def set_my_role(role_id: str, tool_context: ToolContext) -> dict:
    """Grava o papel no estado. NÃO é exposta ao modelo: o papel vem da atribuição do
    responsável (`sync_role`); fica aqui para scripts e testes.

    Args:
        role_id: id do papel, ex. "dev_salesforce".
    """
    role = get_role(role_id)
    if role is None:
        return {"ok": False, "error": f"papel desconhecido: {role_id}",
                "valid_roles": sorted(load_roles())}
    tool_context.state[K.ROLE_ID] = role_id
    return {"ok": True, "role": role.title, "modules": len(role.modules)}


def sync_role(state: MutableMapping[str, Any], user_id: str | None) -> str | None:
    """Copia para o estado o papel atribuído pelo responsável (identidade vem do host).

    Sem atribuição, o estado fica sem papel: o que o colaborador diz na conversa
    ("sou gerente", "sou dev") nunca define a trilha.
    """
    a = get_catalog().get_role_assignment(user_id) if user_id else None
    role_id = a.role_id if a and get_role(a.role_id) else None
    if state.get(K.ROLE_ID) != role_id:
        state[K.ROLE_ID] = role_id
    return role_id


def buddy_info(user_id: str | None, role: Role | None) -> dict:
    """Buddy do tutorado: o atribuído pelo responsável ou, na falta, o canal do papel."""
    a = get_catalog().get_assignment(user_id) if user_id else None
    if a:
        return {"assigned": True, "name": a.buddy_name, "contact": a.buddy_contact}
    return {"assigned": False, "name": None,
            "contact": role.buddy_contact if role else None,
            "note": "sem buddy individual atribuído; use o canal geral do papel"}


def progress_snapshot(state: Mapping[str, Any], user_id: str | None = None) -> dict:
    """Resumo do progresso a partir do estado da sessão (sem LLM, sem I/O).

    Usado pela tool `get_my_progress` e injetado direto na instrução do Tutor,
    o que evita uma ida e volta ao modelo no início de cada conversa.
    """
    role_id = state.get(K.ROLE_ID)
    if not role_id or (role := get_role(role_id)) is None:
        return {"role_id": None,
                "hint": "Papel ainda não atribuído pelo responsável do onboarding. Não defina o "
                "papel pela conversa: oriente o colaborador a pedir a atribuição ao responsável "
                "ou ao buddy.",
                "buddy": buddy_info(user_id, None)}

    progress = dict(state.get(K.PROGRESS) or {})
    modules, next_module, to_review = [], None, []
    for m in role.modules:
        p = ModuleProgress.model_validate(progress.get(m.id, {}))
        prereqs_ok = all(
            progress.get(pid, {}).get("status") == "done" for pid in m.prerequisites
        )
        modules.append({"id": m.id, "title": m.title, "status": p.status, "score": p.score})
        if p.status == "done" and p.score is not None and p.score < PASS_SCORE:
            to_review.append(m.id)
        if next_module is None and p.status != "done" and prereqs_ok:
            next_module = m.id

    from .missions import missions_overview  # import tardio: missions -> quiz -> progress

    done = sum(1 for m in modules if m["status"] == "done")
    quiz = state.get(K.QUIZ)
    return {
        "role_id": role_id,
        "role": role.title,
        "buddy": buddy_info(user_id, role),
        "quiz_in_progress": public_quiz_view(quiz) if quiz else None,
        "pending_escalation": (
            {k: state[K.PENDING_ESCALATION][k] for k in ("category", "summary")}
            if state.get(K.PENDING_ESCALATION) else None),
        "completed": f"{done}/{len(modules)}",
        "current_module": state.get(K.CURRENT_MODULE),
        "next_module": next_module,
        "to_review": to_review,
        "modules": modules,
        **missions_overview(state),
        "mission_check": state.get(K.MISSION_CHECK),
    }


def get_my_progress(tool_context: ToolContext) -> dict:
    """Retorna o papel, o status de cada módulo da trilha, o próximo módulo
    recomendado e os módulos que precisam de revisão (nota abaixo do mínimo)."""
    return progress_snapshot(tool_context.state, tool_context.user_id)


def start_module(module_id: str, tool_context: ToolContext) -> dict:
    """Marca um módulo da trilha como em andamento.

    Args:
        module_id: id do módulo, conforme get_my_progress.
    """
    role = get_role(tool_context.state.get(K.ROLE_ID) or "")
    if role is None or role.module(module_id) is None:
        return {"ok": False, "error": "módulo não pertence à trilha do colaborador"}
    progress = _progress(tool_context)
    p = ModuleProgress.model_validate(progress.get(module_id, {}))
    if p.status != "done":
        p.status = "in_progress"
    p.updated_at = _now()
    progress[module_id] = p.model_dump()
    tool_context.state[K.PROGRESS] = progress
    tool_context.state[K.CURRENT_MODULE] = module_id
    return {"ok": True, "module": role.module(module_id).model_dump()}  # type: ignore[union-attr]


def record_completion(module_id: str, score: float, state: MutableMapping[str, Any]) -> dict:
    """Registra a conclusão de um módulo. NÃO é uma tool exposta ao modelo: só o
    quiz (tools/quiz.py) chama, com a nota calculada por código."""
    role = get_role(state.get(K.ROLE_ID) or "")
    if role is None or role.module(module_id) is None:
        return {"ok": False, "error": "módulo não pertence à trilha do colaborador"}
    score = max(0.0, min(1.0, float(score)))
    progress = dict(state.get(K.PROGRESS) or {})
    p = ModuleProgress.model_validate(progress.get(module_id, {}))
    p.status, p.attempts, p.updated_at = "done", p.attempts + 1, _now()
    p.score = score if p.score is None else max(p.score, score)
    progress[module_id] = p.model_dump()
    state[K.PROGRESS] = progress
    state[K.CURRENT_MODULE] = None
    return {"ok": True, "score": p.score, "needs_review": p.score < PASS_SCORE}
