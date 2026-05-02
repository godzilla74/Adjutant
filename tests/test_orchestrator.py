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


def test_get_due_orchestrator_products_scheduled(db):
    from datetime import datetime, timedelta
    past = (datetime.now() - timedelta(minutes=1)).isoformat(timespec="seconds")
    db.update_orchestrator_config("p1", enabled=1, next_run_at=past)
    due = db.get_due_orchestrator_products()
    assert any(d["product_id"] == "p1" and d["trigger_type"] == "schedule" for d in due)


def test_get_due_orchestrator_products_not_due_when_disabled(db):
    from datetime import datetime, timedelta
    past = (datetime.now() - timedelta(minutes=1)).isoformat(timespec="seconds")
    db.update_orchestrator_config("p1", enabled=0, next_run_at=past)
    due = db.get_due_orchestrator_products()
    assert not any(d["product_id"] == "p1" for d in due)


@pytest.fixture
def populated_db(db):
    """DB with a product, workstream, tag, and signal."""
    with db._conn() as conn:
        conn.execute(
            "INSERT INTO workstreams (product_id, name, status, display_order, tag_subscriptions) "
            "VALUES ('p1', 'LinkedIn Research', 'paused', 1, '[]')"
        )
    tag_id = db.create_tag("social:linkedin", "LinkedIn")
    ws_id = db.get_workstreams("p1")[0]["id"]
    sig_id = db.create_signal(
        tag_id=tag_id, content_type="run_report", content_id=1,
        product_id="p1", tagged_by="agent", note="Brand tone is off",
    )
    return db, ws_id, sig_id


def test_route_signal_sets_workstream_id(populated_db):
    db, ws_id, sig_id = populated_db
    db.route_signal(sig_id, ws_id)
    with db._conn() as conn:
        row = conn.execute(
            "SELECT routed_to_workstream_id FROM signals WHERE id = ?", (sig_id,)
        ).fetchone()
    assert row["routed_to_workstream_id"] == ws_id


def test_route_signal_sets_workstream_next_run_at_now(populated_db):
    db, ws_id, sig_id = populated_db
    db.route_signal(sig_id, ws_id)
    ws = db.get_workstreams("p1")[0]
    assert ws["next_run_at"] is not None


def test_get_routed_signals_for_workstream(populated_db):
    db, ws_id, sig_id = populated_db
    db.route_signal(sig_id, ws_id)
    signals = db.get_routed_signals_for_workstream(ws_id)
    assert len(signals) == 1
    assert signals[0]["tag_name"] == "social:linkedin"
    assert signals[0]["note"] == "Brand tone is off"


def test_get_routed_signals_excludes_consumed(populated_db):
    db, ws_id, sig_id = populated_db
    db.route_signal(sig_id, ws_id)
    db.consume_signal(sig_id, "p1")
    signals = db.get_routed_signals_for_workstream(ws_id)
    assert signals == []


def test_consume_routed_signals(populated_db):
    db, ws_id, sig_id = populated_db
    db.route_signal(sig_id, ws_id)
    db.consume_routed_signals(ws_id)
    with db._conn() as conn:
        row = conn.execute(
            "SELECT consumed_at FROM signals WHERE id = ?", (sig_id,)
        ).fetchone()
    assert row["consumed_at"] is not None


def test_build_context_includes_workstreams(populated_db):
    from backend.orchestrator import build_context
    db, ws_id, sig_id = populated_db
    ctx = build_context("p1")
    assert len(ctx["workstreams"]) == 1
    assert ctx["workstreams"][0]["name"] == "LinkedIn Research"


def test_build_context_includes_unconsumed_signals(populated_db):
    from backend.orchestrator import build_context
    db, ws_id, sig_id = populated_db
    ctx = build_context("p1")
    assert len(ctx["unconsumed_signals"]) == 1
    assert ctx["unconsumed_signals"][0]["note"] == "Brand tone is off"


def test_build_context_empty_product_no_error(db):
    from backend.orchestrator import build_context
    ctx = build_context("p1")
    assert ctx["workstreams"] == []
    assert ctx["unconsumed_signals"] == []
    assert ctx["recent_reports"] == []


def test_apply_update_mission(populated_db):
    from backend.orchestrator import apply_decisions
    from backend.db import _ORCHESTRATOR_DEFAULT_AUTONOMY
    db, ws_id, sig_id = populated_db
    run_id = db.save_orchestrator_run("p1", "schedule", "complete", [], "")
    decisions = [{"action": "update_mission", "workstream_id": ws_id,
                  "new_mission": "Track LinkedIn brand voice daily", "reason": "test"}]
    annotated = apply_decisions("p1", decisions, _ORCHESTRATOR_DEFAULT_AUTONOMY, run_id)
    assert annotated[0]["_status"] == "applied"
    ws = db.get_workstreams("p1")[0]
    assert ws["mission"] == "Track LinkedIn brand voice daily"


def test_apply_route_signal(populated_db):
    from backend.orchestrator import apply_decisions
    from backend.db import _ORCHESTRATOR_DEFAULT_AUTONOMY
    db, ws_id, sig_id = populated_db
    run_id = db.save_orchestrator_run("p1", "schedule", "complete", [], "")
    decisions = [{"action": "route_signal", "signal_id": sig_id,
                  "workstream_id": ws_id, "note": "relevant"}]
    annotated = apply_decisions("p1", decisions, _ORCHESTRATOR_DEFAULT_AUTONOMY, run_id)
    assert annotated[0]["_status"] == "applied"
    signals = db.get_routed_signals_for_workstream(ws_id)
    assert len(signals) == 1


def test_apply_update_schedule(populated_db):
    from backend.orchestrator import apply_decisions
    from backend.db import _ORCHESTRATOR_DEFAULT_AUTONOMY
    db, ws_id, sig_id = populated_db
    run_id = db.save_orchestrator_run("p1", "schedule", "complete", [], "")
    decisions = [{"action": "update_schedule", "workstream_id": ws_id,
                  "new_schedule": "every monday at 9am", "reason": "test"}]
    annotated = apply_decisions("p1", decisions, _ORCHESTRATOR_DEFAULT_AUTONOMY, run_id)
    assert annotated[0]["_status"] == "applied"
    ws = db.get_workstreams("p1")[0]
    assert ws["schedule"] == "every monday at 9am"


def test_apply_update_subscriptions(populated_db):
    from backend.orchestrator import apply_decisions
    from backend.db import _ORCHESTRATOR_DEFAULT_AUTONOMY
    import json
    db, ws_id, sig_id = populated_db
    run_id = db.save_orchestrator_run("p1", "schedule", "complete", [], "")
    decisions = [{"action": "update_subscriptions", "workstream_id": ws_id,
                  "add": ["social:"], "remove": [], "reason": "test"}]
    annotated = apply_decisions("p1", decisions, _ORCHESTRATOR_DEFAULT_AUTONOMY, run_id)
    assert annotated[0]["_status"] == "applied"
    ws = db.get_workstreams("p1")[0]
    subs = json.loads(ws["tag_subscriptions"] or "[]")
    assert "social:" in subs


def test_apply_create_objective(populated_db):
    from backend.orchestrator import apply_decisions
    from backend.db import _ORCHESTRATOR_DEFAULT_AUTONOMY
    db, ws_id, sig_id = populated_db
    run_id = db.save_orchestrator_run("p1", "schedule", "complete", [], "")
    decisions = [{"action": "create_objective", "text": "Grow LinkedIn followers to 1000",
                  "reason": "test"}]
    annotated = apply_decisions("p1", decisions, _ORCHESTRATOR_DEFAULT_AUTONOMY, run_id)
    assert annotated[0]["_status"] == "applied"
    with db._conn() as conn:
        row = conn.execute(
            "SELECT text FROM objectives WHERE product_id = 'p1'"
        ).fetchone()
    assert row["text"] == "Grow LinkedIn followers to 1000"


def test_apply_consume_signal(populated_db):
    from backend.orchestrator import apply_decisions
    from backend.db import _ORCHESTRATOR_DEFAULT_AUTONOMY
    db, ws_id, sig_id = populated_db
    run_id = db.save_orchestrator_run("p1", "schedule", "complete", [], "")
    decisions = [{"action": "consume_signal", "signal_id": sig_id, "reason": "noise"}]
    annotated = apply_decisions("p1", decisions, _ORCHESTRATOR_DEFAULT_AUTONOMY, run_id)
    assert annotated[0]["_status"] == "applied"
    remaining = db.get_signals(product_id="p1")
    assert remaining == []


def test_apply_capability_gap_creates_review_item(populated_db):
    from backend.orchestrator import apply_decisions
    from backend.db import _ORCHESTRATOR_DEFAULT_AUTONOMY
    db, ws_id, sig_id = populated_db
    run_id = db.save_orchestrator_run("p1", "schedule", "complete", [], "")
    decisions = [{"action": "capability_gap", "tag": "email:analytics",
                  "description": "No workstream handles email analytics", "reason": "gap"}]
    annotated = apply_decisions("p1", decisions, _ORCHESTRATOR_DEFAULT_AUTONOMY, run_id)
    assert annotated[0]["_status"] == "applied"
    with db._conn() as conn:
        row = conn.execute(
            "SELECT * FROM review_items WHERE product_id = 'p1'"
        ).fetchone()
    assert row is not None
    assert "email:analytics" in row["title"]


def test_apply_pause_workstream_queues_review(populated_db):
    from backend.orchestrator import apply_decisions
    from backend.db import _ORCHESTRATOR_DEFAULT_AUTONOMY
    db, ws_id, sig_id = populated_db
    run_id = db.save_orchestrator_run("p1", "schedule", "complete", [], "")
    decisions = [{"action": "pause_workstream", "workstream_id": ws_id, "reason": "underperforming"}]
    annotated = apply_decisions("p1", decisions, _ORCHESTRATOR_DEFAULT_AUTONOMY, run_id)
    assert annotated[0]["_status"] == "queued"
    ws = db.get_workstreams("p1")[0]
    assert ws["status"] == "paused"   # unchanged — workstream was already paused, NOT paused by decision


def test_apply_create_workstream_queues_review(populated_db):
    from backend.orchestrator import apply_decisions
    from backend.db import _ORCHESTRATOR_DEFAULT_AUTONOMY
    db, ws_id, sig_id = populated_db
    run_id = db.save_orchestrator_run("p1", "schedule", "complete", [], "")
    decisions = [{"action": "create_workstream", "name": "Email Analytics",
                  "mission": "Track email open rates", "schedule": "weekly",
                  "workstream_type": "email", "reason": "gap"}]
    annotated = apply_decisions("p1", decisions, _ORCHESTRATOR_DEFAULT_AUTONOMY, run_id)
    assert annotated[0]["_status"] == "queued"
    ws_list = db.get_workstreams("p1")
    assert len(ws_list) == 1  # no new workstream created


def test_apply_unknown_action_skipped(populated_db):
    from backend.orchestrator import apply_decisions
    from backend.db import _ORCHESTRATOR_DEFAULT_AUTONOMY
    db, ws_id, sig_id = populated_db
    run_id = db.save_orchestrator_run("p1", "schedule", "complete", [], "")
    decisions = [{"action": "teleport", "reason": "test"}]
    annotated = apply_decisions("p1", decisions, _ORCHESTRATOR_DEFAULT_AUTONOMY, run_id)
    assert annotated[0]["_status"] == "skipped"


def test_apply_invalid_workstream_id_skipped(populated_db):
    from backend.orchestrator import apply_decisions
    from backend.db import _ORCHESTRATOR_DEFAULT_AUTONOMY
    db, ws_id, sig_id = populated_db
    run_id = db.save_orchestrator_run("p1", "schedule", "complete", [], "")
    decisions = [{"action": "update_mission", "workstream_id": 9999,
                  "new_mission": "x", "reason": "test"}]
    annotated = apply_decisions("p1", decisions, _ORCHESTRATOR_DEFAULT_AUTONOMY, run_id)
    assert annotated[0]["_status"] == "error"


def test_apply_autonomy_override_creates_review_item(populated_db):
    from backend.orchestrator import apply_decisions
    from backend.db import _ORCHESTRATOR_DEFAULT_AUTONOMY
    db, ws_id, sig_id = populated_db
    run_id = db.save_orchestrator_run("p1", "schedule", "complete", [], "")
    autonomy = {**_ORCHESTRATOR_DEFAULT_AUTONOMY, "update_mission": "approval_required"}
    decisions = [{"action": "update_mission", "workstream_id": ws_id,
                  "new_mission": "New mission", "reason": "test"}]
    annotated = apply_decisions("p1", decisions, autonomy, run_id)
    assert annotated[0]["_status"] == "queued"
    ws = db.get_workstreams("p1")[0]
    assert ws["mission"] != "New mission"  # not applied


@pytest.fixture
def mock_provider_factory(monkeypatch):
    """Returns a factory that patches make_provider with a given LLM response text."""
    def factory(response_text: str):
        class MockProvider:
            name = "anthropic"
            async def create(self, model, system, messages, max_tokens):
                class _Msg:
                    text = response_text
                class _Resp:
                    content = [_Msg()]
                return _Resp()
        monkeypatch.setattr("backend.orchestrator.make_provider", lambda m: MockProvider())
    return factory


@pytest.mark.asyncio
async def test_run_product_adjutant_applies_decisions(populated_db, mock_provider_factory):
    from backend.orchestrator import run_product_adjutant
    db, ws_id, sig_id = populated_db
    db.update_orchestrator_config("p1", enabled=1)

    response = json.dumps({
        "decisions": [
            {"action": "consume_signal", "signal_id": sig_id, "reason": "noise"}
        ],
        "brief": "Consumed one noisy signal."
    })
    mock_provider_factory(response)

    broadcasts = []

    async def broadcast(event):
        broadcasts.append(event)

    await run_product_adjutant("p1", "schedule", broadcast)

    runs = db.list_orchestrator_runs("p1")
    assert len(runs) == 1
    assert runs[0]["status"] == "complete"
    assert runs[0]["brief"] == "Consumed one noisy signal."
    assert runs[0]["decisions"][0]["_status"] == "applied"
    assert any(b.get("type") == "orchestrator_run_complete" for b in broadcasts)


@pytest.mark.asyncio
async def test_run_product_adjutant_malformed_json_saves_error(populated_db, mock_provider_factory):
    from backend.orchestrator import run_product_adjutant
    db, ws_id, sig_id = populated_db
    db.update_orchestrator_config("p1", enabled=1)

    mock_provider_factory("this is not json at all")

    broadcasts = []

    async def broadcast(event):
        broadcasts.append(event)

    await run_product_adjutant("p1", "schedule", broadcast)

    runs = db.list_orchestrator_runs("p1")
    assert runs[0]["status"] == "error"
    # No decisions applied
    remaining = db.get_signals(product_id="p1")
    assert len(remaining) == 1


def test_build_routed_signal_context_prefix(populated_db):
    from backend.scheduler import _build_routed_signal_prefix
    db, ws_id, sig_id = populated_db
    db.route_signal(sig_id, ws_id)
    prefix = _build_routed_signal_prefix(ws_id)
    assert "=== ROUTED SIGNALS ===" in prefix
    assert "social:linkedin" in prefix
    assert "Brand tone is off" in prefix


def test_build_routed_signal_prefix_empty_when_none(populated_db):
    from backend.scheduler import _build_routed_signal_prefix
    db, ws_id, sig_id = populated_db
    prefix = _build_routed_signal_prefix(ws_id)
    assert prefix == ""
