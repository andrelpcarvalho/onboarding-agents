"""Regras do banco de perguntas de um material (validado ao salvar e ao aprovar)."""

from __future__ import annotations

import unicodedata
from collections.abc import Iterable
from typing import Any

from .schemas import QuizQuestion

QUIZ_SIZE = 3       # perguntas sorteadas por tentativa
MIN_BANK = 4        # banco maior que o quiz => retentativas variam
MAX_BANK = 8


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    return "".join(c for c in s if not unicodedata.combining(c)).strip()


def parse_bank(raw: Any) -> list[QuizQuestion]:
    """Aceita lista de QuizQuestion/dicts, um QuizBank (dict) ou JSON em texto."""
    if isinstance(raw, str):
        import json

        raw = json.loads(raw)
    if isinstance(raw, dict):
        raw = raw.get("questions", [])
    return [QuizQuestion.model_validate(q) for q in (raw or [])]


def validate_bank(questions: Iterable[QuizQuestion]) -> str | None:
    """Retorna a mensagem de erro, ou None se o banco é válido."""
    qs = list(questions)
    if not (MIN_BANK <= len(qs) <= MAX_BANK):
        return f"o banco precisa ter de {MIN_BANK} a {MAX_BANK} perguntas (tem {len(qs)})"
    seen = set()
    for i, q in enumerate(qs, 1):
        if not q.question.strip():
            return f"pergunta {i} sem enunciado"
        if _norm(q.question) in seen:
            return f"pergunta {i} repetida"
        seen.add(_norm(q.question))
        if len(q.options) != 4 or any(not o.strip() for o in q.options):
            return f"pergunta {i}: são necessárias exatamente 4 alternativas não vazias"
        if len({_norm(o) for o in q.options}) != 4:
            return f"pergunta {i}: alternativas repetidas"
        if q.correct_option not in range(4):
            return f"pergunta {i}: correct_option deve ser 0, 1, 2 ou 3"
    return None
