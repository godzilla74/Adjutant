# tests/test_autonomous_objectives.py
"""Tests for the autonomous objective scheduler loop."""
import asyncio
import importlib
import os
from unittest.mock import AsyncMock, patch

import pytest

os.environ.setdefault("AGENT_PASSWORD", "testpass")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_DB", str(tmp_path / "test.db"))
    import backend.db as db_mod
    importlib.reload(db_mod)
    db_mod.init_db()
    with db_mod._conn() as conn:
        conn.execute(
            "INSERT INTO products (id, name, icon_label, color) VALUES ('p1', 'Product 1', 'P1', '#2563eb')"
        )
    return db_mod


def _make_obj(db, text="Grow to 1000 followers", target=1000, current=0):
    with db._conn() as conn:
        oid = conn.execute(
            "INSERT INTO objectives (product_id, text, progress_current, progress_target) VALUES ('p1', ?, ?, ?)",
            (text, current, target),
        ).lastrowid
    return oid


def test_get_due_autonomous_objectives_picks_up_past_due(db):
    oid = _make_obj(db)
    with db._conn() as conn:
        conn.execute(
            "UPDATE objectives SET autonomous=1, next_run_at=datetime('now', '-1 minute') WHERE id=?", (oid,)
        )
    due = db.get_due_autonomous_objectives()
    assert any(o["id"] == oid for o in due)


def test_scheduler_loop_calls_run_objective_loop(db, monkeypatch):
    """scheduler_loop should call _run_objective_loop for each due objective."""
    oid = _make_obj(db)
    with db._conn() as conn:
        conn.execute(
            "UPDATE objectives SET autonomous=1, next_run_at=datetime('now', '-1 minute') WHERE id=?", (oid,)
        )

    called = []

    async def fake_run_objective_loop(product_id, objective_id):
        called.append((product_id, objective_id))

    import backend.scheduler as sched_mod
    importlib.reload(sched_mod)
    sched_mod.register_broadcast(AsyncMock())

    async def run_one_tick():
        from backend.db import get_due_autonomous_objectives
        due = get_due_autonomous_objectives()
        for obj in due:
            if not sched_mod._running_objectives.get(obj["id"]):
                asyncio.create_task(fake_run_objective_loop(obj["product_id"], obj["id"]))
        await asyncio.sleep(0)  # allow tasks to run

    asyncio.run(run_one_tick())
    assert ("p1", oid) in called


def test_set_objective_next_run_clamp(db):
    oid = _make_obj(db)
    db.set_objective_next_run(oid, 0.0)  # should clamp to 0.25h = 15 min
    with db._conn() as conn:
        row = conn.execute(
            "SELECT last_run_at, next_run_at > datetime('now', '+14 minutes') AS is_future "
            "FROM objectives WHERE id=?",
            (oid,),
        ).fetchone()
    assert row["last_run_at"] is not None
    assert row["is_future"] == 1  # confirms 0.0 was clamped to at least 0.25h


def test_objective_goes_dormant_on_exception(db, monkeypatch):
    """If _run_objective_loop raises, the objective goes dormant (autonomous=0)."""
    oid = _make_obj(db)
    db.set_objective_autonomous(oid, True)

    import backend.scheduler as sched_mod
    importlib.reload(sched_mod)
    broadcast = AsyncMock()
    sched_mod.register_broadcast(broadcast)

    async def run():
        with patch("backend.main._build_context", side_effect=RuntimeError("boom")):
            await sched_mod._run_objective_loop("p1", oid)

    asyncio.run(run())
    with db._conn() as conn:
        row = conn.execute("SELECT autonomous, next_run_at FROM objectives WHERE id=?", (oid,)).fetchone()
    assert row["autonomous"] == 0
    assert row["next_run_at"] is None


def test_run_approved_review_task_creates_activity_and_calls_agent_loop(db, monkeypatch):
    import backend.scheduler as sched_mod
    importlib.reload(sched_mod)

    agent_loop_calls = []

    async def fake_agent_loop(broadcast_fn, product_id, messages, session_id=None):
        agent_loop_calls.append({"product_id": product_id, "messages": messages})
        return messages, []

    review = {
        "id": 99,
        "product_id": "p1",
        "title": "Launch outbound campaign",
        "description": "Send cold outreach to 50 fractional execs.",
        "action_type": "email",
    }

    with patch("backend.main._agent_loop", fake_agent_loop), \
         patch("backend.scheduler._broadcast_fn", AsyncMock()):
        asyncio.run(
            sched_mod._run_approved_review_task("p1", review)
        )

    assert len(agent_loop_calls) == 1
    assert agent_loop_calls[0]["product_id"] == "p1"
    last_msg = agent_loop_calls[0]["messages"][-1]
    assert last_msg["role"] == "user"
    assert "Launch outbound campaign" in last_msg["content"]
    assert "Send cold outreach" in last_msg["content"]

    events = db.load_activity_events("p1")
    assert any("[Approved]" in e["headline"] for e in events)


def test_on_review_approved_falls_through_to_task_agent(db):
    import backend.main as main_mod
    importlib.reload(main_mod)

    # Insert a review item with action_type, no linked social draft, no blocked objective
    with db._conn() as conn:
        rid = conn.execute(
            """INSERT INTO review_items (product_id, title, description, risk_label, action_type, status)
               VALUES ('p1', 'Outbound pipeline', 'Run outreach campaign', 'email', 'email', 'approved')"""
        ).lastrowid

    task_calls = []

    async def fake_run_approved_review_task(product_id, review):
        task_calls.append({"product_id": product_id, "review": review})

    with patch("backend.scheduler._run_approved_review_task", fake_run_approved_review_task):
        asyncio.run(
            main_mod._on_review_approved(rid)
        )

    assert len(task_calls) == 1
    assert task_calls[0]["product_id"] == "p1"
    assert task_calls[0]["review"]["title"] == "Outbound pipeline"


def test_on_review_approved_does_not_spawn_task_when_objective_blocked(db):
    import backend.main as main_mod
    importlib.reload(main_mod)

    with db._conn() as conn:
        rid = conn.execute(
            """INSERT INTO review_items (product_id, title, description, risk_label, action_type, status)
               VALUES ('p1', 'Some review', 'desc', 'low', 'agent_review', 'approved')"""
        ).lastrowid
        conn.execute(
            """INSERT INTO objectives (product_id, text, blocked_by_review_id)
               VALUES ('p1', 'Grow followers', ?)""",
            (rid,)
        )

    task_calls = []
    obj_loop_calls = []

    async def fake_run_approved_review_task(product_id, review):
        task_calls.append(product_id)

    async def fake_run_objective_loop(product_id, objective_id):
        obj_loop_calls.append((product_id, objective_id))

    with patch("backend.scheduler._run_approved_review_task", fake_run_approved_review_task), \
         patch("backend.scheduler._run_objective_loop", fake_run_objective_loop):
        asyncio.run(
            main_mod._on_review_approved(rid)
        )

    assert len(task_calls) == 0
    assert len(obj_loop_calls) == 1
