"""Catálogo de materiais e backlog de lacunas (SQLite).

O progresso do colaborador NÃO fica aqui: ele vive no estado `user:` da sessão
ADK, persistido pelo SessionService. Aqui fica o que é compartilhado entre
colaboradores (materiais) e o canal Tutor -> Curador (lacunas).
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from .config import CATALOG_DB
from .db import connect, enable_wal
from .schemas import BuddyAssignment, Escalation, Gap, Material, QuizQuestion, RoleAssignment

_SCHEMA = """
CREATE TABLE IF NOT EXISTS materials (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    role_id     TEXT NOT NULL,
    module_id   TEXT NOT NULL,
    version     INTEGER NOT NULL,
    title       TEXT NOT NULL,
    content_md  TEXT NOT NULL,
    sources     TEXT NOT NULL,
    status      TEXT NOT NULL CHECK (status IN ('draft','approved','stale')),
    approved_by TEXT,
    review_note TEXT,
    quiz_json   TEXT NOT NULL DEFAULT '[]',
    created_at  TEXT NOT NULL,
    UNIQUE (role_id, module_id, version)
);
CREATE TABLE IF NOT EXISTS escalations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     TEXT NOT NULL,
    role_id     TEXT,
    category    TEXT NOT NULL,
    urgency     TEXT NOT NULL,
    summary     TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'open',
    buddy_id    TEXT,
    closed_by   TEXT,
    close_note  TEXT,
    created_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS buddy_assignments (
    user_id       TEXT PRIMARY KEY,
    buddy_id      TEXT NOT NULL,
    buddy_name    TEXT NOT NULL,
    buddy_contact TEXT NOT NULL,
    assigned_by   TEXT NOT NULL,
    assigned_at   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS role_assignments (
    user_id     TEXT PRIMARY KEY,
    role_id     TEXT NOT NULL,
    assigned_by TEXT NOT NULL,
    assigned_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS gaps (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    TEXT NOT NULL,
    role_id    TEXT,
    module_id  TEXT,
    question   TEXT NOT NULL,
    status     TEXT NOT NULL DEFAULT 'open',
    created_at TEXT NOT NULL
);
"""


class Catalog:
    def __init__(self, db_path: Path | str = CATALOG_DB) -> None:
        self.db_path = Path(db_path)
        enable_wal(self.db_path)
        with self._conn() as c:
            c.executescript(_SCHEMA)
            # migração leve: bancos criados antes da coluna de nota de revisão
            cols = {r["name"] for r in c.execute("PRAGMA table_info(materials)")}
            if "review_note" not in cols:
                c.execute("ALTER TABLE materials ADD COLUMN review_note TEXT")
            if "quiz_json" not in cols:
                c.execute("ALTER TABLE materials ADD COLUMN quiz_json TEXT NOT NULL DEFAULT '[]'")
            cols = {r["name"] for r in c.execute("PRAGMA table_info(escalations)")}
            if "buddy_id" not in cols:
                c.execute("ALTER TABLE escalations ADD COLUMN buddy_id TEXT")

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # ---------- materiais ----------

    def save_draft(
        self,
        role_id: str,
        module_id: str,
        title: str,
        content_md: str,
        sources: list[str],
        review_note: str | None = None,
        quiz: list[QuizQuestion] | None = None,
    ) -> Material:
        with self._conn() as c:
            row = c.execute(
                "SELECT COALESCE(MAX(version), 0) AS v FROM materials WHERE role_id=? AND module_id=?",
                (role_id, module_id),
            ).fetchone()
            mat = Material(
                role_id=role_id,
                module_id=module_id,
                version=row["v"] + 1,
                title=title,
                content_md=content_md,
                sources=sources,
                review_note=review_note,
                quiz=quiz or [],
            )
            cur = c.execute(
                "INSERT INTO materials (role_id, module_id, version, title, content_md, sources,"
                " status, review_note, quiz_json, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    mat.role_id,
                    mat.module_id,
                    mat.version,
                    mat.title,
                    mat.content_md,
                    json.dumps(mat.sources),
                    mat.status,
                    mat.review_note,
                    json.dumps([q.model_dump() for q in mat.quiz], ensure_ascii=False),
                    mat.created_at.isoformat(),
                ),
            )
            mat.id = cur.lastrowid
            return mat

    def get_latest(
        self, role_id: str, module_id: str, *, approved_only: bool = True
    ) -> Material | None:
        statuses = ("approved",) if approved_only else ("approved", "draft")
        with self._conn() as c:
            row = c.execute(
                f"SELECT * FROM materials WHERE role_id=? AND module_id=?"
                f" AND status IN ({','.join('?' * len(statuses))})"
                " ORDER BY (status='approved') DESC, version DESC LIMIT 1",
                (role_id, module_id, *statuses),
            ).fetchone()
        return _row_to_material(row) if row else None

    def list_by_status(self, status: str | None = "draft") -> list[Material]:
        """Lista materiais num status (None = todos)."""
        sql, args = "SELECT * FROM materials", []
        if status:
            sql += " WHERE status=?"
            args.append(status)
        with self._conn() as c:
            rows = c.execute(sql + " ORDER BY role_id, module_id, version", args).fetchall()
        return [_row_to_material(r) for r in rows]

    def get(self, material_id: int) -> Material | None:
        with self._conn() as c:
            row = c.execute("SELECT * FROM materials WHERE id=?", (material_id,)).fetchone()
        return _row_to_material(row) if row else None

    def approve(self, material_id: int, approver: str) -> Material:
        """Aprova uma versão e marca as anteriores aprovadas do mesmo módulo como stale."""
        mat = self.get(material_id)
        if mat is None:
            raise KeyError(f"material {material_id} não encontrado")
        with self._conn() as c:
            c.execute(
                "UPDATE materials SET status='stale' WHERE role_id=? AND module_id=?"
                " AND status='approved'",
                (mat.role_id, mat.module_id),
            )
            c.execute(
                "UPDATE materials SET status='approved', approved_by=? WHERE id=?",
                (approver, material_id),
            )
        return self.get(material_id)  # type: ignore[return-value]

    def discard(self, material_id: int, by: str, reason: str) -> Material:
        """Tira um material de uso (status stale) registrando quem e por quê."""
        if self.get(material_id) is None:
            raise KeyError(f"material {material_id} não encontrado")
        with self._conn() as c:
            c.execute(
                "UPDATE materials SET status='stale', review_note=? WHERE id=?",
                (f"descartado por {by}: {reason}", material_id),
            )
        return self.get(material_id)  # type: ignore[return-value]

    def mark_stale_by_source(self, source: str) -> int:
        """Invalida materiais que citam um doc-fonte alterado. Retorna quantos mudaram."""
        with self._conn() as c:
            cur = c.execute(
                "UPDATE materials SET status='stale' WHERE status='approved' AND sources LIKE ?",
                # fontes são "arquivo.md#Seção": casa o arquivo inteiro ou uma seção dele
                (f'%"{source}%',),
            )
            return cur.rowcount

    # ---------- lacunas ----------

    def log_gap(
        self, user_id: str, question: str, role_id: str | None, module_id: str | None
    ) -> Gap:
        gap = Gap(user_id=user_id, role_id=role_id, module_id=module_id, question=question)
        with self._conn() as c:
            cur = c.execute(
                "INSERT INTO gaps (user_id, role_id, module_id, question, status, created_at)"
                " VALUES (?,?,?,?,?,?)",
                (gap.user_id, gap.role_id, gap.module_id, gap.question, gap.status,
                 gap.created_at.isoformat()),
            )
            gap.id = cur.lastrowid
        return gap

    def list_open_gaps(self, role_id: str | None = None) -> list[Gap]:
        sql, args = "SELECT * FROM gaps WHERE status='open'", []
        if role_id:
            sql += " AND role_id=?"
            args.append(role_id)
        with self._conn() as c:
            rows = c.execute(sql + " ORDER BY created_at", args).fetchall()
        return [
            Gap(**{**dict(r), "created_at": datetime.fromisoformat(r["created_at"])})
            for r in rows
        ]

    # ---------- escalonamentos (Tutor -> buddy) ----------

    def create_escalation(
        self,
        user_id: str,
        role_id: str | None,
        category: str,
        urgency: str,
        summary: str,
        buddy_id: str | None = None,
    ) -> Escalation:
        esc = Escalation(user_id=user_id, role_id=role_id, category=category,
                         urgency=urgency, summary=summary, buddy_id=buddy_id)
        with self._conn() as c:
            cur = c.execute(
                "INSERT INTO escalations (user_id, role_id, category, urgency, summary, status,"
                " buddy_id, created_at) VALUES (?,?,?,?,?,?,?,?)",
                (esc.user_id, esc.role_id, esc.category, esc.urgency, esc.summary, esc.status,
                 esc.buddy_id, esc.created_at.isoformat()),
            )
            esc.id = cur.lastrowid
        return esc

    def list_escalations(
        self, status: str | None = "open", buddy_id: str | None = None,
        unassigned: bool = False,
    ) -> list[Escalation]:
        sql, where, args = "SELECT * FROM escalations", [], []
        if status:
            where.append("status=?")
            args.append(status)
        if buddy_id:
            where.append("buddy_id=?")
            args.append(buddy_id)
        if unassigned:
            where.append("buddy_id IS NULL")
        if where:
            sql += " WHERE " + " AND ".join(where)
        with self._conn() as c:
            rows = c.execute(
                sql + " ORDER BY (urgency='alta') DESC, created_at", args
            ).fetchall()
        return [
            Escalation(**{**dict(r), "created_at": datetime.fromisoformat(r["created_at"])})
            for r in rows
        ]

    def count_recent_escalations(self, user_id: str, since: datetime) -> int:
        with self._conn() as c:
            return c.execute(
                "SELECT COUNT(*) FROM escalations WHERE user_id=? AND created_at>=?",
                (user_id, since.isoformat()),
            ).fetchone()[0]

    def close_escalation(self, esc_id: int, by: str, note: str) -> None:
        with self._conn() as c:
            cur = c.execute(
                "UPDATE escalations SET status='closed', closed_by=?, close_note=? WHERE id=?"
                " AND status='open'",
                (by, note, esc_id),
            )
            if cur.rowcount == 0:
                raise KeyError(f"pedido #{esc_id} não encontrado ou já fechado")

    # ---------- atribuição tutorado -> buddy ----------

    def assign_buddy(
        self, user_id: str, buddy_id: str, buddy_name: str, buddy_contact: str, by: str
    ) -> BuddyAssignment:
        a = BuddyAssignment(user_id=user_id, buddy_id=buddy_id, buddy_name=buddy_name,
                            buddy_contact=buddy_contact, assigned_by=by)
        with self._conn() as c:
            c.execute(
                "INSERT INTO buddy_assignments VALUES (?,?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE"
                " SET buddy_id=excluded.buddy_id, buddy_name=excluded.buddy_name,"
                " buddy_contact=excluded.buddy_contact, assigned_by=excluded.assigned_by,"
                " assigned_at=excluded.assigned_at",
                (a.user_id, a.buddy_id, a.buddy_name, a.buddy_contact, a.assigned_by,
                 a.assigned_at.isoformat()),
            )
        return a

    def get_assignment(self, user_id: str) -> BuddyAssignment | None:
        with self._conn() as c:
            row = c.execute(
                "SELECT * FROM buddy_assignments WHERE user_id=?", (user_id,)
            ).fetchone()
        return _row_to_assignment(row) if row else None

    def list_assignments(self, buddy_id: str | None = None) -> list[BuddyAssignment]:
        sql, args = "SELECT * FROM buddy_assignments", []
        if buddy_id:
            sql += " WHERE buddy_id=?"
            args.append(buddy_id)
        with self._conn() as c:
            rows = c.execute(sql + " ORDER BY buddy_id, user_id", args).fetchall()
        return [_row_to_assignment(r) for r in rows]

    def unassign_buddy(self, user_id: str) -> bool:
        with self._conn() as c:
            return c.execute(
                "DELETE FROM buddy_assignments WHERE user_id=?", (user_id,)
            ).rowcount > 0

    # ---------- atribuição tutorado -> papel ----------

    def assign_role(self, user_id: str, role_id: str, by: str) -> RoleAssignment:
        a = RoleAssignment(user_id=user_id, role_id=role_id, assigned_by=by)
        with self._conn() as c:
            c.execute(
                "INSERT INTO role_assignments VALUES (?,?,?,?) ON CONFLICT(user_id) DO UPDATE"
                " SET role_id=excluded.role_id, assigned_by=excluded.assigned_by,"
                " assigned_at=excluded.assigned_at",
                (a.user_id, a.role_id, a.assigned_by, a.assigned_at.isoformat()),
            )
        return a

    def get_role_assignment(self, user_id: str) -> RoleAssignment | None:
        with self._conn() as c:
            row = c.execute(
                "SELECT * FROM role_assignments WHERE user_id=?", (user_id,)
            ).fetchone()
        if not row:
            return None
        return RoleAssignment(**{**dict(row),
                                 "assigned_at": datetime.fromisoformat(row["assigned_at"])})

    def unassign_role(self, user_id: str) -> bool:
        with self._conn() as c:
            return c.execute(
                "DELETE FROM role_assignments WHERE user_id=?", (user_id,)
            ).rowcount > 0

    def resolve_gap(self, gap_id: int) -> None:
        with self._conn() as c:
            c.execute("UPDATE gaps SET status='resolved' WHERE id=?", (gap_id,))


def _row_to_assignment(row: sqlite3.Row) -> BuddyAssignment:
    return BuddyAssignment(**{**dict(row), "assigned_at": datetime.fromisoformat(row["assigned_at"])})


def _row_to_material(row: sqlite3.Row) -> Material:
    d = dict(row)
    d["sources"] = json.loads(d["sources"])
    d["quiz"] = json.loads(d.pop("quiz_json", None) or "[]")
    d["created_at"] = datetime.fromisoformat(d["created_at"])
    return Material(**d)


_catalog: Catalog | None = None


def get_catalog() -> Catalog:
    global _catalog
    if _catalog is None:
        _catalog = Catalog()
    return _catalog
