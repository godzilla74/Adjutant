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


@pytest.fixture
def hca_db(db):
    """DB with two products and a workstream on p1."""
    with db._conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO products (id, name, icon_label, color) "
            "VALUES ('p2', 'Beta', 'B', '#111')"
        )
        conn.execute(
            "INSERT INTO workstreams (product_id, name, status, display_order, mission, schedule) "
            "VALUES ('p1', 'Research', 'paused', 1, 'Track market', 'weekly on mondays')"
        )
    return db


def test_apply_hca_issue_directive(hca_db):
    from backend.hca import apply_hca_decisions
    run_id = hca_db.save_hca_run("schedule", "complete", [], "")
    decisions = [{"action": "issue_directive", "product_id": "p1",
                  "content": "Focus on enterprise", "reason": "market shift"}]
    annotated = apply_hca_decisions(decisions, run_id)
    assert annotated[0]["_status"] == "applied"
    directives = hca_db.list_hca_directives("p1")
    assert any(d["content"] == "Focus on enterprise" for d in directives)


def test_apply_hca_issue_global_directive(hca_db):
    from backend.hca import apply_hca_decisions
    run_id = hca_db.save_hca_run("schedule", "complete", [], "")
    decisions = [{"action": "issue_directive",
                  "content": "All products: cut scope", "reason": "budget"}]
    annotated = apply_hca_decisions(decisions, run_id)
    assert annotated[0]["_status"] == "applied"
    directives = hca_db.list_hca_directives()
    assert any(d["content"] == "All products: cut scope" and d["product_id"] is None
               for d in directives)


def test_apply_hca_supersede_directive(hca_db):
    from backend.hca import apply_hca_decisions
    run_id = hca_db.save_hca_run("schedule", "complete", [], "")
    old_id = hca_db.create_hca_directive("p1", "Old guidance", run_id)
    decisions = [{"action": "supersede_directive", "directive_id": old_id,
                  "replacement": "New guidance", "reason": "updated"}]
    annotated = apply_hca_decisions(decisions, run_id)
    assert annotated[0]["_status"] == "applied"
    with hca_db._conn() as conn:
        old = conn.execute("SELECT status FROM hca_directives WHERE id = ?", (old_id,)).fetchone()
    assert old["status"] == "superseded"


def test_apply_hca_pa_action_updates_mission(hca_db):
    from backend.hca import apply_hca_decisions
    ws_id = hca_db.get_workstreams("p1")[0]["id"]
    run_id = hca_db.save_hca_run("schedule", "complete", [], "")
    decisions = [{
        "action": "pa_action",
        "product_id": "p1",
        "pa_decision": {"action": "update_mission", "workstream_id": ws_id,
                        "new_mission": "New mission from HCA", "reason": "strategic pivot"},
        "reason": "HCA directive",
    }]
    annotated = apply_hca_decisions(decisions, run_id)
    assert annotated[0]["_status"] == "applied"
    ws = hca_db.get_workstreams("p1")[0]
    assert ws["mission"] == "New mission from HCA"


def test_apply_hca_pa_action_bypasses_pa_autonomy(hca_db):
    """HCA executes PA actions directly, bypassing approval_required autonomy settings."""
    from backend.hca import apply_hca_decisions
    from backend.db import _ORCHESTRATOR_DEFAULT_AUTONOMY
    assert _ORCHESTRATOR_DEFAULT_AUTONOMY["pause_workstream"] == "approval_required"
    ws_id = hca_db.get_workstreams("p1")[0]["id"]
    run_id = hca_db.save_hca_run("schedule", "complete", [], "")
    decisions = [{
        "action": "pa_action",
        "product_id": "p1",
        "pa_decision": {"action": "update_schedule", "workstream_id": ws_id,
                        "new_schedule": "daily at 9am", "reason": "HCA override"},
        "reason": "speed up",
    }]
    annotated = apply_hca_decisions(decisions, run_id)
    assert annotated[0]["_status"] == "applied"


def test_apply_hca_propose_new_product_creates_review_item(hca_db):
    from backend.hca import apply_hca_decisions
    run_id = hca_db.save_hca_run("schedule", "complete", [], "")
    decisions = [{
        "action": "propose_new_product",
        "name": "Acme Analytics",
        "description": "Analytics for enterprise",
        "goals": "Drive expansion revenue",
        "icon_label": "📊",
        "color": "#6366f1",
        "suggested_workstreams": [
            {"name": "Research", "mission": "Track analytics market",
             "schedule": "weekly on mondays at 9am",
             "workstream_type": "research", "tag_subscriptions": ["research:"]}
        ],
        "reason": "Opportunity from PA briefs",
    }]
    annotated = apply_hca_decisions(decisions, run_id)
    assert annotated[0]["_status"] == "queued"
    with hca_db._conn() as conn:
        row = conn.execute(
            "SELECT action_type, payload FROM review_items WHERE action_type = 'hca_new_product'"
        ).fetchone()
    assert row is not None
    payload = json.loads(row["payload"])
    assert payload["name"] == "Acme Analytics"
    # Ensure no product row was created
    with hca_db._conn() as conn:
        p = conn.execute("SELECT id FROM products WHERE name = 'Acme Analytics'").fetchone()
    assert p is None


def test_apply_hca_portfolio_gap_creates_review_item(hca_db):
    from backend.hca import apply_hca_decisions
    run_id = hca_db.save_hca_run("schedule", "complete", [], "")
    decisions = [{"action": "portfolio_gap",
                  "description": "No video content workstream", "reason": "gap in content strategy"}]
    annotated = apply_hca_decisions(decisions, run_id)
    assert annotated[0]["_status"] == "applied"
    with hca_db._conn() as conn:
        row = conn.execute(
            "SELECT action_type FROM review_items WHERE action_type = 'portfolio_gap'"
        ).fetchone()
    assert row is not None


def test_apply_hca_unknown_action_skipped(hca_db):
    from backend.hca import apply_hca_decisions
    run_id = hca_db.save_hca_run("schedule", "complete", [], "")
    decisions = [
        {"action": "bogus_action", "reason": "test"},
        {"action": "issue_directive", "product_id": "p1", "content": "Still applies", "reason": "test"},
    ]
    annotated = apply_hca_decisions(decisions, run_id)
    assert annotated[0]["_status"] == "skipped"
    assert annotated[1]["_status"] == "applied"


def test_apply_hca_pa_action_nonexistent_product_skipped(hca_db):
    from backend.hca import apply_hca_decisions
    run_id = hca_db.save_hca_run("schedule", "complete", [], "")
    decisions = [{
        "action": "pa_action",
        "product_id": "no_such_product",
        "pa_decision": {"action": "update_mission", "workstream_id": 999,
                        "new_mission": "nope", "reason": "test"},
        "reason": "test",
    }]
    annotated = apply_hca_decisions(decisions, run_id)
    assert annotated[0]["_status"] == "skipped"


def test_launch_product_from_hca(hca_db):
    import asyncio
    from backend.hca import launch_product_from_hca
    payload = {
        "name": "New Product",
        "description": "A brand new product",
        "goals": "Grow revenue",
        "icon_label": "🚀",
        "color": "#22c55e",
        "suggested_workstreams": [
            {"name": "Research", "mission": "Track market trends",
             "schedule": "weekly on mondays at 9am",
             "tag_subscriptions": ["research:"]}
        ],
    }
    broadcast_calls = []
    async def mock_broadcast(event): broadcast_calls.append(event)
    asyncio.run(launch_product_from_hca(payload, mock_broadcast))
    # Product created
    with hca_db._conn() as conn:
        p = conn.execute("SELECT * FROM products WHERE name = 'New Product'").fetchone()
    assert p is not None
    # Workstream created
    ws_list = hca_db.get_workstreams(p["id"])
    assert any(w["name"] == "Research" for w in ws_list)
    # PA enabled
    cfg = hca_db.get_orchestrator_config(p["id"])
    assert cfg["enabled"] == 1
    # Broadcast fired with correct fields
    launched = next((e for e in broadcast_calls if e["type"] == "product_launched"), None)
    assert launched is not None
    assert launched["product_id"] == "new-product"
    assert launched["product_name"] == "New Product"
    assert launched["source"] == "hca"


def test_run_hca_full_integration(hca_db):
    import asyncio
    from unittest.mock import AsyncMock, MagicMock
    from backend.hca import run_hca

    mock_response = MagicMock()
    mock_response.content = [MagicMock()]
    mock_response.content[0].text = json.dumps({
        "decisions": [
            {"action": "issue_directive", "product_id": "p1",
             "content": "Focus on growth", "reason": "PA brief indicates stagnation"},
        ],
        "brief": "Portfolio is performing well overall.",
    })
    mock_provider = AsyncMock()
    mock_provider.create = AsyncMock(return_value=mock_response)

    broadcast_calls = []
    async def mock_broadcast(event): broadcast_calls.append(event)

    async def run():
        with __import__("unittest.mock", fromlist=["patch"]).patch(
            "backend.hca.make_provider", return_value=mock_provider
        ):
            await run_hca("schedule", mock_broadcast)

    asyncio.run(run())

    runs = hca_db.list_hca_runs()
    assert len(runs) == 1
    assert runs[0]["status"] == "complete"
    assert runs[0]["brief"] == "Portfolio is performing well overall."
    assert any(d["action"] == "issue_directive" for d in runs[0]["decisions"])

    cfg = hca_db.get_hca_config()
    assert cfg["next_run_at"] is not None
    assert cfg["last_run_at"] is not None

    assert any(e["type"] == "hca_run_complete" for e in broadcast_calls)


def test_run_hca_malformed_json_saves_error(hca_db):
    import asyncio
    from unittest.mock import AsyncMock, MagicMock
    from backend.hca import run_hca

    mock_response = MagicMock()
    mock_response.content = [MagicMock()]
    mock_response.content[0].text = "not valid json at all"
    mock_provider = AsyncMock()
    mock_provider.create = AsyncMock(return_value=mock_response)

    broadcast_calls = []
    async def mock_broadcast(event): broadcast_calls.append(event)

    async def run():
        with __import__("unittest.mock", fromlist=["patch"]).patch(
            "backend.hca.make_provider", return_value=mock_provider
        ):
            await run_hca("schedule", mock_broadcast)

    asyncio.run(run())

    runs = hca_db.list_hca_runs()
    assert runs[0]["status"] == "error"
    cfg = hca_db.get_hca_config()
    assert cfg["next_run_at"] is not None   # next_run_at still updated
    assert cfg["last_run_at"] is not None   # last_run_at still updated
