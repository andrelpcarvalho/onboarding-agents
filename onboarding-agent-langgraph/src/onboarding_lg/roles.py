"""Carrega as trilhas de onboarding por papel a partir de data/roles/*.yaml."""

from __future__ import annotations

from functools import lru_cache

import yaml

from .config import ROLES_DIR
from .schemas import Role


@lru_cache
def load_roles() -> dict[str, Role]:
    roles: dict[str, Role] = {}
    for path in sorted(ROLES_DIR.glob("*.yaml")):
        role = Role.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
        roles[role.id] = role
    return roles


def get_role(role_id: str) -> Role | None:
    return load_roles().get(role_id)
