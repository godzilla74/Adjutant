# Token Usage Logging Design

**Date:** 2026-04-27
**Goal:** Capture per-call Anthropic (and future OpenAI) token counts into a DB table, expose them via a backend API endpoint, and surface them in a Settings UI "Usage" section.

---

## Background

Every Anthropic API call returns a `usage` object with `input_tokens`, `output_tokens`, `cache_read_input_tokens`, and `cache_creation_input_tokens`. This data is currently discarded. Without it, there is no way to measure the actual savings from the caching, tool pruning, and description trimming work already shipped.

Three call sites in `backend/main.py` make API calls:

1. **Main agent loop** (`_run_stream`) — the primary Sonnet call per user turn
2. **Compaction** — a Haiku call to summarise conversation history when it grows long
3. **Prescreener** — a Haiku call to route each message before Sonnet runs

A fourth site (workspace bootstrap) is a one-time setup call and is excluded.

---

## Data Model

### New table: `token_usage`

```sql
CREATE TABLE IF NOT EXISTS token_usage (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id           TEXT,
    call_type            TEXT    NOT NULL,
    provider             TEXT    NOT NULL DEFAULT 'anthropic',
    model                TEXT    NOT NULL,
    input_tokens         INTEGER NOT NULL DEFAULT 0,
    output_tokens        INTEGER NOT NULL DEFAULT 0,
    cache_read_tokens    INTEGER NOT NULL DEFAULT 0,
    cache_creation_tokens INTEGER NOT NULL DEFAULT 0,
    created_at           TEXT    NOT NULL DEFAULT (datetime('now'))
);
```

- `product_id`: NULL for the global agent
- `call_type`: one of `"agent"`, `"compaction"`, `"prescreener"`
- `provider`: `"anthropic"` now; `"openai"` when that feature ships

### Provider normalisation

A helper `_normalize_usage(provider: str, usage) -> dict` translates each SDK's response shape into the common schema:

| Field | Anthropic | OpenAI |
|-------|-----------|--------|
| `input_tokens` | `usage.input_tokens` | `usage.prompt_tokens` |
| `output_tokens` | `usage.output_tokens` | `usage.completion_tokens` |
| `cache_read_tokens` | `usage.cache_read_input_tokens` | `usage.prompt_tokens_details.cached_tokens` (or 0) |
| `cache_creation_tokens` | `usage.cache_creation_input_tokens` | 0 |

This normalisation lives in `backend/db.py` alongside the write helper, so the agent loop never knows which provider it is talking to.

---

## DB Layer (`backend/db.py`)

Two new functions:

```python
def _normalize_usage(provider: str, usage) -> dict:
    """Translate provider-specific usage object into common field dict."""

def record_token_usage(
    product_id: str | None,
    call_type: str,
    provider: str,
    model: str,
    usage,
) -> None:
    """Normalise and insert one row into token_usage."""
```

`record_token_usage` is synchronous (same as all other DB helpers). It catches and logs any exception rather than propagating — a failed usage write must never break an agent turn.

A read helper:

```python
def get_token_usage_summary(days: int = 30) -> dict:
```

Returns:
```json
{
  "period_days": 30,
  "totals": {
    "input_tokens": 0,
    "output_tokens": 0,
    "cache_read_tokens": 0,
    "cache_creation_tokens": 0
  },
  "by_call_type": {
    "agent":       { "input_tokens": 0, "output_tokens": 0, "cache_read_tokens": 0, "cache_creation_tokens": 0 },
    "compaction":  { "input_tokens": 0, "output_tokens": 0, "cache_read_tokens": 0, "cache_creation_tokens": 0 },
    "prescreener": { "input_tokens": 0, "output_tokens": 0, "cache_read_tokens": 0, "cache_creation_tokens": 0 }
  },
  "by_day": [
    { "date": "2026-04-27", "input_tokens": 0, "output_tokens": 0, "cache_read_tokens": 0, "cache_creation_tokens": 0 }
  ]
}
```

---

## Instrumentation (`backend/main.py`)

After each API call, call `record_token_usage` with the response's usage object. Three sites:

1. **Agent loop** — after `final = await _run_stream(...)`, call `record_token_usage(product_id, "agent", "anthropic", model, final.usage)`
2. **Compaction** — after `resp = await client.messages.create(...)`, call `record_token_usage(product_id, "compaction", "anthropic", model, resp.usage)`
3. **Prescreener** — after the prescreener's `messages.create(...)` call in `core/prescreener.py`, return `response.usage` alongside the result so `_agent_loop` can record it

For the prescreener, the cleanest approach is to have `prescreen()` return the usage object as an optional field on `PrescreerResult` (or as a side-channel), and record it in `_agent_loop` immediately after the prescreener call.

`record_token_usage` is fire-and-forget in the sense that it never raises — wrapped in try/except internally.

---

## API Endpoint (`backend/api.py`)

```
GET /api/token-usage?days=30
```

- `days`: integer, default 30, max 365
- Returns: the dict from `get_token_usage_summary(days)`
- Auth: password header (same as all other API endpoints)

---

## Settings UI

New collapsible "Usage" section in the Settings sidebar, implemented as a new `ui/src/components/settings/TokenUsageSettings.tsx` component and mounted from the Settings entry point alongside the existing model settings.

Period selector: **7d / 30d / 90d** toggle.

Displays:
- **Input tokens** (total for period)
- **Output tokens** (total for period)
- **Cache hit rate**: `cache_read_tokens / (input_tokens + cache_read_tokens)` as a percentage
- **Breakdown table**: agent / compaction / prescreener rows, each showing input + output + cached

No cost estimate — token prices vary by model and provider.

---

## Files Changed

| File | Change |
|------|--------|
| `backend/db.py` | Add `token_usage` table to schema; add `_normalize_usage`, `record_token_usage`, `get_token_usage_summary` |
| `backend/main.py` | Call `record_token_usage` after agent loop, compaction, and prescreener calls |
| `core/prescreener.py` | Add `usage` field to `PrescreerResult`; populate from API response |
| `backend/api.py` | Add `GET /api/token-usage` endpoint |
| `ui/src/api.ts` | Add `getTokenUsage(password, days)` API call |
| `ui/src/components/settings/TokenUsageSettings.tsx` | New component — Usage section with period toggle and breakdown |
| `ui/src/components/settings/AgentModelSettings.tsx` | Mount `TokenUsageSettings` below existing model fields (or new settings entry point) |

---

## Testing

- **Unit:** `test_record_token_usage` — inserts a row, reads it back, verifies field values
- **Unit:** `test_normalize_usage_anthropic` — verifies Anthropic usage object maps correctly
- **Unit:** `test_normalize_usage_openai` — verifies OpenAI usage dict maps correctly
- **Unit:** `test_get_token_usage_summary` — inserts rows across multiple days/call_types, verifies aggregation
- **Unit:** `test_record_token_usage_survives_db_error` — verify function does not raise on DB failure
- **API:** `test_token_usage_endpoint` — mock `get_token_usage_summary`, verify endpoint returns correct shape
- **Regression:** Full test suite passes

---

## Non-Goals

- Cost estimation (deferred — requires per-model pricing table)
- Per-product breakdown in the UI (global totals only for now)
- Retention policy / pruning of old rows (deferred)
- Real-time streaming of token counts during a turn
