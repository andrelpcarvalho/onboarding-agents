"""Checklist do documento de input (RN-01, RN-02, RN-04) e da massa de homologação.

As regras ficam em data/kb_checklist.yaml para o grupo ajustar sem mexer em código.
`check_document` devolve (erros, avisos): erro bloqueia o `make check`; documento não
aprovado ou vencido também fica fora da busca do Tutor (kb.is_published).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from pathlib import Path

import yaml

from .config import DATA_DIR, HOMOLOG_DATA
from .kb import split_front_matter

CHECKLIST = DATA_DIR / "kb_checklist.yaml"


@dataclass
class Result:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


@lru_cache
def load_rules(path: Path = CHECKLIST) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _sections(body: str) -> list[str]:
    return [ln[3:].strip() for ln in body.splitlines() if ln.startswith("## ")]


def _section_text(body: str, name: str) -> str:
    out, on = [], False
    for ln in body.splitlines():
        if ln.startswith("## "):
            on = ln[3:].strip() == name
        elif on:
            out.append(ln)
    return "\n".join(out)


def check_document(path: Path, text: str | None = None, today: date | None = None,
                   rules: dict | None = None) -> Result:
    """Confere um documento da base contra o checklist."""
    rules = rules or load_rules()
    today = today or date.today()
    text = path.read_text(encoding="utf-8") if text is None else text
    meta, body = split_front_matter(text)
    r = Result()
    if not meta:
        r.errors.append("sem metadados (front matter entre --- no topo)")
        return r

    for k in rules["campos_obrigatorios"]:
        if meta.get(k) in (None, "", []):
            r.errors.append(f"campo obrigatório ausente: {k}")
    if meta.get("slug") and meta["slug"] != path.stem:
        r.errors.append(f"slug '{meta['slug']}' diferente do nome do arquivo '{path.stem}'")
    if meta.get("status") and meta["status"] not in rules["status_validos"]:
        r.errors.append(f"status inválido: {meta['status']} (válidos: {rules['status_validos']})")
    elif meta.get("status") == "rascunho":
        r.warnings.append("status rascunho: fora da busca do Tutor até ser aprovado")

    vig = meta.get("vigente_ate")
    if vig is not None:
        try:
            d = date.fromisoformat(str(vig))
        except ValueError:
            r.errors.append(f"vigente_ate inválido: {vig} (use AAAA-MM-DD)")
        else:
            if d < today:
                r.errors.append(f"documento vencido em {d.isoformat()} (fora da busca)")
            elif (d - today).days <= rules.get("aviso_vencimento_dias", 30):
                r.warnings.append(f"vence em {(d - today).days} dia(s) ({d.isoformat()})")

    tipo = meta.get("tipo")
    spec = rules["tipos"].get(tipo) if tipo else None
    if tipo and spec is None:
        r.errors.append(f"tipo desconhecido: {tipo} (válidos: {sorted(rules['tipos'])})")
    secs = _sections(body)
    if spec:
        for s in spec.get("secoes_obrigatorias", []):
            if s not in secs:
                r.errors.append(f"seção obrigatória ausente: '## {s}'")
        if len(secs) < spec.get("minimo_de_secoes", 0):
            r.errors.append("sem seções '## ' (nada citável)")
        if spec.get("passo_a_passo_numerado") and "Passo a passo" in secs and not re.search(
                r"^\s*1\.", _section_text(body, "Passo a passo"), re.MULTILINE):
            r.errors.append("'Passo a passo' precisa de lista numerada (1., 2., ...)")

    from .pii import redact  # import tardio: Presidio carrega o modelo de linguagem

    _, found = redact(body, tuple(rules.get("pii_bloqueia", [])) or None)
    if found:
        r.errors.append(f"dado pessoal no documento: {', '.join(found)} (RN-04)")
    if "TODO" in body:
        r.warnings.append("contém TODO")
    return r


def check_homolog_data(path: Path = HOMOLOG_DATA) -> Result:
    """A massa de homologação é a única exceção ao mascaramento de CPF: ela precisa
    declarar que é simulada e conter só CPFs com dígito verificador válido."""
    from .pii import cpf_is_valid

    r = Result()
    if not path.exists():
        r.warnings.append("sem massa de homologação: get_test_cpf fica desligado")
        return r
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if raw.get("simulado") is not True:
        r.errors.append("massa de homologação sem 'simulado: true' (só CPF fictício é aceito)")
    cpfs = raw.get("cpfs") or []
    bad = [c for c in cpfs if not cpf_is_valid(str(c))]
    if bad:
        r.errors.append(f"{len(bad)} valor(es) que não são CPF válido: {bad[:3]}")
    if not cpfs:
        r.warnings.append("massa de homologação vazia: get_test_cpf fica desligado")
    return r
