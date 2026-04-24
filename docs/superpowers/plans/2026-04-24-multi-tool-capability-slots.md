# Multi-Tool Capability Slots Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow a capability slot to map to multiple MCP tools from the same server, replacing the single-tool dropdown with a checkbox list.

**Architecture:** Migrate `mcp_capability_overrides.mcp_tool_name` (single string) to `mcp_tool_names` (JSON array) via table-recreate. Update DB functions, API model, frontend types, API client, and UI component. Runtime suppress logic is unchanged — it operates on slot built-in tools, not the stored MCP tool names.

**Tech Stack:** SQLite (table-recreate migration), FastAPI + Pydantic, React/TypeScript, Tailwind CSS

---

## Files

- Modify: `backend/db.py` — migration function + update `list_capability_overrides`, `set_capability_override`
- Modify: `backend/api.py:95-98` — update `CapabilityOverrideBody` Pydantic model
- Modify: `ui/src/components/settings/MCPShared.tsx:53-57` — update `CapabilityOverride` type
- Modify: `ui/src/api.ts:225-236` — update `getCapabilityOverrides` return type + `setCapabilityOverride` payload
- Modify: `ui/src/components/settings/ProductMCPSettings.tsx` — replace tool dropdown with checkbox list
- Modify: `tests/test_capability_overrides.py` — update override tests for new schema

---

### Task 1: DB migration + updated DB functions

**Files:**
- Modify: `backend/db.py`
- Modify: `tests/test_capability_overrides.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_capability_overrides.py`:

```python
def test_set_and_list_capability_override_multi_tool(db):
    db.set_capability_override("prod-1", "social_post", "ghl", ["create-post", "edit-post", "get-post"])
    overrides = db.list_capability_overrides("prod-1")
    assert len(overrides) == 1
    assert overrides[0]["capability_slot"] == "social_post"
    assert overrides[0]["mcp_server_name"] == "ghl"
    assert overrides[0]["mcp_tool_names"] == ["create-post", "edit-post", "get-post"]


def test_set_override_single_tool_list(db):
    db.set_capability_override("prod-1", "email_send", "myserver", ["send-email"])
    overrides = db.list_capability_overrides("prod-1")
    assert overrides[0]["mcp_tool_names"] == ["send-email"]


def test_set_override_upsert_replaces_tool_list(db):
    db.set_capability_override("prod-1", "social_post", "server-a", ["tool-a"])
    db.set_capability_override("prod-1", "social_post", "server-b", ["tool-b", "tool-c"])
    overrides = db.list_capability_overrides("prod-1")
    assert len(overrides) == 1
    assert overrides[0]["mcp_server_name"] == "server-b"
    assert overrides[0]["mcp_tool_names"] == ["tool-b", "tool-c"]


def test_capability_override_migration_preserves_existing_rows(db):
    """After migration, existing single-tool rows appear as single-element lists."""
    # Migration already ran at db fixture setup; verify list_capability_overrides
    # returns mcp_tool_names as a list (not a string).
    db.set_capability_override("prod-1", "social_post", "ghl", ["mcp__ghl__social_post"])
    overrides = db.list_capability_overrides("prod-1")
    assert isinstance(overrides[0]["mcp_tool_names"], list)
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd /home/justin/Code/Adjutant
source .venv/bin/activate
pytest tests/test_capability_overrides.py::test_set_and_list_capability_override_multi_tool -v
```

Expected: `FAILED` — `set_capability_override() takes 4 positional arguments but 5 were given` (or similar).

- [ ] **Step 3: Add migration function to `backend/db.py`**

Add after `migrate_extensions_to_db` definition (around line 1735), before `init_db` calls it:

```python
def migrate_capability_overrides_to_tool_names() -> None:
    """Convert mcp_capability_overrides.mcp_tool_name (str) → mcp_tool_names (JSON array).

    Safe to call on already-migrated databases — the column-existence guard exits early.
    """
    with _conn() as conn:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(mcp_capability_overrides)").fetchall()]
        if "mcp_tool_names" in cols:
            return
        conn.executescript("""
            CREATE TABLE mcp_capability_overrides_new (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id      TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
                capability_slot TEXT NOT NULL,
                mcp_server_name TEXT NOT NULL,
                mcp_tool_names  TEXT NOT NULL DEFAULT '[]',
                created_at      TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE(product_id, capability_slot)
            );
            INSERT INTO mcp_capability_overrides_new
                (id, product_id, capability_slot, mcp_server_name, mcp_tool_names, created_at)
            SELECT id, product_id, capability_slot, mcp_server_name,
                   json_array(mcp_tool_name), created_at
            FROM mcp_capability_overrides;
            DROP TABLE mcp_capability_overrides;
            ALTER TABLE mcp_capability_overrides_new RENAME TO mcp_capability_overrides;
        """)
```

- [ ] **Step 4: Call migration in `init_db`**

In `backend/db.py`, find the line `migrate_extensions_to_db()` (around line 340) and add the new call directly after:

```python
    migrate_extensions_to_db()
    migrate_capability_overrides_to_tool_names()
```

- [ ] **Step 5: Update `CREATE TABLE IF NOT EXISTS` for new databases**

In `init_db`'s `executescript`, find the existing `mcp_capability_overrides` table definition (lines 185-193) and replace `mcp_tool_name TEXT NOT NULL` with `mcp_tool_names TEXT NOT NULL DEFAULT '[]'`:

```sql
CREATE TABLE IF NOT EXISTS mcp_capability_overrides (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id      TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    capability_slot TEXT NOT NULL,
    mcp_server_name TEXT NOT NULL,
    mcp_tool_names  TEXT NOT NULL DEFAULT '[]',
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(product_id, capability_slot)
);
```

- [ ] **Step 6: Update `list_capability_overrides` in `backend/db.py`**

Replace the existing function (lines 1869-1875):

```python
def list_capability_overrides(product_id: str) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT capability_slot, mcp_server_name, mcp_tool_names FROM mcp_capability_overrides WHERE product_id = ?",
            (product_id,),
        ).fetchall()
    return [
        {**dict(r), "mcp_tool_names": json.loads(r["mcp_tool_names"])}
        for r in rows
    ]
```

- [ ] **Step 7: Update `set_capability_override` in `backend/db.py`**

Replace the existing function (lines 1878-1887):

```python
def set_capability_override(
    product_id: str, capability_slot: str, mcp_server_name: str, mcp_tool_names: list[str],
) -> None:
    with _conn() as conn:
        conn.execute(
            """INSERT INTO mcp_capability_overrides (product_id, capability_slot, mcp_server_name, mcp_tool_names)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(product_id, capability_slot) DO UPDATE SET
                 mcp_server_name = excluded.mcp_server_name,
                 mcp_tool_names  = excluded.mcp_tool_names""",
            (product_id, capability_slot, mcp_server_name, json.dumps(mcp_tool_names)),
        )
```

- [ ] **Step 8: Update existing override tests**

In `tests/test_capability_overrides.py`, find the old tests that used `mcp_tool_name` as a string argument and update them. The affected tests are:

- `test_set_and_list_capability_override` (line 129) — update call and assertion
- `test_set_override_is_upsert` (line 138) — update calls
- `test_delete_capability_override` (line 146) — update call
- `test_list_overrides_scoped_to_product` (line 152) — update calls
- `test_override_context_connected_server_suppresses_tools` (line 211) — update call
- `test_override_context_disconnected_server_marks_tools` (line 220) — update call

Updated versions:

```python
def test_set_and_list_capability_override(db):
    db.set_capability_override("prod-1", "social_post", "gohighlevel", ["mcp__gohighlevel__social_media_post"])
    overrides = db.list_capability_overrides("prod-1")
    assert len(overrides) == 1
    assert overrides[0]["capability_slot"] == "social_post"
    assert overrides[0]["mcp_server_name"] == "gohighlevel"
    assert overrides[0]["mcp_tool_names"] == ["mcp__gohighlevel__social_media_post"]


def test_set_override_is_upsert(db):
    db.set_capability_override("prod-1", "social_post", "server-a", ["mcp__server-a__post"])
    db.set_capability_override("prod-1", "social_post", "server-b", ["mcp__server-b__post"])
    overrides = db.list_capability_overrides("prod-1")
    assert len(overrides) == 1
    assert overrides[0]["mcp_server_name"] == "server-b"


def test_delete_capability_override(db):
    db.set_capability_override("prod-1", "social_post", "gohighlevel", ["mcp__gohighlevel__post"])
    db.delete_capability_override("prod-1", "social_post")
    assert db.list_capability_overrides("prod-1") == []


def test_list_overrides_scoped_to_product(db):
    db.set_capability_override("prod-1", "social_post", "server-a", ["mcp__server-a__post"])
    db.set_capability_override("prod-2", "social_post", "server-b", ["mcp__server-b__post"])
    assert len(db.list_capability_overrides("prod-1")) == 1
    assert db.list_capability_overrides("prod-1")[0]["mcp_server_name"] == "server-a"


def test_override_context_connected_server_suppresses_tools(db):
    db.set_capability_override("prod-1", "social_post", "ghl", ["mcp__ghl__social_post"])
    from core.tools import get_capability_override_context
    suppress, disconnected = get_capability_override_context("prod-1", connected_mcp_servers={"ghl"})
    assert "twitter_post" in suppress
    assert "linkedin_post" in suppress
    assert disconnected == {}


def test_override_context_disconnected_server_marks_tools(db):
    db.set_capability_override("prod-1", "social_post", "ghl", ["mcp__ghl__social_post"])
    from core.tools import get_capability_override_context
    suppress, disconnected = get_capability_override_context("prod-1", connected_mcp_servers=set())
    assert suppress == set()
    assert disconnected["twitter_post"] == "ghl"
    assert disconnected["linkedin_post"] == "ghl"
```

- [ ] **Step 9: Run all capability override tests**

```bash
pytest tests/test_capability_overrides.py -v
```

Expected: All tests pass.

- [ ] **Step 10: Commit**

```bash
git add backend/db.py tests/test_capability_overrides.py
git commit -m "feat: migrate capability overrides to multi-tool list (mcp_tool_names)"
```

---

### Task 2: API layer

**Files:**
- Modify: `backend/api.py:95-98, 601-604`

- [ ] **Step 1: Write failing test**

Add to `tests/test_capability_overrides.py`:

```python
def test_api_set_capability_override_accepts_tool_list(client, db):
    payload = {
        "capability_slot": "social_post",
        "mcp_server_name": "ghl",
        "mcp_tool_names": ["create-post", "edit-post"],
    }
    resp = client.post("/api/products/prod-1/capability-overrides", json=payload)
    assert resp.status_code == 200
    overrides = db.list_capability_overrides("prod-1")
    assert overrides[0]["mcp_tool_names"] == ["create-post", "edit-post"]


def test_api_get_capability_overrides_returns_tool_list(client, db):
    db.set_capability_override("prod-1", "social_post", "ghl", ["create-post", "edit-post"])
    resp = client.get("/api/products/prod-1/capability-overrides")
    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["mcp_tool_names"] == ["create-post", "edit-post"]
    assert "mcp_tool_name" not in data[0]
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/test_capability_overrides.py::test_api_set_capability_override_accepts_tool_list -v
```

Expected: `FAILED` — validation error because field `mcp_tool_names` doesn't exist on the model.

- [ ] **Step 3: Update `CapabilityOverrideBody` in `backend/api.py`**

Find lines 95-98 and replace:

```python
class CapabilityOverrideBody(BaseModel):
    capability_slot: str
    mcp_server_name: str
    mcp_tool_names: list[str]
```

- [ ] **Step 4: Update the route handler in `backend/api.py`**

Find `set_product_capability_override` (around line 601) and update the `set_capability_override` call:

```python
@router.post("/products/{product_id}/capability-overrides")
async def set_product_capability_override(product_id: str, body: CapabilityOverrideBody, _=Depends(_auth)):
    from backend.db import set_capability_override
    set_capability_override(product_id, body.capability_slot, body.mcp_server_name, body.mcp_tool_names)
    return {"ok": True}
```

- [ ] **Step 5: Run new tests**

```bash
pytest tests/test_capability_overrides.py::test_api_set_capability_override_accepts_tool_list tests/test_capability_overrides.py::test_api_get_capability_overrides_returns_tool_list -v
```

Expected: Both pass.

- [ ] **Step 6: Run full test suite**

```bash
pytest tests/test_capability_overrides.py -v
```

Expected: All pass.

- [ ] **Step 7: Commit**

```bash
git add backend/api.py tests/test_capability_overrides.py
git commit -m "feat: update capability override API to accept mcp_tool_names list"
```

---

### Task 3: Frontend types + API client

**Files:**
- Modify: `ui/src/components/settings/MCPShared.tsx:53-57`
- Modify: `ui/src/api.ts:225-236`

- [ ] **Step 1: Update `CapabilityOverride` type in `MCPShared.tsx`**

Find lines 53-57 and replace:

```typescript
export type CapabilityOverride = {
  capability_slot: string
  mcp_server_name: string
  mcp_tool_names: string[]
}
```

- [ ] **Step 2: Update `api.ts` — `getCapabilityOverrides` return type**

Find lines 225-228 and replace:

```typescript
  getCapabilityOverrides: (pw: string, productId: string) =>
    apiFetch<{ capability_slot: string; mcp_server_name: string; mcp_tool_names: string[] }[]>(
      `/api/products/${productId}/capability-overrides`, pw,
    ),
```

- [ ] **Step 3: Update `api.ts` — `setCapabilityOverride` payload**

Find lines 230-236 and replace:

```typescript
  setCapabilityOverride: (pw: string, productId: string, payload: {
    capability_slot: string; mcp_server_name: string; mcp_tool_names: string[];
  }) =>
    apiFetch<{ ok: boolean }>(
      `/api/products/${productId}/capability-overrides`, pw,
      { method: 'POST', body: JSON.stringify(payload) },
    ),
```

- [ ] **Step 4: Check TypeScript compiles**

```bash
cd /home/justin/Code/Adjutant/ui
npm run build 2>&1 | tail -20
```

Expected: No TypeScript errors. (Build errors about `mcp_tool_name` not existing on the type are expected to appear in the next step if ProductMCPSettings.tsx isn't updated yet — that's fine, fix them in Task 4.)

- [ ] **Step 5: Commit**

```bash
cd /home/justin/Code/Adjutant
git add ui/src/components/settings/MCPShared.tsx ui/src/api.ts
git commit -m "feat: update frontend CapabilityOverride type and API client for mcp_tool_names"
```

---

### Task 4: UI — replace single dropdown with checkbox list

**Files:**
- Modify: `ui/src/components/settings/ProductMCPSettings.tsx`

- [ ] **Step 1: Update `handleCapServerChange` to use `mcp_tool_names: []`**

Find `handleCapServerChange` (around line 152) and replace it entirely:

```typescript
  const handleCapServerChange = async (slot: string, serverName: string) => {
    if (!serverName) {
      await api.deleteCapabilityOverride(password, productId, slot).catch(() => null)
      setCapOverrides(prev => prev.filter(o => o.capability_slot !== slot))
      return
    }
    const existing = capOverrides.find(o => o.capability_slot === slot)
    if (existing) {
      await api.deleteCapabilityOverride(password, productId, slot).catch(() => null)
    }
    if (!capServerTools[serverName]) {
      const tools = await api.getMcpServerTools(password, serverName).catch(() => [] as { name: string; description: string }[])
      setCapServerTools(prev => ({ ...prev, [serverName]: tools }))
    }
    setCapOverrides(prev => {
      if (existing) return prev.map(o => o.capability_slot === slot ? { ...o, mcp_server_name: serverName, mcp_tool_names: [] } : o)
      return [...prev, { capability_slot: slot, mcp_server_name: serverName, mcp_tool_names: [] }]
    })
  }
```

- [ ] **Step 2: Replace `handleCapToolChange` with `handleCapToolToggle`**

Find and delete `handleCapToolChange` (around lines 169-178). Add `handleCapToolToggle` in its place:

```typescript
  const handleCapToolToggle = async (slot: string, toolName: string, checked: boolean) => {
    const override = capOverrides.find(o => o.capability_slot === slot)
    if (!override) return
    const newTools = checked
      ? [...override.mcp_tool_names, toolName]
      : override.mcp_tool_names.filter(t => t !== toolName)
    if (newTools.length === 0) {
      await api.deleteCapabilityOverride(password, productId, slot).catch(() => null)
      setCapOverrides(prev => prev.filter(o => o.capability_slot !== slot))
    } else {
      await api.setCapabilityOverride(password, productId, {
        capability_slot: slot,
        mcp_server_name: override.mcp_server_name,
        mcp_tool_names: newTools,
      }).catch(() => null)
      setCapOverrides(prev => prev.map(o => o.capability_slot === slot ? { ...o, mcp_tool_names: newTools } : o))
    }
  }
```

- [ ] **Step 3: Update the render section for capability overrides**

Find the capability overrides render block (lines 259-301). Replace the variables and tool picker portion:

Old variable setup (around line 260-263):
```typescript
const override = capOverrides.find(o => o.capability_slot === slot.name)
const selectedServer = override?.mcp_server_name || ''
const selectedTool = override?.mcp_tool_name || ''
const serverToolOptions = capServerTools[selectedServer] || []
```

New variable setup:
```typescript
const override = capOverrides.find(o => o.capability_slot === slot.name)
const selectedServer = override?.mcp_server_name || ''
const selectedTools = override?.mcp_tool_names ?? []
const serverToolOptions = capServerTools[selectedServer] || []
```

Then find and replace the tool picker JSX — old (lines 286-293):
```tsx
{selectedServer && (
  <select className={inputCls} value={selectedTool} onChange={e => handleCapToolChange(slot.name, e.target.value)}>
    <option value="">— pick tool —</option>
    {serverToolOptions.map(t => (
      <option key={t.name} value={t.name} title={t.description}>{t.name}</option>
    ))}
  </select>
)}
```

New checkbox list:
```tsx
{selectedServer && (
  <div className="mt-1 max-h-44 overflow-y-auto flex flex-col gap-0.5 border border-adj-border rounded p-1.5 bg-adj-surface">
    {serverToolOptions.length === 0 ? (
      <p className="text-xs text-adj-text-faint px-1">Loading tools…</p>
    ) : (
      serverToolOptions.map(t => (
        <label key={t.name} className="flex items-center gap-2 px-1 py-0.5 hover:bg-adj-panel rounded cursor-pointer">
          <input
            type="checkbox"
            checked={selectedTools.includes(t.name)}
            onChange={e => handleCapToolToggle(slot.name, t.name, e.target.checked)}
            className="accent-adj-accent"
          />
          <span className="text-xs text-adj-text-secondary truncate" title={t.description}>{t.name}</span>
        </label>
      ))
    )}
  </div>
)}
```

- [ ] **Step 4: Update the initial override load**

Find the line (around line 43) that uses `o.mcp_server_name` from overrides and check if any other reference to `mcp_tool_name` (singular) remains. Search for it:

```bash
grep -n "mcp_tool_name" ui/src/components/settings/ProductMCPSettings.tsx
```

Expected: No matches. If any remain, remove them.

- [ ] **Step 5: TypeScript build check**

```bash
cd /home/justin/Code/Adjutant/ui
npm run build 2>&1 | tail -30
```

Expected: Exits with code 0, no TypeScript errors.

- [ ] **Step 6: Commit**

```bash
cd /home/justin/Code/Adjutant
git add ui/src/components/settings/ProductMCPSettings.tsx
git commit -m "feat: replace single tool dropdown with checkbox list for capability overrides"
```

---

## Self-Review

**Spec coverage:**
- ✅ Migration: table-recreate in `migrate_capability_overrides_to_tool_names`
- ✅ New DB: `CREATE TABLE IF NOT EXISTS` uses `mcp_tool_names`
- ✅ `list_capability_overrides` returns `mcp_tool_names: list[str]`
- ✅ `set_capability_override` takes `mcp_tool_names: list[str]`
- ✅ `CapabilityOverrideBody.mcp_tool_names: list[str]`
- ✅ `CapabilityOverride` type updated in MCPShared.tsx
- ✅ `api.ts` updated for both get and set
- ✅ Checkbox list replaces single dropdown
- ✅ Unchecking all → delete override (revert to Built-in)
- ✅ Changing server → clears old override from DB and resets tool selection
- ✅ Runtime `get_capability_override_context` unchanged (doesn't use stored tool names)

**Placeholder scan:** None found.

**Type consistency:** `mcp_tool_names: list[str]` / `string[]` used consistently across all tasks. `handleCapToolToggle` signature matches usage in checkbox `onChange`.
