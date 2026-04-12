# Launch Wizard — Design Spec

## Goal

Let the user say "launch [product]" and walk away. A short form captures name, description, and primary goal. The agent takes over from there — asking focused questions, autonomously configuring brand context, creating measurable objectives, and enabling autonomous mode — all visible through a live wizard UI.

## Architecture

Three components work together: a launch form (entry point), a wizard agent loop (backend), and a wizard UI (frontend). The only new schema change is a single `launch_wizard_active` flag on the products table. Everything else — sessions, tool calls, WebSocket broadcasts, the agent loop pattern — reuses existing infrastructure.

**Tech Stack:** Python/FastAPI backend, SQLite, existing `_agent_loop()`, React frontend, existing WebSocket broadcast pattern.

---

## Section 1: Data Model

One new column on the `products` table (added via `ALTER TABLE`):

| Column | Type | Default | Purpose |
|--------|------|---------|---------|
| `launch_wizard_active` | `INTEGER` | `0` | 1 = wizard is in progress for this product |

**Lifecycle:**
- Form submitted → `launch_wizard_active = 1` (set when product is created)
- Agent calls `complete_launch` → `launch_wizard_active = 0`
- Frontend shows wizard view when `launch_wizard_active === 1`, normal view otherwise

**New db.py function:**
- `set_launch_wizard_active(product_id: str, active: bool)` — sets the flag and saves `last_run_at` equivalent

The `get_product_config()` function already returns all product fields — just needs `launch_wizard_active` included in its SELECT.

---

## Section 2: New Tools

Two new tools in `core/tools.py`:

### `report_wizard_progress`
```json
{
  "name": "report_wizard_progress",
  "description": "Report what you are currently doing during the launch wizard setup. Call this before each action so the user can see your progress in real time.",
  "input_schema": {
    "message": "string — brief present-tense description of what you are about to do, e.g. 'Configuring brand voice' or 'Creating launch objectives'"
  }
}
```
Handler broadcasts `{"type": "wizard_progress", "product_id": ..., "message": ...}` via WebSocket.

### `complete_launch`
```json
{
  "name": "complete_launch",
  "description": "Call this when the product is fully configured and all objectives are created and set to autonomous mode. This ends the wizard and transitions the user to the live product view.",
  "input_schema": {
    "product_id": "string — the product's ID",
    "summary": "string — 2-3 sentence summary of what was set up: brand configured, objectives created, what the agent will do next"
  }
}
```
Handler: calls `set_launch_wizard_active(product_id, False)`, broadcasts `product_data`, broadcasts `{"type": "launch_complete", "product_id": ..., "summary": ...}`.

---

## Section 3: Wizard Agent Loop

### `_run_launch_wizard(product_id, session_id, description, primary_goal)` in `backend/scheduler.py`

1. Build the launch prompt and prepend to messages:

```
You are setting up a new product launch for "{product_name}".
Description: {description}
Primary goal: {primary_goal}

Your job during this setup session:
1. Ask the user focused questions to understand their brand, audience, and competitive position — one question at a time, conversationally
2. As you learn, call update_product to fill in brand_voice, tone, writing_style, target_audience, social_handles, hashtags, and brand_notes — fill in what you can infer without asking
3. Before each action, call report_wizard_progress with a brief description of what you are doing
4. Create specific, measurable objectives (e.g. "Grow Instagram to 5,000 followers in 90 days") and call set_objective_autonomous to enable each one immediately
5. When all brand fields are configured and at least 2-3 autonomous objectives are created, call complete_launch with a summary

Keep questions short and conversational. Never ask about something you can reasonably infer from the description and primary goal. Fill first, ask only when you genuinely need the user's input.
```

2. Run `_agent_loop(_broadcast_fn, product_id, messages, session_id=session_id)` — the agent runs until it calls `complete_launch`

3. If an exception occurs: call `set_launch_wizard_active(product_id, False)` to avoid leaving the wizard stuck; broadcast error.

**In-flight guard:** Use `_running_objectives` pattern — a module-level `_running_wizards: dict[str, bool]` keyed by `product_id`.

### WebSocket trigger

New `launch_product` WS message handler in `backend/main.py`:

```json
{ "type": "launch_product", "name": "...", "description": "...", "primary_goal": "..." }
```

Handler:
1. Generate a slug ID from the name (lowercase, hyphens)
2. Call `create_product(id, name, icon_label, color)` with a default icon/color
3. Call `set_launch_wizard_active(product_id, True)`
4. Create a dedicated session: `create_session("Launch: {name}", product_id)`
5. Broadcast `product_data` so frontend switches to the new product in wizard mode
6. `asyncio.create_task(_run_launch_wizard(product_id, session_id, description, primary_goal))`

---

## Section 4: Frontend

### New component: `LaunchFormModal.tsx`

Triggered by a "+" button at the bottom of the product rail. A minimal modal with three fields:
- Product name (text input)
- One-line description (text input)
- Primary goal (text input, e.g. "Grow to 10,000 Instagram followers")

Submit sends `launch_product` WS message and closes the modal. The product rail immediately shows the new product (from the `product_data` broadcast) and the app switches to it.

### New component: `LaunchWizardPanel.tsx`

Shown in the center column when `activeState.product.launch_wizard_active === 1`, replacing the normal chat/overview layout.

**Layout: split panel**

```
┌─────────────────────────────────┬──────────────────────────┐
│  Agent Chat                     │  Launch Progress         │
│                                 │                          │
│  [agent messages + user input]  │  ✓ Product created       │
│                                 │  ✓ Brand voice           │
│                                 │  ○ Target audience       │
│                                 │  ○ Social handles        │
│                                 │  ○ Objectives (2)        │
│                                 │  ○ Autonomous mode       │
│                                 │                          │
│                                 │  Configuring brand       │
│                                 │  voice...  ●●●           │
└─────────────────────────────────┴──────────────────────────┘
```

**Progress checklist items** (derived from product state, no extra tracking):
- "Product created" — always ✓ once wizard starts
- "Brand voice" — ✓ when `product.brand_voice` is non-null
- "Target audience" — ✓ when `product.target_audience` is non-null
- "Social handles" — ✓ when `product.social_handles` is non-null/non-empty
- "Objectives (N)" — shows count; ✓ when count ≥ 1
- "Autonomous mode" — ✓ when any objective has `autonomous === 1`

**Activity indicator** (bottom of right panel):
- Driven by `wizard_progress` WebSocket events
- Shows current `message` + animated dots (CSS animation, three dots cycling)
- Clears when `launch_complete` event received

**Transition on completion:**
- `launch_complete` event received → right panel shows "Launch complete" for 1.5s
- Then `launch_wizard_active` flips to 0 in the product data broadcast → normal view renders

### `App.tsx` changes

- Add "+" button to product rail (bottom, below existing product icons)
- Add `launchFormOpen` state; clicking "+" sets it true
- `LaunchFormModal` shown when `launchFormOpen === true`
- `LaunchWizardPanel` shown in center column when `activeState?.product?.launch_wizard_active === 1`
- Handle new `wizard_progress` WS event: store `{ product_id, message }` in state
- Handle `launch_complete` WS event: trigger the brief completion animation

### `types.ts` changes

Add to `Product` interface:
```typescript
launch_wizard_active: number  // 0 | 1
```

---

## Section 5: Error Handling

- **Agent loop exception** → `set_launch_wizard_active(product_id, False)`; broadcast error message to chat; product remains but wizard exits cleanly
- **Duplicate launch attempt** → `_running_wizards` guard returns early if wizard already in flight
- **User navigates away mid-wizard** → wizard continues running in background; switching back to the product shows wizard still in progress
- **Agent never calls `complete_launch`** → the loop ends when `_agent_loop` returns; if `launch_wizard_active` is still 1, a safety check clears it after the loop exits

---

## Section 6: Testing

- `test_set_launch_wizard_active`: flag toggles correctly
- `test_launch_product_ws_handler`: WS message creates product, sets flag, returns product_data broadcast
- `test_report_wizard_progress_tool`: tool broadcasts wizard_progress event
- `test_complete_launch_tool`: tool clears flag, broadcasts launch_complete
- `test_launch_wizard_stuck_guard`: exception in agent loop clears the flag (no stuck wizard)
- Frontend: TypeScript build passes with new fields and components
