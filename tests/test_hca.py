# tests/test_hca.py
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


def test_hca_config_table_created(db):
    with db._conn() as conn:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='hca_config'"
        ).fetchone()
    assert row is not None


def test_hca_runs_table_created(db):
    with db._conn() as conn:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='hca_runs'"
        ).fetchone()
    assert row is not None


def test_hca_directives_table_created(db):
    with db._conn() as conn:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='hca_directives'"
        ).fetchone()
    assert row is not None


def test_get_hca_config_defaults(db):
    cfg = db.get_hca_config()
    assert cfg["enabled"] == 0
    assert cfg["schedule"] == "weekly on mondays at 8am"
    assert cfg["pa_run_threshold"] == 10
    assert cfg["next_run_at"] is None
    assert cfg["last_run_at"] is None


def test_update_hca_config(db):
    db.update_hca_config(enabled=1, schedule="every 3 days", pa_run_threshold=5)
    cfg = db.get_hca_config()
    assert cfg["enabled"] == 1
    assert cfg["schedule"] == "every 3 days"
    assert cfg["pa_run_threshold"] == 5


def test_save_and_get_hca_run(db):
    run_id = db.save_hca_run(
        triggered_by="schedule",
        status="complete",
        decisions=[{"action": "issue_directive", "_status": "applied"}],
        brief="Portfolio is healthy.",
    )
    run = db.get_hca_run(run_id)
    assert run["triggered_by"] == "schedule"
    assert run["status"] == "complete"
    assert run["brief"] == "Portfolio is healthy."
    assert run["decisions"][0]["action"] == "issue_directive"


def test_list_hca_runs(db):
    db.save_hca_run("schedule", "complete", [], "Brief 1")
    db.save_hca_run("pa_run_threshold", "complete", [], "Brief 2")
    runs = db.list_hca_runs()
    assert len(runs) == 2
    assert runs[0]["brief"] == "Brief 2"  # most recent first


def test_create_and_list_hca_directives(db):
    run_id = db.save_hca_run("schedule", "complete", [], "")
    d_id = db.create_hca_directive(product_id="p1", content="Focus on enterprise", hca_run_id=run_id)
    directives = db.list_hca_directives()
    assert any(d["id"] == d_id and d["content"] == "Focus on enterprise" for d in directives)


def test_create_global_hca_directive(db):
    run_id = db.save_hca_run("schedule", "complete", [], "")
    d_id = db.create_hca_directive(product_id=None, content="All products: prioritize retention", hca_run_id=run_id)
    with db._conn() as conn:
        row = conn.execute("SELECT product_id FROM hca_directives WHERE id = ?", (d_id,)).fetchone()
    assert row["product_id"] is None


def test_supersede_hca_directive(db):
    run_id = db.save_hca_run("schedule", "complete", [], "")
    old_id = db.create_hca_directive("p1", "Old guidance", run_id)
    new_id = db.supersede_hca_directive(old_id, "Updated guidance", run_id)
    with db._conn() as conn:
        old = conn.execute("SELECT status FROM hca_directives WHERE id = ?", (old_id,)).fetchone()
        new = conn.execute("SELECT content, status FROM hca_directives WHERE id = ?", (new_id,)).fetchone()
    assert old["status"] == "superseded"
    assert new["content"] == "Updated guidance"
    assert new["status"] == "active"


def test_retire_hca_directive(db):
    run_id = db.save_hca_run("schedule", "complete", [], "")
    d_id = db.create_hca_directive("p1", "Some directive", run_id)
    db.retire_hca_directive(d_id)
    with db._conn() as conn:
        row = conn.execute("SELECT status FROM hca_directives WHERE id = ?", (d_id,)).fetchone()
    assert row["status"] == "retired"


def test_list_hca_directives_excludes_terminal_statuses(db):
    run_id = db.save_hca_run("schedule", "complete", [], "")
    active_id = db.create_hca_directive("p1", "Active", run_id)
    old_id = db.create_hca_directive("p1", "Old", run_id)
    db.retire_hca_directive(old_id)
    directives = db.list_hca_directives()
    ids = [d["id"] for d in directives]
    assert active_id in ids
    assert old_id not in ids


def test_get_due_hca_scheduled(db):
    from datetime import datetime, timedelta
    past = (datetime.now() - timedelta(minutes=1)).isoformat(timespec="seconds")
    db.update_hca_config(enabled=1, next_run_at=past)
    due = db.get_due_hca()
    assert due is not None
    assert due["trigger_type"] == "schedule"


def test_get_due_hca_not_due_when_disabled(db):
    from datetime import datetime, timedelta
    past = (datetime.now() - timedelta(minutes=1)).isoformat(timespec="seconds")
    db.update_hca_config(enabled=0, next_run_at=past)
    due = db.get_due_hca()
    assert due is None


def test_get_due_hca_pa_accumulation_trigger(db):
    from datetime import datetime, timedelta
    future = (datetime.now() + timedelta(days=7)).isoformat(timespec="seconds")
    db.update_hca_config(enabled=1, next_run_at=future, pa_run_threshold=2)
    # Insert 2 PA runs
    with db._conn() as conn:
        conn.execute(
            "INSERT INTO orchestrator_runs (product_id, triggered_by, status, decisions, brief) "
            "VALUES ('p1', 'schedule', 'complete', '[]', 'brief')"
        )
        conn.execute(
            "INSERT INTO orchestrator_runs (product_id, triggered_by, status, decisions, brief) "
            "VALUES ('p1', 'schedule', 'complete', '[]', 'brief')"
        )
    due = db.get_due_hca()
    assert due is not None
    assert due["trigger_type"] == "pa_run_threshold"


def test_create_workstream_for_launch(db):
    ws_id = db.create_workstream_for_launch(
        product_id="p1",
        name="Research",
        mission="Track competitive landscape",
        schedule="weekly on mondays at 9am",
        tag_subscriptions='["research:"]',
        next_run_at=None,
    )
    assert isinstance(ws_id, int)
    ws_list = db.get_workstreams("p1")
    assert any(w["id"] == ws_id and w["name"] == "Research" for w in ws_list)


@pytest.fixture
def populated_db(db):
    """DB with a product, PA runs, and HCA directives."""
    with db._conn() as conn:
        conn.execute(
            "INSERT INTO workstreams (product_id, name, status, display_order) "
            "VALUES ('p1', 'Research', 'paused', 1)"
        )
        # Insert 3 PA runs
        for i in range(3):
            conn.execute(
                "INSERT INTO orchestrator_runs "
                "(product_id, triggered_by, status, decisions, brief) "
                "VALUES ('p1', 'schedule', 'complete', '[]', ?)",
                (f"Brief {i}",),
            )
    # Active directive for p1 and one global
    run_id = db.save_hca_run("schedule", "complete", [], "")
    db.create_hca_directive("p1", "Focus on enterprise", run_id)
    db.create_hca_directive(None, "All products: cut costs", run_id)
    return db


def test_build_hca_context_includes_products(populated_db):
    from backend.hca import build_hca_context
    ctx = build_hca_context()
    product_ids = [p["id"] for p in ctx["products"]]
    assert "p1" in product_ids


def test_build_hca_context_includes_pa_runs(populated_db):
    from backend.hca import build_hca_context
    ctx = build_hca_context()
    p1 = next(p for p in ctx["products"] if p["id"] == "p1")
    assert len(p1["recent_pa_runs"]) == 3


def test_build_hca_context_caps_pa_runs_at_10(db):
    from backend.hca import build_hca_context
    with db._conn() as conn:
        for i in range(15):
            conn.execute(
                "INSERT INTO orchestrator_runs "
                "(product_id, triggered_by, status, decisions, brief) "
                "VALUES ('p1', 'schedule', 'complete', '[]', ?)",
                (f"Brief {i}",),
            )
    ctx = build_hca_context()
    p1 = next(p for p in ctx["products"] if p["id"] == "p1")
    assert len(p1["recent_pa_runs"]) <= 10


def test_build_hca_context_includes_active_directives(populated_db):
    from backend.hca import build_hca_context
    ctx = build_hca_context()
    p1 = next(p for p in ctx["products"] if p["id"] == "p1")
    contents = [d["content"] for d in p1["active_directives"]]
    assert "Focus on enterprise" in contents
    assert "All products: cut costs" in contents


def test_build_hca_context_empty_products_no_error(db):
    from backend.hca import build_hca_context
    ctx = build_hca_context()
    assert isinstance(ctx["products"], list)
    assert isinstance(ctx["recent_hca_runs"], list)


def test_build_hca_context_recent_hca_runs(populated_db):
    from backend.hca import build_hca_context
    populated_db.save_hca_run("schedule", "complete", [], "HCA summary")
    ctx = build_hca_context()
    assert len(ctx["recent_hca_runs"]) >= 1
    assert any(r["brief"] == "HCA summary" for r in ctx["recent_hca_runs"])
