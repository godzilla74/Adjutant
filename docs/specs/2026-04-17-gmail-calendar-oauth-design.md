# Gmail & Google Calendar — Project-Level OAuth Integration

**Date:** 2026-04-17  
**Status:** Approved

## Problem

Adjutant currently relies on a self-hosted Gmail MCP server (port 8765) that requires custom setup most users cannot replicate. Gmail and Calendar access is global, not per-product. The agent cannot take email or calendar actions autonomously on behalf of a specific product.

## Goal

Each product (RetainerOps, Bullsi, etc.) can independently connect its own Gmail account and Google Calendar. The agent can send email, read inbox, create events, and check availability autonomously using the product's connected account, respecting the product's trust tier settings.

## Approach

Native Google OAuth 2.0 (authorization code flow). Adjutant handles the full flow — no MCP server required. User sets up their own Google Cloud project (documented) and enters their Client ID/Secret into Adjutant's global settings once. Each product then independently connects its own Google account via a one-click OAuth flow.

## Data Model

### Global Settings (extend `agent_config` table)

| Field | Type | Description |
|---|---|---|
| `google_oauth_client_id` | TEXT | From user's Google Cloud project |
| `google_oauth_client_secret` | TEXT | From user's Google Cloud project |

### New Table: `oauth_connections`

| Field | Type | Description |
|---|---|---|
| `id` | INTEGER PK | |
| `product_id` | INTEGER FK | References `products.id` |
| `service` | TEXT | `gmail` or `google_calendar` |
| `email` | TEXT | Connected Google account email |
| `access_token` | TEXT | Short-lived token |
| `refresh_token` | TEXT | Long-lived token for silent refresh |
| `token_expiry` | DATETIME | Checked before every API call |
| `scopes` | TEXT | JSON list of granted OAuth scopes |
| `created_at` | DATETIME | |
| `updated_at` | DATETIME | |

Unique constraint on `(product_id, service)`. Each product has at most one Gmail connection and one Calendar connection, independently.

## OAuth Flow

1. User enters Google OAuth Client ID + Client Secret in **Global Settings → Google OAuth** and saves.
2. In **Product Settings → Connections**, user clicks "Connect Gmail" or "Connect Calendar".
3. Adjutant generates a Google authorization URL with `state={product_id, service}` encoded and opens it in a new browser tab.
4. User completes Google consent screen and grants requested scopes.
5. Google redirects to `GET /api/oauth/callback?code=...&state=...`.
6. Adjutant exchanges the code for `access_token` + `refresh_token` and upserts a row in `oauth_connections`.
7. Product settings UI updates to show "Connected as [email]" with a Disconnect button.

**Redirect URI (must be added to Google Cloud console):** `http://localhost:8000/api/oauth/callback`

**Token refresh:** Before every Gmail/Calendar API call, Adjutant checks `token_expiry`. If expired or within 60 seconds of expiry, it silently refreshes using `refresh_token` and updates the row. No user action required.

## Gmail Scopes

- `https://www.googleapis.com/auth/gmail.send`
- `https://www.googleapis.com/auth/gmail.readonly`
- `https://www.googleapis.com/auth/gmail.compose`

## Calendar Scopes

- `https://www.googleapis.com/auth/calendar`

## Agent Tools

Tools are added to `core/tools.py`. A tool is only included in the agent's tool list if the product has a valid connection for that service — no connection means no tool, preventing confusing failures.

### Gmail Tools

| Tool | Parameters | Description |
|---|---|---|
| `gmail_search` | `query`, `max_results` | Search inbox |
| `gmail_read` | `message_id` | Read a full message or thread |
| `gmail_send` | `to`, `subject`, `body`, `thread_id?` | Send or reply to an email |
| `gmail_draft` | `to`, `subject`, `body` | Create a draft (does not send) |

### Calendar Tools

| Tool | Parameters | Description |
|---|---|---|
| `calendar_list_events` | `start`, `end` | List events in a date range |
| `calendar_create_event` | `title`, `start`, `end`, `attendees?`, `description?` | Create a meeting |
| `calendar_find_free_time` | `date`, `duration_minutes` | Find open time slots |

### Trust Tier Behavior

`gmail_send` and `calendar_create_event` respect the product's autonomy setting:

- **Auto:** Action executes immediately.
- **Window:** Action queued and executes within the approval window.
- **Approve:** Creates a review item in the approval queue; user approves before the action executes.

`gmail_draft` always creates a draft regardless of trust tier — useful when the agent is explicitly asked to compose without sending, distinct from the Approve-tier behavior where `gmail_send` is intercepted and queued for review.

## UI

### Global Settings — new "Google OAuth" section
- Client ID field
- Client Secret field
- Save button
- One-time setup, applies to all products

### Product Settings — new "Connections" tab
- **Gmail row:** "Connect Gmail" button, or "Connected as [email]" + Disconnect button
- **Google Calendar row:** Same pattern
- Connections are independent — Gmail without Calendar (or vice versa) is valid

## Activity Feed & Error Handling

- Autonomous email sends and calendar creates appear in the activity feed with the connected account: "Sent email via retainerops@gmail.com"
- If a token refresh fails (e.g., user revoked access), the failure surfaces as an error review item with a message explaining what happened and a link to reconnect — no silent stalls

## Out of Scope

- Encryption of stored tokens (tokens are in local SQLite, same threat model as existing secrets)
- Multi-account per product (one Gmail + one Calendar per product)
- Google Workspace service accounts
- Removing the existing Gmail MCP server (leave it in place, the new native tools take precedence when a connection exists)
