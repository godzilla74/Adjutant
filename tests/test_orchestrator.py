# tests/test_orchestrator.py
import importlib
import json
import pytest


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_DB", str(tmp_path / "test.db"))
    import backend.db as db_mod
    importlib.reload(db_mod)
    db_mod.init_db()
    with db_mod._conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO products (id, name, icon_label, color) "
            "VALUES ('p1', 'Acme', 'A', '#000')"
        )
    return db_mod


def test_orchestrator_config_table_created(db):
    with db._conn() as conn:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='orchestrator_config'"
        ).fetchone()
    assert row is not None


def test_orchestrator_runs_table_created(db):
    with db._conn() as conn:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='orchestrator_runs'"
        ).fetchone()
    assert row is not None


def test_signals_has_routed_column(db):
    with db._conn() as conn:
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(signals)").fetchall()]
    assert "routed_to_workstream_id" in cols
