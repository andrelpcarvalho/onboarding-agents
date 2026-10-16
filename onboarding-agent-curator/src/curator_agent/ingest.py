"""Etapas 1 e 2: PDF → base de conhecimento, e checagem de fidelidade contra o PDF."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .kb import norm, tokens
from .llm import generate
from .prompts import EXTRACT_KB
from .schemas import KnowledgeBaseDraft

GROUNDING_THRESHOLD = 0.7  # fração mínima das palavras da seção que existem no PDF
_STRONG_WORDS = ("nunca", "sempre", "obrigatorio", "obrigatoria", "proibido", "proibida",
                 "vedado", "deve", "devem", "nao pode", "nao podem")
_NUMBER_RE = re.compile(r"\d+(?:[.,:h]\d+|h)?")  # 2, 15, 9h45, 22h, 1.500


def extract_kb(pdf: bytes) -> KnowledgeBaseDraft:
    """O Gemini lê o PDF (inclusive tabelas e páginas escaneadas) e devolve a base."""
    return generate(EXTRACT_KB, schema=KnowledgeBaseDraft, pdf=pdf)


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", norm(s)).strip("_") or "documento"


@dataclass
class SectionCheck:
    source: str
    coverage: float              # fração das palavras da seção encontradas no PDF
    new_strong_words: list[str]  # palavras de regra que a seção tem e o PDF não tem
    missing_numbers: list[str]   # números da seção que não aparecem no PDF

    @property
    def ok(self) -> bool:
        return (self.coverage >= GROUNDING_THRESHOLD and not self.new_strong_words
                and not self.missing_numbers)


def check_grounding(draft: KnowledgeBaseDraft, pdf_text: str) -> list[SectionCheck]:
    """Checagem determinística (sem LLM): cada seção precisa ser sustentada pelo texto do PDF.

    Não prova fidelidade, mas pega os sinais mais comuns de invenção: vocabulário que não
    existe no PDF, números que não existem no PDF e palavras de regra ("nunca",
    "obrigatório") que o PDF não usa.
    """
    pdf_tokens, pdf_norm = tokens(pdf_text), norm(pdf_text)
    pdf_numbers = set(_NUMBER_RE.findall(pdf_text))
    has = lambda text, w: re.search(rf"\b{w}\b", text) is not None
    checks = []
    for doc in draft.documents:
        for sec in doc.sections:
            words = tokens(sec.text)
            coverage = len(words & pdf_tokens) / len(words) if words else 1.0
            sec_norm = norm(sec.text)
            strong = [w for w in _STRONG_WORDS if has(sec_norm, w) and not has(pdf_norm, w)]
            numbers = [n for n in _NUMBER_RE.findall(sec.text) if n not in pdf_numbers]
            checks.append(SectionCheck(f"{_slug(doc.slug)}.md#{sec.heading.strip()}",
                                       round(coverage, 2), strong, numbers))
    return checks


def write_kb(draft: KnowledgeBaseDraft, kb_dir: Path, source_name: str) -> list[Path]:
    """Grava um .md por documento, no formato que o onboarding-agent usa."""
    kb_dir.mkdir(parents=True, exist_ok=True)
    written, used = [], set()
    for doc in draft.documents:
        slug = _slug(doc.slug)
        while slug in used:
            slug += "_2"
        used.add(slug)
        # O comentário fica NA LINHA DO TÍTULO: os parsers da base (aqui e no
        # onboarding-agent) ignoram a linha "# ...", então ele não vira uma seção citável.
        title = (f"# {doc.title.strip()} <!-- gerado pelo onboarding-curator a partir de "
                 f"{source_name}; revise -->")
        lines = [title, ""]
        for sec in doc.sections:
            lines += [f"## {sec.heading.strip()}", sec.text.strip(), ""]
        path = kb_dir / f"{slug}.md"
        path.write_text("\n".join(lines), encoding="utf-8")
        written.append(path)
    return written
