"""Tools do Tutor em LangGraph.

Mesmas regras da versão ADK. O que muda é o acesso ao contexto:
- ADK: `tool_context.state["user:..."]` e `tool_context.user_id`
- LangGraph: `runtime.store` (perfil por usuário), `runtime.context.user_id` e
  `runtime.state["messages"]` (mensagens da thread). O parâmetro `runtime` é
  injetado pelo ToolNode e não aparece no schema que o modelo vê.
"""

from __future__ import annotations

import os
import random
import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from langchain_core.tools import tool
from langgraph.prebuilt import ToolRuntime

from .. import kb, profile
from ..pii import redact_text
from ..progress import buddy_info, record_completion, start_module
from ..quiz_bank import QUIZ_SIZE, validate_bank
from ..quiz_view import LETTERS, question_view, quiz_question
from ..roles import get_role, load_roles
from ..storage import get_catalog

MAX_ESCALATIONS_PER_DAY = 3


@dataclass
class TutorContext:
    """Contexto de execução (LangGraph `context_schema`): quem está conversando."""

    user_id: str


def _profile(runtime: ToolRuntime[TutorContext]) -> tuple[str, dict[str, Any]]:
    uid = runtime.context.user_id
    return uid, profile.load(runtime.store, uid)


def _save(runtime: ToolRuntime[TutorContext], prof: dict[str, Any]) -> None:
    profile.save(runtime.store, runtime.context.user_id, prof)


# ------------------------------------------------------------------ papel e material


@tool
def set_my_role(role_id: str, runtime: ToolRuntime[TutorContext]) -> dict:
    """Define o papel (trilha) do colaborador.

    Args:
        role_id: id do papel, ex. "dev_salesforce" (veja available_roles no contexto).
    """
    role = get_role(role_id)
    if role is None:
        return {"ok": False, "error": f"papel desconhecido: {role_id}",
                "valid_roles": sorted(load_roles())}
    _, prof = _profile(runtime)
    prof["role_id"] = role_id
    _save(runtime, prof)
    return {"ok": True, "role": role.title, "modules": len(role.modules)}


@tool
def get_material(module_id: str, runtime: ToolRuntime[TutorContext]) -> dict:
    """Busca o material de estudo de um módulo para o papel do colaborador e marca o
    módulo como em andamento. Prefere a versão aprovada; rascunho vem com reviewed=False.

    Args:
        module_id: id do módulo.
    """
    _, prof = _profile(runtime)
    role_id = prof.get("role_id")
    if not role_id:
        return {"found": False, "error": "papel do colaborador não definido"}
    mat = get_catalog().get_latest(role_id, module_id, approved_only=False)
    if mat is None:
        return {"found": False, "role_id": role_id, "module_id": module_id}
    prof["material_loaded"] = module_id
    if prof.get("current_module") != module_id:
        start_module(module_id, prof)
    _save(runtime, prof)
    return {"found": True, "reviewed": mat.status == "approved", "title": mat.title,
            "version": mat.version, "content_md": mat.content_md, "sources": mat.sources}


# ------------------------------------------------------------------------------ quiz

_LETTER_RE = re.compile(
    r"^\s*(?:(?:letra|alternativa|opcao|resposta)\s*[:\-]?\s*)?\(?([a-d])\)?\s*[.)!]*\s*$"
)


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    return "".join(c for c in s if not unicodedata.combining(c)).strip()


def parse_choice(text: str, options: list[str]) -> int | None:
    """'B', 'b)', 'letra c', 'alternativa D' ou o texto exato de uma alternativa."""
    t = _norm(text)
    if m := _LETTER_RE.match(t):
        return LETTERS.lower().index(m.group(1))
    for i, opt in enumerate(options):
        if t == _norm(opt):
            return i
    return None


def _last_human(runtime: ToolRuntime[TutorContext]) -> tuple[str | None, str]:
    for m in reversed(runtime.state["messages"]):
        if m.type == "human":
            return m.id, str(m.text)
    return None, ""


def _rng() -> random.Random:
    seed = os.getenv("ONBOARDING_QUIZ_SEED")  # só para evals/testes reproduzíveis
    return random.Random(int(seed)) if seed else random.Random()


@tool
def start_quiz(module_id: str, runtime: ToolRuntime[TutorContext]) -> dict:
    """Inicia o quiz do módulo, sorteando perguntas do banco aprovado. Mostre ao
    colaborador SOMENTE a pergunta retornada em `present`, com as letras A-D.

    Args:
        module_id: id do módulo cujo material foi carregado com get_material.
    """
    _, prof = _profile(runtime)
    if (active := prof.get("quiz")) is not None:
        return {"ok": False, "error": "já existe um quiz em andamento; não é possível recriá-lo",
                "next_step": "reapresente a pergunta atual (`current`) e aguarde a resposta",
                "current": question_view(active)}
    if prof.get("material_loaded") != module_id or prof.get("current_module") != module_id:
        return {"ok": False, "error": "material não carregado",
                "next_step": f"chame get_material('{module_id}') AGORA e depois start_quiz de "
                "novo, sem perguntar ao colaborador"}
    mat = get_catalog().get_latest(prof.get("role_id") or "", module_id, approved_only=False)
    if mat is None or validate_bank(mat.quiz):
        return {"ok": False, "error": "este módulo ainda não tem banco de perguntas",
                "next_step": "avise que o quiz deste módulo ainda não está disponível e "
                "ofereça seguir para o próximo"}
    quiz = {
        "module_id": module_id, "material_id": mat.id, "reviewed": mat.status == "approved",
        "picks": _rng().sample(range(len(mat.quiz)), QUIZ_SIZE), "index": 0, "correct": 0,
        # só conta respostas dadas DEPOIS que a pergunta foi apresentada
        "answered_message_ids": [_last_human(runtime)[0]],
    }
    prof["quiz"] = quiz
    _save(runtime, prof)
    return {"ok": True, "reviewed": quiz["reviewed"], "present": question_view(quiz)}


def grade_answer(prof: dict[str, Any], msg_id: str | None, text: str) -> dict:
    """Corrige `text` contra a pergunta atual do quiz e atualiza `prof` (sem salvar).

    Usada pela tool `answer_quiz` e pelo nó `quiz_gate` do grafo, que corrige a
    mensagem ANTES de o modelo rodar (assim a correção não depende do modelo chamar
    a tool).
    """
    quiz = prof.get("quiz")
    if quiz is None:
        return {"ok": False, "error": "não há quiz em andamento"}
    q = quiz_question(quiz)
    if q is None:
        prof["quiz"] = None
        return {"ok": False, "error": "o material deste quiz não existe mais; quiz cancelado"}
    if msg_id in quiz["answered_message_ids"]:
        return {"ok": False, "error": "aguarde a resposta do colaborador a esta pergunta",
                "current": question_view(quiz)}
    choice = parse_choice(text, q.options)
    if choice is None:
        return {"ok": False,
                "error": "resposta não reconhecida: peça para responder só com A, B, C ou D",
                "current": question_view(quiz)}
    quiz = {**quiz, "answered_message_ids": [*quiz["answered_message_ids"], msg_id]}
    is_correct = choice == q.correct_option
    quiz["correct"] += int(is_correct)
    feedback = {"was_correct": is_correct, "chosen": LETTERS[choice],
                "correct_answer": f"{LETTERS[q.correct_option]}) {q.options[q.correct_option]}",
                "explanation": q.explanation}
    quiz["index"] += 1
    if quiz["index"] < len(quiz["picks"]):
        prof["quiz"] = quiz
        return {"ok": True, "feedback": feedback, "next": question_view(quiz)}
    total = len(quiz["picks"])
    prof["quiz"] = None
    result = record_completion(quiz["module_id"], quiz["correct"] / total, prof)
    return {"ok": True, "feedback": feedback, "finished": True,
            "correct": quiz["correct"], "total": total, **result}


@tool
def answer_quiz(runtime: ToolRuntime[TutorContext]) -> dict:
    """Corrige a resposta do colaborador para a pergunta atual do quiz. Sem argumentos:
    a resposta é lida da última mensagem dele (A, B, C, D ou o texto exato da alternativa)."""
    _, prof = _profile(runtime)
    msg_id, text = _last_human(runtime)
    result = grade_answer(prof, msg_id, text)
    _save(runtime, prof)
    return result


# ----------------------------------------------------------------- base e lacunas


@tool
def search_knowledge_base(question: str, runtime: ToolRuntime[TutorContext]) -> dict:
    """Busca na base oficial a resposta para uma dúvida do colaborador. Cada resultado
    traz `cite` ([arquivo.md#Seção]), que DEVE aparecer na resposta. Se nada for
    encontrado, a dúvida é registrada automaticamente (`gap_registered`).

    Args:
        question: a dúvida do colaborador, em linguagem natural.
    """
    results = kb.search(question)
    if results:
        return {"found": True, "results": [{**r, "cite": f"[{r['source']}]"} for r in results]}
    uid, prof = _profile(runtime)
    gap = get_catalog().log_gap(uid, redact_text(question), prof.get("role_id"),
                                prof.get("current_module"))
    return {"found": False, "gap_registered": gap.id,
            "instruction": "diga que não tem essa informação, NÃO invente, e avise que a "
            "dúvida foi registrada para o time de conteúdo"}


@tool
def log_gap(question: str, runtime: ToolRuntime[TutorContext], module_id: str | None = None) -> dict:
    """Registra uma dúvida que os trechos encontrados na base não respondem.

    Args:
        question: a pergunta, reescrita de forma clara e sem dados pessoais.
        module_id: módulo relacionado, se houver.
    """
    uid, prof = _profile(runtime)
    gap = get_catalog().log_gap(uid, redact_text(question), prof.get("role_id"),
                                module_id or prof.get("current_module"))
    return {"ok": True, "gap_id": gap.id}


# ---------------------------------------------------------------------------- buddy


@tool
def escalate_to_buddy(
    category: Literal["rh", "juridico", "saude", "conflito", "acesso", "outro"],
    summary: str,
    runtime: ToolRuntime[TutorContext],
    urgency: Literal["normal", "alta"] = "normal",
) -> dict:
    """Registra um pedido de ajuda para o buddy humano do colaborador. Use SOMENTE
    depois que o colaborador concordar em ser encaminhado.

    Args:
        category: rh, juridico, saude, conflito, acesso (acesso bloqueado) ou outro.
        summary: 1-2 frases com o assunto, SEM detalhes sensíveis.
        urgency: "alta" só se houver impedimento de trabalhar ou risco; senão "normal".
    """
    catalog = get_catalog()
    uid, prof = _profile(runtime)
    since = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=1)
    if catalog.count_recent_escalations(uid, since) >= MAX_ESCALATIONS_PER_DAY:
        return {"ok": False, "error": "limite diário de encaminhamentos atingido; "
                "oriente o colaborador a procurar o buddy diretamente"}
    role = get_role(prof.get("role_id") or "")
    assignment = catalog.get_assignment(uid)
    esc = catalog.create_escalation(
        user_id=uid, role_id=prof.get("role_id"), category=category, urgency=urgency,
        summary=redact_text(summary.strip())[:500],
        buddy_id=assignment.buddy_id if assignment else None,
    )
    return {"ok": True, "escalation_id": esc.id, "buddy": buddy_info(uid, role),
            "note": "registrado na lista de pedidos do buddy; não há notificação automática, "
            "então indique também o contato"}


TUTOR_TOOLS = [set_my_role, get_material, start_quiz, answer_quiz, search_knowledge_base,
               log_gap, escalate_to_buddy]
