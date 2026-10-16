"""Etapas 3 e 4: proposta de trilha (papel + módulos) e validação determinística."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from .kb import KnowledgeBase
from .llm import generate
from .prompts import PROPOSE_TRAIL
from .schemas import Module, Role, RoleProposal

_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def propose_role(kb: KnowledgeBase, role_id: str, role_title: str,
                 role_hint: str | None = None) -> RoleProposal:
    prompt = PROPOSE_TRAIL.format(
        role_title=role_title,
        role_hint=f"CONTEXTO DA FUNÇÃO: {role_hint}" if role_hint else "",
        kb_outline=kb.outline())
    return generate(prompt, schema=RoleProposal)


def finalize_role(proposal: RoleProposal, kb: KnowledgeBase, role_id: str, role_title: str,
                  buddy_contact: str | None) -> tuple[Role, list[str]]:
    """Corrige o que dá para corrigir sem LLM e devolve (papel, avisos para o revisor)."""
    warnings: list[str] = []
    modules: list[Module] = []
    seen: set[str] = set()
    for m in proposal.modules:
        mid = re.sub(r"[^a-z0-9_]", "_", m.id.lower()).strip("_")
        if not _ID_RE.match(mid) or mid in seen:
            warnings.append(f"módulo '{m.id}' com id inválido ou repetido: descartado")
            continue
        tags = [t for t in m.kb_tags if kb.has_term(t)]
        dropped = sorted(set(m.kb_tags) - set(tags))
        if dropped:
            warnings.append(f"{mid}: tags sem resultado na base removidas: {dropped}")
        if not tags and not kb.search(" ".join(m.objectives)):
            warnings.append(f"{mid}: a base não cobre este módulo; descartado")
            continue
        prereqs = [p for p in m.prerequisites if p in seen]
        if len(prereqs) != len(m.prerequisites):
            warnings.append(f"{mid}: pré-requisitos inexistentes ou fora de ordem removidos")
        if not 2 <= len(m.objectives) <= 3:
            warnings.append(f"{mid}: {len(m.objectives)} objetivos (o recomendado é 2 a 3)")
        modules.append(Module(id=mid, title=m.title, objectives=m.objectives,
                              kb_tags=tags or m.kb_tags, prerequisites=prereqs,
                              estimated_minutes=m.estimated_minutes))
        seen.add(mid)
    if not modules:
        raise ValueError("nenhum módulo válido: a base gerada não sustenta uma trilha")
    role = Role(id=role_id, title=role_title, description=proposal.description,
                buddy_contact=buddy_contact or "TODO canal de apoio do papel", modules=modules)
    return role, warnings


def write_role(role: Role, roles_dir: Path) -> Path:
    roles_dir.mkdir(parents=True, exist_ok=True)
    data = role.model_dump(exclude={"seniority"})
    path = roles_dir / f"{role.id}.yaml"
    header = "# Gerado pelo onboarding-curator. Revise objetivos, ordem e buddy_contact.\n"
    path.write_text(header + yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
                    encoding="utf-8")
    return path
