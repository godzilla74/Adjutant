# tests/test_launch_wizard.py
"""Tests for the launch wizard scheduler loop."""
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


def test_launch_wizard_clears_flag_on_exception(db, monkeypatch):
    """If _agent_loop raises, _run_launch_wizard clears launch_wizard_active."""
    db.set_launch_wizard_active('p1', True)

    import backend.scheduler as sched_mod
    importlib.reload(sched_mod)
    sched_mod.register_broadcast(AsyncMock())

    async def run():
        with patch("backend.main._agent_loop", side_effect=RuntimeError("boom")):
            with patch("backend.main._build_context", return_value=[]):
                await sched_mod._run_launch_wizard(
                    "p1", "test-session-id", "A great product", "Grow to 1000 users"
                )

    asyncio.run(run())

    with db._conn() as conn:
        row = conn.execute("SELECT launch_wizard_active FROM products WHERE id='p1'").fetchone()
    assert row["launch_wizard_active"] == 0


def test_launch_wizard_in_flight_guard(db, monkeypatch):
    """Second call to _run_launch_wizard with same product_id returns immediately."""
    import backend.scheduler as sched_mod
    importlib.reload(sched_mod)
    sched_mod.register_broadcast(AsyncMock())

    call_count = []

    async def slow_agent_loop(*args, **kwargs):
        call_count.append(1)
        await asyncio.sleep(0.05)
        return [], []

    async def run():
        with patch("backend.main._agent_loop", side_effect=slow_agent_loop):
            with patch("backend.main._build_context", return_value=[]):
                t1 = asyncio.create_task(
                    sched_mod._run_launch_wizard("p1", "sid1", "desc", "goal")
                )
                t2 = asyncio.create_task(
                    sched_mod._run_launch_wizard("p1", "sid2", "desc", "goal")
                )
                await asyncio.gather(t1, t2)

    asyncio.run(run())

    assert len(call_count) == 1
