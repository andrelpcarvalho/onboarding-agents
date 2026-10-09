import sqlite3

from conftest import draft

from onboarding_core import db


def test_catalogo_em_wal(tmp_catalog):
    with sqlite3.connect(tmp_catalog.db_path) as c:
        assert c.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


def test_backup_copia_dados(tmp_catalog, tmp_path, monkeypatch):
    draft(tmp_catalog)
    monkeypatch.setitem(db.DATABASES, "catalog", tmp_catalog.db_path)
    monkeypatch.setitem(db.DATABASES, "sessions", tmp_path / "nao_existe.db")
    monkeypatch.setitem(db.DATABASES, "memory", tmp_path / "nao_existe2.db")

    dest = db.backup(tmp_path / "bkp")

    with sqlite3.connect(dest / tmp_catalog.db_path.name) as c:
        assert c.execute("SELECT COUNT(*) FROM materials").fetchone()[0] == 1
