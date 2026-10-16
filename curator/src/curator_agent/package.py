"""Pipeline completo PDF → pacote, e exportação do pacote para o onboarding-agents.

Pacote (out/<papel>-<data-hora>/):
    kb/*.md            base de conhecimento extraída do PDF
    roles/<papel>.yaml trilha proposta
    catalog.db         materiais + bancos de perguntas como RASCUNHO
    relatorio.md       o que foi gerado e o que precisa de revisão humana
    manifest.json      metadados (PDF de origem, modelo, resultados)
"""

from __future__ import annotations

import json
import shutil
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from . import config
from .ingest import check_grounding, extract_kb, write_kb
from .kb import KnowledgeBase
from .materials import curate_module
from .pdf import load_pdf
from .schemas import Role
from .storage import Catalog
from .trail import finalize_role, propose_role, write_role

Log = Callable[[str], None]


def run_pipeline(pdf_path: Path, role_id: str, role_title: str, *, role_hint: str | None = None,
                 buddy_contact: str | None = None, out_dir: Path | None = None,
                 skip_materials: bool = False, log: Log = print) -> Path:
    t0 = time.time()
    pkg = (out_dir or config.OUT_DIR) / f"{role_id}-{datetime.now():%Y%m%d-%H%M%S}"
    pkg.mkdir(parents=True)
    data, text, pages = load_pdf(pdf_path)
    log(f"PDF: {pdf_path.name} ({pages} páginas, {len(text)} caracteres de texto)")

    log("1/5 extraindo a base de conhecimento do PDF...")
    draft = extract_kb(data)
    files = write_kb(draft, pkg / "kb", pdf_path.name)
    log(f"    {len(files)} documento(s), {sum(len(d.sections) for d in draft.documents)} seção(ões)")

    log("2/5 checando fidelidade contra o texto do PDF...")
    checks = check_grounding(draft, text) if text.strip() else []
    flagged = [c for c in checks if not c.ok]
    if not text.strip():
        log("    PDF sem texto extraível (escaneado?): checagem automática indisponível")
    log(f"    {len(checks) - len(flagged)}/{len(checks)} seções sustentadas; {len(flagged)} para revisar")

    log("3/5 propondo a trilha...")
    kb = KnowledgeBase(pkg / "kb")
    proposal = propose_role(kb, role_id, role_title, role_hint)
    log("4/5 validando a trilha...")
    role, warnings = finalize_role(proposal, kb, role_id, role_title, buddy_contact)
    write_role(role, pkg / "roles")
    log(f"    {len(role.modules)} módulo(s); {len(warnings)} aviso(s)")

    results = []
    if not skip_materials:
        log("5/5 gerando materiais e bancos de perguntas...")
        catalog = Catalog(pkg / "catalog.db")
        for m in role.modules:
            log(f"    > {m.id}...")
            try:
                r = curate_module(kb, role, m, catalog)
            except Exception as e:  # noqa: BLE001 - segue para o próximo módulo
                r = {"ok": False, "module_id": m.id, "error": f"{type(e).__name__}: {str(e)[:160]}"}
            log(f"      {'ok' if r['ok'] else 'FALHOU: ' + r['error']}")
            results.append(r)

    manifest = {"pdf": pdf_path.name, "pages": pages, "role_id": role_id, "role_title": role_title,
                "model": config.MODEL, "created_at": datetime.now().isoformat(timespec="seconds"),
                "seconds": round(time.time() - t0), "omitted": draft.omitted,
                "grounding": [c.__dict__ | {"ok": c.ok} for c in checks],
                "role_warnings": warnings, "materials": results}
    (pkg / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                                       encoding="utf-8")
    (pkg / "relatorio.md").write_text(render_report(manifest, role), encoding="utf-8")
    log(f"pacote pronto em {pkg} ({manifest['seconds']}s). Leia o relatorio.md.")
    return pkg


def render_report(m: dict, role: Role) -> str:
    flagged = [g for g in m["grounding"] if not g["ok"]]
    lines = [
        f"# Relatório de importação: {m['pdf']}",
        "",
        f"- Papel: **{m['role_title']}** (`{m['role_id']}`), {len(role.modules)} módulo(s)",
        f"- Seções da base: {len(m['grounding'])} ({len(flagged)} para revisar)",
        f"- Materiais: {sum(r['ok'] for r in m['materials'])}/{len(m['materials'])} gerados",
        f"- Modelo: {m['model']} · tempo: {m['seconds']}s",
        "",
        "> **Nada aqui está aprovado.** Revise a base, a trilha e cada material antes de usar.",
        "",
        "## 1. Base de conhecimento: seções para revisar",
        "",
    ]
    if flagged:
        lines += ["| Seção | Cobertura no PDF | Palavras de regra novas | Números ausentes no PDF |",
                  "|---|---|---|---|"]
        lines += [f"| `{g['source']}` | {g['coverage']:.0%} | {', '.join(g['new_strong_words']) or '-'}"
                  f" | {', '.join(g['missing_numbers']) or '-'} |" for g in flagged]
        lines += ["", "Compare cada seção acima com o PDF original e corrija em `kb/`."]
    else:
        lines.append("Nenhuma seção sinalizada pela checagem automática (ainda assim, leia a base).")
    if m["omitted"]:
        lines += ["", "**Deixado de fora pelo extrator:**", *[f"- {o}" for o in m["omitted"]]]
    lines += ["", "## 2. Trilha proposta", ""]
    for i, mod in enumerate(role.modules, 1):
        lines.append(f"{i}. **{mod.title}** (`{mod.id}`): " + "; ".join(mod.objectives))
    if role.buddy_contact.startswith("TODO"):
        lines.append("\n- `buddy_contact` não informado: preencha no YAML.")
    lines += [f"- {w}" for w in m["role_warnings"]]
    lines += ["", "## 3. Materiais (rascunhos)", "",
              "| Módulo | Resultado | Revisão automática | Perguntas |", "|---|---|---|---|"]
    for r in m["materials"]:
        if r["ok"]:
            auto = "aprovada" if r["auto_review_approved"] else f"NÃO aprovada ({r['review_rounds']} rodadas)"
            lines.append(f"| `{r['module_id']}` | #{r['material_id']} | {auto} | {r['quiz_questions']} |")
        else:
            lines.append(f"| `{r['module_id']}` | FALHOU: {r['error']} | - | - |")
    lines += ["", "## 4. Próximos passos", "",
              "1. Revise `kb/` contra o PDF (comece pelas seções da tabela 1).",
              "2. Revise `roles/*.yaml` (objetivos, ordem, `buddy_contact`).",
              ("3. Exporte para o onboarding-agents: "
              "`python scripts/export_package.py <pacote> <caminho do onboarding-agents>`."),
              ("4. No onboarding-agents: `make check`, depois revise e aprove cada rascunho "
              "(`scripts/approve.py list`).")]
    return "\n".join(lines) + "\n"


def export_package(pkg: Path, target: Path, *, target_catalog: Path | None = None,
                   force: bool = False, log: Log = print) -> dict:
    """Copia base e trilha para o onboarding-agents e importa os materiais como RASCUNHO."""
    kb_src, roles_src = pkg / "kb", pkg / "roles"
    kb_dst, roles_dst = target / "data" / "kb", target / "data" / "roles"
    if not kb_dst.is_dir() or not roles_dst.is_dir():
        raise ValueError(f"{target} não parece o onboarding-agents (falta data/kb ou data/roles)")
    pairs = [(f, kb_dst / f.name) for f in sorted(kb_src.glob("*.md"))]
    pairs += [(f, roles_dst / f.name) for f in sorted(roles_src.glob("*.yaml"))]
    conflicts = [str(d.relative_to(target)) for _, d in pairs if d.exists()]
    if conflicts and not force:
        raise FileExistsError("já existem no destino (use --force para sobrescrever): "
                              + ", ".join(conflicts))
    for src, dst in pairs:
        shutil.copy2(src, dst)
    log(f"copiados {len(pairs)} arquivo(s) para {target / 'data'}")

    imported = []
    src_db = pkg / "catalog.db"
    if src_db.exists():
        dst_cat = Catalog(target_catalog or target / ".adk" / "catalog.db")
        for mat in Catalog(src_db).list_by_status("draft"):
            new = dst_cat.save_draft(mat.role_id, mat.module_id, mat.title, mat.content_md,
                                     mat.sources, quiz=mat.quiz,
                                     review_note=f"importado do onboarding-curator ({pkg.name})")
            imported.append(new.id)
        log(f"importados {len(imported)} rascunho(s) no catálogo do destino: {imported}")
    return {"files": len(pairs), "drafts": imported, "overwritten": conflicts}
