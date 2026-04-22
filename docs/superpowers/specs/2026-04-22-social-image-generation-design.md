# Social Post Image Generation — Design

**Goal:** Let the agent autonomously decide whether to include an image in a social post, and if so, source it either by generating one (OpenAI via Codex OAuth) or searching stock photos (Pexels), without any user intervention.

**Architecture:** Two new agent tools (`generate_image`, `search_stock_photo`) are added to `core/tools.py`. When drafting a social post the agent calls whichever tool is appropriate, receives a URL, and passes it to `draft_social_post` as `image_url`. Generated images are downloaded to local uploads immediately to avoid expiry. Settings for the Pexels API key and OpenAI access token are stored in the existing `settings` table and surfaced in a new Global settings section.

---

## Tools — `core/tools.py`

### `generate_image(prompt: str) -> str`

Calls the OpenAI Images API using the stored access token. Downloads the resulting image to the local uploads directory (`~/.local/share/Adjutant/uploads/` on Linux, `~/Library/Application Support/Adjutant/uploads/` on macOS). Returns a `http://localhost:{port}/uploads/{filename}` URL served by the existing backend.

Rationale for downloading immediately: OpenAI image URLs expire in ~1 hour. Downloading on generation gives a stable local URL for the browser agent to use at post time.

**Limitation:** The local URL is accessible to the browser agent (which runs locally) but not to remote social platform servers. This means `generate_image` works for all browser-mode platforms but not for OAuth API posting. Stock photo URLs (Pexels CDN) are always public and work for both paths. A future improvement could upload generated images to Cloudinary or Imgur for a public URL.

```python
async def _generate_image(prompt: str) -> str:
    # GET /settings openai_access_token
    # POST https://api.openai.com/v1/images/generations
    #   Authorization: Bearer {token}
    #   {"prompt": prompt, "model": "dall-e-3", "n": 1, "size": "1024x1024"}
    # Download image bytes → save to uploads dir with timestamp prefix
    # Return localhost URL
```

### `search_stock_photo(query: str) -> str`

Calls the Pexels API (`https://api.pexels.com/v1/search`) with the stored API key. Returns the URL of the first result's `large2x` photo variant — a stable Pexels CDN URL usable by both browser-mode and OAuth API posting.

```python
async def _search_stock_photo(query: str) -> str:
    # GET /settings pexels_api_key
    # GET https://api.pexels.com/v1/search?query={query}&per_page=1
    #   Authorization: {api_key}
    # Return photos[0].src.large2x
```

Both tools are added to the tool schema list and the `execute_tool` dispatcher. They are included in the tool list for product agents (not global-only).

---

## Settings

### New settings keys

| Key | Description |
|---|---|
| `openai_access_token` | Access token from Codex OAuth flow |
| `pexels_api_key` | Pexels API key (free, from pexels.com/api) |

Stored in the existing `settings` table via `get_setting` / `save_setting` (already used for `agent_model`, Google OAuth keys, etc.).

### Codex OAuth flow — `backend/api.py`

Mirrors the existing Google OAuth pattern. The flow is PKCE (`S256`) and produces an OpenAI API key tied to the user's ChatGPT account, which is then used with the standard OpenAI Images API.

**Constants (from openai/codex source):**
- Client ID: `app_EMoamEEZ73f0CkXaXp7hrann`
- Issuer: `https://auth.openai.com`
- Scopes: `openid profile email offline_access api.connectors.read api.connectors.invoke`
- Redirect URI: `http://localhost:{ADJUTANT_PORT}/api/openai-oauth/callback`

**Step 1 — `GET /api/openai-oauth/start`**

Backend generates a PKCE pair (`code_verifier`, `code_challenge` via SHA-256), stores `code_verifier` in memory, and returns:
```json
{"auth_url": "https://auth.openai.com/oauth/authorize?response_type=code&client_id=app_EMoamEEZ73f0CkXaXp7hrann&redirect_uri=...&scope=...&code_challenge=...&code_challenge_method=S256"}
```
Frontend opens the URL in a popup.

**Step 2 — `GET /api/openai-oauth/callback?code=...`**

Backend POSTs to `https://auth.openai.com/oauth/token`:
```
grant_type=authorization_code&code={code}&redirect_uri={uri}&client_id={client_id}&code_verifier={verifier}
```
Returns `id_token`, `access_token`, `refresh_token`.

Then exchanges `id_token` for an OpenAI API key via a second POST to `https://auth.openai.com/oauth/token`:
```
grant_type=urn:ietf:params:oauth:grant-type:token-exchange
&client_id={client_id}
&requested_token=openai-api-key
&subject_token={id_token}
&subject_token_type=urn:ietf:params:oauth:token-type:id_token
```
Returns `access_token` — this is the actual OpenAI API key. Stored via `save_setting("openai_access_token", token)`. Also store `refresh_token` as `openai_refresh_token` for future token refresh.

Callback responds with an HTML page that posts a message to the opener and closes itself (same pattern as Google OAuth callback).

**Step 3 — `GET /api/openai-oauth/status`**

Returns `{"connected": bool}` based on whether `openai_access_token` is set.

**Step 4 — `DELETE /api/openai-oauth/disconnect`**

Clears both `openai_access_token` and `openai_refresh_token` from settings.

---

## UI — Global Settings

A new **"Image Generation"** card is added to the Global settings sidebar (alongside Agent Model, Google OAuth, Remote Access, MCP Servers).

### Card contents

**Pexels (Stock Photos)**
- Text input: "Pexels API key" — paste from pexels.com/api
- Save button
- Status line: "Connected" / "Not configured"

**OpenAI Image Generation**
- "Connect with OpenAI" button — opens OAuth popup (same pattern as Google OAuth)
- Status line: "Connected" / "Not connected"
- Disconnect link when connected

---

## Agent System Prompt — `core/config.py`

A short addition to the product agent system prompt:

```
**Image tools (use when drafting social posts):**
- **generate_image** — Generate a custom image from a text prompt (abstract visuals, branded graphics, illustrations). Uses OpenAI image generation.
- **search_stock_photo** — Find a relevant real photograph from Pexels (news, lifestyle, people, places). Returns a stable public URL.

When drafting a social post, consider whether an image would increase engagement or clarity. If so, call the appropriate tool before `draft_social_post` and pass the returned URL as `image_url`. Use `generate_image` for abstract or branded content; use `search_stock_photo` for topic-based or real-world content. If neither key is configured, skip image sourcing silently.
```

---

## Error Handling

- If `openai_access_token` is not set, `generate_image` returns an error string: `"Image generation not configured — add an OpenAI access token in Global settings."`
- If `pexels_api_key` is not set, `search_stock_photo` returns: `"Stock photo search not configured — add a Pexels API key in Global settings."`
- If the API call fails (network error, bad token, rate limit), the tool returns a descriptive error string. The agent should gracefully draft the post without an image rather than failing entirely.
- If the image download fails in `generate_image`, return an error string rather than a broken URL.

---

## What Is Not In Scope

- Uploading generated images to a public host (Cloudinary, Imgur) — left as a future improvement
- Image editing or resizing
- Video generation
- Per-product image style preferences
- Automatic retry with a different source if the first tool fails
