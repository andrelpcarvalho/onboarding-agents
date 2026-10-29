"""Revisão humana (human-in-the-loop) dos materiais gerados pelo Curador.

Uso:
    python scripts/approve.py list                       # rascunhos pendentes
    python scripts/approve.py list --all                 # todos (aprovados, rascunhos, fora de uso)
    python scripts/approve.py show 3                     # conteúdo + checagem das fontes
    python scripts/approve.py approve 3 --by maria       # publica para o Tutor
    python scripts/approve.py edit 3 --by maria          # corrige texto e perguntas -> nova versão
    python scripts/approve.py discard 3 --by maria --reason "tom muito técnico"
    python scripts/approve.py gaps                       # lacunas abertas do Tutor
    python scripts/approve.py resolve-gap 7              # marca lacuna como resolvida
    python scripts/approve.py stale pipeline_deploy.md   # tira de uso materiais que citam a fonte

Missões (data/missions/*.yaml; a aprovação grava status no YAML e entra por PR):
    python scripts/approve.py missions                   # lista missões e status
    python scripts/approve.py mission-show site_solar_proposta_acom
    python scripts/approve.py mission-approve site_solar_proposta_acom --by maria
    python scripts/approve.py mission-draft site_solar_proposta_acom --by maria --reason "falta o passo do ACOM"
"""

from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

from onboarding_core import mission_review as mr
from onboarding_core.kb import valid_sources
from onboarding_core.quiz_bank import QUIZ_SIZE, parse_bank, validate_bank
from onboarding_core.schemas import Material
from onboarding_core.storage import get_catalog

STATUS_LABEL = {"draft": "rascunho", "approved": "APROVADO", "stale": "fora de uso"}


def _get(cat, material_id: int) -> Material:
    m = cat.get(material_id)
    if m is None:
        sys.exit(f"material #{material_id} não encontrado")
    return m


def _invalid_sources(m: Material) -> list[str]:
    known = valid_sources()
    return [s for s in m.sources if s not in known]


def _print_row(m: Material) -> None:
    print(f"#{m.id:<4} {STATUS_LABEL[m.status]:<11} {m.role_id}/{m.module_id} v{m.version}  {m.title}")


def cmd_list(cat, args) -> None:
    items = cat.list_by_status(None if args.all else "draft")
    if not items:
        print("nenhum rascunho pendente" if not args.all else "catálogo vazio")
    for m in items:
        _print_row(m)


def cmd_show(cat, args) -> None:
    m = _get(cat, args.id)
    print(f"# {m.title}")
    print(f"papel/módulo: {m.role_id}/{m.module_id} · versão {m.version} · {STATUS_LABEL[m.status]}")
    if m.approved_by:
        print(f"aprovado por: {m.approved_by}")
    if m.review_note:
        print(f"nota: {m.review_note}")
    print("\n" + "-" * 72 + "\n")
    print(m.content_md)
    print("\n" + "-" * 72)
    bad = set(_invalid_sources(m))
    print("Fontes citadas:")
    for s in m.sources:
        print(f"  {'✗ NÃO EXISTE NA BASE' if s in bad else '✓'}  {s}")
    print("\n" + "-" * 72)
    err = validate_bank(m.quiz)
    print(f"Banco de perguntas ({len(m.quiz)}; o quiz sorteia {QUIZ_SIZE})"
          + (f"  ✗ {err}" if err else "  ✓"))
    for i, q in enumerate(m.quiz, 1):
        print(f"\n  {i}. {q.question}")
        for j, opt in enumerate(q.options):
            mark = "  <- correta" if j == q.correct_option else ""
            print(f"     {'ABCD'[j]}) {opt}{mark}")
        if q.explanation:
            print(f"     por quê: {q.explanation}")


def cmd_approve(cat, args) -> None:
    m = _get(cat, args.id)
    if m.status != "draft":
        sys.exit(f"#{m.id} está '{STATUS_LABEL[m.status]}'; só rascunhos podem ser aprovados")
    bad = _invalid_sources(m)
    if bad and not args.force:
        sys.exit(
            "fontes que não existem na base: " + ", ".join(bad)
            + "\nCorrija com `edit`, descarte, ou use --force se tiver certeza."
        )
    if err := validate_bank(m.quiz):
        sys.exit(f"banco de perguntas inválido: {err}\n"
                 "Corrija com `edit` ou descarte e regenere com o Curador.")
    m = cat.approve(m.id, args.by)
    print(f"aprovado: {m.role_id}/{m.module_id} v{m.version} por {m.approved_by}")
    print("O Tutor passa a usar esta versão na próxima mensagem; versões anteriores saem de uso.")


QUIZ_MARKER = "<!-- QUIZ: banco de perguntas em YAML abaixo. correct_option: 0=A, 1=B, 2=C, 3=D -->"


def _to_editable(m: Material) -> str:
    bank = yaml.safe_dump([q.model_dump() for q in m.quiz], allow_unicode=True,
                          sort_keys=False, width=100)
    return f"{m.content_md.rstrip()}\n\n{QUIZ_MARKER}\n```yaml\n{bank}```\n"


def _from_editable(text: str) -> tuple[str, list]:
    if QUIZ_MARKER not in text:
        raise ValueError("o marcador do QUIZ foi removido; não sei onde termina o material")
    content, quiz_part = text.split(QUIZ_MARKER, 1)
    body = quiz_part.strip().removeprefix("```yaml").removesuffix("```")
    return content.rstrip(), parse_bank(yaml.safe_load(body) or [])


def cmd_edit(cat, args) -> None:
    m = _get(cat, args.id)
    editor = os.environ.get("EDITOR", "nano")
    original = _to_editable(m)
    with tempfile.NamedTemporaryFile("w+", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write(original)
        tmp = Path(f.name)
    subprocess.run([*shlex.split(editor), str(tmp)], check=True)
    edited = tmp.read_text(encoding="utf-8")
    if edited.strip() == original.strip():
        tmp.unlink(missing_ok=True)
        print("sem alterações; nada foi salvo")
        return
    try:
        content, quiz = _from_editable(edited)
        if err := validate_bank(quiz):
            raise ValueError(f"banco de perguntas inválido: {err}")
    except (ValueError, yaml.YAMLError) as e:
        sys.exit(f"não salvei: {e}\nSua edição continua em {tmp}; corrija e rode `edit` de novo "
                 "copiando o texto de lá.")
    tmp.unlink(missing_ok=True)
    new = cat.save_draft(
        m.role_id, m.module_id, m.title, content, m.sources,
        review_note=f"editado por {args.by} a partir da v{m.version}", quiz=quiz,
    )
    if m.status == "draft":
        cat.discard(m.id, args.by, f"substituído pela v{new.version} (edição manual)")
    print(f"nova versão salva como rascunho: #{new.id} v{new.version}")
    print(f"Revise com `show {new.id}` e aprove com `approve {new.id} --by {args.by}`.")


def cmd_discard(cat, args) -> None:
    m = cat.discard(_get(cat, args.id).id, args.by, args.reason)
    print(f"#{m.id} fora de uso ({m.review_note})")
    print(
        "Para gerar de novo levando o motivo em conta:\n"
        f'  python scripts/curate_role.py {m.role_id} --module {m.module_id} --feedback "{args.reason}"'
    )


def cmd_gaps(cat, args) -> None:
    gaps = cat.list_open_gaps(args.role)
    if not gaps:
        print("nenhuma lacuna aberta")
    for g in gaps:
        print(f"#{g.id:<4} [{g.role_id}/{g.module_id}] {g.question}")


def cmd_missions(args) -> None:
    if args.cmd == "missions":
        for mf in mr.list_missions():
            if mf.mission is None:
                print(f"{mf.path.stem:<32} INVÁLIDA   {mf.error}")
                continue
            m = mf.mission
            label = "APROVADA" if m.status == "approved" else "rascunho"
            pend = mr.problems(m)
            extra = f"   {len(pend)} pendência(s): mission-show {m.id}" if pend else ""
            print(f"{m.id:<32} {label:<10} por {m.approved_by or '-'}{extra}")
    elif args.cmd == "mission-show":
        mf = mr.find(args.id)
        if mf.mission is None:
            sys.exit(f"YAML inválido: {mf.error}")
        print(mr.describe(mf.mission))
        for e in mr.problems(mf.mission):
            print(f"  PENDÊNCIA: {e}")
    else:
        status = "approved" if args.cmd == "mission-approve" else "draft"
        try:
            path = mr.set_status(args.id, status, args.by, getattr(args, "reason", None))
        except (KeyError, ValueError) as e:
            sys.exit(str(e).strip("'\""))
        verb = "aprovada" if status == "approved" else "devolvida para rascunho"
        print(f"missão {args.id} {verb} por {args.by}. Commit e PR de {path.relative_to(Path.cwd())}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("list", help="lista rascunhos pendentes")
    sp.add_argument("--all", action="store_true", help="inclui aprovados e fora de uso")
    sub.add_parser("show", help="mostra conteúdo e checa fontes").add_argument("id", type=int)

    sp = sub.add_parser("approve", help="publica um rascunho")
    sp.add_argument("id", type=int)
    sp.add_argument("--by", required=True, help="quem aprovou")
    sp.add_argument("--force", action="store_true", help="aprova mesmo com fonte inválida")

    sp = sub.add_parser("edit", help="corrige no editor e salva como nova versão")
    sp.add_argument("id", type=int)
    sp.add_argument("--by", required=True)

    sp = sub.add_parser("discard", help="tira um material de uso")
    sp.add_argument("id", type=int)
    sp.add_argument("--by", required=True)
    sp.add_argument("--reason", required=True)

    sub.add_parser("gaps", help="lacunas abertas").add_argument("--role")
    sub.add_parser("resolve-gap", help="fecha uma lacuna").add_argument("id", type=int)
    sub.add_parser("stale", help="tira de uso o que cita uma fonte").add_argument("source")

    sub.add_parser("missions", help="lista missões e status")
    sub.add_parser("mission-show", help="roteiro e o que o código confere").add_argument("id")
    sp = sub.add_parser("mission-approve", help="aprova uma missão (grava no YAML)")
    sp.add_argument("id")
    sp.add_argument("--by", required=True)
    sp = sub.add_parser("mission-draft", help="devolve uma missão para rascunho")
    sp.add_argument("id")
    sp.add_argument("--by", required=True)
    sp.add_argument("--reason", required=True)
    args = p.parse_args()

    if args.cmd.startswith("mission"):
        cmd_missions(args)
        return

    cat = get_catalog()
    if args.cmd == "list":
        cmd_list(cat, args)
    elif args.cmd == "show":
        cmd_show(cat, args)
    elif args.cmd == "approve":
        cmd_approve(cat, args)
    elif args.cmd == "edit":
        cmd_edit(cat, args)
    elif args.cmd == "discard":
        cmd_discard(cat, args)
    elif args.cmd == "gaps":
        cmd_gaps(cat, args)
    elif args.cmd == "resolve-gap":
        cat.resolve_gap(args.id)
        print(f"lacuna #{args.id} resolvida")
    elif args.cmd == "stale":
        n = cat.mark_stale_by_source(args.source)
        print(f"{n} material(is) tirados de uso. Gere de novo com:")
        print("  python scripts/curate_role.py <papel> --missing-only")


if __name__ == "__main__":
    main()
