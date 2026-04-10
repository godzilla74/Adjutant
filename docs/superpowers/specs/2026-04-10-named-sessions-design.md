# Named Sessions Design

## Goal

Allow users to create named conversation sessions within a product (or globally across all products), so different concerns can have isolated chat histories — e.g. a "Finance" session, a "Q2 Launch" session, a global "Strategy" session.

## Layout Changes

The existing four-column layout is reorganised:

| Column | Before | After |
|---|---|---|
| 1 | ProductRail | ProductRail (unchanged) |
| 2 | WorkstreamsPanel (with Objectives) | SessionsPanel + WorkstreamsPanel (Objectives removed) |
| 3 | ActivityFeed + DirectiveBar | ActivityFeed + DirectiveBar (unchanged) |
| 4 | ReviewQueue | ReviewQueue + ObjectivesPanel |

Sessions sit above Workstreams in the left column. Objectives move to the bottom of the right column, below the review queue.

---

## Data Model

### New `sessions` table

```sql
CREATE TABLE sessions (
    id         TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    product_id TEXT REFERENCES products(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

`product_id` is nullable. `NULL` = global session (cross-product).

### Modified `messages` table

Add column and relax the `product_id` constraint (global session messages have no product):

```sql
ALTER TABLE messages ADD COLUMN session_id TEXT REFERENCES sessions(id) ON DELETE CASCADE;
-- SQLite does not support DROP NOT NULL inline; recreate the table with product_id nullable
-- Migration script handles this during the startup schema upgrade
```

Existing rows keep `session_id = NULL`. The `product_id` column becomes nullable to support global session messages. These are "pre-sessions" messages; they remain accessible under the initial "General" session (see Migration below).

### Modified `conversation_summaries` table

Add column:

```sql
ALTER TABLE conversation_summaries ADD COLUMN session_id TEXT REFERENCES sessions(id) ON DELETE CASCADE;
```

Compaction is scoped per session. Existing summaries keep `session_id = NULL`.

### Migration

On first startup after this change, for each product that has messages but no sessions: auto-create a "General" session and set `session_id` on all existing messages for that product to that session's id. Same for global: if any messages exist with `product_id = NULL`, create a global "General" session and assign them.

---

## Backend — `backend/db.py`

New functions:

```python
def create_session(name: str, product_id: str | None = None) -> str
    # Inserts row, returns session id

def get_sessions(product_id: str | None) -> list[dict]
    # Returns sessions WHERE product_id = ? (or IS NULL for global)
    # Ordered by created_at DESC

def rename_session(session_id: str, name: str) -> None

def delete_session(session_id: str) -> None
    # Cascades via FK to messages and conversation_summaries

def get_first_session(product_id: str | None) -> dict | None
    # Returns newest session for the product (or global if None)
```

Updated functions:

```python
def load_messages(product_id: str | None, session_id: str, limit: int = 100) -> list[dict]
    # Adds WHERE session_id = ? to the existing query

def save_message(product_id: str | None, role: str, content, session_id: str) -> None
    # Passes session_id into the INSERT
```

---

## Backend — `backend/main.py`

### Active session tracking

Server tracks `active_session_id` per WebSocket connection in addition to `active_product_id`.

### `_product_data_payload` update

Adds `sessions` list and `active_session_id` to the existing payload:

```python
{
  ...,
  "sessions": get_sessions(product_id),
  "active_session_id": active_session_id,
}
```

### New WebSocket message types — client → server

| type | fields | behaviour |
|---|---|---|
| `create_session` | `name`, `product_id?` | Creates session, auto-switches to it, broadcasts `session_created` |
| `switch_session` | `session_id` | Loads session history, sends `session_switched` |
| `rename_session` | `session_id`, `name` | Renames, broadcasts `session_renamed` |
| `delete_session` | `session_id` | Deletes session; if last session, auto-creates "General" first; sends `session_deleted` with `next_session_id` |

### New WebSocket message types — server → client

| type | fields |
|---|---|
| `session_created` | session object `{id, name, product_id, created_at}` |
| `session_switched` | `session_id`, `chat_history` |
| `session_renamed` | `session_id`, `name` |
| `session_deleted` | `session_id`, `next_session_id` |

### Directive handling update

The `directive` message handler reads `session_id` from the connection state and passes it to `_build_user_message`, `save_message`, and the queued directive dict. The worker uses the directive's `session_id` when saving the agent response.

### Context building — global sessions

When `product_id = None` (global session), `_build_context()` replaces the single-product system prompt block with a cross-product summary:

```
You are Adjutant, a global executive assistant.
You have context across all products: {product names and brief descriptions}.

Product summaries:
- {product name}: {objectives summary, recent activity}
...
```

Messages are loaded by `session_id` only (no `product_id` filter).

---

## Frontend Components

### New: `ui/src/components/SessionsPanel.tsx`

Props:
```ts
interface Props {
  sessions: Session[]
  activeSessionId: string | null
  onSwitch: (sessionId: string) => void
  onCreate: (name: string) => void
  onRename: (sessionId: string, name: string) => void
  onDelete: (sessionId: string) => void
}
```

Behaviour:
- Lists sessions, active one highlighted
- "+ New" button opens an inline input to name and create
- Double-click on active session name enables inline rename (Enter/blur to submit)
- Hover reveals `×` delete button; clicking it shows a one-step confirmation ("Delete this session and its history?") inline
- Positioned above WorkstreamsPanel in the left column

### Modified: `ui/src/components/WorkstreamsPanel.tsx`

Remove the `objectives` prop and all objectives rendering. No other changes.

### New: `ui/src/components/ObjectivesPanel.tsx`

Extracted from current WorkstreamsPanel. Renders the objectives list with progress bars. Same data, new home. Props: `objectives: Objective[]`.

### Modified: `ui/src/App.tsx`

**State additions** (inside `productState` map per product):
```ts
sessions: Session[]
activeSessionId: string | null
```

**New WebSocket handlers:** `session_created`, `session_switched`, `session_renamed`, `session_deleted` update state accordingly. `session_deleted` also triggers a switch to `next_session_id`.

**Layout changes:**
- Left column: `<SessionsPanel>` above `<WorkstreamsPanel>`
- Right column: `<ReviewQueue>` above `<ObjectivesPanel>` in a `flex-col` wrapper
- `<WorkstreamsPanel>` no longer receives `objectives` prop

**Chat tab header:** shows the active session name as a subtle right-aligned label:
```
Chat    Activity                         Finance session
```

**Global sessions:** when `showOverview` is true, `SessionsPanel` is shown with global sessions (product_id = null). Selecting a global session switches the center panel to a chat view for that session instead of OverviewPanel. A global "General" session is auto-created on first use.

### New type: `ui/src/types.ts`

```ts
export interface Session {
  id: string
  name: string
  product_id: string | null
  created_at: string
}
```

---

## Error Handling

| Scenario | Behaviour |
|---|---|
| Delete last session | Server auto-creates "General" before responding; client never sees a sessionless state |
| Switch to deleted session_id | Server falls back to first available session, sends `session_switched` |
| Directive arrives with stale session_id | Worker falls back to first available session for that product |
| Global session with no products | Context building still works — just returns agent name + empty product list |
| Rename to empty string | Client prevents submit; server rejects with 400 if it somehow reaches the API |

---

## Out of Scope

- Session reordering (drag to reorder)
- Exporting session history
- Session sharing between users
- Pinning sessions
- Session search / filtering
