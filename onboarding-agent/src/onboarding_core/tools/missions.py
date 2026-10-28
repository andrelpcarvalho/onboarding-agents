"""Missões: prática guiada em sistemas (homologação), conduzida pelo Tutor.

- O roteiro vem de data/missions/*.yaml, aprovado por humano (status: approved).
- Missão > etapas > checkpoints. Cada checkpoint é `confirm`, `describe` ou `capture`.
- `answer_mission` não recebe argumentos: lê a última mensagem do colaborador, como
  `answer_quiz`. Quem avança checkpoint e conclui a missão é o código, nunca o modelo.
- Palavras-chave esperadas, regex e termos de bloqueio nunca vão ao modelo.
- Evidências capturadas (ex.: número da proposta) ficam em `user:missions` e o
  critério `done_when` é conferido por código.
"""

from __future__ import annotations

import copy
import re
import unicodedata
import zlib
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from google.adk.tools import ToolContext

from .. import kb
from .. import missions as catalog
from ..config import MISSION_MAX_ATTEMPTS
from ..missions import get_mission, missions_for_role
from ..roles import get_role
from ..schemas import Checkpoint, Mission
from . import state_keys as K
from .quiz import _last_user_message

AFFIRMATIVE = ["sim", "entendi", "ok", "pode seguir", "pode", "claro", "certo", "beleza", "bora"]
NEGATION = ["nao"]


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    return re.sub(r"\s+", " ", "".join(c for c in s if not unicodedata.combining(c))).strip()


def _has(terms: list[str], text: str) -> bool:
    t = _norm(text)
    return any(re.search(rf"\b{re.escape(_norm(x))}\b", t) for x in terms)


def _all(state: Mapping[str, Any]) -> dict[str, dict]:
    return copy.deepcopy(dict(state.get(K.MISSIONS) or {}))


def _save(tool_context: ToolContext, missions: dict[str, dict]) -> None:
    tool_context.state[K.MISSIONS] = missions  # reatribuir gera state_delta


def _checkpoint(m: Mission, p: dict) -> tuple[Any, Checkpoint]:
    step = m.steps[p["step"]]
    return step, step.checkpoints[p["checkpoint"]]


def _prereqs_done(m: Mission, state: Mapping[str, Any], missions: dict[str, dict]) -> bool:
    modules = dict(state.get(K.PROGRESS) or {})
    return all(
        modules.get(pid, {}).get("status") == "done" or missions.get(pid, {}).get("status") == "done"
        for pid in m.prerequisites
    )


def mission_view(m: Mission, p: dict) -> dict:
    """O que o modelo vê do checkpoint atual (sem expected/pattern/block_on)."""
    step, cp = _checkpoint(m, p)
    attempts = p["attempts"].get(cp.id, 0)
    show_fallback = cp.fallback_source and attempts >= cp.fallback_after
    return {
        "mission_id": m.id,
        "mission": m.title,
        "step": f"{p['step'] + 1}/{len(m.steps)}",
        "step_title": step.title,
        "guidance": step.guidance.format(**m.params),
        "checkpoint": cp.id,
        "tutor_instruction": cp.tutor_instruction,
        "explain": [{"cite": f"[{s}]", "text": kb.section(s)} for s in cp.explain],
        "helpers": step.helpers,
        "test_cpf": p["evidence"].get("test_cpf"),
        "fallback": (
            {"cite": f"[{cp.fallback_source}]", "text": kb.section(cp.fallback_source)}
            if show_fallback else None
        ),
    }


def missions_overview(state: Mapping[str, Any]) -> dict:
    """Resumo das missões do papel para a instrução do Tutor (sem LLM, sem I/O de rede)."""
    role = get_role(state.get(K.ROLE_ID) or "")
    missions = _all(state)
    items = [
        {"id": m.id, "title": m.title,
         "status": missions.get(m.id, {}).get("status", "not_started"),
         "locked": not _prereqs_done(m, state, missions)}
        for m in missions_for_role(role)
    ]
    active = state.get(K.ACTIVE_MISSION)
    am = get_mission(active) if active else None
    in_progress = None
    if am is not None and active in missions:
        in_progress = {"status": missions[active]["status"], **mission_view(am, missions[active])}
    return {"missions": items, "mission_in_progress": in_progress}


def list_missions(tool_context: ToolContext) -> dict:
    """Lista as missões práticas da trilha do colaborador, com status e se estão
    bloqueadas por pré-requisito."""
    if not tool_context.state.get(K.ROLE_ID):
        return {"ok": False, "error": "papel do colaborador não definido"}
    return {"ok": True, "missions": missions_overview(tool_context.state)["missions"]}


def start_mission(mission_id: str, tool_context: ToolContext) -> dict:
    """Inicia ou retoma uma missão prática da trilha do colaborador e devolve o
    checkpoint atual. Siga `tutor_instruction` do checkpoint.

    Args:
        mission_id: id da missão, conforme a lista `missions` do contexto.
    """
    state = tool_context.state
    role = get_role(state.get(K.ROLE_ID) or "")
    m = get_mission(mission_id)
    if role is None or m is None or mission_id not in role.missions:
        return {"ok": False, "error": "missão não pertence à trilha do colaborador"}
    missions = _all(state)
    active = state.get(K.ACTIVE_MISSION)
    if active and active != mission_id and missions.get(active, {}).get("status") == "in_progress":
        return {"ok": False, "error": "já existe outra missão em andamento", "active": active,
                "next_step": "ofereça retomar a missão em andamento"}
    p = missions.get(mission_id)
    if p and p["status"] == "done":
        return {"ok": True, "status": "done", "message": "missão já concluída"}
    if not _prereqs_done(m, state, missions):
        return {"ok": False, "error": "pré-requisitos pendentes", "prerequisites": m.prerequisites}

    event_id, _ = _last_user_message(tool_context)  # o pedido de iniciar não conta como resposta
    if p is None:
        p = {"status": "in_progress", "step": 0, "checkpoint": 0, "attempts": {},
             "evidence": {}, "answered_event_ids": [event_id], "started_at": _now()}
    else:  # retomada (ex.: depois de bloqueio de acesso): refaz o mesmo checkpoint
        p["status"] = "in_progress"
        p["answered_event_ids"] = [*p["answered_event_ids"], event_id]
    missions[mission_id] = p
    _save(tool_context, missions)
    state[K.ACTIVE_MISSION] = mission_id
    return {"ok": True, "status": "in_progress", "current": mission_view(m, p)}


def _check(cp: Checkpoint, text: str) -> tuple[bool, str | None]:
    if cp.kind == "confirm":
        return _has(AFFIRMATIVE, text) and not _has(NEGATION, text), None
    if cp.kind == "describe":
        return _has(cp.expected, text), None
    found = re.search(cp.pattern or "", text)
    return (True, found.group(0)) if found else (False, None)


def _fail(tool_context, missions, p, m, cp, status: str, **extra) -> dict:
    p["attempts"][cp.id] = p["attempts"].get(cp.id, 0) + 1
    _save(tool_context, missions)
    n = p["attempts"][cp.id]
    return {"ok": True, "status": status, "attempts": n,
            "suggest_buddy": n >= MISSION_MAX_ATTEMPTS, "current": mission_view(m, p), **extra}


def answer_mission(tool_context: ToolContext) -> dict:
    """Valida a resposta do colaborador ao checkpoint atual da missão. Não recebe
    argumentos: lê a última mensagem dele. Chame só quando ele responder ao que
    você pediu no checkpoint (dúvidas vão para search_knowledge_base)."""
    state = tool_context.state
    mid = state.get(K.ACTIVE_MISSION)
    m = get_mission(mid) if mid else None
    missions = _all(state)
    if m is None or mid not in missions:
        return {"ok": False, "error": "não há missão em andamento"}
    p = missions[mid]
    if p["status"] == "blocked_access":
        return {"ok": False, "status": "blocked_access",
                "next_step": "quando o acesso for liberado, chame start_mission de novo"}

    event_id, text = _last_user_message(tool_context)
    if event_id in p["answered_event_ids"]:
        return {"ok": False, "error": "aguarde a resposta do colaborador a este checkpoint",
                "current": mission_view(m, p)}
    p["answered_event_ids"] = [*p["answered_event_ids"], event_id]
    step, cp = _checkpoint(m, p)

    if cp.block_on and _has(cp.block_on, text):
        p["status"] = "blocked_access"
        p["blocked"] = {"checkpoint": cp.id, "at": _now()}
        _save(tool_context, missions)
        return {"ok": True, "status": "blocked_access",
                "next_step": "oriente pedir o acesso pelo buddy/canal do papel; a missão "
                "retoma deste mesmo checkpoint"}

    ok, value = _check(cp, text)
    if not ok:
        return _fail(tool_context, missions, p, m, cp, "not_confirmed")
    if value is not None:
        p["evidence"][cp.field] = value

    p["checkpoint"] += 1
    if p["checkpoint"] >= len(step.checkpoints):
        p["step"], p["checkpoint"] = p["step"] + 1, 0
    if p["step"] < len(m.steps):
        _save(tool_context, missions)
        return {"ok": True, "status": "advanced", "next": mission_view(m, p)}
    return _finish(tool_context, missions, p, m)


def _finish(tool_context: ToolContext, missions: dict, p: dict, m: Mission) -> dict:
    crit = m.done_when
    left = p["evidence"].get(crit.left) if crit else None
    right = p["evidence"].get(crit.right) if crit else None
    if crit is None or (left is not None and left == right):
        p["status"], p["finished_at"] = "done", _now()
        p["step"], p["checkpoint"] = len(m.steps) - 1, len(m.steps[-1].checkpoints) - 1
        _save(tool_context, missions)
        tool_context.state[K.ACTIVE_MISSION] = None
        return {"ok": True, "status": "mission_done", "mission": m.title,
                "evidence": {k: v for k, v in p["evidence"].items() if k != "test_cpf"}}
    # não confere: volta ao último checkpoint e descarta o valor capturado no fim
    p["step"], p["checkpoint"] = len(m.steps) - 1, len(m.steps[-1].checkpoints) - 1
    p["evidence"].pop(crit.right, None)
    _, cp = _checkpoint(m, p)
    return _fail(tool_context, missions, p, m, cp, "mismatch", expected_from=crit.left,
                 expected_value=left)


def get_test_cpf(tool_context: ToolContext) -> dict:
    """Entrega um CPF da massa de teste de homologação para a missão em andamento.
    Use só quando o colaborador pedir um CPF de teste."""
    state = tool_context.state
    mid = state.get(K.ACTIVE_MISSION)
    m = get_mission(mid) if mid else None
    missions = _all(state)
    if m is None or mid not in missions:
        return {"ok": False, "error": "não há missão em andamento"}
    p = missions[mid]
    if "test_cpf" not in p["evidence"]:
        step, _ = _checkpoint(m, p)
        if "get_test_cpf" not in step.helpers:
            return {"ok": False, "error": "CPF de teste não é usado nesta etapa"}
        pool = catalog.homolog_cpfs()
        if not pool:
            return {"ok": False, "error": "massa de teste não configurada",
                    "next_step": "oriente pedir um CPF de teste ao buddy"}
        idx = zlib.crc32(f"{tool_context.user_id}:{mid}".encode()) % len(pool)
        p["evidence"]["test_cpf"] = pool[idx]  # mesmo CPF durante toda a missão
        _save(tool_context, missions)
    return {"ok": True, "test_cpf": p["evidence"]["test_cpf"],
            "note": "uso exclusivo em homologação"}
