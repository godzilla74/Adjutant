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


def test_get_orchestrator_config_defaults(db):
    cfg = db.get_orchestrator_config("p1")
    assert cfg["product_id"] == "p1"
    assert cfg["enabled"] == 0
    assert cfg["schedule"] == "daily at 8am"
    assert cfg["signal_threshold"] == 5
    assert cfg["next_run_at"] is None
    assert cfg["autonomy_settings"]["route_signal"] == "autonomous"
    assert cfg["autonomy_settings"]["pause_workstream"] == "approval_required"


def test_update_orchestrator_config(db):
    db.update_orchestrator_config("p1", enabled=1, schedule="every 6 hours")
    cfg = db.get_orchestrator_config("p1")
    assert cfg["enabled"] == 1
    assert cfg["schedule"] == "every 6 hours"


def test_update_orchestrator_config_autonomy_settings(db):
    db.update_orchestrator_config(
        "p1",
        autonomy_settings={"update_mission": "approval_required"}
    )
    cfg = db.get_orchestrator_config("p1")
    # Stored partial is merged with defaults
    assert cfg["autonomy_settings"]["update_mission"] == "approval_required"
    assert cfg["autonomy_settings"]["route_signal"] == "autonomous"


def test_save_and_get_orchestrator_run(db):
    run_id = db.save_orchestrator_run(
        product_id="p1",
        triggered_by="schedule",
        status="complete",
        decisions=[{"action": "consume_signal", "signal_id": 1, "_status": "applied"}],
        brief="Everything looks good.",
    )
    run = db.get_orchestrator_run(run_id)
    assert run["product_id"] == "p1"
    assert run["triggered_by"] == "schedule"
    assert run["status"] == "complete"
    assert run["brief"] == "Everything looks good."
    assert run["decisions"][0]["action"] == "consume_signal"


def test_list_orchestrator_runs(db):
    db.save_orchestrator_run("p1", "schedule", "complete", [], "Brief 1")
    db.save_orchestrator_run("p1", "signal_threshold", "complete", [], "Brief 2")
    runs = db.list_orchestrator_runs("p1")
    assert len(runs) == 2
    assert runs[0]["brief"] == "Brief 2"  # most recent first


def test_update_orchestrator_run_decisions(db):
    run_id = db.save_orchestrator_run("p1", "schedule", "complete", [], "")
    db.update_orchestrator_run_decisions(
        run_id,
        [{"action": "update_mission", "_status": "applied"}],
        status="complete",
    )
    run = db.get_orchestrator_run(run_id)
    assert run["decisions"][0]["action"] == "update_mission"
