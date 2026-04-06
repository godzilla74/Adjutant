# tests/test_db.py
import importlib
import json
import os
import pytest


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("HANNAH_DB", str(tmp_path / "test.db"))
    import backend.db as db_mod
    importlib.reload(db_mod)
    db_mod.init_db()
    return db_mod


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
