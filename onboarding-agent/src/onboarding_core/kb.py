"""Busca na base de conhecimento da empresa.

Implementação local por palavras-chave sobre data/kb/*.md, suficiente para o
MVP e para testes. Só entram documentos publicados (front matter com
`status: aprovado` e dentro da vigência; ver `kb_checklist.py`). Para produção, troque `search` por Vertex AI Search
(google.adk.tools.VertexAiSearchTool) ou um vetor store (Chroma, AlloyDB),
mantendo a mesma assinatura de retorno.
"""

from __future__ import annotations

import os
import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from functools import lru_cache

import yaml

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


def split_front_matter(text: str) -> tuple[dict, str]:
    """(metadados, corpo) de um documento. Sem front matter: ({}, texto inteiro)."""
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end < 0:
        return {}, text
    meta = yaml.safe_load(text[4:end]) or {}
    return (meta if isinstance(meta, dict) else {}), text[end + 4:].lstrip("\n")


def is_published(meta: dict, today: date | None = None) -> bool:
    """Documento entra na busca? Sem metadados = legado, entra (o `make check` acusa).
    Com metadados: só `status: aprovado` e dentro da vigência (RN-02, RN-03)."""
    if not meta:
        return True
    if meta.get("status") != "aprovado":
        return False
    vig = meta.get("vigente_ate")
    try:
        return vig is None or date.fromisoformat(str(vig)) >= (today or date.today())
    except ValueError:
        return False


@lru_cache
def load_chunks() -> tuple[Chunk, ...]:
    """Divide cada .md publicado por seção (## ...). Cada seção vira um chunk citável."""
    chunks: list[Chunk] = []
    for path in sorted(KB_DIR.glob("*.md")):
        meta, body = split_front_matter(path.read_text(encoding="utf-8"))
        if not is_published(meta):
            continue
        source = path.name
        heading, buf = path.stem, []
        for line in body.splitlines():
            if line.startswith("## "):
                if buf:
                    chunks.append(Chunk(source, heading, "\n".join(buf).strip()))
                heading, buf = line[3:].strip(), []
            elif not line.startswith("# "):
                buf.append(line)
        if buf:
            chunks.append(Chunk(source, heading, "\n".join(buf).strip()))
    return tuple(c for c in chunks if c.text)


def backend() -> str:
    """`keyword` (padrão) ou `vector` (ver kb_vector.py). Escolha explícita, sem troca automática."""
    return os.getenv("ONBOARDING_KB_BACKEND", "keyword").strip().lower()


def search(query: str, top_k: int = 4) -> list[dict]:
    """Trechos citáveis para a pergunta, pelo backend configurado."""
    if backend() == "vector":
        from . import kb_vector

        return kb_vector.search(query, top_k)
    return keyword_search(query, top_k)


def keyword_search(query: str, top_k: int = 4) -> list[dict]:
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


def section(source: str) -> str | None:
    """Texto de uma fonte `arquivo.md#Seção` (recuperação exata, sem busca)."""
    return next((c.text for c in load_chunks() if f"{c.source}#{c.heading}" == source), None)


def valid_sources() -> set[str]:
    """Todas as fontes citáveis no formato `arquivo.md#Seção`."""
    return {f"{c.source}#{c.heading}" for c in load_chunks()}


def has_term(term: str) -> bool:
    """O termo aparece em algum título, texto ou nome de arquivo da base?

    Para validar `kb_tags` (uma palavra solta): a busca exige relevância mínima e
    rejeitaria uma tag que aparece só uma vez no texto.
    """
    t = _tokens(term)
    return bool(t) and any(
        t <= (_tokens(c.heading) | _tokens(c.text) | _tokens(c.source.removesuffix(".md")))
        for c in load_chunks())
