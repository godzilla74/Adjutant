# Browser Credentials for Social Posting — Design

**Goal:** Allow users to store username/password credentials per social platform so that browser-based posting can log in automatically, instead of guessing or failing.

**Architecture:** A new `browser_credentials` table stores credentials and an `active` toggle per (product_id, service). The connection mode toggle (OAuth vs Browser) is persisted as `active` on that row. `_publish_social_draft` checks the active mode first; if browser is active, credentials are injected into the browser task prompt. The Connections settings UI gains an OAuth/Browser pill toggle on each service card.

---

## Data Layer — `backend/db.py`

### New table

```sql
CREATE TABLE IF NOT EXISTS browser_credentials (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id  TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    service     TEXT NOT NULL,
    username    TEXT NOT NULL DEFAULT '',
    password    TEXT NOT NULL DEFAULT '',
    active      INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(product_id, service)
)
```

`active = 1` means "use browser mode for this service". Credentials and toggle are independent: toggling back to OAuth sets `active = 0` without clearing username/password.

Migration in `init_db()`:

```python
with _conn() as conn:
    cols = [r[1] for r in conn.execute("PRAGMA table_info(browser_credentials)").fetchall()]
    # table created fresh by CREATE TABLE IF NOT EXISTS above; migration only needed
    # if the table existed before this column was added in a future change
```

Because this is a new table (not altering an existing one), the `CREATE TABLE IF NOT EXISTS` statement handles both fresh and existing databases.

### CRUD functions

```python
def save_browser_credential(
    product_id: str, service: str,
    username: str, password: str, active: bool
) -> None:
    with _conn() as conn:
        conn.execute(
            """INSERT INTO browser_credentials (product_id, service, username, password, active)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(product_id, service) DO UPDATE SET
                   username=excluded.username,
                   password=excluded.password,
                   active=excluded.active""",
            (product_id, service, username, password, 1 if active else 0),
        )

def get_browser_credential(product_id: str, service: str) -> dict | None:
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM browser_credentials WHERE product_id = ? AND service = ?",
            (product_id, service),
        ).fetchone()
    return dict(row) if row else None

def delete_browser_credential(product_id: str, service: str) -> None:
    with _conn() as conn:
        conn.execute(
            "DELETE FROM browser_credentials WHERE product_id = ? AND service = ?",
            (product_id, service),
        )

def list_browser_credentials(product_id: str) -> list[dict]:
    """Returns service, username, active — never password."""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT service, username, active FROM browser_credentials WHERE product_id = ?",
            (product_id,),
        ).fetchall()
    return [dict(r) for r in rows]
```

---

## API — `backend/api.py`

Three new endpoints, all authenticated via the existing password middleware pattern.

### `GET /products/{product_id}/browser-credentials`

Returns `[{service, username, active}]`. Password is never returned.

### `PUT /products/{product_id}/browser-credentials/{service}`

Body: `{username: str, password: str, active: bool}`

Upserts the row. If `password` is an empty string and a row already exists, the existing password is preserved (allows toggling `active` without re-entering password).

Response: `{"ok": true}`

### `DELETE /products/{product_id}/browser-credentials/{service}`

Removes the row entirely (both credentials and toggle state).

Response: `{"ok": true}`

---

## Publish Path — `backend/main.py`

`_publish_social_draft` currently picks OAuth vs browser by checking `get_oauth_connection`. New priority order:

1. **Browser mode active** (`get_browser_credential(product_id, platform)` returns a row with `active=True`): use browser task, inject credentials if username is set.
2. **OAuth connection exists** (`get_oauth_connection(product_id, platform)`): use API.
3. **Neither**: use browser task without credentials (existing fallback behavior).

Credential injection in the browser task prompt:

```python
cred = get_browser_credential(product_id, platform)
if cred and cred["active"] and cred["username"]:
    task += (
        f"\n\nLogin credentials: username/email: {cred['username']}, "
        f"password: {cred['password']}. "
        f"Use these to fill the login form directly — do NOT use 'Sign in with Google' "
        f"or other OAuth flows."
    )
```

If browser mode is active but no credentials are saved, the task runs without them (graceful degradation).

---

## UI — `ui/src/components/settings/ConnectionsSettings.tsx`

### Toggle

Each service card gains an **OAuth / Browser** pill toggle. The selected mode is stored in local component state, initialised from the `active` field of `browser_credentials` data fetched on load (alongside the existing `oauthConnections` fetch).

Toggle behaviour:
- Switching **OAuth → Browser**: calls `PUT /browser-credentials/{service}` with `active: true` (preserving any stored credentials). Does not touch the OAuth connection.
- Switching **Browser → OAuth**: calls `PUT /browser-credentials/{service}` with `active: false` (preserving any stored credentials). Does not touch the OAuth connection.

### Browser mode card content

When Browser is selected:

- **Username field** — text input, value shown in plaintext.
- **Password field** — `type="password"` input; browser's built-in masking (dots). After saving, the field remains with value `"••••••••"` (a placeholder string, not the real password — the real password is never sent back from the API).
- **Save button** — calls `PUT /browser-credentials/{service}` with current field values and `active: true`. Disabled if username is empty.
- **Remove credentials link** — calls `DELETE /browser-credentials/{service}` then resets fields and sets mode back to OAuth in local state.

### API client — `ui/src/api.ts`

Three new methods on the API class:

```typescript
getBrowserCredentials(password: string, productId: string): Promise<{service: string; username: string; active: boolean}[]>
saveBrowserCredential(password: string, productId: string, service: string, body: {username: string; password: string; active: boolean}): Promise<void>
deleteBrowserCredential(password: string, productId: string, service: string): Promise<void>
```

---

## Security

Credentials are stored as plaintext in SQLite, consistent with how OAuth access tokens and refresh tokens are stored today. This is acceptable for a personal-use, locally-run application. The API never returns the password field; the UI displays a static placeholder after save.

---

## What Is Not In Scope

- Encryption at rest
- Credential sharing across products
- Browser session persistence (the browser task logs in fresh each time)
