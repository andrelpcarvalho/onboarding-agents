"""SQLite como banco único do MVP: preparo dos arquivos e backup.

Três arquivos em `.adk/`:
- sessions.db : sessões + estado `user:*` (progresso)  -> SqliteSessionService (ADK)
- memory.db   : memória de longo prazo (busca FTS)     -> SqliteMemoryService (ADK, já usa WAL)
- catalog.db  : materiais + lacunas                     -> storage.Catalog

Premissa do MVP: UMA instância com disco persistente. Para mais de uma instância,
migrar sessão/catálogo para Postgres (ver README).
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from .config import CATALOG_DB, MEMORY_DB, PROJECT_ROOT, SESSIONS_DB

BUSY_TIMEOUT_S = 5.0
DATABASES = {"sessions": SESSIONS_DB, "memory": MEMORY_DB, "catalog": CATALOG_DB}


def connect(path: Path) -> sqlite3.Connection:
    """Conexão com espera por lock (evita 'database is locked' em escrita concorrente)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(path, timeout=BUSY_TIMEOUT_S)


def enable_wal(path: Path) -> str:
    """Liga WAL (leitores não bloqueiam o escritor). É persistente no arquivo:
    basta uma vez, vale para qualquer conexão futura, inclusive as do ADK."""
    with connect(path) as conn:
        return conn.execute("PRAGMA journal_mode=WAL").fetchone()[0]


def prepare_databases() -> None:
    """Idempotente. Chamado ao carregar os agentes e ao montar o Runner."""
    enable_wal(SESSIONS_DB)
    enable_wal(CATALOG_DB)


def backup(dest_root: Path | None = None) -> Path:
    """Cópia consistente dos bancos usando a backup API do SQLite (segura com o app rodando).

    Restaurar = parar o app e copiar os .db de volta para `.adk/`.
    """
    dest = (dest_root or PROJECT_ROOT / "backups") / datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    dest.mkdir(parents=True, exist_ok=True)
    for path in DATABASES.values():
        if not path.exists():
            continue
        with connect(path) as src, sqlite3.connect(dest / path.name) as dst:
            src.backup(dst)
    return dest
