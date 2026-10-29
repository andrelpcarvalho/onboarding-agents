"""Busca vetorial sobre a base publicada (item 8, desejável).

Liga com `ONBOARDING_KB_BACKEND=vector` (padrão: `keyword`). Mesma assinatura e retorno de
`kb.search`, então o Tutor, o Curador e o servidor MCP não mudam.

- Embeddings: Gemini via Vertex AI (`ONBOARDING_EMBED_MODEL`, padrão gemini-embedding-001),
  com a mesma credencial do Tutor.
- Índice: um JSON em `.adk/kb_vectors.json`, recalculado só para trechos novos ou alterados
  (chave = modelo + hash do texto). A base da PoC tem dezenas de trechos: cosseno em Python
  puro basta; um vector store (Chroma, AlloyDB) entra quando a base crescer.
- Sem troca silenciosa de provedor: se o embedding falhar, a busca levanta
  `VectorSearchUnavailable` e o Tutor diz que a busca está indisponível (não registra lacuna).
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from collections.abc import Callable, Sequence
from pathlib import Path

from .config import PROJECT_ROOT

INDEX = PROJECT_ROOT / ".adk" / "kb_vectors.json"
MODEL = os.getenv("ONBOARDING_EMBED_MODEL", "gemini-embedding-001")
MIN_SIMILARITY = float(os.getenv("ONBOARDING_KB_MIN_SIMILARITY", "0.55"))

Embedder = Callable[[Sequence[str]], list[list[float]]]


class VectorSearchUnavailable(RuntimeError):
    """O provedor de embeddings falhou; a busca não troca de método sozinha."""


def gemini_embedder(texts: Sequence[str]) -> list[list[float]]:
    from google import genai

    try:
        client = genai.Client()
        out = client.models.embed_content(model=MODEL, contents=list(texts))
        return [list(e.values) for e in out.embeddings]
    except Exception as e:
        raise VectorSearchUnavailable(f"embeddings indisponíveis ({MODEL}): {e}") from e


_embedder: Embedder = gemini_embedder


def set_embedder(fn: Embedder) -> None:
    """Troca o embedder (testes usam um falso e determinístico)."""
    global _embedder
    _embedder = fn


def _key(text: str) -> str:
    return f"{MODEL}:{hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]}"


def _cos(a: Sequence[float], b: Sequence[float]) -> float:
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(x * x for x in b)) or 1.0
    return sum(x * y for x, y in zip(a, b, strict=False)) / (na * nb)


def _load(path: Path) -> dict[str, list[float]]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def build_index(path: Path = INDEX) -> dict[str, list[float]]:
    """Embeddings de todos os trechos publicados; calcula só o que mudou."""
    from .kb import load_chunks

    cache = _load(path)
    chunks = load_chunks()
    texts = {(_key(f"{c.heading}\n{c.text}")): f"{c.heading}\n{c.text}" for c in chunks}
    missing = [k for k in texts if k not in cache]
    if missing:
        vecs = _embedder([texts[k] for k in missing])
        cache.update(dict(zip(missing, vecs, strict=True)))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({k: cache[k] for k in texts}), encoding="utf-8")
    return {k: cache[k] for k in texts}


def search(query: str, top_k: int = 4, path: Path = INDEX) -> list[dict]:
    from .kb import load_chunks

    if not query.strip():
        return []
    index = build_index(path)
    qv = _embedder([query])[0]
    scored = []
    for c in load_chunks():
        s = _cos(qv, index[_key(f"{c.heading}\n{c.text}")])
        if s >= MIN_SIMILARITY:
            scored.append((s, c))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [{"source": f"{c.source}#{c.heading}", "score": round(s, 3), "text": c.text}
            for s, c in scored[:top_k]]
