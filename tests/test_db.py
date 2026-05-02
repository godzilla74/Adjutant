# tests/test_db.py
import importlib
import os
import pytest
import sys


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_DB", str(tmp_path / "test.db"))
    import backend.db as db_mod
    importlib.reload(db_mod)
    db_mod.init_db()
    # Create test products so FK constraints pass in tests that use these IDs
    with db_mod._conn() as conn:
        conn.execute("INSERT OR IGNORE INTO products (id, name, icon_label, color) VALUES ('test-product', 'Test Product', 'TP', '#2563eb')")
        conn.execute("INSERT OR IGNORE INTO products (id, name, icon_label, color) VALUES ('test-product-2', 'Test Product 2', 'T2', '#ea580c')")
    return db_mod


def test_default_db_path_uses_os_convention(monkeypatch):
    """When AGENT_DB is not set, DB_PATH should use OS user data dir, not ~/.hannah."""
    monkeypatch.delenv("AGENT_DB", raising=False)
    import backend.db as db_mod
    importlib.reload(db_mod)
    path_str = str(db_mod.DB_PATH)
    assert ".hannah" not in path_str
    assert "adjutant" in path_str.lower()


def test_no_hardcoded_products_seeded(tmp_path, monkeypatch):
    """Without installer env vars, no products should be auto-seeded."""
    monkeypatch.setenv("AGENT_DB", str(tmp_path / "test.db"))
    monkeypatch.delenv("ADJUTANT_SEED_PRODUCT_ID", raising=False)
    monkeypatch.delenv("ADJUTANT_SEED_PRODUCT_NAME", raising=False)
    import backend.db as db_mod
    importlib.reload(db_mod)
    db_mod.init_db()
    assert db_mod.get_products() == []


def test_installer_product_seeded(db, monkeypatch):
    """With installer env vars set, the specified product is seeded."""
    import importlib
    import backend.seed_data as sd
    monkeypatch.setenv("ADJUTANT_SEED_PRODUCT_ID", "testco")
    monkeypatch.setenv("ADJUTANT_SEED_PRODUCT_NAME", "Test Company")
    importlib.reload(sd)
    import backend.db as db_mod
    importlib.reload(db_mod)
    db_mod.init_db()
    products = db_mod.get_products()
    ids = [p["id"] for p in products]
    assert "testco" in ids
    p = next(p for p in products if p["id"] == "testco")
    assert p["name"] == "Test Company"
    assert p["icon_label"] == "TC"
    assert "color" in p


def test_save_and_load_activity_event(db):
    event_id = db.save_activity_event(
        product_id="test-product",
        agent_type="research",
        headline="Researching competitors",
        rationale="Need pricing data",
        status="running",
    )
    assert isinstance(event_id, int)

    events = db.load_activity_events("test-product")
    assert len(events) == 1
    ev = events[0]
    assert ev["headline"] == "Researching competitors"
    assert ev["rationale"] == "Need pricing data"
    assert ev["status"] == "running"
    assert ev["id"] == event_id


def test_update_activity_event(db):
    event_id = db.save_activity_event(
        product_id="test-product",
        agent_type="research",
        headline="Research task",
        rationale="",
        status="running",
    )
    db.update_activity_event(event_id, status="done", summary="Found 4 competitors")
    events = db.load_activity_events("test-product")
    assert events[0]["status"] == "done"
    assert events[0]["summary"] == "Found 4 competitors"


def test_save_and_load_review_item(db):
    item_id = db.save_review_item(
        product_id="test-product",
        title="LinkedIn post",
        description="Launch announcement draft",
        risk_label="Public-facing · irreversible",
    )
    assert isinstance(item_id, int)

    items = db.load_review_items("test-product")
    assert len(items) == 1
    item = items[0]
    assert item["title"] == "LinkedIn post"
    assert item["status"] == "pending"
    assert item["id"] == item_id


def test_resolve_review_item(db):
    item_id = db.save_review_item(
        product_id="test-product",
        title="Test item",
        description="desc",
        risk_label="risk",
    )
    db.resolve_review_item(item_id, "approved")
    items = db.load_review_items("test-product")
    # pending items not shown
    assert all(i["id"] != item_id or i["status"] == "approved" for i in items)
    # confirmed by loading with status filter
    pending = db.load_review_items("test-product", status="pending")
    assert all(i["id"] != item_id for i in pending)


def test_messages_product_isolation(db):
    db.save_message("test-product", "user", "hello from P1")
    db.save_message("test-product-2", "user", "hello from P2")

    ro_msgs = db.load_messages("test-product")
    ig_msgs = db.load_messages("test-product-2")

    assert len(ro_msgs) == 1
    assert ro_msgs[0]["content"] == "hello from P1"
    assert len(ig_msgs) == 1
    assert ig_msgs[0]["content"] == "hello from P2"


def test_messages_json_roundtrip(db):
    db.save_message("test-product", "assistant", [{"type": "text", "text": "hi"}])
    msgs = db.load_messages("test-product")
    assert msgs[0]["content"] == [{"type": "text", "text": "hi"}]


def test_activity_events_product_isolation(db):
    db.save_activity_event("test-product", "research", "P1 task", "", "running")
    db.save_activity_event("test-product-2", "general", "P2 task", "", "done")

    ro = db.load_activity_events("test-product")
    ig = db.load_activity_events("test-product-2")

    assert len(ro) == 1
    assert ro[0]["headline"] == "P1 task"
    assert len(ig) == 1
    assert ig[0]["headline"] == "P2 task"


def test_update_activity_event_preserves_output_preview(db):
    event_id = db.save_activity_event(
        product_id="test-product",
        agent_type="general",
        headline="Task with preview",
        rationale="",
        status="running",
        output_preview="Initial preview text",
    )
    # Update status without passing output_preview — COALESCE should preserve original
    db.update_activity_event(event_id, status="done")
    events = db.load_activity_events("test-product")
    assert events[0]["output_preview"] == "Initial preview text"


def test_init_db_cleans_stale_running_events(db):
    # Insert a stale running event directly
    with db._conn() as conn:
        conn.execute(
            "INSERT INTO activity_events (product_id, agent_type, headline, status) "
            "VALUES ('test-product', 'research', 'Stale task', 'running')"
        )
    # Re-run init_db (simulates restart)
    db.init_db()
    # Verify it's now done
    with db._conn() as conn:
        row = conn.execute(
            "SELECT status FROM activity_events WHERE headline = 'Stale task'"
        ).fetchone()
    assert row is not None
    assert row[0] == 'done'


def test_seed_uses_env_var_product_when_set(tmp_path, monkeypatch):
    """When ADJUTANT_SEED_PRODUCT_ID is set, init_db seeds with that product only."""
    monkeypatch.setenv("AGENT_DB", str(tmp_path / "test.db"))
    monkeypatch.setenv("ADJUTANT_SEED_PRODUCT_ID", "acme-corp")
    monkeypatch.setenv("ADJUTANT_SEED_PRODUCT_NAME", "Acme Corp")
    import backend.db as db_mod
    importlib.reload(db_mod)
    db_mod.init_db()
    products = db_mod.get_products()
    ids = [p["id"] for p in products]
    assert "acme-corp" in ids
    assert "test-product" not in ids


def test_seed_empty_when_no_env_vars(tmp_path, monkeypatch):
    """Without ADJUTANT_SEED_PRODUCT_ID, init_db seeds no products."""
    monkeypatch.setenv("AGENT_DB", str(tmp_path / "test.db"))
    monkeypatch.delenv("ADJUTANT_SEED_PRODUCT_ID", raising=False)
    monkeypatch.delenv("ADJUTANT_SEED_PRODUCT_NAME", raising=False)
    import backend.db as db_mod
    importlib.reload(db_mod)
    db_mod.init_db()
    products = db_mod.get_products()
    assert products == []


def test_seed_icon_label_single_word_product(tmp_path, monkeypatch):
    """Single-word product names get a 2-char icon label from first two letters."""
    monkeypatch.setenv("AGENT_DB", str(tmp_path / "test.db"))
    monkeypatch.setenv("ADJUTANT_SEED_PRODUCT_ID", "acme")
    monkeypatch.setenv("ADJUTANT_SEED_PRODUCT_NAME", "Acme")
    import backend.db as db_mod
    importlib.reload(db_mod)
    db_mod.init_db()
    products = db_mod.get_products()
    acme = next(p for p in products if p["id"] == "acme")
    assert len(acme["icon_label"]) == 2
    assert acme["icon_label"] == "AC"


def test_create_session_returns_id(db):
    sid = db.create_session("Finance", "test-product")
    assert isinstance(sid, str)
    assert len(sid) > 0


def test_get_sessions_returns_product_sessions(db):
    db.create_session("Finance", "test-product")
    db.create_session("Ops", "test-product")
    sessions = db.get_sessions("test-product")
    names = [s["name"] for s in sessions]
    assert "Finance" in names
    assert "Ops" in names


def test_get_sessions_excludes_other_products(db):
    db.create_session("Finance", "test-product")
    db.create_session("Other", "test-product-2")
    sessions = db.get_sessions("test-product")
    names = [s["name"] for s in sessions]
    assert "Other" not in names


def test_get_sessions_global(db):
    db.create_session("Strategy", None)
    db.create_session("Finance", "test-product")
    sessions = db.get_sessions(None)
    names = [s["name"] for s in sessions]
    assert "Strategy" in names
    assert "Finance" not in names


def test_rename_session(db):
    sid = db.create_session("Old Name", "test-product")
    db.rename_session(sid, "New Name")
    sessions = db.get_sessions("test-product")
    names = [s["name"] for s in sessions]
    assert "New Name" in names
    assert "Old Name" not in names


def test_delete_session_cascades_messages(db):
    sid = db.create_session("Finance", "test-product")
    db.save_message("test-product", "user", "hello", sid)
    db.delete_session(sid)
    # Session gone
    assert db.get_sessions("test-product") == []
    # Messages gone (cascade) — verify directly in DB
    with db._conn() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM messages WHERE session_id = ?", (sid,)
        ).fetchone()[0]
    assert count == 0


def test_get_first_session(db):
    db.create_session("Alpha", "test-product")
    db.create_session("Beta", "test-product")
    first = db.get_first_session("test-product")
    assert first is not None
    assert first["name"] in ("Alpha", "Beta")


def test_load_messages_scoped_to_session(db):
    sid1 = db.create_session("Finance", "test-product")
    sid2 = db.create_session("Ops", "test-product")
    db.save_message("test-product", "user", "finance msg", sid1)
    db.save_message("test-product", "user", "ops msg", sid2)
    msgs1 = db.load_messages("test-product", sid1, limit=50)
    msgs2 = db.load_messages("test-product", sid2, limit=50)
    assert any("finance msg" in str(m["content"]) for m in msgs1)
    assert not any("ops msg" in str(m["content"]) for m in msgs1)
    assert any("ops msg" in str(m["content"]) for m in msgs2)


def test_save_and_get_summary_with_session(db):
    sid = db.create_session("S", "test-product")
    db.save_conversation_summary("test-product", "session summary", sid)
    assert db.get_conversation_summary("test-product", sid) == "session summary"


def test_save_summary_session_and_product_dont_conflict(db):
    """Product-level and session-level summaries coexist without IntegrityError."""
    db.save_conversation_summary("test-product", "product summary")
    sid = db.create_session("S", "test-product")
    db.save_conversation_summary("test-product", "session summary", sid)
    assert db.get_conversation_summary("test-product") == "product summary"
    assert db.get_conversation_summary("test-product", sid) == "session summary"


def test_migration_creates_general_session(tmp_path, monkeypatch):
    """init_db migrates existing messages into a General session."""
    monkeypatch.setenv("AGENT_DB", str(tmp_path / "migrate.db"))
    import backend.db as db_mod
    import importlib
    importlib.reload(db_mod)
    db_mod.init_db()
    with db_mod._conn() as conn:
        conn.execute(
            "INSERT INTO products (id, name, icon_label, color) VALUES ('co', 'Co', 'C', '#000')"
        )
        # Insert a legacy message with no session_id
        conn.execute(
            "INSERT INTO messages (product_id, role, content) VALUES ('co', 'user', 'legacy')"
        )
    # Re-run init_db — migration should create General session and assign message
    db_mod.init_db()
    sessions = db_mod.get_sessions("co")
    assert len(sessions) == 1
    assert sessions[0]["name"] == "General"
    msgs = db_mod.load_messages("co", sessions[0]["id"], limit=50)
    assert any("legacy" in str(m["content"]) for m in msgs)


def test_set_objective_autonomous_on(db):
    with db._conn() as conn:
        oid = conn.execute(
            "INSERT INTO objectives (product_id, text) VALUES ('test-product', 'Grow followers')"
        ).lastrowid
    db.set_objective_autonomous(oid, True)
    with db._conn() as conn:
        row = conn.execute("SELECT autonomous, next_run_at FROM objectives WHERE id = ?", (oid,)).fetchone()
    assert row["autonomous"] == 1
    assert row["next_run_at"] is not None


def test_set_objective_autonomous_off(db):
    with db._conn() as conn:
        oid = conn.execute(
            "INSERT INTO objectives (product_id, text) VALUES ('test-product', 'Grow followers')"
        ).lastrowid
        # Set blocked state to verify it gets cleared
        conn.execute(
            "UPDATE objectives SET autonomous=1, blocked_by_review_id=99, next_run_at=datetime('now') WHERE id=?",
            (oid,),
        )
    db.set_objective_autonomous(oid, False)
    with db._conn() as conn:
        row = conn.execute(
            "SELECT autonomous, next_run_at, blocked_by_review_id FROM objectives WHERE id = ?", (oid,)
        ).fetchone()
    assert row["autonomous"] == 0
    assert row["next_run_at"] is None
    assert row["blocked_by_review_id"] is None


def test_get_due_autonomous_objectives(db):
    with db._conn() as conn:
        oid = conn.execute(
            "INSERT INTO objectives (product_id, text) VALUES ('test-product', 'Grow followers')"
        ).lastrowid
        conn.execute(
            "UPDATE objectives SET autonomous=1, next_run_at=datetime('now', '-1 minute') WHERE id=?",
            (oid,),
        )
    due = db.get_due_autonomous_objectives()
    assert any(o["id"] == oid for o in due)


def test_get_due_autonomous_objectives_excludes_blocked(db):
    with db._conn() as conn:
        oid = conn.execute(
            "INSERT INTO objectives (product_id, text) VALUES ('test-product', 'Grow followers')"
        ).lastrowid
        conn.execute(
            "UPDATE objectives SET autonomous=1, next_run_at=datetime('now', '-1 minute'), blocked_by_review_id=99 WHERE id=?",
            (oid,),
        )
    due = db.get_due_autonomous_objectives()
    assert not any(o["id"] == oid for o in due)


def test_get_due_autonomous_objectives_excludes_future(db):
    with db._conn() as conn:
        oid = conn.execute(
            "INSERT INTO objectives (product_id, text) VALUES ('test-product', 'Grow followers')"
        ).lastrowid
        conn.execute(
            "UPDATE objectives SET autonomous=1, next_run_at=datetime('now', '+1 hour') WHERE id=?",
            (oid,),
        )
    due = db.get_due_autonomous_objectives()
    assert not any(o["id"] == oid for o in due)


def test_set_objective_next_run_clamps_minimum(db):
    with db._conn() as conn:
        oid = conn.execute(
            "INSERT INTO objectives (product_id, text) VALUES ('test-product', 'Grow followers')"
        ).lastrowid
    db.set_objective_next_run(oid, 0)  # should clamp to 0.25h = 15 min
    with db._conn() as conn:
        row = conn.execute(
            "SELECT next_run_at > datetime('now', '+14 minutes') AS is_future FROM objectives WHERE id=?",
            (oid,),
        ).fetchone()
    assert row["is_future"] == 1


def test_get_objective_blocked_by_review(db):
    with db._conn() as conn:
        oid = conn.execute(
            "INSERT INTO objectives (product_id, text) VALUES ('test-product', 'Grow followers')"
        ).lastrowid
        conn.execute("UPDATE objectives SET blocked_by_review_id=42 WHERE id=?", (oid,))
    result = db.get_objective_blocked_by_review(42)
    assert result is not None
    assert result["id"] == oid


def test_clear_objective_block(db):
    with db._conn() as conn:
        oid = conn.execute(
            "INSERT INTO objectives (product_id, text) VALUES ('test-product', 'Grow followers')"
        ).lastrowid
        conn.execute("UPDATE objectives SET autonomous=1, blocked_by_review_id=42, next_run_at=NULL WHERE id=?", (oid,))
    db.clear_objective_block(oid)
    with db._conn() as conn:
        row = conn.execute("SELECT blocked_by_review_id, next_run_at FROM objectives WHERE id=?", (oid,)).fetchone()
    assert row["blocked_by_review_id"] is None
    assert row["next_run_at"] is not None


def test_get_objectives_returns_new_fields(db):
    with db._conn() as conn:
        conn.execute(
            "INSERT INTO objectives (product_id, text) VALUES ('test-product', 'Grow followers')"
        )
    objs = db.get_objectives('test-product')
    assert len(objs) == 1
    assert "autonomous" in objs[0]
    assert "next_run_at" in objs[0]
    assert "blocked_by_review_id" in objs[0]


def test_schedule_next_run_tool(db, monkeypatch):
    """schedule_next_run tool calls set_objective_next_run with clamping."""
    import importlib
    import core.tools as tools_mod
    importlib.reload(tools_mod)
    with db._conn() as conn:
        oid = conn.execute(
            "INSERT INTO objectives (product_id, text) VALUES ('test-product', 'Grow followers')"
        ).lastrowid
    import asyncio
    result = asyncio.run(
        tools_mod.execute_tool("schedule_next_run", {"objective_id": oid, "hours": 8.0, "reason": "posted today"})
    )
    assert "8" in result
    with db._conn() as conn:
        row = conn.execute("SELECT next_run_at FROM objectives WHERE id=?", (oid,)).fetchone()
    assert row["next_run_at"] is not None


def test_update_objective_progress_tool(db, monkeypatch):
    import importlib
    import core.tools as tools_mod
    importlib.reload(tools_mod)
    with db._conn() as conn:
        oid = conn.execute(
            "INSERT INTO objectives (product_id, text, progress_target) VALUES ('test-product', 'Grow followers', 1000)"
        ).lastrowid
    import asyncio
    asyncio.run(
        tools_mod.execute_tool("update_objective_progress", {"objective_id": oid, "current": 250, "notes": "checked API"})
    )
    with db._conn() as conn:
        row = conn.execute("SELECT progress_current FROM objectives WHERE id=?", (oid,)).fetchone()
    assert row["progress_current"] == 250


def test_set_objective_autonomous_tool(db):
    import importlib
    import core.tools as tools_mod
    importlib.reload(tools_mod)
    with db._conn() as conn:
        oid = conn.execute(
            "INSERT INTO objectives (product_id, text) VALUES ('test-product', 'Grow followers')"
        ).lastrowid
    import asyncio
    result = asyncio.run(
        tools_mod.execute_tool("set_objective_autonomous", {"objective_id": oid, "autonomous": True})
    )
    assert "enabled" in result
    with db._conn() as conn:
        row = conn.execute("SELECT autonomous, next_run_at FROM objectives WHERE id=?", (oid,)).fetchone()
    assert row["autonomous"] == 1
    assert row["next_run_at"] is not None


def test_set_launch_wizard_active(db):
    """set_launch_wizard_active toggles the flag on and off."""
    with db._conn() as conn:
        conn.execute("INSERT INTO products (id, name, icon_label, color) VALUES ('wiz-p', 'WizP', 'WP', '#000')")

    db.set_launch_wizard_active('wiz-p', True)
    with db._conn() as conn:
        row = conn.execute("SELECT launch_wizard_active FROM products WHERE id = 'wiz-p'").fetchone()
    assert row["launch_wizard_active"] == 1

    db.set_launch_wizard_active('wiz-p', False)
    with db._conn() as conn:
        row = conn.execute("SELECT launch_wizard_active FROM products WHERE id = 'wiz-p'").fetchone()
    assert row["launch_wizard_active"] == 0


def test_get_product_config_includes_launch_wizard_active(db):
    """get_product_config returns launch_wizard_active."""
    with db._conn() as conn:
        conn.execute("INSERT INTO products (id, name, icon_label, color) VALUES ('wiz-p2', 'WizP2', 'WP', '#000')")
    config = db.get_product_config('wiz-p2')
    assert "launch_wizard_active" in config
    assert config["launch_wizard_active"] == 0


def test_complete_launch_tool_clears_wizard_flag(db):
    """complete_launch tool executor clears launch_wizard_active."""
    import os, importlib
    os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
    with db._conn() as conn:
        conn.execute("INSERT INTO products (id, name, icon_label, color) VALUES ('lw-p', 'LWP', 'LW', '#000')")
    db.set_launch_wizard_active('lw-p', True)

    import core.tools as tools_mod
    importlib.reload(tools_mod)

    import asyncio
    result = asyncio.run(
        tools_mod.execute_tool("complete_launch", {"product_id": "lw-p", "summary": "Done!"})
    )
    assert result == "Done!"
    with db._conn() as conn:
        row = conn.execute("SELECT launch_wizard_active FROM products WHERE id='lw-p'").fetchone()
    assert row["launch_wizard_active"] == 0


def test_get_autonomy_config_resolution_order(db):
    """Master tier overrides action row; action row overrides default."""
    # Default: no config → approve
    tier, window = db.get_autonomy_config("test-product", "social_post")
    assert tier == "approve"
    assert window is None

    # Per-action row
    db.set_action_autonomy("test-product", "social_post", "auto", None)
    tier, window = db.get_autonomy_config("test-product", "social_post")
    assert tier == "auto"

    # Master overrides per-action row
    db.set_master_autonomy("test-product", "window", 15)
    tier, window = db.get_autonomy_config("test-product", "social_post")
    assert tier == "window"
    assert window == 15

    # Clearing master falls back to per-action row
    db.set_master_autonomy("test-product", None, None)
    tier, window = db.get_autonomy_config("test-product", "social_post")
    assert tier == "auto"


def test_auto_resolve_expired_reviews(db):
    """Only resolves items past their deadline; returns correct ids."""
    from datetime import datetime, timedelta
    item_id_past = db.save_review_item(
        "test-product", "Past", "desc", "risk", action_type="agent_review"
    )
    item_id_future = db.save_review_item(
        "test-product", "Future", "desc", "risk", action_type="agent_review"
    )
    # Set past deadline (UTC for consistency with DB timestamp handling)
    db.set_auto_approve_at(item_id_past, datetime.utcnow() - timedelta(minutes=1))
    # Set future deadline (UTC for consistency with DB timestamp handling)
    db.set_auto_approve_at(item_id_future, datetime.utcnow() + timedelta(minutes=10))

    resolved = db.auto_resolve_expired_reviews()
    assert len(resolved) == 1
    assert resolved[0]["id"] == item_id_past
    assert resolved[0]["product_id"] == "test-product"

    # Verify DB state
    with db._conn() as conn:
        row = conn.execute(
            "SELECT status FROM review_items WHERE id = ?", (item_id_past,)
        ).fetchone()
        assert row["status"] == "approved"
        row2 = conn.execute(
            "SELECT status FROM review_items WHERE id = ?", (item_id_future,)
        ).fetchone()
        assert row2["status"] == "pending"


def test_get_product_autonomy_settings(db):
    """Returns master tier and all per-action overrides."""
    db.set_master_autonomy("test-product", "window", 10)
    db.set_action_autonomy("test-product", "social_post", "auto", None)
    db.set_action_autonomy("test-product", "email", "window", 5)

    settings = db.get_product_autonomy_settings("test-product")
    assert settings["master_tier"] == "window"
    assert settings["master_window_minutes"] == 10
    overrides = {o["action_type"]: o for o in settings["action_overrides"]}
    assert overrides["social_post"]["tier"] == "auto"
    assert overrides["email"]["tier"] == "window"
    assert overrides["email"]["window_minutes"] == 5


def test_save_review_item_with_action_type(db):
    """action_type is stored and returned by load_review_items."""
    item_id = db.save_review_item(
        "test-product", "Title", "Desc", "Risk", action_type="social_post"
    )
    items = db.load_review_items("test-product")
    assert items[0]["action_type"] == "social_post"
    assert items[0]["auto_approve_at"] is None


def test_save_social_draft_with_scheduled_for(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_DB", str(tmp_path / "test.db"))
    import importlib, backend.db as db
    importlib.reload(db)
    db.init_db()
    with db._conn() as conn:
        conn.execute("INSERT INTO products (id, name, icon_label, color) VALUES ('p1', 'P', 'P', '#000')")
    draft_id = db.save_social_draft("p1", "twitter", "Hello world", scheduled_for="2099-01-01T09:00:00")
    with db._conn() as conn:
        row = dict(conn.execute("SELECT * FROM social_drafts WHERE id = ?", (draft_id,)).fetchone())
    assert row["scheduled_for"] == "2099-01-01T09:00:00"


def test_get_due_scheduled_drafts_returns_past_only(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_DB", str(tmp_path / "test.db"))
    import importlib, backend.db as db
    importlib.reload(db)
    db.init_db()
    with db._conn() as conn:
        conn.execute("INSERT INTO products (id, name, icon_label, color) VALUES ('p1', 'P', 'P', '#000')")
    # Past — due
    past_id = db.save_social_draft("p1", "twitter", "Past post",
                                    scheduled_for="2000-01-01T09:00:00")
    db.update_social_draft_status(past_id, "scheduled")
    # Future — not yet due
    future_id = db.save_social_draft("p1", "twitter", "Future post",
                                      scheduled_for="2099-01-01T09:00:00")
    db.update_social_draft_status(future_id, "scheduled")
    # No scheduled_for — should not appear
    plain_id = db.save_social_draft("p1", "twitter", "Plain post")
    db.update_social_draft_status(plain_id, "scheduled")

    due = db.get_due_scheduled_drafts()
    due_ids = [d["id"] for d in due]
    assert past_id in due_ids
    assert future_id not in due_ids
    assert plain_id not in due_ids


def test_save_and_get_browser_credential(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_DB", str(tmp_path / "test.db"))
    import importlib, backend.db as db
    importlib.reload(db)
    db.init_db()
    with db._conn() as conn:
        conn.execute("INSERT INTO products (id, name, icon_label, color) VALUES ('p1', 'P', 'P', '#000')")
    db.save_browser_credential("p1", "twitter", "myuser", "mypass", active=True)
    cred = db.get_browser_credential("p1", "twitter")
    assert cred is not None
    assert cred["username"] == "myuser"
    assert cred["password"] == "mypass"
    assert cred["active"] == 1


def test_save_browser_credential_upserts(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_DB", str(tmp_path / "test.db"))
    import importlib, backend.db as db
    importlib.reload(db)
    db.init_db()
    with db._conn() as conn:
        conn.execute("INSERT INTO products (id, name, icon_label, color) VALUES ('p1', 'P', 'P', '#000')")
    db.save_browser_credential("p1", "twitter", "user1", "pass1", active=True)
    db.save_browser_credential("p1", "twitter", "user2", "pass2", active=False)
    cred = db.get_browser_credential("p1", "twitter")
    assert cred["username"] == "user2"
    assert cred["active"] == 0


def test_delete_browser_credential(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_DB", str(tmp_path / "test.db"))
    import importlib, backend.db as db
    importlib.reload(db)
    db.init_db()
    with db._conn() as conn:
        conn.execute("INSERT INTO products (id, name, icon_label, color) VALUES ('p1', 'P', 'P', '#000')")
    db.save_browser_credential("p1", "twitter", "u", "p", active=True)
    db.delete_browser_credential("p1", "twitter")
    assert db.get_browser_credential("p1", "twitter") is None


def test_list_browser_credentials_omits_password(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_DB", str(tmp_path / "test.db"))
    import importlib, backend.db as db
    importlib.reload(db)
    db.init_db()
    with db._conn() as conn:
        conn.execute("INSERT INTO products (id, name, icon_label, color) VALUES ('p1', 'P', 'P', '#000')")
    db.save_browser_credential("p1", "twitter", "u1", "secret", active=True)
    db.save_browser_credential("p1", "linkedin", "u2", "secret2", active=False)
    results = db.list_browser_credentials("p1")
    assert len(results) == 2
    for r in results:
        assert "password" not in r
    services = {r["service"] for r in results}
    assert services == {"twitter", "linkedin"}


# ── run_reports ───────────────────────────────────────────────────────────────

def test_create_run_report_returns_id(db):
    report_id = db.create_run_report("test-product", 1, "Daily Brief", "Full output here")
    assert isinstance(report_id, int)
    assert report_id > 0


def test_get_run_reports_returns_most_recent_first(db):
    db.create_run_report("test-product", 1, "Brief A", "Output A")
    db.create_run_report("test-product", 2, "Brief B", "Output B")
    reports = db.get_run_reports("test-product")
    assert len(reports) == 2
    assert reports[0]["workstream_name"] == "Brief B"
    assert reports[1]["workstream_name"] == "Brief A"


def test_get_run_reports_scoped_to_product(db):
    db.create_run_report("test-product", 1, "Brief A", "Output A")
    db.create_run_report("test-product-2", 2, "Brief B", "Output B")
    reports = db.get_run_reports("test-product")
    assert len(reports) == 1
    assert reports[0]["workstream_name"] == "Brief A"


def test_get_run_report_returns_single(db):
    report_id = db.create_run_report("test-product", 1, "Brief", "Full content")
    report = db.get_run_report(report_id)
    assert report is not None
    assert report["full_output"] == "Full content"
    assert report["workstream_name"] == "Brief"


def test_get_run_report_returns_none_for_missing(db):
    assert db.get_run_report(99999) is None


def test_delete_run_report_removes_it(db):
    report_id = db.create_run_report("test-product", 1, "Brief", "Output")
    db.delete_run_report(report_id)
    assert db.get_run_report(report_id) is None


def test_delete_run_report_is_idempotent(db):
    report_id = db.create_run_report("test-product", 1, "Brief", "Output")
    db.delete_run_report(report_id)
    db.delete_run_report(report_id)  # should not raise


def test_update_activity_event_with_report_id(db):
    event_id = db.save_activity_event("test-product", "general", "Test", "Rationale")
    report_id = db.create_run_report("test-product", 1, "Brief", "Output")
    db.update_activity_event(event_id, status="done", summary="done", report_id=report_id)
    events = db.load_activity_events("test-product")
    assert events[0]["report_id"] == report_id


def test_load_activity_events_includes_report_id(db):
    event_id = db.save_activity_event("test-product", "general", "Test", "Rationale")
    events = db.load_activity_events("test-product")
    assert "report_id" in events[0]
    assert events[0]["report_id"] is None


# ── Tags ──────────────────────────────────────────────────────────────────

def test_create_and_list_tags(db):
    tag_id = db.create_tag("social:linkedin", "LinkedIn post opportunity")
    assert isinstance(tag_id, int)
    tags = db.list_tags()
    assert len(tags) == 1
    assert tags[0]["name"] == "social:linkedin"
    assert tags[0]["description"] == "LinkedIn post opportunity"
    assert tags[0]["id"] == tag_id


def test_create_tag_duplicate_name_raises(db):
    db.create_tag("social:linkedin", "First")
    with pytest.raises(Exception):
        db.create_tag("social:linkedin", "Second")


def test_update_tag(db):
    tag_id = db.create_tag("social:linkedin", "Old description")
    db.update_tag(tag_id, name="social:linkedin-post", description="New description")
    tags = db.list_tags()
    assert tags[0]["name"] == "social:linkedin-post"
    assert tags[0]["description"] == "New description"
    assert tags[0]["updated_at"] >= tags[0]["created_at"]


def test_delete_tag(db):
    tag_id = db.create_tag("social:linkedin", "Test")
    db.delete_tag(tag_id)
    assert db.list_tags() == []


def test_get_tag_by_name(db):
    db.create_tag("social:linkedin", "LinkedIn")
    tag = db.get_tag_by_name("social:linkedin")
    assert tag is not None
    assert tag["name"] == "social:linkedin"
    assert db.get_tag_by_name("nonexistent") is None


def test_get_tag_by_id(db):
    tag_id = db.create_tag("social:linkedin", "LinkedIn")
    tag = db.get_tag(tag_id)
    assert tag is not None
    assert tag["id"] == tag_id
    assert tag["name"] == "social:linkedin"
    assert db.get_tag(tag_id + 999) is None


# ── Signals ───────────────────────────────────────────────────────────────

def test_create_and_get_signals(db):
    tag_id = db.create_tag("social:linkedin", "LinkedIn")
    signal_id = db.create_signal(
        tag_id=tag_id,
        content_type="run_report",
        content_id=42,
        product_id="test-product",
        tagged_by="agent",
        note="New feature X — strong enterprise angle",
    )
    assert isinstance(signal_id, int)
    signals = db.get_signals(product_id="test-product", tag_prefix="social:")
    assert len(signals) == 1
    s = signals[0]
    assert s["tag_id"] == tag_id
    assert s["content_type"] == "run_report"
    assert s["content_id"] == 42
    assert s["note"] == "New feature X — strong enterprise angle"
    assert s["consumed_at"] is None
    assert s["tag_name"] == "social:linkedin"


def test_get_signals_excludes_consumed(db):
    tag_id = db.create_tag("social:linkedin", "LinkedIn")
    signal_id = db.create_signal(
        tag_id=tag_id,
        content_type="run_report",
        content_id=1,
        product_id="test-product",
        tagged_by="agent",
        note="Test",
    )
    db.consume_signal(signal_id)
    signals = db.get_signals(product_id="test-product", tag_prefix="social:")
    assert signals == []


def test_get_signals_scoped_to_product(db):
    tag_id = db.create_tag("social:linkedin", "LinkedIn")
    db.create_signal(tag_id=tag_id, content_type="run_report", content_id=1,
                     product_id="test-product", tagged_by="agent", note="A")
    db.create_signal(tag_id=tag_id, content_type="run_report", content_id=2,
                     product_id="test-product-2", tagged_by="agent", note="B")
    signals = db.get_signals(product_id="test-product", tag_prefix="social:")
    assert len(signals) == 1
    assert signals[0]["note"] == "A"


def test_get_signals_filters_by_prefix(db):
    tag1 = db.create_tag("social:linkedin", "LinkedIn")
    tag2 = db.create_tag("email:customers", "Email")
    db.create_signal(tag_id=tag1, content_type="run_report", content_id=1,
                     product_id="test-product", tagged_by="agent", note="Social")
    db.create_signal(tag_id=tag2, content_type="run_report", content_id=2,
                     product_id="test-product", tagged_by="agent", note="Email")
    social = db.get_signals(product_id="test-product", tag_prefix="social:")
    assert len(social) == 1
    assert social[0]["note"] == "Social"


def test_consume_signal(db):
    tag_id = db.create_tag("social:linkedin", "LinkedIn")
    signal_id = db.create_signal(tag_id=tag_id, content_type="run_report", content_id=1,
                                  product_id="test-product", tagged_by="agent", note="Test")
    db.consume_signal(signal_id)
    with db._conn() as conn:
        row = conn.execute("SELECT consumed_at FROM signals WHERE id = ?", (signal_id,)).fetchone()
    assert row["consumed_at"] is not None


def test_get_or_create_tag(db):
    tag_id1 = db.get_or_create_tag("social:linkedin", "LinkedIn")
    tag_id2 = db.get_or_create_tag("social:linkedin", "LinkedIn")
    assert tag_id1 == tag_id2
    assert len(db.list_tags()) == 1


def test_get_signals_include_consumed(db):
    tag_id = db.create_tag("social:linkedin", "LinkedIn")
    signal_id = db.create_signal(tag_id=tag_id, content_type="run_report", content_id=1,
                                  product_id="test-product", tagged_by="agent", note="Test")
    db.consume_signal(signal_id)
    all_signals = db.get_signals(product_id="test-product", include_consumed=True)
    assert len(all_signals) == 1
    assert all_signals[0]["consumed_at"] is not None


def test_workstream_tag_subscriptions_field(db):
    import json
    db.create_workstream("test-product", "Social Media", "paused")
    ws = db.get_workstreams("test-product")[0]
    ws_id = ws["id"]
    assert ws["tag_subscriptions"] == "[]"

    db.update_workstream_fields(ws_id, tag_subscriptions=json.dumps(["social:"]))
    ws = db.get_workstreams("test-product")[0]
    assert json.loads(ws["tag_subscriptions"]) == ["social:"]


def test_capability_gap_creates_review_item(db):
    import json
    # No workstream subscribes to "video:" tags
    db.create_tag("video:youtube", "YouTube opportunity")
    # Simulate the scheduler logic
    from backend.scheduler import _check_capability_gap
    _check_capability_gap(
        product_id="test-product",
        tag_name="video:youtube",
        note="Strong YouTube opportunity found",
    )
    items = db.load_review_items("test-product")
    assert len(items) == 1
    assert items[0]["action_type"] == "capability_gap"
    assert "video:youtube" in items[0]["title"]
