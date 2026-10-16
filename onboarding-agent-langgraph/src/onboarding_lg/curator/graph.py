"""Curador como StateGraph explícito.

    START → gather → plan → write → review ─┬─(aprovado ou 3 rodadas)→ quiz → publish → END
                                            └─(reprovado)→ review (com o texto corrigido)

Diferenças em relação à versão ADK (SequentialAgent + LoopAgent + 5 LlmAgents):
- `gather` e `publish` são nós de código, sem LLM: buscar contexto e salvar o
  rascunho são operações determinísticas. Na versão ADK o planner buscava via tool
  calling e um LlmAgent "publisher" transcrevia os dados para a tool de salvar.
- O loop de revisão é uma aresta condicional com contador no estado, no lugar do
  LoopAgent + exit_loop + callback que copiava a resposta para `draft`.
- O revisor recebe os TRECHOS ORIGINAIS da base (não só o roteiro) e devolve saída
  estruturada (approved / issues / corrected_draft).
"""

from __future__ import annotations

import re
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from .. import config, kb
from ..prompts import CURATOR_PLANNER, CURATOR_QUIZ_WRITER, CURATOR_REVIEWER, CURATOR_WRITER
from ..quiz_bank import parse_bank, validate_bank
from ..roles import get_role
from ..schemas import QuizBank
from ..storage import get_catalog

MAX_REVIEW_ROUNDS = 3
_SOURCE_RE = re.compile(r"\[([^\[\]]+?\.md#[^\[\]]+?)\]")


class CuratorState(TypedDict, total=False):
    role_id: str
    module_id: str
    feedback: str | None
    module: str          # descrição do módulo (objetivos, tags)
    sources: str         # trechos da base, com a fonte de cada um
    gaps: str
    outline: str
    draft: str
    review_round: int
    review_issues: list[str]
    approved: bool
    quiz_bank: dict
    result: dict
    error: str


class Review(BaseModel):
    approved: bool = Field(description="true só se todos os critérios forem atendidos")
    issues: list[str] = Field(default_factory=list, description="problemas encontrados")
    corrected_draft: str = Field(default="", description="material completo corrigido, se reprovado")


def _text(msg: Any) -> str:
    return str(msg.text).strip()  # normaliza conteúdo em blocos (thinking do Gemini)


# ------------------------------------------------------------------------------ nós


def gather(state: CuratorState) -> CuratorState:
    """Determinístico: valida o módulo e junta objetivos, trechos da base e lacunas."""
    role = get_role(state["role_id"])
    module = role.module(state["module_id"]) if role else None
    if module is None:
        return {"error": f"role_id/module_id inválidos: {state['role_id']}/{state['module_id']}"}
    seen, chunks = set(), []
    for query in [" ".join(module.kb_tags), *module.kb_tags, *module.objectives]:
        for r in kb.search(query, top_k=4):
            if r["source"] not in seen:
                seen.add(r["source"])
                chunks.append(f"[{r['source']}]\n{r['text']}")
    gaps = [g.question for g in get_catalog().list_open_gaps(role.id) if g.module_id == module.id]
    return {
        "module": (f"role_id={role.id} module_id={module.id}\ntítulo: {module.title}\n"
                   "objetivos:\n" + "\n".join(f"- {o}" for o in module.objectives)),
        "sources": "\n\n".join(chunks) or "(nenhum trecho encontrado)",
        "gaps": "\n".join(f"- {q}" for q in gaps) or "(nenhuma)",
        "review_round": 0,
    }


def plan(state: CuratorState) -> CuratorState:
    feedback = (f"AJUSTES PEDIDOS PELO REVISOR (obrigatórios)\n{state['feedback']}\n"
                if state.get("feedback") else "")
    prompt = CURATOR_PLANNER.format(module=state["module"], sources=state["sources"],
                                    gaps=state["gaps"], feedback=feedback)
    return {"outline": _text(config.llm("curator").invoke(prompt))}


def write(state: CuratorState) -> CuratorState:
    return {"draft": _text(config.llm("curator").invoke(CURATOR_WRITER.format(outline=state["outline"])))}


def review(state: CuratorState) -> CuratorState:
    reviewer = config.llm("reviewer").with_structured_output(Review)
    r: Review = reviewer.invoke(CURATOR_REVIEWER.format(
        sources=state["sources"], outline=state["outline"], draft=state["draft"]))
    update: CuratorState = {"review_round": state.get("review_round", 0) + 1,
                            "approved": r.approved, "review_issues": r.issues}
    if not r.approved and r.corrected_draft.strip():
        update["draft"] = r.corrected_draft.strip()
    return update


def after_review(state: CuratorState) -> str:
    if state.get("approved") or state.get("review_round", 0) >= MAX_REVIEW_ROUNDS:
        return "quiz"
    return "review"


def quiz(state: CuratorState) -> CuratorState:
    writer = config.llm("curator").with_structured_output(QuizBank)
    bank: QuizBank = writer.invoke(CURATOR_QUIZ_WRITER.format(outline=state["outline"],
                                                              draft=state["draft"]))
    return {"quiz_bank": bank.model_dump()}


def publish(state: CuratorState) -> CuratorState:
    """Determinístico: extrai as fontes do texto, valida o banco e salva o rascunho."""
    draft = state["draft"]
    valid = kb.valid_sources()
    cited = list(dict.fromkeys(s.strip() for s in _SOURCE_RE.findall(draft)))
    sources = [s for s in cited if s in valid]
    if not sources:
        return {"error": "material sem nenhuma fonte válida; não foi salvo",
                "result": {"ok": False, "cited": cited}}
    bank = parse_bank(state.get("quiz_bank"))
    if err := validate_bank(bank):
        return {"error": f"banco de perguntas inválido: {err}", "result": {"ok": False}}
    title_line = next((ln for ln in draft.splitlines() if ln.startswith("# ")), "")
    role = get_role(state["role_id"])
    title = title_line[2:].strip() or role.module(state["module_id"]).title
    note = None if state.get("approved") else (
        f"revisão automática não aprovou após {state.get('review_round')} rodadas: "
        + "; ".join(state.get("review_issues") or [])[:400])
    mat = get_catalog().save_draft(state["role_id"], state["module_id"], title, draft, sources,
                                   review_note=note, quiz=bank)
    return {"result": {"ok": True, "material_id": mat.id, "version": mat.version,
                       "quiz_questions": len(bank), "invalid_citations": [c for c in cited if c not in valid],
                       "auto_review_approved": bool(state.get("approved"))}}


def _stop_on_error(next_node: str):
    def route(state: CuratorState) -> str:
        return END if state.get("error") else next_node
    return route


def build_curator_graph():
    g = StateGraph(CuratorState)
    for name, fn in [("gather", gather), ("plan", plan), ("write", write), ("review", review),
                     ("quiz", quiz), ("publish", publish)]:
        g.add_node(name, fn)
    g.add_edge(START, "gather")
    g.add_conditional_edges("gather", _stop_on_error("plan"), ["plan", END])
    g.add_edge("plan", "write")
    g.add_edge("write", "review")
    g.add_conditional_edges("review", after_review, ["review", "quiz"])
    g.add_edge("quiz", "publish")
    g.add_edge("publish", END)
    return g.compile()


def curate(role_id: str, module_id: str, feedback: str | None = None) -> dict:
    """Roda o Curador para um módulo e devolve o resultado (material_id ou erro)."""
    out = build_curator_graph().invoke(
        {"role_id": role_id, "module_id": module_id, "feedback": feedback})
    return out.get("result") or {"ok": False, "error": out.get("error")}
