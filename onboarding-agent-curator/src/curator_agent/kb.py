"""Base de conhecimento em Markdown (um arquivo por assunto, seções `##`) com busca por
palavra-chave. Mesmo formato e mesma busca do onboarding-agent, mas parametrizada por
diretório (cada pacote gerado tem a sua base)."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

_STOPWORDS = {
    "que", "qual", "quais", "como", "onde", "quando", "quem", "para", "por", "pra", "com",
    "sem", "uma", "uns", "umas", "dos", "das", "nos", "nas", "aos", "seu", "sua", "seus",
    "suas", "meu", "minha", "meus", "minhas", "esse", "essa", "este", "esta", "isso",
    "isto", "aqui", "ali", "tem", "ter", "sao", "ser", "estao", "foi", "vai", "pode",
    "posso", "preciso", "fazer", "faz", "sobre", "mais", "muito", "tambem", "empresa",
    "gente", "voce", "voces", "ele", "ela", "eles", "elas", "nao", "sim", "dia", "hoje",
    "agora", "the", "and", "deve", "devem",
}
MIN_SCORE = 2


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    return "".join(ch for ch in s if not unicodedata.combining(ch))


def tokens(s: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", norm(s)) if len(t) > 2 and t not in _STOPWORDS}


@dataclass(frozen=True)
class Chunk:
    source: str
    heading: str
    text: str


class KnowledgeBase:
    def __init__(self, kb_dir: Path) -> None:
        self.kb_dir = Path(kb_dir)
        self.chunks: list[Chunk] = []
        for path in sorted(self.kb_dir.glob("*.md")):
            heading, buf = path.stem, []
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.startswith("## "):
                    if buf:
                        self.chunks.append(Chunk(path.name, heading, "\n".join(buf).strip()))
                    heading, buf = line[3:].strip(), []
                elif not line.startswith("# ") and not line.lstrip().startswith("<!--"):
                    buf.append(line)
            if buf:
                self.chunks.append(Chunk(path.name, heading, "\n".join(buf).strip()))
        self.chunks = [c for c in self.chunks if c.text]

    def search(self, query: str, top_k: int = 4) -> list[dict]:
        q = tokens(query)
        scored = []
        for c in self.chunks:
            score = (len(q & tokens(c.heading)) * 2 + len(q & tokens(c.source.removesuffix(".md")))
                     + len(q & tokens(c.text)))
            if score >= MIN_SCORE:
                scored.append((score, c))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [{"source": f"{c.source}#{c.heading}", "text": c.text} for _, c in scored[:top_k]]

    def has_term(self, term: str) -> bool:
        """O termo aparece em algum título, texto ou nome de arquivo da base?"""
        t = tokens(term)
        return bool(t) and any(
            t <= (tokens(c.heading) | tokens(c.text) | tokens(c.source.removesuffix(".md")))
            for c in self.chunks)

    def valid_sources(self) -> set[str]:
        return {f"{c.source}#{c.heading}" for c in self.chunks}

    def outline(self, max_chars: int = 220) -> str:
        """Resumo compacto (arquivo, seção, início do texto) para o prompt da trilha."""
        return "\n".join(f"- [{c.source}#{c.heading}] {c.text[:max_chars]}" for c in self.chunks)
