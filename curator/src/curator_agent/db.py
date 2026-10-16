"""Helpers de SQLite usados pelo catálogo (mesmo formato do onboarding-agents)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

BUSY_TIMEOUT_S = 5.0


def connect(path: Path, **kwargs) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(path, timeout=BUSY_TIMEOUT_S, **kwargs)


def enable_wal(path: Path) -> str:
    with connect(path) as conn:
        return conn.execute("PRAGMA journal_mode=WAL").fetchone()[0]
