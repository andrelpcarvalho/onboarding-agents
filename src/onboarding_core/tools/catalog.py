"""Tools de catálogo: trilhas por papel e materiais gerados pelo Curador."""

from __future__ import annotations

from google.adk.tools import ToolContext

from ..quiz_bank import parse_bank, validate_bank
from ..roles import get_role, load_roles
from ..storage import get_catalog
from . import state_keys as K
from .progress import start_module


def list_roles() -> dict:
    """Lista os papéis (trilhas de onboarding) disponíveis."""
    return {
        "roles": [
            {"id": r.id, "title": r.title, "description": r.description}
            for r in load_roles().values()
        ]
    }


def get_learning_path(role_id: str) -> dict:
    """Retorna a trilha completa de um papel: módulos, objetivos, tags da base
    de conhecimento e pré-requisitos.

    Args:
        role_id: id do papel.
    """
    role = get_role(role_id)
    if role is None:
        return {"error": f"papel desconhecido: {role_id}"}
    return role.model_dump()


def get_material(module_id: str, tool_context: ToolContext) -> dict:
    """Busca o material de estudo de um módulo para o papel do colaborador e marca
    o módulo como em andamento. Prefere a versão aprovada; se só houver rascunho,
    retorna com reviewed=False.

    Args:
        module_id: id do módulo.
    """
    role_id = tool_context.state.get(K.ROLE_ID)
    if not role_id:
        return {"found": False, "error": "papel do colaborador não definido"}
    mat = get_catalog().get_latest(role_id, module_id, approved_only=False)
    if mat is None:
        return {"found": False, "role_id": role_id, "module_id": module_id}
    tool_context.state[K.MATERIAL_LOADED] = module_id
    if tool_context.state.get(K.CURRENT_MODULE) != module_id:
        start_module(module_id, tool_context)  # carregar material = abrir o módulo
    return {
        "found": True,
        "reviewed": mat.status == "approved",
        "title": mat.title,
        "version": mat.version,
        "content_md": mat.content_md,
        "sources": mat.sources,
    }


def save_material_draft(
    role_id: str, module_id: str, title: str, sources: list[str], tool_context: ToolContext
) -> dict:
    """Salva como RASCUNHO o material final e o banco de perguntas produzidos pelo
    pipeline do Curador (lidos do estado `draft` e `quiz_bank`, não passe o texto).
    Só é publicado ao colaborador após aprovação humana (scripts/approve.py).

    Args:
        role_id: id do papel.
        module_id: id do módulo.
        title: título curto do material.
        sources: fontes citadas no material, formato "arquivo.md#Seção" (sem colchetes).
    """
    role = get_role(role_id)
    if role is None or role.module(module_id) is None:
        return {"ok": False, "error": "role_id/module_id inválidos"}
    if not sources:
        return {"ok": False, "error": "material sem fontes não pode ser salvo"}
    content = (tool_context.state.get("draft") or "").strip()
    if not content:
        return {"ok": False, "error": "não há material final no estado `draft`"}
    try:
        quiz = parse_bank(tool_context.state.get("quiz_bank"))
    except (ValueError, TypeError) as e:
        return {"ok": False, "error": f"banco de perguntas ilegível: {e}"}
    if err := validate_bank(quiz):
        return {"ok": False, "error": f"banco de perguntas inválido: {err}"}
    sources = [s.strip().strip("[]") for s in sources]
    mat = get_catalog().save_draft(role_id, module_id, title, content, sources, quiz=quiz)
    return {"ok": True, "material_id": mat.id, "version": mat.version, "status": mat.status,
            "quiz_questions": len(mat.quiz)}
