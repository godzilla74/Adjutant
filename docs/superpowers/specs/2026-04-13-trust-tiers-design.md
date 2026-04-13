# Trust Tiers — Design Spec

## Goal

Give the user per-product, per-action-type control over how much the agent can do autonomously. Three tiers: **Auto** (fires immediately, no review), **Window** (fires after X minutes unless cancelled — like Gmail undo-send), and **Approve** (current behavior, blocks until explicit approval). A master override per product lets the user set everything at once without configuring individual action types.

## Architecture

Four pieces: a schema extension (new table + columns), backend resolution logic at review-item creation time, a 30-second scheduler poll for expired window items, and a settings UI panel. The existing `review_resolved` broadcast is reused for auto-approved items. No new background processes beyond the poll.

**Tech Stack:** Python/FastAPI backend, SQLite, existing `_agent_loop()`, React frontend, existing WebSocket broadcast pattern.

---

## Section 1: Data Model

### New table: `product_autonomy`

Stores per-action-type tier configuration per product.

| Column | Type | Notes |
|--------|------|-------|
| `product_id` | TEXT | FK → products.id |
| `action_type` | TEXT | `'social_post'` \| `'email'` \| `'agent_review'` |
| `tier` | TEXT | `'auto'` \| `'window'` \| `'approve'` |
| `window_minutes` | INTEGER | NULL when tier != `'window'` |

Primary key: `(product_id, action_type)`.

### `products` table — two new columns

| Column | Type | Default | Purpose |
|--------|------|---------|---------|
| `autonomy_master_tier` | TEXT | NULL | When set, overrides all per-action rows for this product |
| `autonomy_master_window_minutes` | INTEGER | NULL | Window duration when master tier is `'window'` |

### `review_items` table — two new columns

| Column | Type | Default | Purpose |
|--------|------|---------|---------|
| `action_type` | TEXT | NULL | `'social_post'` \| `'email'` \| `'agent_review'` — set at creation |
| `auto_approve_at` | DATETIME | NULL | Set at creation for window-tier items; NULL otherwise |

### Resolution order

At review item creation, resolve tier as follows:

1. If `products.autonomy_master_tier` is non-null → use master tier (overrides everything)
2. Else look up `product_autonomy` for `(product_id, action_type)` → use that row if found
3. Else → default to `'approve'` (current behavior, no change)

### Lifecycle

- **Auto**: review item resolved immediately at creation, never appears in queue
- **Window**: review item created with `auto_approve_at` set; scheduler resolves on expiry; user can cancel before expiry
- **Approve**: review item created with `auto_approve_at = NULL`; blocks until explicit user action

---

## Section 2: New db.py Functions

- `get_autonomy_config(product_id: str, action_type: str) -> tuple[str, int | None]` — returns `(tier, window_minutes)` using resolution order above. Defaults to `('approve', None)`.
- `set_action_autonomy(product_id: str, action_type: str, tier: str, window_minutes: int | None) -> None` — upserts a row in `product_autonomy`.
- `set_master_autonomy(product_id: str, tier: str | None, window_minutes: int | None) -> None` — updates `autonomy_master_tier` + `autonomy_master_window_minutes` on `products`. Pass `tier=None` to clear (falls back to per-action rows).
- `get_product_autonomy_settings(product_id: str) -> dict` — returns `{ master_tier, master_window_minutes, action_overrides: [{action_type, tier, window_minutes}] }` for the settings UI.
- `auto_resolve_expired_reviews() -> list[int]` — finds `review_items` where `status='pending'` AND `auto_approve_at <= now()`, marks them `status='approved'`, returns list of resolved IDs.

---

## Section 3: `create_review_item` Tool Changes

Add `action_type` as a **required** parameter to the `create_review_item` tool definition. Valid values: `'social_post'`, `'email'`, `'agent_review'`. If omitted or invalid, the tool returns an error string; the item is not created; the agent retries with a valid value.

In `_run_one_tool` in `main.py`, after the review item is saved:

1. Call `get_autonomy_config(product_id, action_type)`
2. **Auto**: immediately call `resolve_review_item(id, 'approved')`, broadcast `review_resolved` with `action='auto_approved'`. Do not broadcast `review_item_added`.
3. **Window**: set `auto_approve_at = now() + window_minutes`. Broadcast `review_item_added` with the deadline visible to the frontend.
4. **Approve**: current behavior — broadcast `review_item_added`, block until user resolves.

---

## Section 4: Scheduler Poll

Add a poll loop in `scheduler.py` alongside the existing objective runner:

- Runs every 30 seconds
- Calls `auto_resolve_expired_reviews()`
- For each resolved ID, looks up the review item's `product_id`, broadcasts `review_resolved` with `action='auto_approved'` to all connected clients for that product
- Stateless — safe across restarts; expired items from downtime are resolved on first poll

---

## Section 5: Frontend

### Settings UI — Autonomy Panel

Added to the existing product settings view.

**Master override row** at the top:
- Dropdown: Approve / Window / Auto
- When Window selected: `window_minutes` number input appears inline
- "Clear override" link → sets master to null (falls back to per-action rows)
- When master is set, per-action rows are visually dimmed but still editable (they persist, ignored while master is active)

**Per-action table** below master row:

| Action | Tier | Window |
|--------|------|--------|
| Social posts | [dropdown] | [X min] |
| Emails | [dropdown] | [X min] |
| Agent reviews | [dropdown] | [X min] |

### Review Queue — Window-Tier Items

- Yellow badge with remaining time: "Auto-approving in 4m 32s" (frontend counts down from `auto_approve_at`)
- "Cancel" button → sends `cancel_auto_approve` WS message; clears `auto_approve_at`; item stays pending as approve-tier

### WebSocket Protocol

**Client → server:**

```json
{ "type": "get_autonomy_config", "product_id": "..." }

{ "type": "set_autonomy_config", "product_id": "...", "master_tier": "window" | null, "master_window_minutes": 10 | null, "action_overrides": [{ "action_type": "social_post", "tier": "auto", "window_minutes": null }] }
// action_overrides is a full replacement: handler deletes all existing product_autonomy rows for this product, then inserts the provided rows

{ "type": "cancel_auto_approve", "review_item_id": 123 }
```

**Server → client:**

```json
{ "type": "autonomy_config", "product_id": "...", "master_tier": "window" | null, "master_window_minutes": 10, "action_overrides": [...] }
```

Auto-approved items reuse the existing `review_resolved` broadcast:
```json
{ "type": "review_resolved", "review_item_id": 123, "action": "auto_approved" }
```

### `types.ts` Changes

- Add `action_type?: string` and `auto_approve_at?: string | null` to `ReviewItem`
- Add `autonomy_config` to `ServerMessage` union
- Add `cancel_auto_approve` as a recognized client message type

---

## Section 6: Error Handling & Edge Cases

- **Agent omits `action_type`**: tool returns an error string; item not created; agent retries
- **`cancel_auto_approve` races with scheduler**: scheduler uses `UPDATE ... WHERE status='pending' AND auto_approve_at <= now()`. If cancel clears `auto_approve_at` first, scheduler UPDATE finds nothing — safe no-op. If scheduler wins, cancel handler checks current status and returns a graceful notice.
- **Master tier cleared mid-window**: existing review items with `auto_approve_at` set are unaffected — they still auto-resolve on schedule. Only new items use the updated config.
- **Product deleted with pending window items**: FK cascade on `review_items` handles cleanup. Scheduler finds nothing to resolve.
- **Server restart with overdue window items**: `auto_resolve_expired_reviews()` is stateless. Items that expired during downtime are resolved and broadcast on first poll after restart.

---

## Section 7: Testing

- `test_get_autonomy_config_resolution_order` — master tier overrides action row; action row overrides default; missing config returns `('approve', None)`
- `test_auto_resolve_expired_reviews` — only resolves items past their deadline, not future ones; returns correct IDs
- `test_create_review_item_auto_tier` — auto-tier action resolved immediately, `review_item_added` not broadcast
- `test_create_review_item_window_tier` — `auto_approve_at` set correctly at creation; `review_item_added` broadcast with deadline
- `test_cancel_auto_approve_ws` — clears `auto_approve_at`, item stays pending
- `test_cancel_auto_approve_race` — scheduler resolves first, cancel returns graceful notice
- `test_scheduler_polls_expired_reviews` — scheduler loop broadcasts `review_resolved` with `action='auto_approved'` for expired items
- Frontend: TypeScript build passes with new `action_type`, `auto_approve_at` fields on `ReviewItem` and `autonomy_config` server message type
