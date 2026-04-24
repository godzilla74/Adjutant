# Multi-Tool Capability Slots Design

**Goal:** Allow a capability slot to map to multiple MCP tools from the same server, rather than a single tool.

**Architecture:** Migrate `mcp_capability_overrides.mcp_tool_name` (single string) to `mcp_tool_names` (JSON array). The UI replaces the single tool dropdown with a checkbox list. The runtime suppress logic is unchanged — it suppresses all built-in tools for a slot when any override is set, regardless of which specific tools are named.

**Tech Stack:** SQLite (table-recreate migration), FastAPI, React/TypeScript

---

## Data Layer

### Migration

Recreate `mcp_capability_overrides` with `mcp_tool_names TEXT NOT NULL DEFAULT '[]'` replacing `mcp_tool_name TEXT NOT NULL`. Copy existing rows wrapping the old value with `json_array(mcp_tool_name)`.

```sql
CREATE TABLE mcp_capability_overrides_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    capability_slot TEXT NOT NULL,
    mcp_server_name TEXT NOT NULL,
    mcp_tool_names TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(product_id, capability_slot)
);
INSERT INTO mcp_capability_overrides_new
    (id, product_id, capability_slot, mcp_server_name, mcp_tool_names, created_at)
SELECT id, product_id, capability_slot, mcp_server_name, json_array(mcp_tool_name), created_at
FROM mcp_capability_overrides;
DROP TABLE mcp_capability_overrides;
ALTER TABLE mcp_capability_overrides_new RENAME TO mcp_capability_overrides;
```

Run in `init_db` behind a column-existence guard: if `mcp_tool_names` column already exists, skip.

### DB Functions (`backend/db.py`)

- `set_capability_override(product_id, capability_slot, mcp_server_name, mcp_tool_names: list[str])` — stores `json.dumps(mcp_tool_names)`. Upserts on `UNIQUE(product_id, capability_slot)`.
- `list_capability_overrides(product_id)` — returns rows with `mcp_tool_names` parsed from JSON to `list[str]`.

---

## Backend API (`backend/api.py`)

### Pydantic model change

```python
class CapabilityOverrideBody(BaseModel):
    capability_slot: str
    mcp_server_name: str
    mcp_tool_names: list[str]   # was: mcp_tool_name: str
```

`POST /api/products/{product_id}/capability-overrides` passes `body.mcp_tool_names` to `set_capability_override`.

`GET /api/products/{product_id}/capability-overrides` returns `mcp_tool_names: list[str]` per row.

---

## Runtime (`core/tools.py`)

`get_capability_override_context` reads `override["mcp_tool_names"]` (list) instead of `override["mcp_tool_name"]` (string). The suppress and disconnected logic is unchanged — it operates on the slot's `built_in_tools` list, not the stored MCP tool names.

---

## UI

### Types (`MCPShared.tsx`)

```typescript
type CapabilityOverride = {
  capability_slot: string
  mcp_server_name: string
  mcp_tool_names: string[]   // was: mcp_tool_name: string
}
```

### `api.ts`

```typescript
setCapabilityOverride: (pw, productId, payload: {
  capability_slot: string; mcp_server_name: string; mcp_tool_names: string[];
})
```

### Tool picker (`ProductMCPSettings.tsx`)

Replace single tool `<select>` with a scrollable checkbox list:

- Rendered below the server dropdown when a server is selected and its tools are loaded.
- Each tool is a labeled checkbox. Checked = included in `mcp_tool_names`.
- On any checkbox toggle: if resulting array is non-empty, call `api.setCapabilityOverride` with the updated array. If empty (all unchecked), call `api.deleteCapabilityOverride`.
- No separate Save button — each toggle saves immediately, consistent with existing single-tool behavior.
