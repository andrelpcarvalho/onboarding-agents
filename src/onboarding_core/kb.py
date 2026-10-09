"""Busca na base de conhecimento da empresa.

Implementação local por palavras-chave sobre data/kb/*.md, suficiente para o
MVP e para testes. Para produção, troque `search` por Vertex AI Search
(google.adk.tools.VertexAiSearchTool) ou um vetor store (Chroma, AlloyDB),
mantendo a mesma assinatura de retorno.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache

from .config import KB_DIR


@dataclass(frozen=True)
class Chunk:
    source: str
    heading: str
    text: str


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    return "".join(ch for ch in s if not unicodedata.combining(ch))


# Palavras frequentes demais para indicar relevância (sem acento, já normalizadas).
_STOPWORDS = {
    "que", "qual", "quais", "como", "onde", "quando", "quem", "para", "por", "pra", "com",
    "sem", "uma", "uns", "umas", "dos", "das", "nos", "nas", "aos", "seu", "sua", "seus",
    "suas", "meu", "minha", "meus", "minhas", "esse", "essa", "este", "esta", "isso",
    "isto", "aqui", "ali", "tem", "ter", "sao", "ser", "estao", "foi", "vai",
    "pode", "posso", "preciso", "fazer", "faz", "sobre", "mais", "muito", "tambem",
    "empresa", "gente", "voce", "voces", "ele", "ela", "eles", "elas", "nao", "sim",
    "dia", "hoje", "agora", "the", "and",
}
MIN_SCORE = 2  # 1 palavra no título da seção, ou 2 no texto/nome do arquivo


def _tokens(s: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", _norm(s)) if len(t) > 2 and t not in _STOPWORDS}


@lru_cache
def load_chunks() -> tuple[Chunk, ...]:
    """Divide cada .md por seção (## ...). Cada seção vira um chunk citável."""
    chunks: list[Chunk] = []
    for path in sorted(KB_DIR.glob("*.md")):
        source = path.name
        heading, buf = path.stem, []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("## "):
                if buf:
                    chunks.append(Chunk(source, heading, "\n".join(buf).strip()))
                heading, buf = line[3:].strip(), []
            elif not line.startswith("# "):
                buf.append(line)
        if buf:
            chunks.append(Chunk(source, heading, "\n".join(buf).strip()))
    return tuple(c for c in chunks if c.text)


def search(query: str, top_k: int = 4) -> list[dict]:
    q = _tokens(query)
    if not q:
        return []
    scored = []
    for c in load_chunks():
        # título da seção pesa 2x; nome do arquivo (ex.: cultura.md) e texto pesam 1x
        score = (
            len(q & _tokens(c.heading)) * 2
            + len(q & _tokens(c.source.removesuffix(".md")))
            + len(q & _tokens(c.text))
        )
        if score >= MIN_SCORE:
            scored.append((score, c))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [
        {"source": f"{c.source}#{c.heading}", "score": s, "text": c.text}
        for s, c in scored[:top_k]
    ]


def valid_sources() -> set[str]:
    """Todas as fontes citáveis no formato `arquivo.md#Seção`."""
    return {f"{c.source}#{c.heading}" for c in load_chunks()}
