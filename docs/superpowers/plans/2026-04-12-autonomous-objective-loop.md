# Autonomous Objective Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend Adjutant so objectives can run autonomously — the scheduler drives each one via the full agent loop, the agent sets its own next-run cadence, and the loop resumes automatically when a blocking review is resolved.

**Architecture:** Add 5 columns to the objectives table; extend the scheduler to check for due autonomous objectives and run `_run_objective_loop()` (which calls the existing `_agent_loop()` via lazy import); add 3 new tools (`schedule_next_run`, `update_objective_progress`, `set_objective_autonomous`); add a WS handler and a review-resolution hook in main.py; update the ObjectivesPanel with a 🤖 toggle.

**Tech Stack:** Python/FastAPI, SQLite (ALTER TABLE migration), asyncio, React/TypeScript, Tailwind CSS.

---

## File Structure

| File | Change |
|------|--------|
| `backend/db.py` | Add 5 columns to objectives via ALTER TABLE; add 7 new functions; update `get_objectives()` SELECT |
| `backend/scheduler.py` | Add `_running_objectives`, `_run_objective_loop()`, extend `scheduler_loop()` |
| `core/tools.py` | Add 3 tool definitions to `TOOLS_DEFINITIONS`; add 3 executor functions; wire into `execute_tool()` |
| `backend/main.py` | Add `set_objective_autonomous` WS handler; add review-resume hook in `resolve_review` handler |
| `ui/src/types.ts` | Add 4 fields to `Objective` interface |
| `ui/src/components/ObjectivesPanel.tsx` | Add 🤖 toggle + status text; accept `onToggleAutonomous` prop |
| `ui/src/App.tsx` | Add `toggleObjectiveAutonomous` callback; pass to ObjectivesPanel |
| `tests/test_db.py` | Add tests for new db functions |
| `tests/test_autonomous_objectives.py` | New file: scheduler + loop integration tests |

---

## Task 1: DB Schema + Functions

**Files:**
- Modify: `backend/db.py`
- Test: `tests/test_db.py`

Context: The objectives table currently has `id, product_id, text, progress_current, progress_target, display_order`. We need 5 new columns added via ALTER TABLE (same idempotent pattern used for workstream columns around line 196). We also need 7 new functions and `get_objectives()` updated.

- [ ] **Step 1: Write failing tests**

Add to `tests/test_db.py`:

```python
def test_set_objective_autonomous_on(db):
    db.create_product_if_missing = lambda: None
    oid = db._conn().__enter__().execute(
        "INSERT INTO objectives (product_id, text) VALUES ('test-product', 'Grow followers') RETURNING id"
    ).fetchone()[0]
    # Need to use a real objective insert
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
    db.set_objective_autonomous(oid, True)
    db.set_objective_autonomous(oid, False)
    with db._conn() as conn:
        row = conn.execute("SELECT autonomous, next_run_at FROM objectives WHERE id = ?", (oid,)).fetchone()
    assert row["autonomous"] == 0
    assert row["next_run_at"] is None


def test_get_due_autonomous_objectives(db):
    with db._conn() as conn:
        oid = conn.execute(
            "INSERT INTO objectives (product_id, text) VALUES ('test-product', 'Grow followers')"
        ).lastrowid
        # Set autonomous=1, next_run_at in the past
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
    db.set_objective_next_run(oid, 0)  # should clamp to 0.25
    with db._conn() as conn:
        row = conn.execute("SELECT next_run_at FROM objectives WHERE id=?", (oid,)).fetchone()
    assert row["next_run_at"] is not None


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
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /home/justin/Code/Adjutant
.venv/bin/pytest tests/test_db.py -k "autonomous or blocked_by_review or next_run or new_fields" -v
```

Expected: multiple failures with `AttributeError: module 'backend.db' has no attribute 'set_objective_autonomous'`

- [ ] **Step 3: Add ALTER TABLE migration in `init_db()`**

In `backend/db.py`, after the existing `_ws_cols` block (around line 206), add:

```python
        # Add autonomous objective columns (idempotent)
        _obj_auto_cols = [
            ("autonomous",           "INTEGER NOT NULL DEFAULT 0"),
            ("session_id",           "TEXT"),
            ("next_run_at",          "TEXT"),
            ("last_run_at",          "TEXT"),
            ("blocked_by_review_id", "INTEGER"),
        ]
        for col_name, col_type in _obj_auto_cols:
            try:
                conn.execute(f"ALTER TABLE objectives ADD COLUMN {col_name} {col_type}")
            except Exception:
                pass  # column already exists
```

- [ ] **Step 4: Update `get_objectives()` to return new fields**

Replace the existing `get_objectives` function (around line 537):

```python
def get_objectives(product_id: str) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            """SELECT id, text, progress_current, progress_target, display_order,
                      autonomous, session_id, next_run_at, last_run_at, blocked_by_review_id
               FROM objectives WHERE product_id = ? ORDER BY display_order""",
            (product_id,),
        ).fetchall()
    return [dict(r) for r in rows]
```

- [ ] **Step 5: Add 7 new db functions**

Add these functions after `delete_objective()` (around line 581), before `# ── Activity events ───`:

```python
def get_objective_by_id(obj_id: int) -> dict | None:
    with _conn() as conn:
        row = conn.execute(
            """SELECT id, product_id, text, progress_current, progress_target, display_order,
                      autonomous, session_id, next_run_at, last_run_at, blocked_by_review_id
               FROM objectives WHERE id = ?""",
            (obj_id,),
        ).fetchone()
    return dict(row) if row else None


def set_objective_autonomous(obj_id: int, autonomous: bool) -> None:
    with _conn() as conn:
        if autonomous:
            conn.execute(
                "UPDATE objectives SET autonomous = 1, next_run_at = datetime('now') WHERE id = ?",
                (obj_id,),
            )
        else:
            conn.execute(
                "UPDATE objectives SET autonomous = 0, next_run_at = NULL, blocked_by_review_id = NULL WHERE id = ?",
                (obj_id,),
            )


def set_objective_session(obj_id: int, session_id: str) -> None:
    with _conn() as conn:
        conn.execute(
            "UPDATE objectives SET session_id = ? WHERE id = ?",
            (session_id, obj_id),
        )


def set_objective_next_run(obj_id: int, hours: float) -> None:
    """Set next_run_at to now + hours (minimum 0.25h = 15 min). Updates last_run_at to now."""
    hours = max(0.25, float(hours))
    with _conn() as conn:
        conn.execute(
            "UPDATE objectives SET next_run_at = datetime('now', ? || ' hours'), last_run_at = datetime('now') WHERE id = ?",
            (f"+{hours}", obj_id),
        )


def set_objective_blocked(obj_id: int, review_item_id: int) -> None:
    with _conn() as conn:
        conn.execute(
            "UPDATE objectives SET blocked_by_review_id = ?, next_run_at = NULL WHERE id = ?",
            (review_item_id, obj_id),
        )


def get_due_autonomous_objectives() -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            """SELECT id, product_id, text, progress_current, progress_target,
                      autonomous, session_id, next_run_at, last_run_at, blocked_by_review_id
               FROM objectives
               WHERE autonomous = 1
                 AND next_run_at IS NOT NULL
                 AND next_run_at <= datetime('now')
                 AND blocked_by_review_id IS NULL""",
        ).fetchall()
    return [dict(r) for r in rows]


def get_objective_blocked_by_review(review_item_id: int) -> dict | None:
    with _conn() as conn:
        row = conn.execute(
            "SELECT id, product_id FROM objectives WHERE blocked_by_review_id = ?",
            (review_item_id,),
        ).fetchone()
    return dict(row) if row else None


def clear_objective_block(obj_id: int) -> None:
    """Clear blocked state and schedule immediate re-run."""
    with _conn() as conn:
        conn.execute(
            "UPDATE objectives SET blocked_by_review_id = NULL, next_run_at = datetime('now') WHERE id = ?",
            (obj_id,),
        )
```

- [ ] **Step 6: Run tests to confirm they pass**

```bash
.venv/bin/pytest tests/test_db.py -k "autonomous or blocked_by_review or next_run or new_fields" -v
```

Expected: all 9 new tests PASS

- [ ] **Step 7: Run full test suite to check for regressions**

```bash
.venv/bin/pytest tests/test_db.py -v
```

Expected: all tests PASS

- [ ] **Step 8: Commit**

```bash
git add backend/db.py tests/test_db.py
git commit -m "feat: add autonomous objective columns and db functions"
```

---

## Task 2: Three New Tools

**Files:**
- Modify: `core/tools.py`
- Test: `tests/test_db.py` (tool executors call db functions already tested)

Context: Tools are defined in `TOOLS_DEFINITIONS` (a list, ends around line 471 before `TOOLS_DEFINITIONS.extend(_load_extensions())`). Executors go near the bottom of the file and are wired into `execute_tool()` (around line 585). Follow the exact pattern of existing tools like `_create_objective`.

- [ ] **Step 1: Write failing test**

Add to `tests/test_db.py`:

```python
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
    result = asyncio.get_event_loop().run_until_complete(
        tools_mod.execute_tool("schedule_next_run", {"objective_id": oid, "hours": 8.0, "reason": "posted today"})
    )
    assert "8.0h" in result or "8" in result
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
    asyncio.get_event_loop().run_until_complete(
        tools_mod.execute_tool("update_objective_progress", {"objective_id": oid, "current": 250, "notes": "checked API"})
    )
    with db._conn() as conn:
        row = conn.execute("SELECT progress_current FROM objectives WHERE id=?", (oid,)).fetchone()
    assert row["progress_current"] == 250
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
.venv/bin/pytest tests/test_db.py -k "schedule_next_run_tool or update_objective_progress_tool" -v
```

Expected: FAIL — `Unknown tool: schedule_next_run`

- [ ] **Step 3: Add 3 tool definitions to `TOOLS_DEFINITIONS`**

In `core/tools.py`, insert before `]` that closes `TOOLS_DEFINITIONS` (just before line `# Load extensions and append their definitions`):

```python
    {
        "name": "schedule_next_run",
        "description": (
            "Schedule the next autonomous run for the current objective. "
            "Call this at the end of every autonomous cycle to keep the loop running. "
            "If you need human input instead, call create_review_item — do not call this tool."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "objective_id": {"type": "integer", "description": "The objective's ID"},
                "hours": {
                    "type": "number",
                    "description": "Hours until next run (fractional ok, e.g. 0.5 for 30 min). Minimum 0.25.",
                },
                "reason": {
                    "type": "string",
                    "description": "Brief explanation of why this cadence makes sense",
                },
            },
            "required": ["objective_id", "hours", "reason"],
        },
    },
    {
        "name": "update_objective_progress",
        "description": (
            "Update the measurable progress toward an objective. "
            "Call this whenever you have a concrete new number (e.g., follower count, deals closed, items completed)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "objective_id": {"type": "integer", "description": "The objective's ID"},
                "current": {"type": "integer", "description": "The new current progress value"},
                "notes": {
                    "type": "string",
                    "description": "Optional context about how this was measured or what changed",
                },
            },
            "required": ["objective_id", "current"],
        },
    },
    {
        "name": "set_objective_autonomous",
        "description": (
            "Enable or disable autonomous mode for an objective. "
            "When enabled, the scheduler will begin driving the objective immediately. "
            "Use this when the user asks to run an objective autonomously or to stop autonomous execution."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "objective_id": {"type": "integer", "description": "The objective's ID"},
                "autonomous": {"type": "boolean", "description": "true to enable, false to disable"},
            },
            "required": ["objective_id", "autonomous"],
        },
    },
```

- [ ] **Step 4: Add 3 executor functions**

Add these functions at the bottom of `core/tools.py`, after the last existing executor function:

```python
def _schedule_next_run(objective_id: int, hours: float, reason: str) -> str:
    from backend.db import set_objective_next_run
    set_objective_next_run(objective_id, hours)
    return f"Scheduled next run in {hours}h. Reason: {reason}"


def _update_objective_progress(objective_id: int, current: int, notes: str = "") -> str:
    from backend.db import update_objective_by_id
    update_objective_by_id(objective_id, progress_current=current)
    msg = f"Progress updated to {current}"
    return f"{msg}. {notes}" if notes else msg


def _set_objective_autonomous_tool(objective_id: int, autonomous: bool) -> str:
    from backend.db import set_objective_autonomous
    set_objective_autonomous(objective_id, autonomous)
    state = "enabled" if autonomous else "disabled"
    return f"Objective {objective_id} autonomous mode {state}."
```

- [ ] **Step 5: Wire into `execute_tool()`**

In `execute_tool()`, add these three dispatches before the extension executor check (`if name in _EXTENSION_EXECUTORS`):

```python
    if name == "schedule_next_run":
        return _schedule_next_run(**inputs)
    if name == "update_objective_progress":
        return _update_objective_progress(**inputs)
    if name == "set_objective_autonomous":
        return _set_objective_autonomous_tool(**inputs)
```

- [ ] **Step 6: Run tests to confirm they pass**

```bash
.venv/bin/pytest tests/test_db.py -k "schedule_next_run_tool or update_objective_progress_tool" -v
```

Expected: both PASS

- [ ] **Step 7: Commit**

```bash
git add core/tools.py tests/test_db.py
git commit -m "feat: add schedule_next_run, update_objective_progress, set_objective_autonomous tools"
```

---

## Task 3: Scheduler Extension

**Files:**
- Modify: `backend/scheduler.py`
- Create: `tests/test_autonomous_objectives.py`

Context: `scheduler.py` has a module-level `_running: dict[int, bool]` guard for workstreams. We need the same pattern for objectives. `_run_objective_loop` calls `_build_context` and `_agent_loop` from `backend.main` via lazy imports inside the function (safe — by runtime both modules are fully loaded; same pattern `_run_workstream` uses for db imports). `_broadcast_fn` is already registered at startup via `register_broadcast`.

- [ ] **Step 1: Write failing tests**

Create `tests/test_autonomous_objectives.py`:

```python
# tests/test_autonomous_objectives.py
"""Tests for the autonomous objective scheduler loop."""
import asyncio
import importlib
import os
from unittest.mock import AsyncMock, MagicMock, patch

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

    asyncio.get_event_loop().run_until_complete(run_one_tick())
    assert ("p1", oid) in called


def test_set_objective_next_run_clamp(db):
    oid = _make_obj(db)
    db.set_objective_next_run(oid, 0.0)  # should clamp to 0.25
    with db._conn() as conn:
        row = conn.execute("SELECT next_run_at, last_run_at FROM objectives WHERE id=?", (oid,)).fetchone()
    assert row["next_run_at"] is not None
    assert row["last_run_at"] is not None


def test_objective_goes_dormant_on_exception(db, monkeypatch):
    """If _run_objective_loop raises, the objective goes dormant (autonomous=0)."""
    oid = _make_obj(db)
    db.set_objective_autonomous(oid, True)

    import backend.scheduler as sched_mod
    importlib.reload(sched_mod)
    broadcast = AsyncMock()
    sched_mod.register_broadcast(broadcast)

    async def run():
        # Patch _build_context to raise
        with patch("backend.main._build_context", side_effect=RuntimeError("boom")):
            await sched_mod._run_objective_loop("p1", oid)

    asyncio.get_event_loop().run_until_complete(run())
    with db._conn() as conn:
        row = conn.execute("SELECT autonomous, next_run_at FROM objectives WHERE id=?", (oid,)).fetchone()
    assert row["autonomous"] == 0
    assert row["next_run_at"] is None
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
.venv/bin/pytest tests/test_autonomous_objectives.py -v
```

Expected: failures including `AttributeError: module 'backend.scheduler' has no attribute '_running_objectives'` and `_run_objective_loop`

- [ ] **Step 3: Add `_running_objectives` and extend `scheduler_loop`**

In `backend/scheduler.py`, after the existing `_running: dict[int, bool] = {}` line, add:

```python
_running_objectives: dict[int, bool] = {}
```

At the end of `scheduler_loop()`, after the existing workstream loop, add the objectives check:

```python
async def scheduler_loop(broadcast: BroadcastFn, interval_seconds: int = 60) -> None:
    """Main loop — polls for due workstreams and autonomous objectives every `interval_seconds`."""
    log.info("Workstream scheduler started (interval=%ds)", interval_seconds)
    while True:
        try:
            from backend.db import get_due_workstreams, get_due_autonomous_objectives
            due = get_due_workstreams()
            for ws in due:
                if not _running.get(ws["id"]):
                    asyncio.create_task(_run_workstream(ws, broadcast))
            due_objs = get_due_autonomous_objectives()
            for obj in due_objs:
                if not _running_objectives.get(obj["id"]):
                    asyncio.create_task(_run_objective_loop(obj["product_id"], obj["id"]))
        except Exception as exc:
            log.error("Scheduler poll error: %s", exc)
        await asyncio.sleep(interval_seconds)
```

- [ ] **Step 4: Add `_run_objective_loop()`**

Add this function in `backend/scheduler.py`, after `_run_workstream()` and before `# ── Public API ───`:

```python
async def _run_objective_loop(product_id: str, objective_id: int) -> None:
    """Run one autonomous cycle for an objective using the full agent loop."""
    if _running_objectives.get(objective_id):
        return

    _running_objectives[objective_id] = True
    event_id = None

    try:
        from backend.db import (
            get_objective_by_id, set_objective_autonomous, set_objective_session,
            set_objective_blocked, save_review_item,
            save_activity_event, update_activity_event,
            get_workstreams, get_objectives, load_activity_events, load_review_items,
        )
        from backend.main import _build_context, _agent_loop
        from backend.db import create_session

        obj = get_objective_by_id(objective_id)
        if not obj:
            return

        # Ensure dedicated session exists
        session_id = obj.get("session_id")
        if not session_id:
            session_id = create_session(f"Objective: {obj['text'][:40]}", product_id)
            set_objective_session(objective_id, session_id)

        # Activity feed entry
        event_id = save_activity_event(
            product_id=product_id,
            agent_type="general",
            headline=f"[Auto] {obj['text'][:60]}",
            rationale="Autonomous objective run",
            status="running",
        )
        now_ts = datetime.now().isoformat(timespec="seconds")
        if _broadcast_fn:
            await _broadcast_fn({
                "type": "activity_started",
                "product_id": product_id,
                "id": event_id,
                "agent_type": "general",
                "headline": f"[Auto] {obj['text'][:60]}",
                "rationale": "Autonomous objective run",
                "ts": now_ts,
            })

        # Build context: product system prompt + objective session history
        messages = _build_context(product_id, session_id=session_id)

        # Inject the cycle prompt
        progress_str = str(obj["progress_current"])
        if obj.get("progress_target") is not None:
            progress_str += f" of {obj['progress_target']}"
        last_run = obj.get("last_run_at") or "never"

        cycle_prompt = (
            f'You are autonomously working toward this objective: "{obj["text"]}"\n'
            f"Current progress: {progress_str}.\n"
            f"Last run: {last_run}.\n\n"
            "Use your available tools to take the best next action toward this goal.\n\n"
            "When you have taken action, call `update_objective_progress` to record measurable "
            "progress, then call `schedule_next_run` with how many hours until you should check "
            "back and why.\n\n"
            "If you are blocked and need human input before you can proceed, call "
            "`create_review_item` instead — do NOT call `schedule_next_run`.\n\n"
            "If you need a capability you don't currently have (e.g., posting to a social "
            "platform, reading analytics), use `find_skill` or `manage_mcp_server` to add it "
            "before proceeding — don't create a review item just because a tool is missing."
        )
        messages.append({"role": "user", "content": cycle_prompt})

        # Run the full agent loop
        _updated_messages, new_review_items = await _agent_loop(
            _broadcast_fn, product_id, messages, session_id=session_id
        )

        # Refresh objective from DB (agent may have updated progress via tools)
        refreshed = get_objective_by_id(objective_id)
        if not refreshed:
            return

        target = refreshed.get("progress_target")
        current = refreshed.get("progress_current", 0)

        # Priority 1: target reached → create "what's next?" review, go dormant
        if target is not None and current >= target:
            review_id = save_review_item(
                product_id=product_id,
                title=f"Goal reached: {obj['text'][:60]}",
                description=(
                    f"Objective reached its target of {target}. "
                    "Set a new target to continue, or disable autonomous mode."
                ),
                risk_label="Goal milestone — awaiting new direction",
                activity_event_id=event_id,
            )
            set_objective_autonomous(objective_id, False)
            if _broadcast_fn:
                review_item = {
                    "id": review_id,
                    "title": f"Goal reached: {obj['text'][:60]}",
                    "description": f"Objective reached its target of {target}. Set a new target to continue, or disable autonomous mode.",
                    "risk_label": "Goal milestone — awaiting new direction",
                    "status": "pending",
                    "created_at": now_ts,
                }
                await _broadcast_fn({"type": "review_item_added", "product_id": product_id, "item": review_item})

        # Priority 2: agent created blocking review → go dormant until resolved
        elif new_review_items:
            set_objective_blocked(objective_id, new_review_items[-1]["id"])

        # Priority 3: schedule_next_run was called → next_run_at already set by tool
        # No action needed. If agent forgot to call schedule_next_run, default 24h.
        else:
            refreshed2 = get_objective_by_id(objective_id)
            if refreshed2 and not refreshed2.get("next_run_at"):
                from backend.db import set_objective_next_run
                set_objective_next_run(objective_id, 24.0)

        summary = "Autonomous cycle complete."
        update_activity_event(event_id, status="done", summary=summary)
        done_ts = datetime.now().isoformat(timespec="seconds")
        if _broadcast_fn:
            await _broadcast_fn({
                "type": "activity_done",
                "product_id": product_id,
                "id": event_id,
                "summary": summary,
                "ts": done_ts,
            })
            await _broadcast_fn({
                "type": "product_data",
                "product_id": product_id,
                "workstreams":  get_workstreams(product_id),
                "objectives":   get_objectives(product_id),
                "events":       load_activity_events(product_id),
                "review_items": load_review_items(product_id),
            })

    except Exception as exc:
        log.error("Objective %s (%s) loop failed: %s", objective_id, product_id, exc)
        if event_id is not None:
            try:
                from backend.db import update_activity_event
                update_activity_event(event_id, status="done", summary=f"Error: {exc}")
            except Exception:
                pass
        if _broadcast_fn:
            await _broadcast_fn({
                "type": "activity_done",
                "product_id": product_id,
                "id": event_id,
                "summary": f"Objective loop error: {exc}",
                "ts": datetime.now().isoformat(timespec="seconds"),
            })
        # Go dormant on error to avoid crash loop
        try:
            from backend.db import set_objective_autonomous
            set_objective_autonomous(objective_id, False)
        except Exception:
            pass
    finally:
        _running_objectives.pop(objective_id, None)
```

- [ ] **Step 5: Run tests**

```bash
.venv/bin/pytest tests/test_autonomous_objectives.py -v
```

Expected: all tests PASS

- [ ] **Step 6: Run full test suite**

```bash
.venv/bin/pytest tests/ -x -q --ignore=tests/test_main.py
```

Expected: all PASS (test_main.py has a pre-existing unrelated failure, ignore it)

- [ ] **Step 7: Commit**

```bash
git add backend/scheduler.py tests/test_autonomous_objectives.py
git commit -m "feat: add _run_objective_loop and extend scheduler to drive autonomous objectives"
```

---

## Task 4: main.py WS Handlers

**Files:**
- Modify: `backend/main.py`

Context: Two changes in main.py. (1) New `set_objective_autonomous` WS handler — receives `{type, objective_id, autonomous}`, flips the flag, broadcasts `product_data`. (2) Review-resume hook appended to the existing `resolve_review` handler — after all existing social-post logic, check if the resolved review was blocking an objective and if so re-trigger its loop.

The `resolve_review` handler ends around line 962. The new `set_objective_autonomous` handler goes in the `elif msg_type ==` chain.

- [ ] **Step 1: Add `set_objective_autonomous` to imports from db**

In `backend/main.py`, the import block from `backend.db` (lines ~19-49), add these to the import list:

```python
    get_objective_by_id,
    set_objective_autonomous,
    get_objective_blocked_by_review,
    clear_objective_block,
```

- [ ] **Step 2: Add the WS handler**

In `backend/main.py`, in the WebSocket message dispatch chain, add after the `delete_session` handler and before the `resolve_review` handler:

```python
            elif msg_type == "set_objective_autonomous":
                obj_id   = msg.get("objective_id")
                auto_val = msg.get("autonomous", False)
                if obj_id is None:
                    continue
                set_objective_autonomous(int(obj_id), bool(auto_val))
                obj = get_objective_by_id(int(obj_id))
                if obj:
                    await _broadcast(_product_data_payload(obj["product_id"]))
```

- [ ] **Step 3: Add review-resume hook**

At the very end of the `resolve_review` handler, after all the social post publishing logic (after the final `await _send(ws, {...})` for activity_done, around line 962), add:

```python
                    # Resume any autonomous objective that was blocked by this review
                    blocked_obj = get_objective_blocked_by_review(item_id)
                    if blocked_obj:
                        clear_objective_block(blocked_obj["id"])
                        from backend.scheduler import _run_objective_loop
                        asyncio.create_task(
                            _run_objective_loop(blocked_obj["product_id"], blocked_obj["id"])
                        )
```

Note: this goes inside the `if item_id and action in ("approved", "skipped"):` block, at the same indentation level as the social post check.

- [ ] **Step 4: Run tests**

```bash
.venv/bin/pytest tests/ -x -q --ignore=tests/test_main.py
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add backend/main.py
git commit -m "feat: add set_objective_autonomous WS handler and review-resume hook"
```

---

## Task 5: Frontend

**Files:**
- Modify: `ui/src/types.ts`
- Modify: `ui/src/components/ObjectivesPanel.tsx`
- Modify: `ui/src/App.tsx`

Context: The `Objective` interface needs 4 new fields. `ObjectivesPanel` needs a 🤖 toggle per row and a callback prop. `App.tsx` needs the callback wired to a WS send. No new WS message types are needed — `set_objective_autonomous` is sent client→server, and the server responds with a `product_data` broadcast which the frontend already handles.

- [ ] **Step 1: Update `Objective` interface in `ui/src/types.ts`**

Replace the existing `Objective` interface:

```typescript
export interface Objective {
  id: number
  text: string
  progress_current: number
  progress_target: number | null
  display_order: number
  autonomous: number          // 0 | 1
  session_id: string | null
  next_run_at: string | null
  last_run_at: string | null
  blocked_by_review_id: number | null
}
```

- [ ] **Step 2: Rewrite `ObjectivesPanel.tsx`**

Replace the full file contents:

```tsx
// ui/src/components/ObjectivesPanel.tsx
import { Objective } from '../types'

interface Props {
  objectives: Objective[]
  onToggleAutonomous: (objectiveId: number, autonomous: boolean) => void
}

function formatNextRun(next_run_at: string | null): string {
  if (!next_run_at) return ''
  // SQLite stores "YYYY-MM-DD HH:MM:SS" — parse as local time
  const next = new Date(next_run_at.replace(' ', 'T'))
  const diffMs = next.getTime() - Date.now()
  if (diffMs <= 0) return 'soon'
  const diffH = diffMs / (1000 * 60 * 60)
  if (diffH < 1) return `in ${Math.round(diffH * 60)}m`
  return `in ${diffH.toFixed(1).replace('.0', '')}h`
}

function ObjectiveRow({ obj, onToggleAutonomous }: { obj: Objective; onToggleAutonomous: Props['onToggleAutonomous'] }) {
  const progress = obj.progress_target != null
    ? `${obj.progress_current} / ${obj.progress_target}`
    : `${obj.progress_current} so far`

  const isAuto    = obj.autonomous === 1
  const isBlocked = isAuto && obj.blocked_by_review_id != null
  const isRunning = isAuto && !isBlocked && obj.next_run_at != null

  const robotColor = isBlocked
    ? 'text-amber-400'
    : isRunning
    ? 'text-indigo-400'
    : 'text-zinc-700 hover:text-zinc-500'

  const statusText = isBlocked
    ? 'awaiting review'
    : isRunning
    ? formatNextRun(obj.next_run_at)
    : ''

  return (
    <div className="px-3.5 py-1.5 flex items-start gap-2">
      <button
        onClick={() => onToggleAutonomous(obj.id, !isAuto)}
        title={isAuto ? 'Disable autonomous mode' : 'Enable autonomous mode'}
        className={`flex-shrink-0 mt-0.5 text-sm transition-colors ${robotColor}`}
      >
        🤖
      </button>
      <div className="flex-1 min-w-0">
        <div className="text-xs text-zinc-500 leading-snug">{obj.text}</div>
        <div className="flex items-center gap-2 mt-0.5">
          <span className="text-xs text-zinc-600">{progress}</span>
          {statusText && (
            <span className={`text-[10px] ${isBlocked ? 'text-amber-500' : 'text-indigo-400'}`}>
              {statusText}
            </span>
          )}
        </div>
      </div>
    </div>
  )
}

export default function ObjectivesPanel({ objectives, onToggleAutonomous }: Props) {
  if (objectives.length === 0) return null
  return (
    <div className="border-t border-zinc-800/60 pt-2">
      <div className="px-3.5 pb-2 text-[10px] font-semibold text-zinc-600 uppercase tracking-widest">
        Objectives
      </div>
      {objectives.map(obj => (
        <ObjectiveRow key={obj.id} obj={obj} onToggleAutonomous={onToggleAutonomous} />
      ))}
    </div>
  )
}
```

- [ ] **Step 3: Update `App.tsx`**

Add the `toggleObjectiveAutonomous` callback. Find the existing session callbacks block (around `createSession`, `switchSession`, etc.) and add after `deleteSession`:

```tsx
  const toggleObjectiveAutonomous = useCallback((objectiveId: number, autonomous: boolean) => {
    wsRef.current?.send(JSON.stringify({
      type: 'set_objective_autonomous',
      objective_id: objectiveId,
      autonomous,
    }))
  }, [])
```

Find the `<ObjectivesPanel>` render (in both the product layout and the global chat layout if applicable) and add the new prop:

```tsx
<ObjectivesPanel
  objectives={activeState.objectives}
  onToggleAutonomous={toggleObjectiveAutonomous}
/>
```

- [ ] **Step 4: Build and verify no TypeScript errors**

```bash
cd /home/justin/Code/Adjutant/ui && npm run build 2>&1 | tail -15
```

Expected: `✓ built in X.XXs` with no errors

- [ ] **Step 5: Commit**

```bash
git add ui/src/types.ts ui/src/components/ObjectivesPanel.tsx ui/src/App.tsx
git commit -m "feat: add autonomous toggle to ObjectivesPanel with robot icon and status text"
```

---

## Self-Review

**Spec coverage check:**
- ✅ Section 1 (Data Model): Task 1 covers all 5 columns + all 7 db functions + `get_objectives` update
- ✅ Section 2 (Agent Loop): Task 3 `_run_objective_loop` covers all 5 outcomes (schedule, block, target reached, exception, default fallback)
- ✅ Section 3 (New Tools): Task 2 covers all 3 tools with definitions + executors
- ✅ Section 4 (Scheduler Extension): Task 3 extends `scheduler_loop`; Task 4 adds review-resume hook
- ✅ Section 5 (Frontend): Task 5 covers toggle, status text, robot icon, WS callback
- ✅ Error Handling: dormant on exception (Task 3), 0.25h minimum clamp (Task 1 `set_objective_next_run`), session creation fallback (Task 3 `_run_objective_loop` creates session if missing)
- ✅ Testing: 9 db tests, 4 scheduler tests, 2 tool tests, TypeScript build check

**Type consistency check:**
- `set_objective_autonomous(obj_id: int, autonomous: bool)` — used consistently in tools.py executor and main.py handler
- `get_objective_by_id(obj_id: int) -> dict | None` — used in scheduler and main.py
- `set_objective_next_run(obj_id: int, hours: float)` — called in tool executor and as fallback in `_run_objective_loop`
- `_run_objective_loop(product_id: str, objective_id: int)` — called from `scheduler_loop` and main.py review hook
- `Objective.autonomous: number` (0|1 from SQLite) — `isAuto = obj.autonomous === 1` in ObjectivesPanel ✅
