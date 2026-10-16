"""Chamadas ao Gemini (google-genai) com saída estruturada."""

from __future__ import annotations

from typing import TypeVar

from google.genai import types
from pydantic import BaseModel

from . import config

T = TypeVar("T", bound=BaseModel)


def generate(prompt: str, *, schema: type[T] | None = None, pdf: bytes | None = None,
             model: str | None = None, thinking_budget: int | None = None) -> T | str:
    parts = [types.Part.from_bytes(data=pdf, mime_type="application/pdf")] if pdf else []
    parts.append(types.Part.from_text(text=prompt))
    cfg = types.GenerateContentConfig(
        temperature=0.2,
        response_mime_type="application/json" if schema else None,
        response_schema=schema,
        thinking_config=(types.ThinkingConfig(thinking_budget=thinking_budget)
                         if thinking_budget is not None else None),
    )
    resp = config.client().models.generate_content(
        model=model or config.MODEL, contents=[types.Content(role="user", parts=parts)],
        config=cfg)
    if schema is None:
        return (resp.text or "").strip()
    if resp.parsed is not None:
        return resp.parsed
    return schema.model_validate_json(resp.text)
