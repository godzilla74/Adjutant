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


import uuid as _uuid


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
