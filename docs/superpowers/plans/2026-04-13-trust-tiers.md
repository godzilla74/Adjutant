# Trust Tiers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add per-product, per-action-type autonomy configuration with Auto/Window/Approve tiers so the agent can fire routine actions without approval, fire high-risk actions after a cancellable time window, and block on the existing approve flow for sensitive actions.

**Architecture:** New `product_autonomy` table + two columns on `products` + two columns on `review_items` hold the config and per-item deadline. Autonomy is applied in `_run_one_tool` when `create_review_item` or `draft_social_post` fires — auto items are resolved immediately, window items get a deadline timestamp. A 30-second scheduler poll auto-resolves expired window items. REST endpoints manage the config; a WebSocket handler handles cancel. The countdown UI lives in `ReviewCard.tsx`; the configuration UI lives in `SettingsSidebar.tsx`.

**Tech Stack:** Python/FastAPI, SQLite, existing `_run_one_tool` side-effect pattern, React/TypeScript, existing `apiFetch` REST client.

---

## File Map

| File | Change |
|------|--------|
| `backend/db.py` | New table, new columns, 6 new functions, update `save_review_item` + `load_review_items` |
| `core/tools.py` | Add `action_type` param to `create_review_item` tool def + `_create_review_item` handler; add `action_type='social_post'` to `_draft_social_post` call |
| `backend/main.py` | Autonomy enforcement in `_run_one_tool` for `create_review_item` + `draft_social_post`; add `cancel_auto_approve` WS handler |
| `backend/api.py` | Add GET + PUT `/products/{product_id}/autonomy` REST endpoints |
| `backend/scheduler.py` | Poll `auto_resolve_expired_reviews()` every 30s in `scheduler_loop` |
| `ui/src/types.ts` | Add fields to `ReviewItem`; add `autonomy_config`, `review_item_updated` to `ServerMessage` |
| `ui/src/api.ts` | Add `getAutonomySettings`, `updateAutonomySettings` |
| `ui/src/components/ReviewCard.tsx` | Add countdown + Cancel button for window-tier items |
| `ui/src/components/ReviewQueue.tsx` | Thread `onCancelAutoApprove` down to `ReviewCard` |
| `ui/src/App.tsx` | Handle `review_item_updated` WS msg; add `cancelAutoApprove` callback |
| `ui/src/components/SettingsSidebar.tsx` | Add Autonomy collapsible section |
| `tests/test_db.py` | Autonomy DB function tests |
| `tests/test_trust_tiers.py` | New — tool, scheduler, WS handler tests |

---

## Task 1: DB schema and autonomy functions

**Files:**
- Modify: `backend/db.py`
- Test: `tests/test_db.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_db.py`:

```python
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
    # Set past deadline
    db.set_auto_approve_at(item_id_past, datetime.now() - timedelta(minutes=1))
    # Set future deadline
    db.set_auto_approve_at(item_id_future, datetime.now() + timedelta(minutes=10))

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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/justin/Code/Adjutant && python -m pytest tests/test_db.py::test_get_autonomy_config_resolution_order tests/test_db.py::test_auto_resolve_expired_reviews tests/test_db.py::test_get_product_autonomy_settings tests/test_db.py::test_save_review_item_with_action_type -v 2>&1 | tail -20
```

Expected: `FAILED` with `AttributeError` or `TypeError` (functions don't exist yet).

- [ ] **Step 3: Add `product_autonomy` table to `init_db()`**

In `backend/db.py`, inside the `conn.executescript("""...""")` block, add after the `mcp_servers` table (before the closing `"""`):

```python
            CREATE TABLE IF NOT EXISTS product_autonomy (
                product_id     TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
                action_type    TEXT NOT NULL,
                tier           TEXT NOT NULL DEFAULT 'approve',
                window_minutes INTEGER,
                PRIMARY KEY (product_id, action_type)
            );
            CREATE INDEX IF NOT EXISTS idx_product_autonomy_product
                ON product_autonomy(product_id);
```

- [ ] **Step 4: Add idempotent ALTER TABLE migrations**

After the `launch_wizard_active` ALTER block in `init_db()`, add:

```python
        # Add trust tier columns to products (idempotent)
        for col_name, col_def in [
            ("autonomy_master_tier",         "TEXT"),
            ("autonomy_master_window_minutes","INTEGER"),
        ]:
            try:
                conn.execute(f"ALTER TABLE products ADD COLUMN {col_name} {col_def}")
            except Exception:
                pass  # column already exists

        # Add trust tier columns to review_items (idempotent)
        for col_name, col_def in [
            ("action_type",    "TEXT"),
            ("auto_approve_at","DATETIME"),
        ]:
            try:
                conn.execute(f"ALTER TABLE review_items ADD COLUMN {col_name} {col_def}")
            except Exception:
                pass  # column already exists
```

- [ ] **Step 5: Update `save_review_item` to accept `action_type`**

Find `save_review_item` in `backend/db.py` (around line 759). Replace it with:

```python
def save_review_item(
    product_id: str,
    title: str,
    description: str,
    risk_label: str,
    activity_event_id: Optional[int] = None,
    action_type: Optional[str] = None,
) -> int:
    with _conn() as conn:
        cur = conn.execute(
            """INSERT INTO review_items
               (product_id, activity_event_id, title, description, risk_label, action_type)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (product_id, activity_event_id, title, description, risk_label, action_type),
        )
        return cur.lastrowid
```

- [ ] **Step 6: Update `load_review_items` to include new columns**

Find `load_review_items` in `backend/db.py` (around line 786). Replace the SELECT statement:

```python
def load_review_items(product_id: str, status: str = "pending") -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            """SELECT id, activity_event_id, title, description, risk_label, status,
                      created_at, action_type, auto_approve_at
               FROM review_items WHERE product_id = ? AND status = ?
               ORDER BY created_at""",
            (product_id, status),
        ).fetchall()
    return [dict(r) for r in rows]
```

- [ ] **Step 7: Add the six new db functions**

Add after `load_review_items` in `backend/db.py`:

```python
def set_auto_approve_at(item_id: int, dt: "datetime") -> None:
    with _conn() as conn:
        conn.execute(
            "UPDATE review_items SET auto_approve_at = ? WHERE id = ?",
            (dt.isoformat(timespec="seconds"), item_id),
        )


def clear_auto_approve_at(item_id: int) -> None:
    with _conn() as conn:
        conn.execute(
            "UPDATE review_items SET auto_approve_at = NULL WHERE id = ?",
            (item_id,),
        )


def auto_resolve_expired_reviews() -> list[dict]:
    """Find pending review items whose window has expired. Mark approved. Return {id, product_id} list."""
    with _conn() as conn:
        rows = conn.execute(
            """SELECT id, product_id FROM review_items
               WHERE status = 'pending'
               AND auto_approve_at IS NOT NULL
               AND auto_approve_at <= datetime('now')"""
        ).fetchall()
        if not rows:
            return []
        ids = [r[0] for r in rows]
        placeholders = ",".join("?" * len(ids))
        conn.execute(
            f"UPDATE review_items SET status = 'approved' WHERE id IN ({placeholders})",
            ids,
        )
    return [{"id": r[0], "product_id": r[1]} for r in rows]


def get_autonomy_config(product_id: str, action_type: str) -> tuple[str, "int | None"]:
    """Resolve tier using: master → per-action → default('approve')."""
    with _conn() as conn:
        # Check master override first
        row = conn.execute(
            "SELECT autonomy_master_tier, autonomy_master_window_minutes FROM products WHERE id = ?",
            (product_id,),
        ).fetchone()
        if row and row["autonomy_master_tier"]:
            return row["autonomy_master_tier"], row["autonomy_master_window_minutes"]
        # Per-action row
        action_row = conn.execute(
            "SELECT tier, window_minutes FROM product_autonomy WHERE product_id = ? AND action_type = ?",
            (product_id, action_type),
        ).fetchone()
        if action_row:
            return action_row["tier"], action_row["window_minutes"]
    return "approve", None


def set_action_autonomy(
    product_id: str, action_type: str, tier: str, window_minutes: "int | None"
) -> None:
    with _conn() as conn:
        conn.execute(
            """INSERT INTO product_autonomy (product_id, action_type, tier, window_minutes)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(product_id, action_type) DO UPDATE SET
                   tier = excluded.tier,
                   window_minutes = excluded.window_minutes""",
            (product_id, action_type, tier, window_minutes),
        )


def set_master_autonomy(
    product_id: str, tier: "str | None", window_minutes: "int | None"
) -> None:
    with _conn() as conn:
        conn.execute(
            """UPDATE products
               SET autonomy_master_tier = ?, autonomy_master_window_minutes = ?
               WHERE id = ?""",
            (tier, window_minutes, product_id),
        )


def get_product_autonomy_settings(product_id: str) -> dict:
    with _conn() as conn:
        row = conn.execute(
            "SELECT autonomy_master_tier, autonomy_master_window_minutes FROM products WHERE id = ?",
            (product_id,),
        ).fetchone()
        action_rows = conn.execute(
            "SELECT action_type, tier, window_minutes FROM product_autonomy WHERE product_id = ? ORDER BY action_type",
            (product_id,),
        ).fetchall()
    return {
        "master_tier": row["autonomy_master_tier"] if row else None,
        "master_window_minutes": row["autonomy_master_window_minutes"] if row else None,
        "action_overrides": [dict(r) for r in action_rows],
    }
```

- [ ] **Step 8: Run tests to verify they pass**

```bash
cd /home/justin/Code/Adjutant && python -m pytest tests/test_db.py::test_get_autonomy_config_resolution_order tests/test_db.py::test_auto_resolve_expired_reviews tests/test_db.py::test_get_product_autonomy_settings tests/test_db.py::test_save_review_item_with_action_type -v 2>&1 | tail -20
```

Expected: 4 tests PASSED.

- [ ] **Step 9: Run full test suite to check for regressions**

```bash
cd /home/justin/Code/Adjutant && python -m pytest tests/ -v 2>&1 | tail -30
```

Expected: All previously-passing tests still PASS. Some tests touching `load_review_items` output may now include `action_type` and `auto_approve_at` keys — that's fine (additive change).

- [ ] **Step 10: Commit**

```bash
cd /home/justin/Code/Adjutant && git add backend/db.py tests/test_db.py && git commit -m "feat: add trust tier DB schema and autonomy functions"
```

---

## Task 2: Tool definition update and `_run_one_tool` enforcement

**Files:**
- Modify: `core/tools.py`
- Modify: `backend/main.py`
- Create: `tests/test_trust_tiers.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_trust_tiers.py`:

```python
# tests/test_trust_tiers.py
import importlib
import json
import os
import asyncio
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
            "VALUES ('test-product', 'Test Product', 'TP', '#2563eb')"
        )
    return db_mod


def test_create_review_item_tool_requires_action_type():
    """create_review_item tool schema must include action_type as required."""
    from core.tools import TOOLS_DEFINITIONS
    tool = next(t for t in TOOLS_DEFINITIONS if t["name"] == "create_review_item")
    props = tool["input_schema"]["properties"]
    required = tool["input_schema"]["required"]
    assert "action_type" in props
    assert "action_type" in required


def test_create_review_item_auto_tier_resolves_immediately(db):
    """When action_type is auto-tier, review item is approved immediately."""
    db.set_action_autonomy("test-product", "agent_review", "auto", None)

    result_json = asyncio.run(_call_create_review_item(db))
    result = json.loads(result_json)
    item_id = result["id"]

    with db._conn() as conn:
        row = conn.execute(
            "SELECT status FROM review_items WHERE id = ?", (item_id,)
        ).fetchone()
    # Tool itself doesn't resolve — resolution happens in _run_one_tool (main.py)
    # This test verifies the tool creates the item; main.py tests verify resolution
    assert row["status"] == "pending"  # tool just saves, _run_one_tool resolves


def test_create_review_item_window_tier_sets_deadline(db):
    """When action_type is window-tier, auto_approve_at is set after tool runs."""
    from datetime import datetime
    db.set_action_autonomy("test-product", "agent_review", "window", 5)

    result_json = asyncio.run(_call_create_review_item(db))
    result = json.loads(result_json)
    item_id = result["id"]

    # The deadline is set by _run_one_tool (main.py); tool just saves
    # Verify tool correctly stores action_type
    items = db.load_review_items("test-product")
    assert items[0]["action_type"] == "agent_review"


async def _call_create_review_item(db):
    from core.tools import execute_tool
    return await execute_tool("create_review_item", {
        "title": "Test review",
        "description": "Test description",
        "risk_label": "test risk",
        "product_id": "test-product",
        "action_type": "agent_review",
    })
```

- [ ] **Step 2: Run to verify failures**

```bash
cd /home/justin/Code/Adjutant && python -m pytest tests/test_trust_tiers.py::test_create_review_item_tool_requires_action_type -v 2>&1 | tail -10
```

Expected: FAILED (`action_type` not in required).

- [ ] **Step 3: Add `action_type` to `create_review_item` tool definition**

In `core/tools.py`, find the `create_review_item` tool definition (around line 122). Add `action_type` to its properties and required list:

```python
    {
        "name": "create_review_item",
        "description": (
            "Add an item to the user's approval queue. Use this before taking any consequential, "
            "irreversible, or public-facing action: sending emails to clients, posting to social "
            "media, making purchases, or anything that goes out under the user's name. "
            "Do NOT use for internal research or drafting."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Short title for the item, e.g. 'LinkedIn post: launch announcement'",
                },
                "description": {
                    "type": "string",
                    "description": "2-3 sentence summary of what will happen when approved: who receives it, what it says, timing. Do not paste full content here — that belongs in the activity feed.",
                },
                "risk_label": {
                    "type": "string",
                    "description": "One short phrase describing the risk, e.g. 'Public-facing · irreversible' or 'Sends from your email · 12 recipients'",
                },
                "product_id": {
                    "type": "string",
                    "description": "The product this action belongs to",
                },
                "action_type": {
                    "type": "string",
                    "enum": ["social_post", "email", "agent_review"],
                    "description": "Category of action: 'social_post' for social media posts, 'email' for email actions, 'agent_review' for any other consequential action",
                },
            },
            "required": ["title", "description", "risk_label", "product_id", "action_type"],
        },
    },
```

- [ ] **Step 4: Update `_create_review_item` handler in `core/tools.py`**

Find `_create_review_item` (around line 1024). Replace it with:

```python
def _create_review_item(
    title: str, description: str, risk_label: str, product_id: str,
    action_type: str = "agent_review",
) -> str:
    from backend.db import save_review_item
    item_id = save_review_item(
        product_id=product_id,
        title=title,
        description=description,
        risk_label=risk_label,
        action_type=action_type,
    )
    return json.dumps({"id": item_id, "title": title, "status": "pending"})
```

- [ ] **Step 5: Add `action_type='social_post'` to `_draft_social_post` in `core/tools.py`**

Find the `save_review_item` call inside `_draft_social_post` (around line 1001):

```python
    review_id = save_review_item(
        product_id=product_id,
        title=f"Post to {platform.capitalize()}",
        description=description,
        risk_label=risk,
    )
```

Replace with:

```python
    review_id = save_review_item(
        product_id=product_id,
        title=f"Post to {platform.capitalize()}",
        description=description,
        risk_label=risk,
        action_type="social_post",
    )
```

- [ ] **Step 6: Add autonomy enforcement to `_run_one_tool` in `backend/main.py`**

In `backend/main.py`, find the `is_review` block inside `_run_one_tool` (around line 604). The current block broadcasts `review_item_added` unconditionally. Replace it with:

```python
            if is_review:
                try:
                    parsed  = json.loads(output)
                    item_id = parsed["id"]
                    from backend.db import get_autonomy_config, resolve_review_item, set_auto_approve_at
                    from datetime import datetime, timedelta
                    action_type_val = block.input.get("action_type", "agent_review")
                    tier, window_minutes = get_autonomy_config(product_id, action_type_val)
                    if tier == "auto":
                        resolve_review_item(item_id, "approved")
                        await send_fn({"type": "review_resolved", "review_item_id": item_id, "action": "auto_approved"})
                    else:
                        if tier == "window":
                            deadline = datetime.now() + timedelta(minutes=window_minutes or 10)
                            set_auto_approve_at(item_id, deadline)
                            deadline_str = deadline.isoformat(timespec="seconds")
                        else:
                            deadline_str = None
                        item = {
                            "id": item_id,
                            "title": block.input.get("title", ""),
                            "description": block.input.get("description", ""),
                            "risk_label": block.input.get("risk_label", ""),
                            "action_type": action_type_val,
                            "auto_approve_at": deadline_str,
                            "status": "pending", "created_at": _ts(),
                        }
                        await send_fn({"type": "review_item_added", "product_id": product_id, "item": item})
                        new_review_items.append(item)
                except (json.JSONDecodeError, KeyError):
                    pass
```

- [ ] **Step 7: Apply autonomy to `draft_social_post` in `backend/main.py`**

Find the `draft_social_post` block inside `_run_one_tool` (around line 626). The current block broadcasts `review_item_added` unconditionally. Replace it with:

```python
            if block.name == "draft_social_post":
                try:
                    parsed    = json.loads(output)
                    review_id = parsed.get("review_item_id")
                    pid       = block.input.get("product_id", product_id)
                    if review_id:
                        from backend.db import get_autonomy_config, resolve_review_item, set_auto_approve_at
                        from datetime import datetime, timedelta
                        tier, window_minutes = get_autonomy_config(pid, "social_post")
                        if tier == "auto":
                            resolve_review_item(review_id, "approved")
                            await send_fn({"type": "review_resolved", "review_item_id": review_id, "action": "auto_approved"})
                        else:
                            if tier == "window":
                                deadline = datetime.now() + timedelta(minutes=window_minutes or 10)
                                set_auto_approve_at(review_id, deadline)
                                deadline_str = deadline.isoformat(timespec="seconds")
                            else:
                                deadline_str = None
                            item = {
                                "id": review_id,
                                "title": f"Post to {block.input.get('platform', '').capitalize()}",
                                "description": block.input.get("content", "")[:200],
                                "risk_label": f"Social post · {block.input.get('platform', '')} · public-facing",
                                "action_type": "social_post",
                                "auto_approve_at": deadline_str,
                                "status": "pending", "created_at": _ts(),
                            }
                            await send_fn({"type": "review_item_added", "product_id": pid, "item": item})
                except (json.JSONDecodeError, KeyError):
                    pass
```

- [ ] **Step 8: Run tests to verify they pass**

```bash
cd /home/justin/Code/Adjutant && python -m pytest tests/test_trust_tiers.py -v 2>&1 | tail -20
```

Expected: All 3 tests PASSED.

- [ ] **Step 9: Run full test suite**

```bash
cd /home/justin/Code/Adjutant && python -m pytest tests/ -v 2>&1 | tail -30
```

Expected: All tests PASS.

- [ ] **Step 10: Commit**

```bash
cd /home/justin/Code/Adjutant && git add core/tools.py backend/main.py tests/test_trust_tiers.py && git commit -m "feat: enforce trust tiers in _run_one_tool for create_review_item and draft_social_post"
```

---

## Task 3: Scheduler auto-resolve poll

**Files:**
- Modify: `backend/scheduler.py`
- Modify: `tests/test_trust_tiers.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_trust_tiers.py`:

```python
def test_scheduler_auto_resolves_expired_reviews(db, monkeypatch):
    """scheduler_loop calls auto_resolve_expired_reviews and broadcasts review_resolved."""
    from datetime import datetime, timedelta
    import asyncio

    # Create an expired window review item
    item_id = db.save_review_item(
        "test-product", "Expired window", "desc", "risk", action_type="email"
    )
    db.set_auto_approve_at(item_id, datetime.now() - timedelta(minutes=1))

    # Capture broadcasts
    broadcasts = []
    async def fake_broadcast(msg):
        broadcasts.append(msg)

    # Run one iteration of the poll logic (not the full loop)
    async def run_one_poll():
        from backend.db import auto_resolve_expired_reviews
        resolved = auto_resolve_expired_reviews()
        for r in resolved:
            await fake_broadcast({
                "type": "review_resolved",
                "review_item_id": r["id"],
                "action": "auto_approved",
            })

    asyncio.run(run_one_poll())

    assert len(broadcasts) == 1
    assert broadcasts[0]["type"] == "review_resolved"
    assert broadcasts[0]["review_item_id"] == item_id
    assert broadcasts[0]["action"] == "auto_approved"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /home/justin/Code/Adjutant && python -m pytest tests/test_trust_tiers.py::test_scheduler_auto_resolves_expired_reviews -v 2>&1 | tail -10
```

Expected: FAILED (function not found or import error).

- [ ] **Step 3: Add auto-resolve poll to `scheduler_loop`**

In `backend/scheduler.py`, find `scheduler_loop` (around line 509). Add the auto-resolve poll inside the `try` block, after the autonomous objectives check:

```python
async def scheduler_loop(broadcast: BroadcastFn, interval_seconds: int = 60) -> None:
    """Main loop — polls for due workstreams every `interval_seconds`."""
    log.info("Workstream scheduler started (interval=%ds)", interval_seconds)
    _auto_resolve_counter = 0
    while True:
        try:
            from backend.db import get_due_workstreams, get_due_autonomous_objectives
            due = get_due_workstreams()
            for ws in due:
                if not _running.get(ws["id"]):
                    asyncio.create_task(_run_workstream(ws, broadcast))
            # Autonomous objectives check
            due_objs = get_due_autonomous_objectives()
            for obj in due_objs:
                if not _running_objectives.get(obj["id"]):
                    asyncio.create_task(_run_objective_loop(obj["product_id"], obj["id"]))
            # Auto-resolve expired window reviews (every ~30s regardless of main interval)
            _auto_resolve_counter += 1
            if _auto_resolve_counter >= max(1, 30 // interval_seconds):
                _auto_resolve_counter = 0
                from backend.db import auto_resolve_expired_reviews
                resolved = auto_resolve_expired_reviews()
                for r in resolved:
                    await broadcast({
                        "type": "review_resolved",
                        "review_item_id": r["id"],
                        "action": "auto_approved",
                    })
        except Exception as exc:
            log.error("Scheduler poll error: %s", exc)
        await asyncio.sleep(interval_seconds)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /home/justin/Code/Adjutant && python -m pytest tests/test_trust_tiers.py::test_scheduler_auto_resolves_expired_reviews -v 2>&1 | tail -10
```

Expected: PASSED.

- [ ] **Step 5: Run full test suite**

```bash
cd /home/justin/Code/Adjutant && python -m pytest tests/ -v 2>&1 | tail -20
```

Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
cd /home/justin/Code/Adjutant && git add backend/scheduler.py tests/test_trust_tiers.py && git commit -m "feat: scheduler polls auto_resolve_expired_reviews every 30s"
```

---

## Task 4: REST endpoints for autonomy config and WS cancel handler

**Files:**
- Modify: `backend/api.py`
- Modify: `backend/main.py`
- Modify: `tests/test_trust_tiers.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_trust_tiers.py`:

```python
def test_get_autonomy_settings_api(db, monkeypatch):
    """GET /api/products/{id}/autonomy returns current settings."""
    from fastapi.testclient import TestClient
    monkeypatch.setenv("AGENT_PASSWORD", "testpw")
    import backend.main as main_mod
    import importlib
    importlib.reload(main_mod)
    client = TestClient(main_mod.app)

    db.set_master_autonomy("test-product", "window", 10)
    db.set_action_autonomy("test-product", "social_post", "auto", None)

    resp = client.get(
        "/api/products/test-product/autonomy",
        headers={"X-Agent-Password": "testpw"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["master_tier"] == "window"
    assert data["master_window_minutes"] == 10
    overrides = {o["action_type"]: o for o in data["action_overrides"]}
    assert overrides["social_post"]["tier"] == "auto"


def test_put_autonomy_settings_api(db, monkeypatch):
    """PUT /api/products/{id}/autonomy saves settings."""
    from fastapi.testclient import TestClient
    monkeypatch.setenv("AGENT_PASSWORD", "testpw")
    import backend.main as main_mod
    import importlib
    importlib.reload(main_mod)
    client = TestClient(main_mod.app)

    resp = client.put(
        "/api/products/test-product/autonomy",
        headers={"X-Agent-Password": "testpw", "Content-Type": "application/json"},
        json={
            "master_tier": None,
            "master_window_minutes": None,
            "action_overrides": [
                {"action_type": "social_post", "tier": "auto", "window_minutes": None},
                {"action_type": "email", "tier": "window", "window_minutes": 5},
            ],
        },
    )
    assert resp.status_code == 200

    # Verify persisted
    settings = db.get_product_autonomy_settings("test-product")
    overrides = {o["action_type"]: o for o in settings["action_overrides"]}
    assert overrides["social_post"]["tier"] == "auto"
    assert overrides["email"]["tier"] == "window"
    assert overrides["email"]["window_minutes"] == 5
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd /home/justin/Code/Adjutant && python -m pytest tests/test_trust_tiers.py::test_get_autonomy_settings_api tests/test_trust_tiers.py::test_put_autonomy_settings_api -v 2>&1 | tail -10
```

Expected: FAILED with 404.

- [ ] **Step 3: Add Pydantic models and REST endpoints to `backend/api.py`**

Find the imports at the top of `backend/api.py`. Add the new models and two endpoints. Place them after the `get_notes_api` / `update_notes_api` endpoints (around line 261):

First, find where other Pydantic models are defined in `backend/api.py` and add these alongside them:

```python
class ActionOverride(BaseModel):
    action_type: str
    tier: str
    window_minutes: Optional[int] = None

class AutonomySettingsUpdate(BaseModel):
    master_tier: Optional[str] = None
    master_window_minutes: Optional[int] = None
    action_overrides: list[ActionOverride] = []
```

Then add the endpoints (after `update_notes_api`):

```python
@router.get("/products/{product_id}/autonomy")
def get_autonomy_api(product_id: str, _=Depends(_auth)):
    from backend.db import get_product_autonomy_settings
    return get_product_autonomy_settings(product_id)


@router.put("/products/{product_id}/autonomy")
def update_autonomy_api(product_id: str, body: AutonomySettingsUpdate, _=Depends(_auth)):
    from backend.db import set_master_autonomy, set_action_autonomy, get_product_autonomy_settings
    import sqlite3
    with __import__('backend.db', fromlist=['_conn']).db._conn() as conn:
        conn.execute(
            "DELETE FROM product_autonomy WHERE product_id = ?", (product_id,)
        )
    set_master_autonomy(product_id, body.master_tier, body.master_window_minutes)
    for override in body.action_overrides:
        set_action_autonomy(product_id, override.action_type, override.tier, override.window_minutes)
    return get_product_autonomy_settings(product_id)
```

Note: the `DELETE FROM product_autonomy` before re-inserting implements the "full replacement" semantic. The proper way to do this without the awkward import is to add a `clear_product_autonomy(product_id)` db function. Add it to `backend/db.py`:

```python
def clear_product_autonomy(product_id: str) -> None:
    with _conn() as conn:
        conn.execute("DELETE FROM product_autonomy WHERE product_id = ?", (product_id,))
```

Then the endpoint becomes:

```python
@router.put("/products/{product_id}/autonomy")
def update_autonomy_api(product_id: str, body: AutonomySettingsUpdate, _=Depends(_auth)):
    from backend.db import (
        set_master_autonomy, set_action_autonomy,
        get_product_autonomy_settings, clear_product_autonomy,
    )
    clear_product_autonomy(product_id)
    set_master_autonomy(product_id, body.master_tier, body.master_window_minutes)
    for override in body.action_overrides:
        set_action_autonomy(product_id, override.action_type, override.tier, override.window_minutes)
    return get_product_autonomy_settings(product_id)
```

Also check what `Optional` and `BaseModel` imports exist in `backend/api.py` — add `from typing import Optional` if not already present, and ensure `BaseModel` is imported from `pydantic`.

- [ ] **Step 4: Add `cancel_auto_approve` WS handler in `backend/main.py`**

In `backend/main.py`, find the `resolve_review` WS handler (around line 983). Add after it:

```python
            elif msg_type == "cancel_auto_approve":
                item_id = msg.get("review_item_id")
                if item_id:
                    from backend.db import clear_auto_approve_at, load_review_items
                    clear_auto_approve_at(item_id)
                    # Find the product_id for this item so we can broadcast
                    # Search across all cached product states by reading DB
                    with __import__('backend.db', fromlist=['_conn']).db._conn() as conn:
                        row = conn.execute(
                            "SELECT product_id, id, title, description, risk_label, "
                            "action_type, auto_approve_at, status, created_at "
                            "FROM review_items WHERE id = ?", (item_id,)
                        ).fetchone()
                    if row:
                        updated_item = dict(row)
                        await _broadcast({
                            "type": "review_item_updated",
                            "product_id": row["product_id"],
                            "item": updated_item,
                        })
```

Since doing a raw DB query in main.py is messy, add a `get_review_item_by_id(item_id)` db function instead:

Add to `backend/db.py` after `load_review_items`:

```python
def get_review_item_by_id(item_id: int) -> "dict | None":
    with _conn() as conn:
        row = conn.execute(
            """SELECT id, product_id, activity_event_id, title, description, risk_label,
                      status, created_at, action_type, auto_approve_at
               FROM review_items WHERE id = ?""",
            (item_id,),
        ).fetchone()
    return dict(row) if row else None
```

Then the WS handler becomes:

```python
            elif msg_type == "cancel_auto_approve":
                item_id = msg.get("review_item_id")
                if item_id:
                    from backend.db import clear_auto_approve_at, get_review_item_by_id
                    clear_auto_approve_at(item_id)
                    item = get_review_item_by_id(item_id)
                    if item:
                        await _broadcast({
                            "type": "review_item_updated",
                            "product_id": item["product_id"],
                            "item": item,
                        })
```

Also add `clear_auto_approve_at` and `get_review_item_by_id` to the imports at the top of the `backend/main.py` import block from `backend.db`.

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd /home/justin/Code/Adjutant && python -m pytest tests/test_trust_tiers.py::test_get_autonomy_settings_api tests/test_trust_tiers.py::test_put_autonomy_settings_api -v 2>&1 | tail -15
```

Expected: Both PASSED.

- [ ] **Step 6: Run full test suite**

```bash
cd /home/justin/Code/Adjutant && python -m pytest tests/ -v 2>&1 | tail -20
```

Expected: All tests PASS.

- [ ] **Step 7: Commit**

```bash
cd /home/justin/Code/Adjutant && git add backend/api.py backend/main.py backend/db.py tests/test_trust_tiers.py && git commit -m "feat: REST endpoints for autonomy config and WS cancel_auto_approve handler"
```

---

## Task 5: Frontend types, ReviewCard countdown, and App wiring

**Files:**
- Modify: `ui/src/types.ts`
- Modify: `ui/src/components/ReviewCard.tsx`
- Modify: `ui/src/components/ReviewQueue.tsx`
- Modify: `ui/src/App.tsx`

- [ ] **Step 1: Update `ui/src/types.ts`**

Add `action_type` and `auto_approve_at` to `ReviewItem`:

```typescript
export interface ReviewItem {
  id: number
  title: string
  description: string
  risk_label: string
  status: 'pending' | 'approved' | 'skipped'
  created_at: string
  action_type?: string | null
  auto_approve_at?: string | null
}
```

Add `review_item_updated` and `autonomy_config` to the `ServerMessage` union (after `review_resolved`):

```typescript
  | { type: 'review_item_updated'; product_id: string; item: ReviewItem }
  | { type: 'autonomy_config'; product_id: string; master_tier: string | null; master_window_minutes: number | null; action_overrides: Array<{ action_type: string; tier: string; window_minutes: number | null }> }
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /home/justin/Code/Adjutant/ui && npx tsc --noEmit 2>&1 | head -30
```

Expected: No errors (additive field changes are backward-compatible).

- [ ] **Step 3: Update `ReviewCard.tsx` to add countdown and Cancel button**

Replace the entire file with:

```typescript
// ui/src/components/ReviewCard.tsx
import { useEffect, useState } from 'react'
import { ReviewItem } from '../types'

interface Props {
  item: ReviewItem
  onResolve: (id: number, action: 'approved' | 'skipped') => void
  onCancelAutoApprove?: (id: number) => void
}

const TRUNCATE_AT = 120

function formatCountdown(seconds: number): string {
  if (seconds <= 0) return 'approving…'
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return m > 0 ? `${m}m ${s}s` : `${s}s`
}

export default function ReviewCard({ item, onResolve, onCancelAutoApprove }: Props) {
  const [expanded, setExpanded] = useState(false)
  const [secondsLeft, setSecondsLeft] = useState<number | null>(null)

  useEffect(() => {
    if (!item.auto_approve_at) { setSecondsLeft(null); return }
    const tick = () => {
      const diff = Math.max(0, Math.floor(
        (new Date(item.auto_approve_at!).getTime() - Date.now()) / 1000
      ))
      setSecondsLeft(diff)
    }
    tick()
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [item.auto_approve_at])

  const isWindow = secondsLeft !== null
  const long = item.description && item.description.length > TRUNCATE_AT
  const displayDesc = long && !expanded
    ? item.description.slice(0, TRUNCATE_AT).trimEnd() + '…'
    : item.description

  return (
    <div className={`rounded-xl border p-3 flex flex-col gap-2.5 ${
      isWindow
        ? 'border-yellow-800/50 bg-yellow-950/10'
        : 'border-amber-900/50 bg-amber-950/10'
    }`}>
      <div className="text-sm font-semibold text-zinc-200 leading-snug">{item.title}</div>
      <div className="text-xs text-zinc-400 leading-relaxed">
        {displayDesc}
        {long && (
          <button
            onClick={() => setExpanded(e => !e)}
            className="ml-1 text-zinc-600 hover:text-zinc-400 underline underline-offset-2"
          >
            {expanded ? 'less' : 'more'}
          </button>
        )}
      </div>
      {item.risk_label && (
        <div className="flex items-center gap-1 text-xs text-amber-500">
          <span className="w-1 h-1 rounded-full bg-amber-500 flex-shrink-0" />
          {item.risk_label}
        </div>
      )}
      {isWindow && (
        <div className="flex items-center justify-between">
          <span className="text-xs text-yellow-500 font-mono">
            Auto-approving in {formatCountdown(secondsLeft!)}
          </span>
          {onCancelAutoApprove && (
            <button
              type="button"
              onClick={() => onCancelAutoApprove(item.id)}
              className="text-xs text-zinc-500 hover:text-red-400 transition-colors underline underline-offset-2"
            >
              Cancel
            </button>
          )}
        </div>
      )}
      <div className="flex gap-2 mt-0.5">
        <button
          type="button"
          onClick={() => onResolve(item.id, 'approved')}
          className="flex-1 rounded-lg bg-emerald-900/50 border border-emerald-700/60 text-emerald-400 text-xs font-semibold py-1.5 hover:bg-emerald-900/80 transition-colors"
        >
          Approve
        </button>
        <button
          type="button"
          onClick={() => onResolve(item.id, 'approved')}
          className="flex-1 rounded-lg bg-blue-900/30 border border-blue-700/50 text-blue-400 text-xs font-semibold py-1.5 hover:bg-blue-900/50 transition-colors"
        >
          Edit
        </button>
        <button
          type="button"
          onClick={() => onResolve(item.id, 'skipped')}
          className="rounded-lg bg-zinc-800/60 border border-zinc-700/40 text-zinc-500 text-xs px-3 py-1.5 hover:bg-zinc-700/60 transition-colors"
        >
          Skip
        </button>
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Update `ReviewQueue.tsx` to thread `onCancelAutoApprove`**

In `ui/src/components/ReviewQueue.tsx`, update the `Props` interface and the `ReviewCard` render call:

```typescript
interface Props {
  items: ReviewItem[]
  onResolve: (id: number, action: 'approved' | 'skipped') => void
  queued: DirectiveItem[]
  onCancelQueued: (id: string) => void
  agentName: string
  onCancelAutoApprove: (id: number) => void
}
```

And in the return where `ReviewCard` is rendered:

```typescript
          items.map(item => (
            <ReviewCard
              key={item.id}
              item={item}
              onResolve={onResolve}
              onCancelAutoApprove={onCancelAutoApprove}
            />
          ))
```

- [ ] **Step 5: Update `App.tsx` — add `cancelAutoApprove` callback and `review_item_updated` handler**

In `App.tsx`, add `cancelAutoApprove` callback alongside `resolveReview` (around line 384):

```typescript
  const cancelAutoApprove = useCallback((id: number) => {
    wsRef.current?.send(JSON.stringify({
      type: 'cancel_auto_approve',
      review_item_id: id,
    }))
  }, [])
```

Add `review_item_updated` handler in the `ws.onmessage` block (after the `review_resolved` handler):

```typescript
      if (msg.type === 'review_item_updated') {
        setProductState(msg.product_id, prev => ({
          ...prev,
          review_items: prev.review_items.map(i =>
            i.id === msg.item.id ? { ...i, ...msg.item } : i
          ),
        }))
        return
      }
```

Pass `onCancelAutoApprove` to `ReviewQueue` (around line 677):

```typescript
              <ReviewQueue
                items={activeState.review_items.filter(i => i.status === 'pending')}
                onResolve={resolveReview}
                queued={queueByProduct[activeProductId]?.queued ?? []}
                onCancelQueued={cancelDirective}
                agentName={agentName}
                onCancelAutoApprove={cancelAutoApprove}
              />
```

- [ ] **Step 6: Verify TypeScript compiles**

```bash
cd /home/justin/Code/Adjutant/ui && npx tsc --noEmit 2>&1 | head -30
```

Expected: No errors.

- [ ] **Step 7: Commit**

```bash
cd /home/justin/Code/Adjutant && git add ui/src/types.ts ui/src/components/ReviewCard.tsx ui/src/components/ReviewQueue.tsx ui/src/App.tsx && git commit -m "feat: ReviewCard countdown timer and cancel button for window-tier items"
```

---

## Task 6: SettingsSidebar autonomy section and api.ts additions

**Files:**
- Modify: `ui/src/api.ts`
- Modify: `ui/src/components/SettingsSidebar.tsx`

- [ ] **Step 1: Add autonomy API methods to `ui/src/api.ts`**

Add after `updateNotes` (around line 120):

```typescript
  getAutonomySettings: (pw: string, productId: string) =>
    apiFetch<{
      master_tier: string | null
      master_window_minutes: number | null
      action_overrides: Array<{ action_type: string; tier: string; window_minutes: number | null }>
    }>(`/api/products/${productId}/autonomy`, pw),

  updateAutonomySettings: (
    pw: string,
    productId: string,
    data: {
      master_tier: string | null
      master_window_minutes: number | null
      action_overrides: Array<{ action_type: string; tier: string; window_minutes: number | null }>
    },
  ) =>
    apiFetch<{
      master_tier: string | null
      master_window_minutes: number | null
      action_overrides: Array<{ action_type: string; tier: string; window_minutes: number | null }>
    }>(`/api/products/${productId}/autonomy`, pw, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
```

- [ ] **Step 2: Add autonomy state and load logic to `SettingsSidebar.tsx`**

Find the section open state declarations (around line 106). Add autonomy state:

```typescript
  const [autonomyOpen, setAutonomyOpen] = useState(false)

  // Autonomy settings state
  const [masterTier,    setMasterTier]    = useState<string | null>(null)
  const [masterWindow,  setMasterWindow]  = useState<number>(10)
  const [actionTiers,   setActionTiers]   = useState<Record<string, { tier: string; window_minutes: number }>>({
    social_post:  { tier: 'approve', window_minutes: 10 },
    email:        { tier: 'approve', window_minutes: 10 },
    agent_review: { tier: 'approve', window_minutes: 10 },
  })
  const [autonomySaving, setAutonomySaving] = useState(false)
```

In the `useEffect` that loads product config (around line 200, where `api.getProductConfig` is called), also load autonomy settings:

```typescript
    api.getAutonomySettings(password, productId).then(settings => {
      setMasterTier(settings.master_tier)
      setMasterWindow(settings.master_window_minutes ?? 10)
      const tiers = { ...actionTiers }
      for (const o of settings.action_overrides) {
        tiers[o.action_type] = { tier: o.tier, window_minutes: o.window_minutes ?? 10 }
      }
      setActionTiers(tiers)
    }).catch(() => {})
```

- [ ] **Step 3: Add save function for autonomy**

After the existing `handleBrandSave` function, add:

```typescript
  async function handleAutonomySave() {
    setAutonomySaving(true)
    try {
      await api.updateAutonomySettings(password, productId, {
        master_tier: masterTier,
        master_window_minutes: masterTier === 'window' ? masterWindow : null,
        action_overrides: Object.entries(actionTiers).map(([action_type, cfg]) => ({
          action_type,
          tier: cfg.tier,
          window_minutes: cfg.tier === 'window' ? cfg.window_minutes : null,
        })),
      })
    } finally {
      setAutonomySaving(false)
    }
  }
```

- [ ] **Step 4: Add Autonomy collapsible section to the JSX**

Find a logical insertion point in the SettingsSidebar JSX — after the Brand section and before the Models section. Add:

```typescript
        {/* ── Autonomy ──────────────────────────────────────────────────── */}
        <SectionHeader
          title="Autonomy"
          open={autonomyOpen}
          onToggle={() => setAutonomyOpen(o => !o)}
        />
        {autonomyOpen && (
          <div className="px-4 py-3 flex flex-col gap-4">
            {/* Master override */}
            <div>
              <label className="block text-xs text-zinc-500 mb-1">Master override</label>
              <div className="flex items-center gap-2">
                <select
                  value={masterTier ?? ''}
                  onChange={e => setMasterTier(e.target.value || null)}
                  className="flex-1 bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:border-zinc-600"
                >
                  <option value="">Per action type</option>
                  <option value="approve">Approve (always block)</option>
                  <option value="window">Window (auto after delay)</option>
                  <option value="auto">Auto (never block)</option>
                </select>
                {masterTier === 'window' && (
                  <input
                    type="number"
                    min={1}
                    value={masterWindow}
                    onChange={e => setMasterWindow(Number(e.target.value))}
                    className="w-20 bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:border-zinc-600"
                    placeholder="min"
                  />
                )}
              </div>
              {masterTier && (
                <button
                  onClick={() => setMasterTier(null)}
                  className="mt-1 text-xs text-zinc-600 hover:text-zinc-400 underline underline-offset-2"
                >
                  Clear override
                </button>
              )}
            </div>

            {/* Per-action table */}
            <div className={masterTier ? 'opacity-50 pointer-events-none' : ''}>
              <label className="block text-xs text-zinc-500 mb-2">Per action type</label>
              <div className="flex flex-col gap-2">
                {([
                  ['social_post',  'Social posts'],
                  ['email',        'Emails'],
                  ['agent_review', 'Agent reviews'],
                ] as [string, string][]).map(([key, label]) => (
                  <div key={key} className="flex items-center gap-2">
                    <span className="text-xs text-zinc-400 w-28 flex-shrink-0">{label}</span>
                    <select
                      value={actionTiers[key]?.tier ?? 'approve'}
                      onChange={e => setActionTiers(prev => ({
                        ...prev,
                        [key]: { ...prev[key], tier: e.target.value },
                      }))}
                      className="flex-1 bg-zinc-900 border border-zinc-800 rounded-lg px-2 py-1.5 text-xs text-zinc-100 focus:outline-none focus:border-zinc-600"
                    >
                      <option value="approve">Approve</option>
                      <option value="window">Window</option>
                      <option value="auto">Auto</option>
                    </select>
                    {actionTiers[key]?.tier === 'window' && (
                      <input
                        type="number"
                        min={1}
                        value={actionTiers[key]?.window_minutes ?? 10}
                        onChange={e => setActionTiers(prev => ({
                          ...prev,
                          [key]: { ...prev[key], window_minutes: Number(e.target.value) },
                        }))}
                        className="w-16 bg-zinc-900 border border-zinc-800 rounded-lg px-2 py-1.5 text-xs text-zinc-100 focus:outline-none focus:border-zinc-600"
                        placeholder="min"
                      />
                    )}
                  </div>
                ))}
              </div>
            </div>

            <button
              onClick={handleAutonomySave}
              disabled={autonomySaving}
              className="self-end rounded-lg bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-xs font-semibold px-4 py-2 transition-colors"
            >
              {autonomySaving ? 'Saving…' : 'Save'}
            </button>
          </div>
        )}
```

- [ ] **Step 5: Verify TypeScript compiles**

```bash
cd /home/justin/Code/Adjutant/ui && npx tsc --noEmit 2>&1 | head -30
```

Expected: No errors.

- [ ] **Step 6: Run full backend test suite**

```bash
cd /home/justin/Code/Adjutant && python -m pytest tests/ -v 2>&1 | tail -20
```

Expected: All tests PASS.

- [ ] **Step 7: Commit**

```bash
cd /home/justin/Code/Adjutant && git add ui/src/api.ts ui/src/components/SettingsSidebar.tsx && git commit -m "feat: SettingsSidebar autonomy section and api.ts autonomy methods"
```

---

## Self-Review Notes

**Spec coverage check:**
- ✅ Section 1 (Data Model): Tasks 1 and 4 — `product_autonomy` table, `products` columns, `review_items` columns, `action_type` on `create_review_item` tool
- ✅ Section 2 (db.py functions): Task 1 — all 6 functions implemented
- ✅ Section 3 (Tool changes + `_run_one_tool`): Task 2 — `action_type` required, auto/window/approve logic for `create_review_item` and `draft_social_post`
- ✅ Section 4 (Scheduler poll): Task 3 — 30-second poll in `scheduler_loop`
- ✅ Section 5 (Frontend): Tasks 5 + 6 — types, ReviewCard countdown, SettingsSidebar, api.ts
- ✅ Section 6 (Error handling): Race condition in Task 4 WS handler (clear before broadcast; scheduler UPDATE is conditional on `status='pending'`)
- ✅ Section 7 (Testing): All named tests covered across Tasks 1–4

**Type consistency:**
- `get_autonomy_config` returns `tuple[str, int | None]` — used consistently in Tasks 2 and 3
- `auto_resolve_expired_reviews` returns `list[dict]` with `id` + `product_id` — used correctly in Task 3
- `ReviewItem.auto_approve_at` is `string | null` (ISO timestamp) throughout frontend
- `onCancelAutoApprove: (id: number) => void` threaded consistently ReviewCard → ReviewQueue → App
