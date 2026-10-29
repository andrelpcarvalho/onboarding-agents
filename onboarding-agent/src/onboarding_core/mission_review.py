"""Revisão humana de missões pelo mesmo caminho dos materiais (scripts/approve.py).

A fonte da verdade continua sendo o YAML em data/missions/ (versionado no Git): aprovar
ou devolver uma missão reescreve só as linhas `status:` e `approved_by:` do topo do
arquivo, e o PR mostra exatamente essa mudança. Antes de aprovar, a missão precisa
passar nas mesmas validações do `make check`.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import ValidationError

from . import kb
from .config import MISSIONS_DIR
from .schemas import Mission


@dataclass
class MissionFile:
    path: Path
    mission: Mission | None
    error: str | None = None


def list_missions(folder: Path = MISSIONS_DIR) -> list[MissionFile]:
    out = []
    for path in sorted(folder.glob("*.yaml")):
        try:
            m = Mission.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
            out.append(MissionFile(path, m))
        except (yaml.YAMLError, ValidationError) as e:
            out.append(MissionFile(path, None, str(e).splitlines()[0]))
    return out


def find(mission_id: str, folder: Path = MISSIONS_DIR) -> MissionFile:
    for mf in list_missions(folder):
        if mf.path.stem == mission_id:
            return mf
    raise KeyError(f"missão '{mission_id}' não encontrada em {folder}")


def problems(m: Mission) -> list[str]:
    """O que impede a aprovação (as mesmas regras do make check, mais `ask`)."""
    srcs, out = kb.valid_sources(), []
    for step in m.steps:
        for cp in step.checkpoints:
            where = f"{step.id} › {cp.id}"
            for s in [*cp.explain, *([cp.fallback_source] if cp.fallback_source else [])]:
                if s not in srcs:
                    out.append(f"{where}: fonte '{s}' não existe na base publicada")
            if not cp.ask:
                out.append(f"{where}: sem `ask` (pergunta que fecha a mensagem do Tutor)")
            if cp.pattern:
                try:
                    re.compile(cp.pattern)
                except re.error as e:
                    out.append(f"{where}: regex inválida: {e}")
    return out


def _set_top_level(text: str, key: str, value: str) -> str:
    line = f"{key}: {value}"
    pat = re.compile(rf"^{re.escape(key)}:.*$", re.MULTILINE)
    if pat.search(text):
        return pat.sub(line, text, count=1)
    # chave ausente: entra logo depois de `status:` (ou no fim do bloco do topo)
    st = re.search(r"^status:.*$", text, re.MULTILINE)
    if st:
        return text[:st.end()] + "\n" + line + text[st.end():]
    return line + "\n" + text


def set_status(mission_id: str, status: str, by: str, reason: str | None = None,
               folder: Path = MISSIONS_DIR) -> Path:
    """Grava `status` e `approved_by` no YAML da missão. Aprovar exige zero problemas."""
    mf = find(mission_id, folder)
    if mf.mission is None:
        raise ValueError(f"YAML inválido: {mf.error}")
    if status == "approved" and (errs := problems(mf.mission)):
        raise ValueError("não aprovada:\n  " + "\n  ".join(errs))
    text = mf.path.read_text(encoding="utf-8")
    text = _set_top_level(text, "status", status)
    text = _set_top_level(text, "approved_by", by if status == "approved" else "null")
    if status == "draft" and reason:
        text = _set_top_level(text, "review_note", json.dumps(reason.strip(), ensure_ascii=False))
    mf.path.write_text(text, encoding="utf-8")
    Mission.model_validate(yaml.safe_load(text))  # a escrita não pode quebrar o arquivo
    return mf.path


def describe(m: Mission) -> str:
    """Visão do revisor: roteiro, perguntas e o que o código confere (o modelo não vê isso)."""
    lines = [f"{m.id} · {m.title} · status: {m.status} · aprovado por: {m.approved_by or '-'}"]
    for i, step in enumerate(m.steps, 1):
        lines.append(f"\n{i}. {step.title}")
        for cp in step.checkpoints:
            check = (f"palavras: {cp.expected}" if cp.kind == "describe" else
                     f"captura {cp.field} com {cp.pattern}" if cp.kind == "capture" else
                     "confirmação (sim/entendi)")
            lines.append(f"   - [{cp.kind}] {cp.id}: \"{cp.ask or '(sem ask)'}\"  → {check}")
            if cp.block_on:
                lines.append(f"       bloqueia com: {cp.block_on}")
    if m.done_when:
        lines.append(f"\nconclui quando: {m.done_when.left} == {m.done_when.right}")
    return "\n".join(lines)
