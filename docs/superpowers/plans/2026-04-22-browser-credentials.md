# Browser Credentials Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Store per-service username/password credentials in the database so browser-based social posting can log in automatically, with a UI toggle to choose OAuth vs Browser mode per platform.

**Architecture:** New `browser_credentials` table (product_id, service, username, password, active) stores credentials and the active mode toggle independently. `_publish_social_draft` checks browser mode first; if active, credentials are injected into the browser task prompt. The Connections settings UI gets an OAuth/Browser pill toggle per social service card, with username/password fields shown when Browser is selected.

**Tech Stack:** Python/SQLite (backend/db.py), FastAPI (backend/api.py), asyncio (backend/main.py), React + TypeScript (ui/src/components/settings/ConnectionsSettings.tsx, ui/src/api.ts).

---

## File Map

| File | Change |
|---|---|
| `backend/db.py` | Add `browser_credentials` table, 4 CRUD functions |
| `backend/api.py` | Add 3 endpoints: GET list, PUT upsert, DELETE |
| `backend/main.py` | Update `_publish_social_draft` to check browser mode + inject credentials |
| `ui/src/api.ts` | Add 3 API client methods |
| `ui/src/components/settings/ConnectionsSettings.tsx` | Add OAuth/Browser toggle + credential form per social service card |
| `tests/test_db.py` | Tests for new CRUD functions |
| `tests/test_oauth_endpoints.py` | Tests for 3 new endpoints |
| `tests/test_main.py` | Tests for updated publish path |

---

## Task 1: DB — `browser_credentials` table + CRUD

**Files:**
- Modify: `backend/db.py`
- Test: `tests/test_db.py`

- [ ] **Step 1: Write failing tests**

Add at the end of `tests/test_db.py`:

```python
def test_save_and_get_browser_credential(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_DB", str(tmp_path / "test.db"))
    import importlib, backend.db as db
    importlib.reload(db)
    db.init_db()
    with db._conn() as conn:
        conn.execute("INSERT INTO products (id, name, icon_label, color) VALUES ('p1', 'P', 'P', '#000')")
    db.save_browser_credential("p1", "twitter", "myuser", "mypass", active=True)
    cred = db.get_browser_credential("p1", "twitter")
    assert cred is not None
    assert cred["username"] == "myuser"
    assert cred["password"] == "mypass"
    assert cred["active"] == 1


def test_save_browser_credential_upserts(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_DB", str(tmp_path / "test.db"))
    import importlib, backend.db as db
    importlib.reload(db)
    db.init_db()
    with db._conn() as conn:
        conn.execute("INSERT INTO products (id, name, icon_label, color) VALUES ('p1', 'P', 'P', '#000')")
    db.save_browser_credential("p1", "twitter", "user1", "pass1", active=True)
    db.save_browser_credential("p1", "twitter", "user2", "pass2", active=False)
    cred = db.get_browser_credential("p1", "twitter")
    assert cred["username"] == "user2"
    assert cred["active"] == 0


def test_delete_browser_credential(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_DB", str(tmp_path / "test.db"))
    import importlib, backend.db as db
    importlib.reload(db)
    db.init_db()
    with db._conn() as conn:
        conn.execute("INSERT INTO products (id, name, icon_label, color) VALUES ('p1', 'P', 'P', '#000')")
    db.save_browser_credential("p1", "twitter", "u", "p", active=True)
    db.delete_browser_credential("p1", "twitter")
    assert db.get_browser_credential("p1", "twitter") is None


def test_list_browser_credentials_omits_password(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_DB", str(tmp_path / "test.db"))
    import importlib, backend.db as db
    importlib.reload(db)
    db.init_db()
    with db._conn() as conn:
        conn.execute("INSERT INTO products (id, name, icon_label, color) VALUES ('p1', 'P', 'P', '#000')")
    db.save_browser_credential("p1", "twitter", "u1", "secret", active=True)
    db.save_browser_credential("p1", "linkedin", "u2", "secret2", active=False)
    results = db.list_browser_credentials("p1")
    assert len(results) == 2
    for r in results:
        assert "password" not in r
    services = {r["service"] for r in results}
    assert services == {"twitter", "linkedin"}
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/justin/Code/Adjutant && .venv/bin/pytest tests/test_db.py::test_save_and_get_browser_credential tests/test_db.py::test_save_browser_credential_upserts tests/test_db.py::test_delete_browser_credential tests/test_db.py::test_list_browser_credentials_omits_password -v
```

Expected: FAIL — `save_browser_credential` not defined.

- [ ] **Step 3: Add `CREATE TABLE` to `backend/db.py`**

Find the `CREATE TABLE IF NOT EXISTS oauth_connections` block (around line 258). Add the new table immediately after it:

```python
    conn.execute("""
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
    """)
```

- [ ] **Step 4: Add CRUD functions to `backend/db.py`**

Add these four functions after the `delete_oauth_connection` / `list_oauth_connections` block (around line 1635):

```python
def save_browser_credential(
    product_id: str,
    service: str,
    username: str,
    password: str,
    active: bool,
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

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd /home/justin/Code/Adjutant && .venv/bin/pytest tests/test_db.py::test_save_and_get_browser_credential tests/test_db.py::test_save_browser_credential_upserts tests/test_db.py::test_delete_browser_credential tests/test_db.py::test_list_browser_credentials_omits_password -v
```

Expected: PASS

- [ ] **Step 6: Run full suite**

```bash
cd /home/justin/Code/Adjutant && .venv/bin/pytest tests/ -q
```

Expected: all pass

- [ ] **Step 7: Commit**

```bash
cd /home/justin/Code/Adjutant && git add backend/db.py tests/test_db.py && git commit -m "feat: browser_credentials table + CRUD"
```

---

## Task 2: API endpoints

**Files:**
- Modify: `backend/api.py`
- Test: `tests/test_oauth_endpoints.py`

The existing `tests/test_oauth_endpoints.py` has a `client` fixture that creates a fresh FastAPI app + test DB. Use the same fixture (it's `autouse`-capable via import or just copy its pattern).

- [ ] **Step 1: Write failing tests**

Add at the end of `tests/test_oauth_endpoints.py`:

```python
def test_list_browser_credentials_empty(client):
    import backend.db as db
    with db._conn() as conn:
        conn.execute("INSERT INTO products (id, name, icon_label, color) VALUES ('p1', 'P', 'P', '#000')")
    resp = client.get("/api/products/p1/browser-credentials", headers=AUTH)
    assert resp.status_code == 200
    assert resp.json() == []


def test_save_and_list_browser_credential(client):
    import backend.db as db
    with db._conn() as conn:
        conn.execute("INSERT INTO products (id, name, icon_label, color) VALUES ('p1', 'P', 'P', '#000')")
    resp = client.put(
        "/api/products/p1/browser-credentials/twitter",
        json={"username": "myuser", "password": "mypass", "active": True},
        headers=AUTH,
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

    resp = client.get("/api/products/p1/browser-credentials", headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["service"] == "twitter"
    assert data[0]["username"] == "myuser"
    assert data[0]["active"] is True
    assert "password" not in data[0]


def test_save_browser_credential_preserves_password_when_empty(client):
    import backend.db as db
    with db._conn() as conn:
        conn.execute("INSERT INTO products (id, name, icon_label, color) VALUES ('p1', 'P', 'P', '#000')")
    # Save initial credentials
    client.put(
        "/api/products/p1/browser-credentials/twitter",
        json={"username": "myuser", "password": "secret", "active": True},
        headers=AUTH,
    )
    # Toggle active only — send empty password
    client.put(
        "/api/products/p1/browser-credentials/twitter",
        json={"username": "myuser", "password": "", "active": False},
        headers=AUTH,
    )
    # Verify password is still stored
    cred = db.get_browser_credential("p1", "twitter")
    assert cred["password"] == "secret"
    assert cred["active"] == 0


def test_delete_browser_credential_endpoint(client):
    import backend.db as db
    with db._conn() as conn:
        conn.execute("INSERT INTO products (id, name, icon_label, color) VALUES ('p1', 'P', 'P', '#000')")
    client.put(
        "/api/products/p1/browser-credentials/twitter",
        json={"username": "u", "password": "p", "active": True},
        headers=AUTH,
    )
    resp = client.delete("/api/products/p1/browser-credentials/twitter", headers=AUTH)
    assert resp.status_code == 204
    assert db.get_browser_credential("p1", "twitter") is None


def test_browser_credentials_require_auth(client):
    resp = client.get("/api/products/p1/browser-credentials")
    assert resp.status_code == 401
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/justin/Code/Adjutant && .venv/bin/pytest tests/test_oauth_endpoints.py::test_list_browser_credentials_empty tests/test_oauth_endpoints.py::test_save_and_list_browser_credential tests/test_oauth_endpoints.py::test_save_browser_credential_preserves_password_when_empty tests/test_oauth_endpoints.py::test_delete_browser_credential_endpoint tests/test_oauth_endpoints.py::test_browser_credentials_require_auth -v
```

Expected: FAIL — endpoints don't exist.

- [ ] **Step 3: Add endpoints to `backend/api.py`**

Find the `delete_oauth_connection_api` endpoint (around line 917) and add after it:

```python
@router.get("/products/{product_id}/browser-credentials")
def list_browser_credentials_api(product_id: str, _=Depends(_auth)):
    from backend.db import list_browser_credentials
    return list_browser_credentials(product_id)


class BrowserCredentialBody(BaseModel):
    username: str
    password: str
    active: bool


@router.put("/products/{product_id}/browser-credentials/{service}")
def save_browser_credential_api(
    product_id: str, service: str, body: BrowserCredentialBody, _=Depends(_auth)
):
    from backend.db import save_browser_credential, get_browser_credential
    password = body.password
    if not password:
        existing = get_browser_credential(product_id, service)
        if existing:
            password = existing["password"]
    save_browser_credential(product_id, service, body.username, password, body.active)
    return {"ok": True}


@router.delete("/products/{product_id}/browser-credentials/{service}", status_code=204)
def delete_browser_credential_api(product_id: str, service: str, _=Depends(_auth)):
    from backend.db import delete_browser_credential
    delete_browser_credential(product_id, service)
```

`BaseModel` is already imported in `api.py` from pydantic (check the imports at the top; if not present, add `from pydantic import BaseModel`).

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /home/justin/Code/Adjutant && .venv/bin/pytest tests/test_oauth_endpoints.py::test_list_browser_credentials_empty tests/test_oauth_endpoints.py::test_save_and_list_browser_credential tests/test_oauth_endpoints.py::test_save_browser_credential_preserves_password_when_empty tests/test_oauth_endpoints.py::test_delete_browser_credential_endpoint tests/test_oauth_endpoints.py::test_browser_credentials_require_auth -v
```

Expected: PASS

- [ ] **Step 5: Run full suite**

```bash
cd /home/justin/Code/Adjutant && .venv/bin/pytest tests/ -q
```

Expected: all pass

- [ ] **Step 6: Commit**

```bash
cd /home/justin/Code/Adjutant && git add backend/api.py tests/test_oauth_endpoints.py && git commit -m "feat: browser-credentials API endpoints"
```

---

## Task 3: Update `_publish_social_draft` to use browser credentials

**Files:**
- Modify: `backend/main.py`
- Test: `tests/test_main.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_main.py`:

```python
def test_publish_uses_browser_when_active_cred(isolated_db):
    """When browser mode is active with credentials, browser task is used and creds are injected."""
    import asyncio
    from unittest.mock import AsyncMock, patch
    import backend.db as db

    with db._conn() as conn:
        conn.execute("INSERT OR IGNORE INTO products (id, name, icon_label, color) VALUES ('product-alpha', 'PA', 'PA', '#000')")
    db.save_browser_credential("product-alpha", "twitter", "myuser", "mypass", active=True)

    draft = {
        "id": 1, "product_id": "product-alpha", "platform": "twitter",
        "content": "Hello!", "image_url": None,
    }

    async def run():
        mock_execute = AsyncMock(return_value='{"status":"success","result":"SUCCESS: https://x.com/tweet/1"}')
        with patch("backend.main.execute_tool", mock_execute):
            result = await __import__("backend.main", fromlist=["_publish_social_draft"])._publish_social_draft(draft)
        assert result["success"] is True
        call_args = mock_execute.call_args
        task_text = call_args[0][1]["task"]
        assert "myuser" in task_text
        assert "mypass" in task_text

    asyncio.run(run())


def test_publish_uses_oauth_when_no_active_browser_cred(isolated_db):
    """When no active browser credential, falls through to OAuth path."""
    import asyncio
    from unittest.mock import AsyncMock, patch
    import backend.db as db

    with db._conn() as conn:
        conn.execute("INSERT OR IGNORE INTO products (id, name, icon_label, color) VALUES ('product-alpha', 'PA', 'PA', '#000')")
    db.save_oauth_connection("product-alpha", "twitter", "@handle", "tok", "ref", "2099-01-01T00:00:00+00:00", "")

    draft = {
        "id": 1, "product_id": "product-alpha", "platform": "twitter",
        "content": "Hello!", "image_url": None,
    }

    async def run():
        mock_twitter = AsyncMock(return_value="posted")
        with patch("backend.social_api.twitter_post", mock_twitter):
            result = await __import__("backend.main", fromlist=["_publish_social_draft"])._publish_social_draft(draft)
        assert result["success"] is True
        mock_twitter.assert_awaited_once()

    asyncio.run(run())


def test_publish_browser_cred_inactive_falls_through_to_oauth(isolated_db):
    """Browser credential exists but active=False → uses OAuth if available."""
    import asyncio
    from unittest.mock import AsyncMock, patch
    import backend.db as db

    with db._conn() as conn:
        conn.execute("INSERT OR IGNORE INTO products (id, name, icon_label, color) VALUES ('product-alpha', 'PA', 'PA', '#000')")
    db.save_browser_credential("product-alpha", "twitter", "u", "p", active=False)
    db.save_oauth_connection("product-alpha", "twitter", "@handle", "tok", "ref", "2099-01-01T00:00:00+00:00", "")

    draft = {
        "id": 1, "product_id": "product-alpha", "platform": "twitter",
        "content": "Hello!", "image_url": None,
    }

    async def run():
        mock_twitter = AsyncMock(return_value="posted")
        with patch("backend.social_api.twitter_post", mock_twitter):
            result = await __import__("backend.main", fromlist=["_publish_social_draft"])._publish_social_draft(draft)
        assert result["success"] is True
        mock_twitter.assert_awaited_once()

    asyncio.run(run())
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/justin/Code/Adjutant && .venv/bin/pytest tests/test_main.py::test_publish_uses_browser_when_active_cred tests/test_main.py::test_publish_uses_oauth_when_no_active_browser_cred tests/test_main.py::test_publish_browser_cred_inactive_falls_through_to_oauth -v
```

Expected: FAIL

- [ ] **Step 3: Update `_publish_social_draft` in `backend/main.py`**

Replace the current `_publish_social_draft` function body with the new version. The key change: at the start of each platform block, check for an active browser credential first.

Add a small helper just above `_publish_social_draft`:

```python
def _inject_creds(task: str, cred: dict | None) -> str:
    """Append login credentials to a browser task prompt if available."""
    if cred and cred.get("username"):
        task += (
            f"\n\nLogin credentials — username/email: {cred['username']}, "
            f"password: {cred['password']}. "
            f"Use these to fill the login form directly. "
            f"Do NOT use 'Sign in with Google' or other OAuth flows."
        )
    return task
```

Then replace the full `_publish_social_draft` function:

```python
async def _publish_social_draft(draft: dict) -> dict:
    """Post an approved social draft. Browser mode (with credentials) takes priority over OAuth API."""
    from backend.social_api import twitter_post, linkedin_post, facebook_post, instagram_post
    from backend.db import get_oauth_connection, get_browser_credential
    platform = draft.get("platform", "")
    product_id = draft.get("product_id", "")
    text = draft.get("content", "")
    image_url = draft.get("image_url") or None

    cred = get_browser_credential(product_id, platform)
    browser_active = bool(cred and cred.get("active"))

    try:
        if platform == "twitter":
            if not browser_active and get_oauth_connection(product_id, "twitter"):
                result = await twitter_post(product_id, text, image_url)
                return {"success": True, "result": result}
            else:
                task = f"Post the following tweet on X (twitter.com).\n\nTweet text: {text}"
                if image_url:
                    task += f"\n\nAttach this media: {image_url}"
                task = _inject_creds(task, cred)
                task += _BROWSER_OUTCOME_SUFFIX
                return _parse_browser_result(await execute_tool("browser_task", {"task": task}))
        elif platform == "linkedin":
            if not browser_active and get_oauth_connection(product_id, "linkedin"):
                result = await linkedin_post(product_id, text, image_url)
                return {"success": True, "result": result}
            else:
                task = f"Post the following to LinkedIn (linkedin.com).\n\nPost text:\n{text}"
                if image_url:
                    task += f"\n\nAttach this image: {image_url}"
                task = _inject_creds(task, cred)
                task += _BROWSER_OUTCOME_SUFFIX
                return _parse_browser_result(await execute_tool("browser_task", {"task": task}))
        elif platform == "facebook":
            if not browser_active and get_oauth_connection(product_id, "facebook"):
                result = await facebook_post(product_id, text, image_url)
                return {"success": True, "result": result}
            else:
                task = f"Post the following to Facebook (facebook.com).\n\nPost text:\n{text}"
                if image_url:
                    task += f"\n\nAttach this image: {image_url}"
                task = _inject_creds(task, cred)
                task += _BROWSER_OUTCOME_SUFFIX
                return _parse_browser_result(await execute_tool("browser_task", {"task": task}))
        elif platform == "instagram":
            if not image_url:
                return {"success": False, "error": "Instagram requires an image URL"}
            if not browser_active and get_oauth_connection(product_id, "instagram"):
                result = await instagram_post(product_id, text, image_url)
                return {"success": True, "result": result}
            else:
                task = (
                    f"Post the following to Instagram (instagram.com).\n\n"
                    f"Caption:\n{text}\n\nImage URL: {image_url}\n\n"
                    f"Download or use the image at that URL for the post."
                )
                task = _inject_creds(task, cred)
                task += _BROWSER_OUTCOME_SUFFIX
                return _parse_browser_result(await execute_tool("browser_task", {"task": task}))
        else:
            return {"success": False, "error": f"Unknown platform: {platform}"}
    except RuntimeError as e:
        return {"success": False, "error": str(e)}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /home/justin/Code/Adjutant && .venv/bin/pytest tests/test_main.py::test_publish_uses_browser_when_active_cred tests/test_main.py::test_publish_uses_oauth_when_no_active_browser_cred tests/test_main.py::test_publish_browser_cred_inactive_falls_through_to_oauth -v
```

Expected: PASS

- [ ] **Step 5: Run full suite**

```bash
cd /home/justin/Code/Adjutant && .venv/bin/pytest tests/ -q
```

Expected: all pass

- [ ] **Step 6: Commit**

```bash
cd /home/justin/Code/Adjutant && git add backend/main.py tests/test_main.py && git commit -m "feat: inject browser credentials into social posting task"
```

---

## Task 4: UI API client methods

**Files:**
- Modify: `ui/src/api.ts`

No automated test — these are thin HTTP wrappers matching the pattern of existing methods.

- [ ] **Step 1: Read `ui/src/api.ts`** to find where `deleteOAuthConnection` is defined (around line 249). Add three new methods immediately after it:

```typescript
getBrowserCredentials: (pw: string, productId: string) =>
  apiFetch<{ service: string; username: string; active: boolean }[]>(
    `/api/products/${productId}/browser-credentials`, pw,
  ),

saveBrowserCredential: (
  pw: string,
  productId: string,
  service: string,
  body: { username: string; password: string; active: boolean },
) =>
  apiFetch<{ ok: boolean }>(
    `/api/products/${productId}/browser-credentials/${service}`, pw,
    { method: 'PUT', body: JSON.stringify(body) },
  ),

deleteBrowserCredential: (pw: string, productId: string, service: string) =>
  apiFetch<void>(
    `/api/products/${productId}/browser-credentials/${service}`, pw,
    { method: 'DELETE' },
  ),
```

- [ ] **Step 2: TypeScript check**

```bash
cd /home/justin/Code/Adjutant/ui && npx tsc --noEmit
```

Expected: no errors

- [ ] **Step 3: Commit**

```bash
cd /home/justin/Code/Adjutant && git add ui/src/api.ts && git commit -m "feat: browser-credentials API client methods"
```

---

## Task 5: UI — OAuth/Browser toggle + credential form

**Files:**
- Modify: `ui/src/components/settings/ConnectionsSettings.tsx`

- [ ] **Step 1: Read the full `ConnectionsSettings.tsx`** to understand current state shape and service card render structure before editing.

- [ ] **Step 2: Add new state and load browser credentials on mount**

The social services that support browser mode are twitter, linkedin, facebook, instagram. Gmail and Google Calendar are always OAuth-only.

Add a constant near the top of the file (after `BROWSER_AUTO_SERVICES`):

```typescript
const BROWSER_CRED_SERVICES = new Set(['twitter', 'linkedin', 'facebook', 'instagram'])
```

Add new state variables inside the component (after the existing state declarations):

```typescript
const [browserCreds, setBrowserCreds] = useState<
  { service: string; username: string; active: boolean }[]
>([])
const [credFields, setCredFields] = useState<
  Record<string, { username: string; password: string; saved: boolean }>
>({})
const [savingCred, setSavingCred] = useState<string | null>(null)
```

In the `useEffect` that loads data (the one with `Promise.all`), add `api.getBrowserCredentials(password, productId)` to the Promise.all:

```typescript
Promise.all([
  api.getOAuthConnections(password, productId),
  api.getGoogleOAuthSettings(password),
  api.getBrowserCredentials(password, productId),
]).then(([conns, googleCfg, bCreds]) => {
  setOauthConnections(conns)
  setGoogleOAuthConfigured(!!googleCfg.google_oauth_client_id)
  setBrowserCreds(bCreds)
  // Pre-populate credFields for services that have saved credentials
  const fields: Record<string, { username: string; password: string; saved: boolean }> = {}
  for (const c of bCreds) {
    fields[c.service] = { username: c.username, password: '', saved: true }
  }
  setCredFields(fields)
}).catch(() => {}).finally(() => setLoading(false))
```

- [ ] **Step 3: Add handler functions**

Add these handlers after `handleDisconnectOAuth`:

```typescript
async function handleToggleMode(service: string, toBrowser: boolean) {
  if (!productId) return
  const existing = credFields[service]
  await api.saveBrowserCredential(password, productId, service, {
    username: existing?.username ?? '',
    password: existing?.saved ? '' : (existing?.password ?? ''),
    active: toBrowser,
  })
  setBrowserCreds((prev) => {
    const exists = prev.find((c) => c.service === service)
    if (exists) return prev.map((c) => c.service === service ? { ...c, active: toBrowser } : c)
    return [...prev, { service, username: existing?.username ?? '', active: toBrowser }]
  })
}

async function handleSaveCred(service: string) {
  if (!productId) return
  const fields = credFields[service]
  if (!fields?.username) return
  setSavingCred(service)
  try {
    await api.saveBrowserCredential(password, productId, service, {
      username: fields.username,
      password: fields.password,
      active: true,
    })
    setBrowserCreds((prev) => {
      const exists = prev.find((c) => c.service === service)
      if (exists) return prev.map((c) => c.service === service ? { ...c, username: fields.username, active: true } : c)
      return [...prev, { service, username: fields.username, active: true }]
    })
    setCredFields((prev) => ({ ...prev, [service]: { username: fields.username, password: '', saved: true } }))
  } finally {
    setSavingCred(false as unknown as string | null)
    setSavingCred(null)
  }
}

async function handleRemoveCred(service: string) {
  if (!productId) return
  await api.deleteBrowserCredential(password, productId, service)
  setBrowserCreds((prev) => prev.filter((c) => c.service !== service))
  setCredFields((prev) => {
    const next = { ...prev }
    delete next[service]
    return next
  })
}
```

- [ ] **Step 4: Update the service card render**

The current card is a simple `flex items-center justify-between` row. Replace the entire `{SERVICES.map(...)}` block with the new version that supports the toggle. Find the block starting at line 137 (`{SERVICES.map(({ key, label, connectAs }) => {`) and replace through the closing `})}` of the map:

```tsx
{SERVICES.map(({ key, label, connectAs }) => {
  const conn = oauthConnections.find((c) => c.service === key)
  const isConnecting = connectingService === connectAs
  const needsGoogleOAuth = GOOGLE_SERVICES.has(key) && !googleOAuthConfigured
  const isBrowserCapable = BROWSER_CRED_SERVICES.has(key)
  const browserCred = browserCreds.find((c) => c.service === key)
  const isBrowserMode = isBrowserCapable && (browserCred?.active ?? false)
  const fields = credFields[key]

  return (
    <div
      key={key}
      className="bg-adj-panel border border-adj-border rounded-md px-4 py-3 flex flex-col gap-3"
    >
      {/* Header row: label + toggle */}
      <div className="flex items-center justify-between">
        <p className="text-sm text-adj-text-secondary font-medium">{label}</p>
        {isBrowserCapable && (
          <div className="flex rounded overflow-hidden border border-adj-border text-[11px]">
            <button
              onClick={() => handleToggleMode(key, false)}
              className={`px-2.5 py-1 transition-colors ${!isBrowserMode ? 'bg-adj-accent text-white' : 'text-adj-text-muted hover:text-adj-text-secondary'}`}
            >
              OAuth
            </button>
            <button
              onClick={() => handleToggleMode(key, true)}
              className={`px-2.5 py-1 transition-colors ${isBrowserMode ? 'bg-adj-accent text-white' : 'text-adj-text-muted hover:text-adj-text-secondary'}`}
            >
              Browser
            </button>
          </div>
        )}
      </div>

      {/* OAuth mode content */}
      {!isBrowserMode && (
        <div className="flex items-center justify-between">
          <div>
            {conn ? (
              <p className="text-xs text-adj-text-muted">Connected as {conn.email}</p>
            ) : needsGoogleOAuth ? (
              <p className="text-xs text-amber-600">Google OAuth required</p>
            ) : (
              <p className="text-xs text-adj-text-faint">Not connected</p>
            )}
          </div>
          {conn ? (
            <button
              onClick={() => handleDisconnectOAuth(key)}
              className="text-xs text-red-400 hover:text-red-300 hover:underline"
            >
              Disconnect
            </button>
          ) : needsGoogleOAuth ? (
            <span className="text-xs text-adj-text-faint">Configure Google OAuth first</span>
          ) : (
            <button
              onClick={() => handleConnectOAuth(connectAs)}
              disabled={isConnecting}
              className="px-3 py-1.5 text-xs bg-adj-accent hover:bg-adj-accent-dark text-white rounded disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isConnecting ? 'Connecting…' : 'Connect'}
            </button>
          )}
        </div>
      )}

      {/* Browser mode content */}
      {isBrowserMode && (
        <div className="flex flex-col gap-2">
          <input
            type="text"
            placeholder="Username or email"
            value={fields?.username ?? ''}
            onChange={(e) => setCredFields((prev) => ({
              ...prev,
              [key]: { username: e.target.value, password: prev[key]?.password ?? '', saved: false },
            }))}
            className="w-full text-xs bg-adj-bg border border-adj-border rounded px-2.5 py-1.5 text-adj-text-secondary placeholder:text-adj-text-faint focus:outline-none focus:border-adj-accent"
          />
          <input
            type="password"
            placeholder="Password"
            value={fields?.saved ? '••••••••' : (fields?.password ?? '')}
            onFocus={(e) => {
              if (fields?.saved) {
                setCredFields((prev) => ({ ...prev, [key]: { ...prev[key], password: '', saved: false } }))
                e.target.value = ''
              }
            }}
            onChange={(e) => setCredFields((prev) => ({
              ...prev,
              [key]: { username: prev[key]?.username ?? '', password: e.target.value, saved: false },
            }))}
            className="w-full text-xs bg-adj-bg border border-adj-border rounded px-2.5 py-1.5 text-adj-text-secondary placeholder:text-adj-text-faint focus:outline-none focus:border-adj-accent"
          />
          <div className="flex items-center justify-between">
            <button
              onClick={() => handleSaveCred(key)}
              disabled={!fields?.username || savingCred === key}
              className="px-3 py-1.5 text-xs bg-adj-accent hover:bg-adj-accent-dark text-white rounded disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {savingCred === key ? 'Saving…' : fields?.saved ? 'Saved ✓' : 'Save'}
            </button>
            {browserCred && (
              <button
                onClick={() => handleRemoveCred(key)}
                className="text-xs text-red-400 hover:text-red-300 hover:underline"
              >
                Remove credentials
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  )
})}
```

- [ ] **Step 5: TypeScript check**

```bash
cd /home/justin/Code/Adjutant/ui && npx tsc --noEmit
```

Fix any type errors before continuing.

- [ ] **Step 6: Run Python tests to confirm no regressions**

```bash
cd /home/justin/Code/Adjutant && .venv/bin/pytest tests/ -q
```

Expected: all pass

- [ ] **Step 7: Commit**

```bash
cd /home/justin/Code/Adjutant && git add ui/src/components/settings/ConnectionsSettings.tsx && git commit -m "feat: OAuth/Browser toggle + credential form in ConnectionsSettings"
```

---

## Self-Review

**Spec coverage:**
- ✅ `browser_credentials` table with `(product_id, service, username, password, active)` — Task 1
- ✅ `save_browser_credential`, `get_browser_credential`, `delete_browser_credential`, `list_browser_credentials` — Task 1
- ✅ GET list, PUT upsert (with password-preservation when empty), DELETE endpoints — Task 2
- ✅ `_publish_social_draft` checks browser mode first, injects credentials — Task 3
- ✅ API client methods — Task 4
- ✅ OAuth/Browser pill toggle per social service card — Task 5
- ✅ Username plaintext + masked password (`type="password"`) fields — Task 5
- ✅ After save: saved=true shows placeholder dots, password clears on focus — Task 5
- ✅ Remove credentials link — Task 5
- ✅ Toggle switches without deleting credentials (PUT with empty password preserves existing) — Task 2 + Task 5

**Placeholder scan:** None found.

**Type consistency:**
- `save_browser_credential(product_id, service, username, password, active: bool)` — used consistently across db.py, api.py, and test code
- `get_browser_credential` returns `dict | None` — checked with `cred and cred.get("active")` in main.py
- `list_browser_credentials` returns `[{service, username, active}]` — matches API response and TypeScript type `{ service: string; username: string; active: boolean }[]`
- `credFields[key].saved` flag controls whether password field shows placeholder — used consistently in render and handlers
