"""SQLite do MVP: conexões, WAL e backup.

Três arquivos em `.lg/`:
- checkpoints.db : histórico das conversas (threads)  -> SqliteSaver (LangGraph)
- store.db       : perfil/progresso e lembranças      -> SqliteStore (LangGraph)
- catalog.db     : materiais, lacunas, pedidos, buddies -> storage.Catalog
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from .config import CATALOG_DB, CHECKPOINT_DB, PROJECT_ROOT, STORE_DB

BUSY_TIMEOUT_S = 5.0
DATABASES = {"checkpoints": CHECKPOINT_DB, "store": STORE_DB, "catalog": CATALOG_DB}


def connect(path: Path, **kwargs) -> sqlite3.Connection:
    """Conexão com espera por lock (evita 'database is locked' em escrita concorrente)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(path, timeout=BUSY_TIMEOUT_S, **kwargs)


def enable_wal(path: Path) -> str:
    with connect(path) as conn:
        return conn.execute("PRAGMA journal_mode=WAL").fetchone()[0]


def backup(dest_root: Path | None = None) -> Path:
    """Cópia consistente dos bancos (segura com o app rodando)."""
    dest = (dest_root or PROJECT_ROOT / "backups") / datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    dest.mkdir(parents=True, exist_ok=True)
    for path in DATABASES.values():
        if path.exists():
            with connect(path) as src, sqlite3.connect(dest / path.name) as dst:
                src.backup(dst)
    return dest
