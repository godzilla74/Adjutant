# Token Usage Logging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Capture per-call token counts into a DB table, expose them via a `GET /api/token-usage` endpoint, and show them in a Settings "Usage" tab.

**Architecture:** Four sequential tasks: (1) DB layer with schema + helpers, (2) instrumentation in `backend/main.py` and `core/prescreener.py`, (3) API endpoint in `backend/api.py`, (4) UI component `TokenUsageSettings.tsx` wired into `SettingsPage.tsx`. Provider-agnostic from the start via a `_normalize_usage()` helper so OpenAI can be plugged in later.

**Tech Stack:** Python (SQLite, FastAPI), React (TypeScript, Tailwind)

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `backend/db.py` | Modify | Add `token_usage` table to schema; add `_normalize_usage`, `record_token_usage`, `get_token_usage_summary` |
| `core/prescreener.py` | Modify | Add `usage` field to `PrescreerResult`; populate from API response |
| `backend/main.py` | Modify | Call `record_token_usage` after agent loop, compaction, and prescreener calls |
| `backend/api.py` | Modify | Add `GET /api/token-usage` endpoint |
| `ui/src/api.ts` | Modify | Add `getTokenUsage(pw, days)` |
| `ui/src/components/settings/TokenUsageSettings.tsx` | Create | Usage section — period toggle + totals + breakdown table |
| `ui/src/components/SettingsPage.tsx` | Modify | Add `'usage'` tab, import + render `TokenUsageSettings` |
| `tests/test_token_usage.py` | Create | DB helpers, normalization, and API endpoint tests |

---

### Task 1: DB layer — schema, record, and query helpers

**Files:**
- Modify: `backend/db.py`
- Create: `tests/test_token_usage.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_token_usage.py`:

```python
"""Tests for token usage DB helpers."""
import importlib
import pytest


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_DB", str(tmp_path / "test.db"))
    import backend.db as db_mod
    importlib.reload(db_mod)
    db_mod.init_db()
    return db_mod


def test_record_token_usage_inserts_row(db):
    class FakeUsage:
        input_tokens = 100
        output_tokens = 50
        cache_read_input_tokens = 20
        cache_creation_input_tokens = 5

    db.record_token_usage("prod-1", "agent", "anthropic", "claude-sonnet-4-6", FakeUsage())
    summary = db.get_token_usage_summary(days=30)
    assert summary["totals"]["input_tokens"] == 100
    assert summary["totals"]["output_tokens"] == 50
    assert summary["totals"]["cache_read_tokens"] == 20
    assert summary["totals"]["cache_creation_tokens"] == 5


def test_normalize_usage_anthropic(db):
    class FakeUsage:
        input_tokens = 200
        output_tokens = 80
        cache_read_input_tokens = 150
        cache_creation_input_tokens = 10

    result = db._normalize_usage("anthropic", FakeUsage())
    assert result == {
        "input_tokens": 200,
        "output_tokens": 80,
        "cache_read_tokens": 150,
        "cache_creation_tokens": 10,
    }


def test_normalize_usage_openai(db):
    class Details:
        cached_tokens = 60

    class FakeUsage:
        prompt_tokens = 300
        completion_tokens = 90
        prompt_tokens_details = Details()

    result = db._normalize_usage("openai", FakeUsage())
    assert result == {
        "input_tokens": 300,
        "output_tokens": 90,
        "cache_read_tokens": 60,
        "cache_creation_tokens": 0,
    }


def test_normalize_usage_openai_no_details(db):
    class FakeUsage:
        prompt_tokens = 300
        completion_tokens = 90
        prompt_tokens_details = None

    result = db._normalize_usage("openai", FakeUsage())
    assert result["cache_read_tokens"] == 0


def test_get_token_usage_summary_by_call_type(db):
    class U:
        def __init__(self, i, o):
            self.input_tokens = i
            self.output_tokens = o
            self.cache_read_input_tokens = 0
            self.cache_creation_input_tokens = 0

    db.record_token_usage("p1", "agent",       "anthropic", "claude-sonnet-4-6", U(500, 200))
    db.record_token_usage("p1", "prescreener", "anthropic", "claude-haiku-4-5-20251001", U(100, 10))
    db.record_token_usage("p1", "compaction",  "anthropic", "claude-haiku-4-5-20251001", U(300, 50))

    summary = db.get_token_usage_summary(days=30)
    assert summary["by_call_type"]["agent"]["input_tokens"] == 500
    assert summary["by_call_type"]["prescreener"]["input_tokens"] == 100
    assert summary["by_call_type"]["compaction"]["input_tokens"] == 300
    assert summary["totals"]["input_tokens"] == 900


def test_record_token_usage_survives_exception(db):
    # Passing None as usage — should not raise
    db.record_token_usage("p1", "agent", "anthropic", "claude-sonnet-4-6", None)


def test_get_token_usage_summary_empty(db):
    summary = db.get_token_usage_summary(days=30)
    assert summary["totals"]["input_tokens"] == 0
    assert summary["by_call_type"] == {}
    assert summary["by_day"] == []
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd /home/justin/Code/Adjutant
.venv/bin/python -m pytest tests/test_token_usage.py -v 2>&1 | tail -15
```

Expected: all tests FAIL with `AttributeError` or `ImportError` — `record_token_usage` not defined yet.

- [ ] **Step 3: Add `token_usage` table to `init_db()` in `backend/db.py`**

Inside `init_db()`, find the `conn.executescript("""` block. Add this table at the end of the script, before the closing `""")`:

```sql
CREATE TABLE IF NOT EXISTS token_usage (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id            TEXT,
    call_type             TEXT    NOT NULL,
    provider              TEXT    NOT NULL DEFAULT 'anthropic',
    model                 TEXT    NOT NULL,
    input_tokens          INTEGER NOT NULL DEFAULT 0,
    output_tokens         INTEGER NOT NULL DEFAULT 0,
    cache_read_tokens     INTEGER NOT NULL DEFAULT 0,
    cache_creation_tokens INTEGER NOT NULL DEFAULT 0,
    created_at            TEXT    NOT NULL DEFAULT (datetime('now'))
);
```

- [ ] **Step 4: Add `_normalize_usage`, `record_token_usage`, and `get_token_usage_summary` to `backend/db.py`**

Add these three functions near the end of `backend/db.py` (after the `agent_config` helpers):

```python
# ── Token usage tracking ──────────────────────────────────────────────────────

def _normalize_usage(provider: str, usage) -> dict:
    """Translate provider-specific usage object into a common field dict."""
    try:
        if provider == "anthropic":
            return {
                "input_tokens":          getattr(usage, "input_tokens", 0) or 0,
                "output_tokens":         getattr(usage, "output_tokens", 0) or 0,
                "cache_read_tokens":     getattr(usage, "cache_read_input_tokens", 0) or 0,
                "cache_creation_tokens": getattr(usage, "cache_creation_input_tokens", 0) or 0,
            }
        if provider == "openai":
            details = getattr(usage, "prompt_tokens_details", None)
            cached = 0
            if details is not None:
                cached = getattr(details, "cached_tokens", None)
                if cached is None:
                    cached = details.get("cached_tokens", 0) if isinstance(details, dict) else 0
                cached = cached or 0
            return {
                "input_tokens":          getattr(usage, "prompt_tokens", 0) or 0,
                "output_tokens":         getattr(usage, "completion_tokens", 0) or 0,
                "cache_read_tokens":     cached,
                "cache_creation_tokens": 0,
            }
    except Exception:
        pass
    return {"input_tokens": 0, "output_tokens": 0, "cache_read_tokens": 0, "cache_creation_tokens": 0}


def record_token_usage(
    product_id: str | None,
    call_type: str,
    provider: str,
    model: str,
    usage,
) -> None:
    """Normalise and insert one usage row. Never raises — a failed write must not break an agent turn."""
    try:
        fields = _normalize_usage(provider, usage)
        with _conn() as conn:
            conn.execute(
                """INSERT INTO token_usage
                   (product_id, call_type, provider, model,
                    input_tokens, output_tokens, cache_read_tokens, cache_creation_tokens)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (product_id, call_type, provider, model,
                 fields["input_tokens"], fields["output_tokens"],
                 fields["cache_read_tokens"], fields["cache_creation_tokens"]),
            )
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("record_token_usage failed: %s", exc)


def get_token_usage_summary(days: int = 30) -> dict:
    """Return aggregated token usage totals, by-call-type breakdown, and daily series."""
    period = f"-{days} days"
    with _conn() as conn:
        type_rows = conn.execute(
            """SELECT call_type,
                      SUM(input_tokens)          AS input_tokens,
                      SUM(output_tokens)         AS output_tokens,
                      SUM(cache_read_tokens)     AS cache_read_tokens,
                      SUM(cache_creation_tokens) AS cache_creation_tokens
               FROM token_usage
               WHERE created_at >= datetime('now', ?)
               GROUP BY call_type""",
            (period,),
        ).fetchall()

        day_rows = conn.execute(
            """SELECT DATE(created_at)           AS date,
                      SUM(input_tokens)          AS input_tokens,
                      SUM(output_tokens)         AS output_tokens,
                      SUM(cache_read_tokens)     AS cache_read_tokens,
                      SUM(cache_creation_tokens) AS cache_creation_tokens
               FROM token_usage
               WHERE created_at >= datetime('now', ?)
               GROUP BY DATE(created_at)
               ORDER BY date""",
            (period,),
        ).fetchall()

    by_call_type = {
        r["call_type"]: {
            "input_tokens":          r["input_tokens"] or 0,
            "output_tokens":         r["output_tokens"] or 0,
            "cache_read_tokens":     r["cache_read_tokens"] or 0,
            "cache_creation_tokens": r["cache_creation_tokens"] or 0,
        }
        for r in type_rows
    }

    totals = {
        "input_tokens":          sum(v["input_tokens"]          for v in by_call_type.values()),
        "output_tokens":         sum(v["output_tokens"]         for v in by_call_type.values()),
        "cache_read_tokens":     sum(v["cache_read_tokens"]     for v in by_call_type.values()),
        "cache_creation_tokens": sum(v["cache_creation_tokens"] for v in by_call_type.values()),
    }

    by_day = [
        {
            "date":                  r["date"],
            "input_tokens":          r["input_tokens"] or 0,
            "output_tokens":         r["output_tokens"] or 0,
            "cache_read_tokens":     r["cache_read_tokens"] or 0,
            "cache_creation_tokens": r["cache_creation_tokens"] or 0,
        }
        for r in day_rows
    ]

    return {"period_days": days, "totals": totals, "by_call_type": by_call_type, "by_day": by_day}
```

- [ ] **Step 5: Run the tests to verify they pass**

```bash
.venv/bin/python -m pytest tests/test_token_usage.py -v
```

Expected: all 7 tests PASS.

- [ ] **Step 6: Run full suite for regressions**

```bash
.venv/bin/python -m pytest tests/ -q 2>&1 | tail -5
```

Expected: 4 pre-existing failures in `test_openai_oauth.py`, everything else passes.

- [ ] **Step 7: Commit**

```bash
git add backend/db.py tests/test_token_usage.py
git commit -m "feat: add token_usage table and record/query helpers"
```

---

### Task 2: Instrumentation — wire `record_token_usage` into agent loop, compaction, and prescreener

**Files:**
- Modify: `core/prescreener.py` (add `usage` field to `PrescreerResult`)
- Modify: `backend/main.py` (3 call sites)

- [ ] **Step 1: Add `usage` field to `PrescreerResult` in `core/prescreener.py`**

The `PrescreerResult` dataclass is at the top of `core/prescreener.py`. Add a `usage` field with default `None`:

```python
@dataclass
class PrescreerResult:
    """Routing decision from the prescreener: respond directly or delegate to Sonnet."""
    route: Literal["haiku", "sonnet"]
    tool_groups: list[str] = field(default_factory=list)
    response: str | None = None
    usage: object | None = None
```

- [ ] **Step 2: Populate `usage` from the API response in `prescreen()`**

In `core/prescreener.py`, inside the `prescreen()` function, find where `PrescreerResult` objects are constructed and returned. Attach `usage=response.usage` to each successful result (not the fallback). The function already catches exceptions and returns `_fallback()` for those — the fallback keeps `usage=None`.

Find the two `return PrescreerResult(...)` lines inside the `try` block (the haiku and sonnet paths) and add `usage=response.usage` to each:

```python
        # haiku path
        return PrescreerResult(route="haiku", response=response, usage=response.usage)

        # sonnet path
        return PrescreerResult(route="sonnet", tool_groups=merged, usage=response.usage)
```

The variable `response` is the raw Anthropic `Message` object returned by `messages.create()`. Its `.usage` attribute is the Anthropic usage object.

- [ ] **Step 3: Verify prescreener tests still pass**

```bash
cd /home/justin/Code/Adjutant
.venv/bin/python -m pytest tests/test_prescreener.py -v
```

Expected: all tests PASS (the new `usage` field has a default, so existing tests are unaffected).

- [ ] **Step 4: Wire `record_token_usage` into `backend/main.py`**

At the top of `backend/main.py`, add the import near the other `backend.db` imports:

```python
from backend.db import record_token_usage as _record_token_usage
```

**Site 1 — Prescreener** (around line 828, after `_pre = await _prescreen(...)`):

```python
            _pre = await _prescreen(_last_user_msg_for_prescreener, _available_groups, client, _prescreener_model)
            _record_token_usage(product_id, "prescreener", "anthropic", _prescreener_model, _pre.usage)
```

**Site 2 — Agent loop** (around line 881, after `final = await _run_stream(_stream_kwargs)`):

```python
        try:
            final = await _run_stream(_stream_kwargs)
            _record_token_usage(product_id, "agent", "anthropic", _agent_model, final.usage)
        except anthropic.BadRequestError as e:
            if _remote_mcp and "mcp" in str(e).lower():
                ...
                final = await _run_stream(fallback)
                _record_token_usage(product_id, "agent", "anthropic", _agent_model, final.usage)
            else:
                raise
```

**Site 3 — Compaction** (around line 741, after `new_summary = resp.content[0].text.strip()`):

```python
    new_summary = resp.content[0].text.strip()
    _record_token_usage(product_id, "compaction", "anthropic", "claude-haiku-4-5-20251001", resp.usage)
```

- [ ] **Step 5: Run full suite for regressions**

```bash
.venv/bin/python -m pytest tests/ -q 2>&1 | tail -5
```

Expected: 4 pre-existing failures in `test_openai_oauth.py`, everything else passes.

- [ ] **Step 6: Commit**

```bash
git add core/prescreener.py backend/main.py
git commit -m "feat: instrument agent loop, compaction, and prescreener with token usage recording"
```

---

### Task 3: API endpoint

**Files:**
- Modify: `backend/api.py`
- Modify: `tests/test_token_usage.py`

- [ ] **Step 1: Write a failing API test**

Add to `tests/test_token_usage.py`:

```python
import importlib


@pytest.fixture
def api_client(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_DB", str(tmp_path / "test.db"))
    monkeypatch.setenv("AGENT_PASSWORD", "testpw")
    import backend.db as db_mod
    importlib.reload(db_mod)
    db_mod.init_db()

    import backend.api as api_mod
    importlib.reload(api_mod)
    from fastapi.testclient import TestClient
    from backend.server import app
    return TestClient(app)


def test_token_usage_endpoint_returns_summary(api_client):
    resp = api_client.get(
        "/api/token-usage?days=30",
        headers={"X-Agent-Password": "testpw"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "totals" in body
    assert "by_call_type" in body
    assert "by_day" in body
    assert body["period_days"] == 30
    assert body["totals"]["input_tokens"] == 0


def test_token_usage_endpoint_requires_auth(api_client):
    resp = api_client.get("/api/token-usage")
    assert resp.status_code == 401
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd /home/justin/Code/Adjutant
.venv/bin/python -m pytest tests/test_token_usage.py::test_token_usage_endpoint_returns_summary tests/test_token_usage.py::test_token_usage_endpoint_requires_auth -v
```

Expected: FAIL — `/api/token-usage` route not found (404).

- [ ] **Step 3: Add the endpoint to `backend/api.py`**

Find the existing endpoint pattern in `backend/api.py` (e.g. the `get_agent_config` endpoint around line 104). Add this new endpoint nearby:

```python
@router.get("/token-usage")
def get_token_usage_endpoint(days: int = 30, _=Depends(_auth)):
    from backend.db import get_token_usage_summary
    days = max(1, min(365, days))
    return get_token_usage_summary(days)
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
.venv/bin/python -m pytest tests/test_token_usage.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Run full suite for regressions**

```bash
.venv/bin/python -m pytest tests/ -q 2>&1 | tail -5
```

Expected: 4 pre-existing failures in `test_openai_oauth.py`, everything else passes.

- [ ] **Step 6: Commit**

```bash
git add backend/api.py tests/test_token_usage.py
git commit -m "feat: add GET /api/token-usage endpoint"
```

---

### Task 4: UI — TokenUsageSettings component and Settings tab

**Files:**
- Modify: `ui/src/api.ts`
- Create: `ui/src/components/settings/TokenUsageSettings.tsx`
- Modify: `ui/src/components/SettingsPage.tsx`

No backend tests for this task — verify by running the UI dev server and checking the new tab renders correctly.

- [ ] **Step 1: Add `getTokenUsage` to `ui/src/api.ts`**

In `ui/src/api.ts`, add after the `updateAgentConfig` entry:

```typescript
  getTokenUsage: (pw: string, days: number = 30) =>
    apiFetch<{
      period_days: number
      totals: { input_tokens: number; output_tokens: number; cache_read_tokens: number; cache_creation_tokens: number }
      by_call_type: Record<string, { input_tokens: number; output_tokens: number; cache_read_tokens: number; cache_creation_tokens: number }>
      by_day: Array<{ date: string; input_tokens: number; output_tokens: number; cache_read_tokens: number; cache_creation_tokens: number }>
    }>(`/api/token-usage?days=${days}`, pw),
```

- [ ] **Step 2: Create `ui/src/components/settings/TokenUsageSettings.tsx`**

```tsx
import { useEffect, useState } from 'react'
import { api } from '../../api'

interface UsageSummary {
  period_days: number
  totals: {
    input_tokens: number
    output_tokens: number
    cache_read_tokens: number
    cache_creation_tokens: number
  }
  by_call_type: Record<string, {
    input_tokens: number
    output_tokens: number
    cache_read_tokens: number
    cache_creation_tokens: number
  }>
  by_day: Array<{
    date: string
    input_tokens: number
    output_tokens: number
    cache_read_tokens: number
    cache_creation_tokens: number
  }>
}

interface Props {
  password: string
}

const PERIODS = [7, 30, 90] as const
type Period = (typeof PERIODS)[number]

const CALL_TYPES = ['agent', 'compaction', 'prescreener'] as const

function fmt(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return String(n)
}

export default function TokenUsageSettings({ password }: Props) {
  const [period, setPeriod] = useState<Period>(30)
  const [data, setData] = useState<UsageSummary | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    api.getTokenUsage(password, period)
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [password, period])

  const totalInput = data?.totals.input_tokens ?? 0
  const totalCacheRead = data?.totals.cache_read_tokens ?? 0
  const cacheHitRate = totalInput + totalCacheRead > 0
    ? (totalCacheRead / (totalInput + totalCacheRead)) * 100
    : 0

  const labelCls = 'block text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-1.5'

  return (
    <div className="w-full">
      <h2 className="text-base font-bold text-adj-text-primary mb-1">Usage</h2>
      <p className="text-xs text-adj-text-muted mb-6">Token consumption by the agent and its helpers</p>

      {/* Period selector */}
      <div className="flex gap-2 mb-6">
        {PERIODS.map(p => (
          <button
            key={p}
            onClick={() => setPeriod(p)}
            className={`px-3 py-1.5 rounded text-xs font-semibold transition-colors ${
              period === p
                ? 'bg-adj-accent text-white'
                : 'bg-adj-panel border border-adj-border text-adj-text-muted hover:text-adj-text-secondary'
            }`}
          >
            {p}d
          </button>
        ))}
      </div>

      {loading && <p className="text-adj-text-muted text-sm">Loading…</p>}

      {!loading && data && (
        <div className="flex flex-col gap-6">
          {/* Summary cards */}
          <div className="grid grid-cols-3 gap-3">
            <div className="bg-adj-panel border border-adj-border rounded-lg p-3">
              <div className="text-[10px] uppercase tracking-wider text-adj-text-muted mb-1">Input tokens</div>
              <div className="text-lg font-bold text-adj-text-primary">{fmt(data.totals.input_tokens)}</div>
            </div>
            <div className="bg-adj-panel border border-adj-border rounded-lg p-3">
              <div className="text-[10px] uppercase tracking-wider text-adj-text-muted mb-1">Output tokens</div>
              <div className="text-lg font-bold text-adj-text-primary">{fmt(data.totals.output_tokens)}</div>
            </div>
            <div className="bg-adj-panel border border-adj-border rounded-lg p-3">
              <div className="text-[10px] uppercase tracking-wider text-adj-text-muted mb-1">Cache hit rate</div>
              <div className="text-lg font-bold text-adj-text-primary">{cacheHitRate.toFixed(1)}%</div>
            </div>
          </div>

          {/* Breakdown by call type */}
          <div>
            <div className={labelCls}>By call type</div>
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="text-[10px] uppercase tracking-wider text-adj-text-muted">
                  <th className="text-left py-1.5 pr-4 font-semibold">Type</th>
                  <th className="text-right py-1.5 px-2 font-semibold">Input</th>
                  <th className="text-right py-1.5 px-2 font-semibold">Output</th>
                  <th className="text-right py-1.5 pl-2 font-semibold">Cached</th>
                </tr>
              </thead>
              <tbody>
                {CALL_TYPES.map(ct => {
                  const row = data.by_call_type[ct] ?? {
                    input_tokens: 0, output_tokens: 0, cache_read_tokens: 0, cache_creation_tokens: 0,
                  }
                  return (
                    <tr key={ct} className="border-t border-adj-border/50">
                      <td className="py-2 pr-4 capitalize text-adj-text-primary">{ct}</td>
                      <td className="py-2 px-2 text-right tabular-nums text-adj-text-secondary">{fmt(row.input_tokens)}</td>
                      <td className="py-2 px-2 text-right tabular-nums text-adj-text-secondary">{fmt(row.output_tokens)}</td>
                      <td className="py-2 pl-2 text-right tabular-nums text-adj-text-secondary">{fmt(row.cache_read_tokens)}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 3: Wire into `ui/src/components/SettingsPage.tsx`**

**3a.** Add `'usage'` to the `Tab` type (line 17):

```typescript
export type Tab =
  | 'overview' | 'workstreams' | 'objectives' | 'autonomy'
  | 'connections' | 'social' | 'product-mcp'
  | 'agent-model' | 'google-oauth' | 'remote-access' | 'mcp' | 'image-generation'
  | 'usage'
```

**3b.** Add import at the top (alongside other settings imports):

```typescript
import TokenUsageSettings from './settings/TokenUsageSettings'
```

**3c.** Add to `GLOBAL_TABS` array (around line 48):

```typescript
const GLOBAL_TABS: { key: Tab; label: string; icon: string }[] = [
  { key: 'agent-model',       label: 'Agent Model',       icon: '🤖' },
  { key: 'google-oauth',      label: 'Google OAuth',      icon: '🔑' },
  { key: 'remote-access',     label: 'Remote Access',     icon: '📡' },
  { key: 'mcp',               label: 'MCP Servers',       icon: '⚡' },
  { key: 'image-generation',  label: 'Image Generation',  icon: '🖼' },
  { key: 'usage',             label: 'Usage',             icon: '📊' },
]
```

**3d.** Add case to `renderContent()` switch (around line 103):

```typescript
      case 'image-generation': return <ImageGenerationSettings {...common} />
      case 'usage':            return <TokenUsageSettings {...common} />
```

- [ ] **Step 4: Build the UI to check for TypeScript errors**

```bash
cd /home/justin/Code/Adjutant/ui
npm run build 2>&1 | tail -20
```

Expected: build succeeds with no TypeScript errors.

- [ ] **Step 5: Commit**

```bash
cd /home/justin/Code/Adjutant
git add ui/src/api.ts ui/src/components/settings/TokenUsageSettings.tsx ui/src/components/SettingsPage.tsx
git commit -m "feat: add Usage settings tab with token consumption breakdown"
```

---

## Self-Review

### Spec coverage

- ✅ `token_usage` table with provider-agnostic columns — Task 1 Step 3
- ✅ `_normalize_usage()` for Anthropic and OpenAI — Task 1 Step 4
- ✅ `record_token_usage()` fire-and-forget (catches exceptions) — Task 1 Step 4
- ✅ `get_token_usage_summary()` with totals, by_call_type, by_day — Task 1 Step 4
- ✅ `usage` field on `PrescreerResult` — Task 2 Step 1
- ✅ Instrumentation at agent loop, compaction, and prescreener — Task 2 Steps 2 + 4
- ✅ `GET /api/token-usage?days=N` endpoint with auth — Task 3 Step 3
- ✅ `getTokenUsage` in `ui/src/api.ts` — Task 4 Step 1
- ✅ `TokenUsageSettings` component with period toggle, totals, cache hit rate, breakdown table — Task 4 Step 2
- ✅ 'usage' tab in `SettingsPage.tsx` — Task 4 Step 3

### Placeholder scan

None.

### Type consistency

- `record_token_usage(product_id, call_type, provider, model, usage)` — called identically at all 3 sites in Task 2
- `get_token_usage_summary(days)` → `{period_days, totals, by_call_type, by_day}` — matches `apiFetch` type in `api.ts` and `UsageSummary` interface in component
- `PrescreerResult.usage: object | None = None` — set in Task 2 Step 1, read in Task 2 Step 4
