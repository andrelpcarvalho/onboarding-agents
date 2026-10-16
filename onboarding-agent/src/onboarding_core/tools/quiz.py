"""Quiz de checagem com perguntas aprovadas e nota calculada por código.

- As perguntas vêm do banco do material (gerado pelo Curador e APROVADO por um
  revisor junto com o conteúdo). O modelo não cria perguntas nem vê o gabarito.
- `start_quiz` sorteia QUIZ_SIZE perguntas do banco; não dá para recriar o quiz
  enquanto ele estiver em andamento.
- `answer_quiz` não recebe argumentos: a resposta é lida da última mensagem do
  colaborador, então o modelo não escolhe a alternativa por ele.
- A nota é acertos/total, gravada por `record_completion` (não exposto ao modelo).
"""

from __future__ import annotations

import os
import random
import re
import unicodedata
from typing import Any

from google.adk.tools import ToolContext

from ..quiz_bank import QUIZ_SIZE, validate_bank
from ..storage import get_catalog
from . import state_keys as K
from .progress import record_completion
from .quiz_view import LETTERS, question_view, quiz_question

_LETTER_RE = re.compile(
    r"^\s*(?:(?:letra|alternativa|opcao|resposta)\s*[:\-]?\s*)?\(?([a-d])\)?\s*[.)!]*\s*$"
)


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    return "".join(c for c in s if not unicodedata.combining(c)).strip()


def _rng() -> random.Random:
    # Semente fixa só para evals/testes reproduzíveis (ONBOARDING_QUIZ_SEED).
    seed = os.getenv("ONBOARDING_QUIZ_SEED")
    return random.Random(int(seed)) if seed else random.Random()


def _last_user_message(tool_context: ToolContext) -> tuple[str | None, str]:
    for ev in reversed(tool_context.session.events):
        if ev.author == "user" and ev.content and ev.content.parts:
            return ev.id, "".join(p.text or "" for p in ev.content.parts)
    return None, ""


def parse_choice(text: str, options: list[str]) -> int | None:
    """'B', 'b)', 'letra c', 'alternativa D' ou o texto exato de uma alternativa."""
    t = _norm(text)
    if m := _LETTER_RE.match(t):
        return LETTERS.lower().index(m.group(1))
    for i, opt in enumerate(options):
        if t == _norm(opt):
            return i
    return None


def start_quiz(module_id: str, tool_context: ToolContext) -> dict:
    """Inicia o quiz de checagem do módulo, sorteando perguntas do banco aprovado.
    Apresente ao colaborador SOMENTE a pergunta retornada em `present`, com as letras A-D.

    Args:
        module_id: id do módulo cujo material foi carregado com get_material.
    """
    state = tool_context.state
    if (active := state.get(K.QUIZ)) is not None:
        return {
            "ok": False,
            "error": "já existe um quiz em andamento; não é possível recriá-lo",
            "next_step": "reapresente a pergunta atual (`current`) e aguarde a resposta",
            "current": question_view(active),
        }
    if state.get(K.MATERIAL_LOADED) != module_id or state.get(K.CURRENT_MODULE) != module_id:
        return {"ok": False, "error": "material não carregado",
                "next_step": f"chame get_material('{module_id}') AGORA e depois start_quiz de "
                "novo, sem perguntar ao colaborador"}

    mat = get_catalog().get_latest(state.get(K.ROLE_ID) or "", module_id, approved_only=False)
    if mat is None or validate_bank(mat.quiz):
        return {"ok": False, "error": "este módulo ainda não tem banco de perguntas",
                "next_step": "avise o colaborador que o quiz deste módulo ainda não está "
                "disponível (o time de conteúdo vai completar) e ofereça seguir para o próximo"}

    picks = _rng().sample(range(len(mat.quiz)), QUIZ_SIZE)
    quiz: dict[str, Any] = {
        "module_id": module_id,
        "material_id": mat.id,
        "reviewed": mat.status == "approved",
        "picks": picks,
        "index": 0,
        "correct": 0,
        # Só conta respostas dadas DEPOIS que a pergunta foi apresentada.
        "answered_event_ids": [_last_user_message(tool_context)[0]],
    }
    state[K.QUIZ] = quiz
    return {"ok": True, "reviewed": quiz["reviewed"], "present": question_view(quiz)}


def answer_quiz(tool_context: ToolContext) -> dict:
    """Corrige a resposta do colaborador para a pergunta atual do quiz. Não recebe
    argumentos: a resposta é lida da última mensagem dele (A, B, C, D ou o texto
    exato da alternativa). Chame logo após ele responder."""
    state = tool_context.state
    quiz = state.get(K.QUIZ)
    if quiz is None:
        return {"ok": False, "error": "não há quiz em andamento"}
    q = quiz_question(quiz)
    if q is None:
        state[K.QUIZ] = None
        return {"ok": False, "error": "o material deste quiz não existe mais; quiz cancelado",
                "next_step": "ofereça iniciar o quiz de novo"}

    event_id, text = _last_user_message(tool_context)
    if event_id in quiz["answered_event_ids"]:
        return {"ok": False, "error": "aguarde a resposta do colaborador a esta pergunta",
                "current": question_view(quiz)}
    choice = parse_choice(text, q.options)
    if choice is None:
        return {"ok": False,
                "error": "resposta não reconhecida: peça para responder só com A, B, C ou D",
                "current": question_view(quiz)}

    quiz = {**quiz, "answered_event_ids": [*quiz["answered_event_ids"], event_id]}
    is_correct = choice == q.correct_option
    quiz["correct"] += int(is_correct)
    feedback = {
        "was_correct": is_correct,
        "chosen": LETTERS[choice],
        "correct_answer": f"{LETTERS[q.correct_option]}) {q.options[q.correct_option]}",
        "explanation": q.explanation,
    }
    quiz["index"] += 1
    if quiz["index"] < len(quiz["picks"]):
        state[K.QUIZ] = quiz
        return {"ok": True, "feedback": feedback, "next": question_view(quiz)}

    total = len(quiz["picks"])
    state[K.QUIZ] = None
    result = record_completion(quiz["module_id"], quiz["correct"] / total, state)
    return {"ok": True, "feedback": feedback, "finished": True,
            "correct": quiz["correct"], "total": total, **result}
