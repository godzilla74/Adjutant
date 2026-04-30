# Slack & Discord Integration Design

**Date:** 2026-04-30
**Status:** Approved

## Overview

Add Slack and Discord as messaging integrations alongside the existing Telegram bot. Both platforms allow users to @mention the bot in a server channel, receive threaded replies, and interact with review items via inline buttons. A unified "Integrations" UI section (renaming the current "Remote Access") manages all three platforms with per-integration enable/disable toggles and disconnect actions.

## Architecture

Each platform is implemented as an independent bot class mirroring the existing `TelegramBot` pattern — no shared abstraction, no changes to Telegram.

**New files:**
- `backend/slack_bot.py` — `SlackBot` class using `slack_sdk` with Socket Mode (WebSocket, no public URL required)
- `backend/discord_bot.py` — `DiscordBot` class using `discord.py` with Gateway WebSocket
- `backend/slack_state.py` — Hot-reload state mirroring `telegram_state.py`
- `backend/discord_state.py` — Hot-reload state mirroring `telegram_state.py`

Both classes mirror `TelegramBot`'s constructor shape. `SlackBot` takes two token params (`bot_token`, `app_token`); `DiscordBot` takes one (`token`). All other params are identical:
```python
# SlackBot
def __init__(self, bot_token: str, app_token: str, directive_callback, resolve_review_fn, broadcast_fn, on_review_approved_fn=None)

# DiscordBot
def __init__(self, token: str, directive_callback, resolve_review_fn, broadcast_fn, on_review_approved_fn=None)
```

Both implement: `start()`, `send_message()`, `send_long_message()`, `notify()`.

`main.py` instantiates all enabled bots in the lifespan handler. No changes to routing logic — all platforms route to `product_id=None` (global agent).

## Interaction Model

- Users @mention the bot in any channel the bot is a member of
- Bot replies in a thread under the original message (Slack: `thread_ts`; Discord: `message.reply()`)
- Proactive notifications (review items, activity summaries) are sent to a single configured notification channel per platform
- Any channel member may interact with the bot; access control is managed at the platform level by the workspace/server admin

## Message Length Handling

Each bot owns its own `send_long_message()` with platform-specific chunking:

| Platform | Limit | Strategy |
|---|---|---|
| Telegram | 4096 chars | Split into sequential messages (existing) |
| Discord | 2000 chars | Split into sequential messages |
| Slack | 3000 chars per Block Kit text block | Pack multiple blocks into one message payload; no practical per-response limit |

## Feature Parity

All three platforms support:
- Text message routing to global agent
- Review item notifications with Approve/Reject inline buttons
- Typing indicator while agent is processing
- File/attachment handling (forwarded to global agent as attached file reference)
- Activity summary notifications

## Configuration & Storage

New keys in `model_config` table:

| Key | Description |
|---|---|
| `telegram_enabled` | `"true"`/`"false"`, default `"true"` if token exists |
| `slack_bot_token` | `xoxb-...` bot token |
| `slack_app_token` | `xapp-...` app-level token (Socket Mode) |
| `slack_notification_channel_id` | Channel ID for proactive notifications |
| `slack_enabled` | `"true"`/`"false"` |
| `discord_bot_token` | Bot token |
| `discord_notification_channel_id` | Channel ID for proactive notifications |
| `discord_enabled` | `"true"`/`"false"` |

Slack requires two tokens; Discord requires one. Both are validated against their respective APIs before saving.

## API Endpoints

### Slack

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/slack/status` | Connected state, enabled flag, bot username |
| `PUT` | `/api/slack/tokens` | Validate and save both tokens, hot-reload bot |
| `GET` | `/api/slack/channels` | List channels the bot is a member of |
| `PUT` | `/api/slack/notification-channel` | Save notification channel ID |
| `PUT` | `/api/slack/enabled` | Toggle enabled/disabled |
| `DELETE` | `/api/slack` | Wipe all credentials and disable |

### Discord

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/discord/status` | Connected state, enabled flag, bot username |
| `PUT` | `/api/discord/token` | Validate and save token, hot-reload bot |
| `GET` | `/api/discord/channels` | List text channels the bot can see |
| `PUT` | `/api/discord/notification-channel` | Save notification channel ID |
| `PUT` | `/api/discord/enabled` | Toggle enabled/disabled |
| `DELETE` | `/api/discord` | Wipe all credentials and disable |

### Telegram additions

| Method | Path | Description |
|---|---|---|
| `PUT` | `/api/telegram/enabled` | Toggle enabled/disabled (new) |
| `DELETE` | `/api/telegram` | Wipe credentials and disable (new) |

## Frontend UI

The "Remote Access" section is renamed to "Integrations." Each platform is a card with consistent structure:

- **Header**: platform name + logo icon, active/inactive toggle (disabled if not connected), delete/disconnect button
- **Connection status**: bot username and connected state when active; "Not connected" when unconfigured
- **Setup fields**: token input(s), hidden after connection with a "Reconfigure" button to re-show
- **Notification channel**: dropdown populated from `GET /api/{platform}/channels`, visible only once connected
- **Setup guide link**: opens the platform's step-by-step setup document
- **Slack-specific**: two clearly labeled token fields ("Bot Token" and "App-Level Token") with a note that both are required for Socket Mode

Setup flow: enter token(s) → validate → channel selector appears → pick notification channel → save.

## Setup Documentation

Two new setup guides created:

**`docs/slack-setup.md`**
1. Create a Slack App at api.slack.com
2. Enable Socket Mode and generate the App-Level Token (`xapp-...`)
3. Add required bot scopes: `app_mentions:read`, `chat:write`, `channels:read`, `files:read`
4. Install app to workspace and copy the Bot Token (`xoxb-...`)
5. Create a notification channel in Slack, invite the bot (`/invite @botname`)
6. Enter both tokens in Adjutant, select the notification channel

**`docs/discord-setup.md`**
1. Create an application at discord.com/developers
2. Add a Bot, enable Message Content Intent and Server Members Intent
3. Copy the bot token
4. Generate an OAuth2 invite URL with `bot` scope + `Send Messages`, `Read Message History`, `Use Slash Commands` permissions
5. Invite bot to your server
6. Create a notification channel and ensure bot has access
7. Enter token in Adjutant, select the notification channel

## Dependencies

New Python packages required:
- `slack_sdk` — Slack Web API + Socket Mode client
- `discord.py` (or maintained fork `py-cord`) — Discord Gateway WebSocket client

## Testing

Each bot class gets a test file (`tests/test_slack_bot.py`, `tests/test_discord_bot.py`) covering:
- Message routing to global agent
- Thread reply behavior
- Review item approval/rejection via buttons
- Long message chunking at platform-specific limits
- Notification event handling (agent_done, activity_done, review_item_added)
- Enable/disable behavior
