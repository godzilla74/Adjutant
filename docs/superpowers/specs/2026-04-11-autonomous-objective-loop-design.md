# Autonomous Objective Loop — Design Spec

## Goal

Enable objectives to run autonomously: the agent works toward each objective on its own cadence, uses available tools (installing new ones as needed), reports progress, and only surfaces a review item when genuine human judgment is required.

## Architecture

Extend the existing scheduler (which already drives workstreams) to also drive autonomous objectives. Each objective gets a dedicated session for continuity. The agent sets its own next-run time via a tool call at the end of each cycle.

**Tech Stack:** Python/FastAPI backend, SQLite, existing `_agent_loop()`, existing scheduler pattern, React frontend.

---

## Section 1: Data Model

Five new columns on the `objectives` table (added via `ALTER TABLE`):

| Column | Type | Default | Purpose |
|--------|------|---------|---------|
| `autonomous` | `INTEGER` | `0` | 1 = scheduler drives this objective |
| `session_id` | `TEXT REFERENCES sessions(id)` | `NULL` | Dedicated session for objective history |
| `next_run_at` | `TEXT` | `NULL` | When scheduler should run next; NULL = dormant |
| `last_run_at` | `TEXT` | `NULL` | Timestamp of last run, injected as agent context |
| `blocked_by_review_id` | `INTEGER` | `NULL` | FK to review_items; set when agent creates blocking review, cleared on resolution |

**Lifecycle of `next_run_at`:**
- Toggled autonomous ON → set to `datetime('now')` (fires immediately)
- Agent calls `schedule_next_run(hours)` → set to `now + hours`
- Agent creates a review item → cleared; `blocked_by_review_id` set
- Review resolved → set back to `datetime('now')`; `blocked_by_review_id` cleared

**New db.py functions:**
- `set_objective_autonomous(obj_id, autonomous: bool)` — flips flag, sets/clears `next_run_at`
- `get_due_autonomous_objectives()` — returns objectives where `autonomous=1 AND next_run_at <= now AND blocked_by_review_id IS NULL`
- `get_objective_blocked_by_review(review_item_id)` — returns objective blocked by a given review item
- `clear_objective_block(obj_id)` — clears `blocked_by_review_id`, sets `next_run_at = datetime('now')`
- `set_objective_next_run(obj_id, hours)` — sets `next_run_at = datetime('now', '+N hours')`, updates `last_run_at`

---

## Section 2: Agent Loop

### `_run_objective_loop(product_id, objective_id)` in `backend/scheduler.py`

1. Load objective from DB
2. If no `session_id`, create one (`create_session(f"Objective: {obj['text'][:40]}", product_id)`) and save it to the objective
3. Call `_build_context(product_id, session_id)` — agent gets full product context (brand, audience, system prompt) + objective session history
4. Append this user message to kick off the cycle:

```
You are autonomously working toward this objective: "{objective.text}"
Current progress: {progress_current}{' of ' + str(progress_target) if progress_target else ''}.
Last run: {last_run_at or 'never'}.

Use your available tools to take the best next action toward this goal.

When you have taken action, call `update_objective_progress` to record measurable progress,
then call `schedule_next_run` with how many hours until you should check back and why.

If you are blocked and need human input before you can proceed, call `create_review_item`
instead — do NOT call `schedule_next_run`.

If you need a capability you don't currently have (e.g., posting to a social platform,
reading analytics), use `find_skill` or `manage_mcp_server` to add it before proceeding
— don't create a review item just because a tool is missing.
```

5. Run `_agent_loop(_broadcast, product_id, messages, session_id=session_id)` — full tool-use loop
6. After loop completes, check outcome:
   - Agent called `schedule_next_run` → `next_run_at` already updated by tool; update `last_run_at`; done
   - Agent called `create_review_item` → set `blocked_by_review_id`; clear `next_run_at`; done
   - `progress_current >= progress_target` (target met) → create review item "Goal reached: '{text}'. What's next?" → go dormant (clear `next_run_at`)
   - Exception → broadcast error; clear `next_run_at` (go dormant to avoid crash loop)

**In-flight guard:** `_running_objectives: dict[int, bool]` — same pattern as `_running` for workstreams.

### Agent's Decision Tree (every cycle)

```
Have the tools I need?
  No  → find_skill / manage_mcp_server → install → proceed
  Yes → take best next action
        → update_objective_progress
        → schedule_next_run(hours, reason)    [continue autonomously]
        OR
        → create_review_item                  [go dormant, need human]
```

---

## Section 3: New Tools

Two new tools added to `core/tools.py`:

### `schedule_next_run`
```json
{
  "name": "schedule_next_run",
  "description": "Schedule the next autonomous run for the current objective. Call this at the end of every autonomous cycle to keep the loop running. If you need human input instead, call create_review_item — do not call this tool.",
  "input_schema": {
    "objective_id": "integer — the objective's ID",
    "hours": "number — how many hours until the next run (can be fractional, e.g. 0.5 for 30 minutes)",
    "reason": "string — brief explanation of why this cadence makes sense"
  }
}
```

### `update_objective_progress`
```json
{
  "name": "update_objective_progress",
  "description": "Update the measurable progress toward an objective. Call this whenever you have a concrete new number (e.g., follower count, deals closed, items completed).",
  "input_schema": {
    "objective_id": "integer — the objective's ID",
    "current": "integer — the current progress value",
    "notes": "string — optional context about how this was measured or what changed"
  }
}
```

### `set_objective_autonomous`
```json
{
  "name": "set_objective_autonomous",
  "description": "Enable or disable autonomous mode for an objective. When enabled, the scheduler will begin driving the objective immediately.",
  "input_schema": {
    "objective_id": "integer — the objective's ID",
    "autonomous": "boolean — true to enable, false to disable"
  }
}
```

---

## Section 4: Scheduler Extension

In `backend/scheduler.py`, after the existing workstream loop:

```python
_running_objectives: dict[int, bool] = {}

# In scheduler_loop, after workstream check:
due_objectives = get_due_autonomous_objectives()
for obj in due_objectives:
    if not _running_objectives.get(obj['id']):
        asyncio.create_task(_run_objective_loop(obj['product_id'], obj['id']))
```

### Review Resolution Hook

In `backend/main.py`, when `resolve_review` is processed, after existing social post logic:

```python
from backend.db import get_objective_blocked_by_review, clear_objective_block
from backend.scheduler import _run_objective_loop

blocked_obj = get_objective_blocked_by_review(item_id)
if blocked_obj:
    clear_objective_block(blocked_obj['id'])
    asyncio.create_task(
        _run_objective_loop(blocked_obj['product_id'], blocked_obj['id'])
    )
```

---

## Section 5: Frontend

### `ObjectivesPanel.tsx` changes

Each objective row gains:

- **🤖 toggle button** (indigo when autonomous + scheduled, amber when autonomous + blocked awaiting review, zinc when off)
- **Status text** next to the toggle: `runs in 6h` / `awaiting review` / nothing

```
[🤖] Grow to 10,000 followers    ████░░  847 / 10,000    runs in 6h
[🤖] Close 5 enterprise deals    ██░░░░    2 / 5         awaiting review  ← amber
[ ] Launch email campaign         ░░░░░░    0             (manual)
```

Clicking the 🤖 button sends `set_objective_autonomous` WebSocket message (or calls the API directly — follows existing workstream toggle pattern).

### New `product_data` fields

`product_data` WebSocket payload already includes objectives. Add the new fields (`autonomous`, `next_run_at`, `blocked_by_review_id`) to what `get_objectives()` returns so the frontend can render state without additional calls.

### WebSocket message: `set_objective_autonomous`

```json
{ "type": "set_objective_autonomous", "objective_id": 3, "autonomous": true }
```

Backend handler flips the flag and broadcasts an updated `product_data` payload.

### Chat activation

The agent's existing natural language understanding handles "make this autonomous" — it calls the new `set_objective_autonomous` tool. No additional frontend work needed.

---

## Error Handling

- **Agent loop exception** → go dormant (clear `next_run_at`); broadcast error to UI; do not retry automatically to avoid crash loops
- **Tool call to `schedule_next_run` with 0 or negative hours** → clamp to minimum 0.25 hours (15 minutes) to prevent runaway loops
- **Session creation failure** → fall back to product's active session; log warning
- **`blocked_by_review_id` set but review already resolved** → `get_due_autonomous_objectives` won't return it; safe

---

## Testing

- `test_objective_autonomous_loop`: objective with `autonomous=1` and due `next_run_at` is picked up by scheduler and runs
- `test_schedule_next_run_tool`: calling tool updates `next_run_at` correctly
- `test_objective_goes_dormant_on_review`: creating a review item during loop sets `blocked_by_review_id` and clears `next_run_at`
- `test_review_resolution_resumes_objective`: resolving the review clears block and triggers new loop
- `test_target_reached_creates_review`: when `progress_current >= progress_target`, loop creates review and goes dormant
- `test_minimum_cadence_clamp`: `schedule_next_run(hours=0)` clamps to 0.25
