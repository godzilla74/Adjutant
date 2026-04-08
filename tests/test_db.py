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
    return db_mod


def test_default_db_path_uses_os_convention(monkeypatch):
    """When AGENT_DB is not set, DB_PATH should use OS user data dir, not ~/.hannah."""
    monkeypatch.delenv("AGENT_DB", raising=False)
    import backend.db as db_mod
    importlib.reload(db_mod)
    path_str = str(db_mod.DB_PATH)
    assert ".hannah" not in path_str
    assert "adjutant" in path_str.lower()


def test_products_seeded(db):
    products = db.get_products()
    ids = [p["id"] for p in products]
    assert "retainerops" in ids
    assert "ignitara" in ids
    assert "bullsi" in ids
    assert "eligibility" in ids
    assert all("name" in p and "icon_label" in p and "color" in p for p in products)


def test_workstreams_seeded(db):
    ws = db.get_workstreams("retainerops")
    names = [w["name"] for w in ws]
    assert "Marketing" in names
    assert "Growth" in names
    assert all("status" in w and "display_order" in w for w in ws)


def test_objectives_seeded(db):
    objs = db.get_objectives("retainerops")
    assert len(objs) >= 1
    assert all("text" in o and "progress_current" in o for o in objs)


def test_save_and_load_activity_event(db):
    event_id = db.save_activity_event(
        product_id="retainerops",
        agent_type="research",
        headline="Researching competitors",
        rationale="Need pricing data",
        status="running",
    )
    assert isinstance(event_id, int)

    events = db.load_activity_events("retainerops")
    assert len(events) == 1
    ev = events[0]
    assert ev["headline"] == "Researching competitors"
    assert ev["rationale"] == "Need pricing data"
    assert ev["status"] == "running"
    assert ev["id"] == event_id


def test_update_activity_event(db):
    event_id = db.save_activity_event(
        product_id="retainerops",
        agent_type="research",
        headline="Research task",
        rationale="",
        status="running",
    )
    db.update_activity_event(event_id, status="done", summary="Found 4 competitors")
    events = db.load_activity_events("retainerops")
    assert events[0]["status"] == "done"
    assert events[0]["summary"] == "Found 4 competitors"


def test_save_and_load_review_item(db):
    item_id = db.save_review_item(
        product_id="retainerops",
        title="LinkedIn post",
        description="Launch announcement draft",
        risk_label="Public-facing · irreversible",
    )
    assert isinstance(item_id, int)

    items = db.load_review_items("retainerops")
    assert len(items) == 1
    item = items[0]
    assert item["title"] == "LinkedIn post"
    assert item["status"] == "pending"
    assert item["id"] == item_id


def test_resolve_review_item(db):
    item_id = db.save_review_item(
        product_id="retainerops",
        title="Test item",
        description="desc",
        risk_label="risk",
    )
    db.resolve_review_item(item_id, "approved")
    items = db.load_review_items("retainerops")
    # pending items not shown
    assert all(i["id"] != item_id or i["status"] == "approved" for i in items)
    # confirmed by loading with status filter
    pending = db.load_review_items("retainerops", status="pending")
    assert all(i["id"] != item_id for i in pending)


def test_messages_product_isolation(db):
    db.save_message("retainerops", "user", "hello from RO")
    db.save_message("ignitara", "user", "hello from IG")

    ro_msgs = db.load_messages("retainerops")
    ig_msgs = db.load_messages("ignitara")

    assert len(ro_msgs) == 1
    assert ro_msgs[0]["content"] == "hello from RO"
    assert len(ig_msgs) == 1
    assert ig_msgs[0]["content"] == "hello from IG"


def test_messages_json_roundtrip(db):
    db.save_message("retainerops", "assistant", [{"type": "text", "text": "hi"}])
    msgs = db.load_messages("retainerops")
    assert msgs[0]["content"] == [{"type": "text", "text": "hi"}]


def test_activity_events_product_isolation(db):
    db.save_activity_event("retainerops", "research", "RO task", "", "running")
    db.save_activity_event("ignitara", "general", "IG task", "", "done")

    ro = db.load_activity_events("retainerops")
    ig = db.load_activity_events("ignitara")

    assert len(ro) == 1
    assert ro[0]["headline"] == "RO task"
    assert len(ig) == 1
    assert ig[0]["headline"] == "IG task"


def test_update_activity_event_preserves_output_preview(db):
    event_id = db.save_activity_event(
        product_id="retainerops",
        agent_type="general",
        headline="Task with preview",
        rationale="",
        status="running",
        output_preview="Initial preview text",
    )
    # Update status without passing output_preview — COALESCE should preserve original
    db.update_activity_event(event_id, status="done")
    events = db.load_activity_events("retainerops")
    assert events[0]["output_preview"] == "Initial preview text"


def test_init_db_cleans_stale_running_events(db):
    # Insert a stale running event directly
    with db._conn() as conn:
        conn.execute(
            "INSERT INTO activity_events (product_id, agent_type, headline, status) "
            "VALUES ('retainerops', 'research', 'Stale task', 'running')"
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
    assert "retainerops" not in ids


def test_seed_falls_back_to_hardcoded_when_env_not_set(tmp_path, monkeypatch):
    """Without ADJUTANT_SEED_PRODUCT_ID, init_db seeds the hardcoded products."""
    monkeypatch.setenv("AGENT_DB", str(tmp_path / "test.db"))
    monkeypatch.delenv("ADJUTANT_SEED_PRODUCT_ID", raising=False)
    import backend.db as db_mod
    importlib.reload(db_mod)
    db_mod.init_db()
    products = db_mod.get_products()
    ids = [p["id"] for p in products]
    assert "retainerops" in ids


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
