"""Carrega missões (data/missions/*.yaml) e a massa de teste de homologação."""

from __future__ import annotations

import re
from functools import lru_cache

import yaml

from .config import HOMOLOG_DATA, MISSIONS_DIR
from .schemas import Mission, Role


@lru_cache
def load_missions() -> dict[str, Mission]:
    missions: dict[str, Mission] = {}
    for path in sorted(MISSIONS_DIR.glob("*.yaml")):
        m = Mission.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
        missions[m.id] = m
    return missions


def get_mission(mission_id: str) -> Mission | None:
    """Só missões aprovadas chegam ao colaborador."""
    m = load_missions().get(mission_id)
    return m if m is not None and m.status == "approved" else None


def missions_for_role(role: Role | None) -> list[Mission]:
    if role is None:
        return []
    return [m for mid in role.missions if (m := get_mission(mid)) is not None]


@lru_cache
def homolog_cpfs() -> tuple[str, ...]:
    """CPFs da massa de homologação, só dígitos. Valores que não são CPF ficam de fora."""
    from .pii import cpf_is_valid  # import tardio: pii também usa este módulo

    if not HOMOLOG_DATA.exists():
        return ()
    raw = yaml.safe_load(HOMOLOG_DATA.read_text(encoding="utf-8")) or {}
    digits = (re.sub(r"\D", "", str(c)) for c in raw.get("cpfs", []))
    return tuple(d for d in digits if cpf_is_valid(d))
