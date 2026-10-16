"""Regras de progresso (funções puras sobre o dict de perfil; sem LLM, sem framework)."""

from __future__ import annotations

from collections.abc import MutableMapping
from datetime import UTC, datetime
from typing import Any

from .config import PASS_SCORE
from .quiz_view import public_quiz_view
from .roles import get_role
from .schemas import ModuleProgress, Role
from .storage import get_catalog


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def buddy_info(user_id: str | None, role: Role | None) -> dict:
    """Buddy do tutorado: o atribuído pelo responsável ou, na falta, o canal do papel."""
    a = get_catalog().get_assignment(user_id) if user_id else None
    if a:
        return {"assigned": True, "name": a.buddy_name, "contact": a.buddy_contact}
    return {"assigned": False, "name": None,
            "contact": role.buddy_contact if role else None,
            "note": "sem buddy individual atribuído; use o canal geral do papel"}


def snapshot(profile: dict[str, Any], user_id: str | None = None) -> dict:
    """Resumo injetado no prompt do Tutor a cada chamada (sem gabarito)."""
    role_id = profile.get("role_id")
    if not role_id or (role := get_role(role_id)) is None:
        return {"role_id": None, "hint": "Papel ainda não definido. Pergunte e use set_my_role.",
                "buddy": buddy_info(user_id, None)}
    progress = dict(profile.get("progress") or {})
    modules, next_module, to_review = [], None, []
    for m in role.modules:
        p = ModuleProgress.model_validate(progress.get(m.id, {}))
        prereqs_ok = all(progress.get(pid, {}).get("status") == "done" for pid in m.prerequisites)
        modules.append({"id": m.id, "title": m.title, "status": p.status, "score": p.score})
        if p.status == "done" and p.score is not None and p.score < PASS_SCORE:
            to_review.append(m.id)
        if next_module is None and p.status != "done" and prereqs_ok:
            next_module = m.id
    done = sum(1 for m in modules if m["status"] == "done")
    quiz = profile.get("quiz")
    return {
        "role_id": role_id,
        "role": role.title,
        "buddy": buddy_info(user_id, role),
        "quiz_in_progress": public_quiz_view(quiz) if quiz else None,
        "completed": f"{done}/{len(modules)}",
        "current_module": profile.get("current_module"),
        "next_module": next_module,
        "to_review": to_review,
        "modules": modules,
    }


def start_module(module_id: str, profile: MutableMapping[str, Any]) -> dict:
    role = get_role(profile.get("role_id") or "")
    if role is None or role.module(module_id) is None:
        return {"ok": False, "error": "módulo não pertence à trilha do colaborador"}
    progress = dict(profile.get("progress") or {})
    p = ModuleProgress.model_validate(progress.get(module_id, {}))
    if p.status != "done":
        p.status = "in_progress"
    p.updated_at = now()
    progress[module_id] = p.model_dump()
    profile["progress"] = progress
    profile["current_module"] = module_id
    return {"ok": True}


def record_completion(module_id: str, score: float, profile: MutableMapping[str, Any]) -> dict:
    """Só o quiz chama, com a nota calculada por código. Nunca exposto ao modelo."""
    role = get_role(profile.get("role_id") or "")
    if role is None or role.module(module_id) is None:
        return {"ok": False, "error": "módulo não pertence à trilha do colaborador"}
    score = max(0.0, min(1.0, float(score)))
    progress = dict(profile.get("progress") or {})
    p = ModuleProgress.model_validate(progress.get(module_id, {}))
    p.status, p.attempts, p.updated_at = "done", p.attempts + 1, now()
    p.score = score if p.score is None else max(p.score, score)
    progress[module_id] = p.model_dump()
    profile["progress"] = progress
    profile["current_module"] = None
    return {"ok": True, "score": p.score, "needs_review": p.score < PASS_SCORE}
