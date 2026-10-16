"""Agente conversacional do Curador (ADK): mesma lógica do CLI, exposta como tools.

Serve tanto o `adk web agents` quanto o servidor A2A (scripts/serve_a2a.py), para
outros agentes (ex.: o Tutor) pedirem uma importação pela rede.

A exportação para o onboarding-agent NÃO é uma tool de propósito: ela altera outro
projeto e deve ser uma decisão humana (scripts/export_package.py).
"""

from __future__ import annotations

import json
import re

from google.adk.agents import LlmAgent

from . import config
from .package import run_pipeline

_ROLE_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def list_pdfs() -> dict:
    """Lista os PDFs disponíveis para importação (pasta inbox/)."""
    config.INBOX_DIR.mkdir(parents=True, exist_ok=True)
    return {"inbox": str(config.INBOX_DIR),
            "pdfs": sorted(p.name for p in config.INBOX_DIR.glob("*.pdf"))}


def import_pdf(pdf_name: str, role_id: str, role_title: str, role_hint: str | None = None,
               buddy_contact: str | None = None) -> dict:
    """Importa um PDF da inbox: gera base de conhecimento, trilha do papel e materiais com
    banco de perguntas (tudo como rascunho para revisão humana). Leva alguns minutos.

    Args:
        pdf_name: nome do arquivo na inbox (veja list_pdfs).
        role_id: id do papel em snake_case, ex. "analista_qa".
        role_title: nome do papel, ex. "Analista de QA".
        role_hint: (opcional) 1 frase sobre o que a função faz, para orientar a trilha.
        buddy_contact: (opcional) canal geral de apoio do papel, ex. "#onboarding-qa no Slack".
    """
    path = (config.INBOX_DIR / pdf_name).resolve()
    if path.parent != config.INBOX_DIR.resolve() or path.suffix.lower() != ".pdf" or not path.exists():
        return {"ok": False, "error": "PDF não encontrado na inbox", **list_pdfs()}
    if not _ROLE_ID_RE.match(role_id):
        return {"ok": False, "error": "role_id deve ser snake_case sem acentos (ex.: analista_qa)"}
    log: list[str] = []
    try:
        pkg = run_pipeline(path, role_id, role_title, role_hint=role_hint,
                           buddy_contact=buddy_contact, log=log.append)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {str(e)[:300]}", "log": log}
    return {"ok": True, "package": pkg.name, "log": log, **package_summary(pkg.name)}


def list_packages() -> dict:
    """Lista os pacotes já gerados, do mais recente para o mais antigo."""
    if not config.OUT_DIR.exists():
        return {"packages": []}
    pkgs = sorted((p for p in config.OUT_DIR.iterdir() if (p / "manifest.json").exists()),
                  reverse=True)
    return {"packages": [package_summary(p.name) for p in pkgs]}


def package_summary(package: str) -> dict:
    """Resumo de um pacote: base, trilha, materiais e pontos para revisão humana.

    Args:
        package: nome do pacote (pasta em out/).
    """
    pkg = (config.OUT_DIR / package).resolve()
    if pkg.parent != config.OUT_DIR.resolve() or not (pkg / "manifest.json").exists():
        return {"ok": False, "error": "pacote não encontrado"}
    m = json.loads((pkg / "manifest.json").read_text(encoding="utf-8"))
    return {
        "package": package, "pdf": m["pdf"], "role": f"{m['role_title']} ({m['role_id']})",
        "sections": len(m["grounding"]),
        "sections_to_review": [g["source"] for g in m["grounding"] if not g["ok"]],
        "role_warnings": m["role_warnings"],
        "materials": [{k: r.get(k) for k in ("module_id", "ok", "auto_review_approved", "error")}
                      for r in m["materials"]],
        "report_path": str(pkg / "relatorio.md"),
    }


INSTRUCTION = """\
Você é o Curador de conteúdo de onboarding. Você transforma documentos internos (PDF) em
base de conhecimento, trilha de onboarding e materiais com quiz, sempre como RASCUNHO.

- Para importar, precisa de: o PDF (use list_pdfs), o role_id (snake_case) e o nome do
  papel. Peça o que faltar; role_hint e buddy_contact são opcionais, mas ajudam.
- Avise que a importação leva alguns minutos antes de chamar import_pdf.
- Depois, resuma: quantas seções, quantos módulos, quantos materiais e, principalmente,
  o que precisa de revisão humana (sections_to_review, role_warnings, materiais com a
  revisão automática não aprovada). Indique o relatorio.md.
- Nada gerado está aprovado. Para levar ao onboarding-agent, oriente o uso de
  `python scripts/export_package.py <pacote> <caminho>`; você não exporta.
- Responda em português do Brasil, de forma objetiva.
"""


def build_agent() -> LlmAgent:
    return LlmAgent(
        name="curador",
        model=config.AGENT_MODEL,
        description=("Transforma um PDF interno em base de conhecimento, trilha de onboarding "
                     "e materiais com banco de perguntas, como rascunho para revisão humana."),
        instruction=INSTRUCTION,
        tools=[list_pdfs, import_pdf, list_packages, package_summary],
    )
