"""Visão do quiz sem gabarito (o que pode ser mostrado ao modelo e ao colaborador).

O estado do quiz guarda só referências (material_id + índices sorteados); as
perguntas e o gabarito vivem no catálogo e nunca passam pelo modelo.
"""

from __future__ import annotations

from typing import Any

from ..schemas import QuizQuestion
from ..storage import get_catalog

LETTERS = "ABCD"


def quiz_question(quiz: dict[str, Any], position: int | None = None) -> QuizQuestion | None:
    mat = get_catalog().get(quiz["material_id"])
    if mat is None:
        return None
    idx = quiz["picks"][quiz["index"] if position is None else position]
    return mat.quiz[idx] if idx < len(mat.quiz) else None


def question_view(quiz: dict[str, Any]) -> dict[str, Any]:
    q = quiz_question(quiz)
    if q is None:
        return {"error": "pergunta indisponível"}
    return {
        "question_number": quiz["index"] + 1,
        "total": len(quiz["picks"]),
        "question": q.question,
        "options": {LETTERS[i]: opt for i, opt in enumerate(q.options)},
    }


def public_quiz_view(quiz: dict[str, Any]) -> dict[str, Any]:
    return {"module_id": quiz["module_id"], "current": question_view(quiz)}
