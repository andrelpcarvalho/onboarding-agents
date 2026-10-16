"""Etapa 5: material + banco de perguntas por módulo, salvo como rascunho.

Mesmo desenho do Curador da versão LangGraph: busca de contexto e publicação são
código; o revisor compara o texto com os TRECHOS ORIGINAIS (não só com o roteiro) e
pode reprovar e corrigir em até 3 rodadas.
"""

from __future__ import annotations

import re

from . import config
from .kb import KnowledgeBase
from .llm import generate
from .prompts import PLANNER, QUIZ_WRITER, REVIEWER, WRITER
from .quiz_bank import validate_bank
from .schemas import Module, QuizBank, Review, Role
from .storage import Catalog

MAX_REVIEW_ROUNDS = 3
_SOURCE_RE = re.compile(r"\[([^\[\]]+?\.md#[^\[\]]+?)\]")


def _sources(kb: KnowledgeBase, module: Module) -> str:
    seen, chunks = set(), []
    for query in [" ".join(module.kb_tags), *module.kb_tags, *module.objectives]:
        for r in kb.search(query):
            if r["source"] not in seen:
                seen.add(r["source"])
                chunks.append(f"[{r['source']}]\n{r['text']}")
    return "\n\n".join(chunks)


def curate_module(kb: KnowledgeBase, role: Role, module: Module, catalog: Catalog) -> dict:
    sources = _sources(kb, module)
    if not sources:
        return {"ok": False, "module_id": module.id, "error": "nenhum trecho da base para o módulo"}
    desc = (f"role_id={role.id} module_id={module.id}\ntítulo: {module.title}\nobjetivos:\n"
            + "\n".join(f"- {o}" for o in module.objectives))
    outline = generate(PLANNER.format(module=desc, sources=sources))
    draft = generate(WRITER.format(outline=outline))
    approved, issues, rounds = False, [], 0
    while not approved and rounds < MAX_REVIEW_ROUNDS:
        rounds += 1
        r: Review = generate(REVIEWER.format(sources=sources, outline=outline, draft=draft),
                             schema=Review, model=config.REVIEWER_MODEL)
        approved, issues = r.approved, r.issues
        if not approved and r.corrected_draft.strip():
            draft = r.corrected_draft.strip()
    bank: QuizBank = generate(QUIZ_WRITER.format(outline=outline, draft=draft), schema=QuizBank)

    valid = kb.valid_sources()
    cited = list(dict.fromkeys(s.strip() for s in _SOURCE_RE.findall(draft)))
    srcs = [s for s in cited if s in valid]
    if not srcs:
        return {"ok": False, "module_id": module.id, "error": "material sem fonte válida"}
    if err := validate_bank(bank.questions):
        return {"ok": False, "module_id": module.id, "error": f"banco inválido: {err}"}
    title = next((ln[2:].strip() for ln in draft.splitlines() if ln.startswith("# ")), module.title)
    note = None if approved else (f"revisão automática não aprovou após {rounds} rodadas: "
                                  + "; ".join(issues)[:400])
    mat = catalog.save_draft(role.id, module.id, title, draft, srcs, review_note=note,
                             quiz=bank.questions)
    return {"ok": True, "module_id": module.id, "material_id": mat.id, "version": mat.version,
            "quiz_questions": len(bank.questions), "auto_review_approved": approved,
            "review_rounds": rounds, "invalid_citations": [c for c in cited if c not in valid]}
