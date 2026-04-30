# Slack & Discord Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Slack and Discord as messaging integrations with full feature parity to Telegram, and refactor the "Remote Access" settings section into a unified "Integrations" section with per-platform enable/disable/delete controls.

**Architecture:** Independent `SlackBot` and `DiscordBot` classes mirror the existing `TelegramBot` pattern with identical constructor shapes and `notify()` interface. `main.py` instantiates all enabled bots in the lifespan handler; `_broadcast` notifies all three. Frontend replaces `RemoteAccessSettings.tsx` with `IntegrationsSettings.tsx` composed of three platform cards.

**Tech Stack:** Python `slack_sdk` (Socket Mode + AsyncWebClient), `discord.py` 2.x (Gateway WebSocket), React/TypeScript frontend following existing adj-* Tailwind patterns.

---

## File Map

**Create:**
- `backend/slack_bot.py` — `SlackBot` class
- `backend/discord_bot.py` — `DiscordBot` class
- `backend/slack_state.py` — hot-reload state for Slack
- `backend/discord_state.py` — hot-reload state for Discord
- `tests/test_slack_bot.py` — SlackBot unit tests
- `tests/test_discord_bot.py` — DiscordBot unit tests
- `ui/src/components/settings/integrations/TelegramCard.tsx`
- `ui/src/components/settings/integrations/SlackCard.tsx`
- `ui/src/components/settings/integrations/DiscordCard.tsx`
- `ui/src/components/settings/IntegrationsSettings.tsx`
- `docs/slack-setup.md`
- `docs/discord-setup.md`

**Modify:**
- `requirements.txt` — add `slack_sdk`, `discord.py`
- `backend/api.py` — add Telegram enable/delete + all Slack/Discord endpoints
- `backend/main.py` — wire Slack/Discord bots in lifespan, update `_broadcast`
- `ui/src/api.ts` — add Slack/Discord/Telegram-enable API calls
- `ui/src/components/SettingsPage.tsx` — rename section, swap component

**Delete:**
- `ui/src/components/settings/RemoteAccessSettings.tsx`

---

## Task 1: Add Python dependencies

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add packages to requirements.txt**

Open `requirements.txt` and add these two lines after the `httpx` entry:

```
slack_sdk>=3.27.0
discord.py>=2.3.0
```

- [ ] **Step 2: Install dependencies**

```bash
pip install slack_sdk "discord.py>=2.3.0"
```

Expected: both packages install without errors.

- [ ] **Step 3: Verify imports work**

```bash
python -c "from slack_sdk.web.async_client import AsyncWebClient; import discord; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add requirements.txt
git commit -m "chore: add slack_sdk and discord.py dependencies"
```

---

## Task 2: Create state modules

**Files:**
- Create: `backend/slack_state.py`
- Create: `backend/discord_state.py`

These mirror `backend/telegram_state.py` exactly, with different parameter types.

- [ ] **Step 1: Create slack_state.py**

```python
# backend/slack_state.py
"""Shared state for hot-reloading the Slack bot without circular imports."""
from typing import Callable, Awaitable

_restarter: Callable[[str, str], Awaitable[None]] | None = None


def register(fn: Callable[[str, str], Awaitable[None]]) -> None:
    global _restarter
    _restarter = fn


async def restart(bot_token: str, app_token: str) -> None:
    if _restarter is not None:
        await _restarter(bot_token, app_token)
```

- [ ] **Step 2: Create discord_state.py**

```python
# backend/discord_state.py
"""Shared state for hot-reloading the Discord bot without circular imports."""
from typing import Callable, Awaitable

_restarter: Callable[[str], Awaitable[None]] | None = None


def register(fn: Callable[[str], Awaitable[None]]) -> None:
    global _restarter
    _restarter = fn


async def restart(token: str) -> None:
    if _restarter is not None:
        await _restarter(token)
```

- [ ] **Step 3: Commit**

```bash
git add backend/slack_state.py backend/discord_state.py
git commit -m "feat: add slack and discord hot-reload state modules"
```

---

## Task 3: SlackBot — write failing tests

**Files:**
- Create: `tests/test_slack_bot.py`

- [ ] **Step 1: Write the test file**

```python
# tests/test_slack_bot.py
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.slack_bot import SlackBot


def _make_bot(notification_channel_id="C_NOTIF"):
    bot = SlackBot(
        bot_token="xoxb-test",
        app_token="xapp-test",
        notification_channel_id=notification_channel_id,
        directive_callback=AsyncMock(),
        resolve_review_fn=MagicMock(),
        broadcast_fn=AsyncMock(),
    )
    bot._bot_user_id = "U12345"
    bot._web_client = MagicMock()
    bot._web_client.chat_postMessage = AsyncMock(return_value={"ok": True, "ts": "1234.5678"})
    bot._web_client.chat_update = AsyncMock(return_value={"ok": True})
    return bot


# ── notify ────────────────────────────────────────────────────────────────────

def test_notify_agent_done_sends_to_pending_channel():
    bot = _make_bot()
    bot._pending_products[None] = ("C12345", "1617000000.001")
    asyncio.run(bot.notify({"type": "agent_done", "product_id": None, "content": "Done!"}))
    bot._web_client.chat_postMessage.assert_awaited_once()
    call_kwargs = bot._web_client.chat_postMessage.call_args.kwargs
    assert call_kwargs["channel"] == "C12345"
    assert call_kwargs["thread_ts"] == "1617000000.001"
    assert None not in bot._pending_products


def test_notify_agent_done_ignores_non_pending():
    bot = _make_bot()
    asyncio.run(bot.notify({"type": "agent_done", "product_id": None, "content": "Done!"}))
    bot._web_client.chat_postMessage.assert_not_awaited()


def test_notify_activity_done_sends_to_notification_channel():
    bot = _make_bot()
    asyncio.run(bot.notify({"type": "activity_done", "summary": "Research done"}))
    bot._web_client.chat_postMessage.assert_awaited_once()
    call_kwargs = bot._web_client.chat_postMessage.call_args.kwargs
    assert call_kwargs["channel"] == "C_NOTIF"


def test_notify_review_item_sends_buttons_to_notification_channel():
    bot = _make_bot()
    item = {"id": 42, "title": "Email to client", "description": "Send invoice.", "risk_label": "financial"}
    asyncio.run(bot.notify({"type": "review_item_added", "item": item}))
    bot._web_client.chat_postMessage.assert_awaited_once()
    call_kwargs = bot._web_client.chat_postMessage.call_args.kwargs
    assert call_kwargs["channel"] == "C_NOTIF"
    blocks = call_kwargs.get("blocks", [])
    actions_block = next((b for b in blocks if b.get("type") == "actions"), None)
    assert actions_block is not None
    action_ids = [e.get("action_id") for e in actions_block.get("elements", [])]
    assert "approve:42" in action_ids
    assert "reject:42" in action_ids


def test_notify_skips_review_if_no_notification_channel():
    bot = _make_bot(notification_channel_id="")
    item = {"id": 1, "title": "T", "description": "D", "risk_label": ""}
    asyncio.run(bot.notify({"type": "review_item_added", "item": item}))
    bot._web_client.chat_postMessage.assert_not_awaited()


# ── _handle_event ─────────────────────────────────────────────────────────────

def test_handle_event_app_mention_routes_to_global_agent():
    bot = _make_bot()
    payload = {
        "type": "event_callback",
        "event": {
            "type": "app_mention",
            "text": "<@U12345> hello world",
            "user": "U67890",
            "ts": "1617000000.001",
            "channel": "C12345",
        },
    }
    asyncio.run(bot._process_event_payload(payload))
    bot._directive_callback.assert_awaited_once_with(None, "hello world")
    assert None in bot._pending_products
    assert bot._pending_products[None] == ("C12345", "1617000000.001")


def test_handle_event_strips_mention_from_text():
    bot = _make_bot()
    payload = {
        "type": "event_callback",
        "event": {
            "type": "app_mention",
            "text": "<@U12345>   update me on sales",
            "user": "U67890",
            "ts": "1617000000.002",
            "channel": "C12345",
        },
    }
    asyncio.run(bot._process_event_payload(payload))
    bot._directive_callback.assert_awaited_once_with(None, "update me on sales")


def test_handle_event_empty_text_after_mention_ignored():
    bot = _make_bot()
    payload = {
        "type": "event_callback",
        "event": {
            "type": "app_mention",
            "text": "<@U12345>   ",
            "user": "U67890",
            "ts": "1617000000.003",
            "channel": "C12345",
        },
    }
    asyncio.run(bot._process_event_payload(payload))
    bot._directive_callback.assert_not_awaited()


# ── _handle_block_actions ─────────────────────────────────────────────────────

def test_handle_block_actions_approve():
    bot = _make_bot()
    payload = {
        "type": "block_actions",
        "actions": [{"action_id": "approve:42", "value": "42"}],
        "message": {"ts": "1617000000.001"},
        "channel": {"id": "C_NOTIF"},
    }
    asyncio.run(bot._process_event_payload(payload))
    bot.resolve_review_fn.assert_called_once_with(42, "approved")
    bot.broadcast_fn.assert_awaited_once()


def test_handle_block_actions_reject():
    bot = _make_bot()
    payload = {
        "type": "block_actions",
        "actions": [{"action_id": "reject:42", "value": "42"}],
        "message": {"ts": "1617000000.001"},
        "channel": {"id": "C_NOTIF"},
    }
    asyncio.run(bot._process_event_payload(payload))
    bot.resolve_review_fn.assert_called_once_with(42, "skipped")


# ── send_long_message ─────────────────────────────────────────────────────────

def test_send_long_message_short_text_single_block():
    bot = _make_bot()
    asyncio.run(bot.send_long_message("C12345", "Hello!", thread_ts="1234.5"))
    bot._web_client.chat_postMessage.assert_awaited_once()
    kwargs = bot._web_client.chat_postMessage.call_args.kwargs
    assert kwargs["thread_ts"] == "1234.5"
    assert len(kwargs["blocks"]) == 1
    assert kwargs["blocks"][0]["text"]["text"] == "Hello!"


def test_send_long_message_long_text_multiple_blocks_single_call():
    bot = _make_bot()
    chunk_a = "A" * 2500
    chunk_b = "B" * 2500
    long_text = chunk_a + "\n\n" + chunk_b
    asyncio.run(bot.send_long_message("C12345", long_text))
    # All blocks sent in ONE chat_postMessage call
    bot._web_client.chat_postMessage.assert_awaited_once()
    kwargs = bot._web_client.chat_postMessage.call_args.kwargs
    assert len(kwargs["blocks"]) == 2
    assert kwargs["blocks"][0]["text"]["text"] == chunk_a
    assert kwargs["blocks"][1]["text"]["text"] == chunk_b


def test_send_long_message_hard_splits_at_3000():
    bot = _make_bot()
    long_text = "X" * 7000
    asyncio.run(bot.send_long_message("C12345", long_text))
    bot._web_client.chat_postMessage.assert_awaited_once()
    kwargs = bot._web_client.chat_postMessage.call_args.kwargs
    for block in kwargs["blocks"]:
        assert len(block["text"]["text"]) <= 3000
```

- [ ] **Step 2: Run to confirm all tests fail**

```bash
cd /home/justin/Code/Adjutant && python -m pytest tests/test_slack_bot.py -v 2>&1 | head -30
```

Expected: `ModuleNotFoundError: No module named 'backend.slack_bot'` or similar import error.

---

## Task 4: SlackBot — implement to pass tests

**Files:**
- Create: `backend/slack_bot.py`

- [ ] **Step 1: Create the implementation**

```python
# backend/slack_bot.py
"""Slack bot integration — Socket Mode, @mention routing, review item approval."""
import asyncio
import logging
import mimetypes
import re
from typing import Callable, Awaitable

import httpx

logger = logging.getLogger(__name__)


class SlackBot:
    _MAX_BLOCK_LEN = 3000

    def __init__(
        self,
        bot_token: str,
        app_token: str,
        notification_channel_id: str,
        directive_callback: Callable[[str | None, str], Awaitable[None]],
        resolve_review_fn: Callable[[int, str], None],
        broadcast_fn: Callable[[dict], Awaitable[None]],
        on_review_approved_fn: Callable[[int], Awaitable[None]] | None = None,
    ):
        self.bot_token = bot_token
        self.app_token = app_token
        self.notification_channel_id = notification_channel_id
        self._directive_callback = directive_callback
        self.resolve_review_fn = resolve_review_fn
        self.broadcast_fn = broadcast_fn
        self._on_review_approved_fn = on_review_approved_fn
        self._pending_products: dict[str | None, tuple[str, str]] = {}
        self._bot_user_id: str | None = None

        from slack_sdk.web.async_client import AsyncWebClient
        self._web_client = AsyncWebClient(token=bot_token)

    async def send_long_message(self, channel: str, text: str, thread_ts: str | None = None) -> None:
        """Send text as Block Kit blocks in a single chat_postMessage call."""
        blocks = []
        remaining = text
        while remaining:
            if len(remaining) <= self._MAX_BLOCK_LEN:
                blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": remaining}})
                break
            split_at = remaining.rfind('\n\n', 0, self._MAX_BLOCK_LEN)
            if split_at == -1:
                split_at = remaining.rfind('\n', 0, self._MAX_BLOCK_LEN)
            if split_at == -1:
                split_at = self._MAX_BLOCK_LEN
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": remaining[:split_at].rstrip()}})
            remaining = remaining[split_at:].lstrip()

        try:
            await self._web_client.chat_postMessage(
                channel=channel,
                text=text[:200],
                blocks=blocks,
                thread_ts=thread_ts,
            )
        except Exception as e:
            logger.warning("Slack send_long_message failed: %s", e)

    async def notify(self, event: dict) -> None:
        """Forward relevant backend events to Slack."""
        event_type = event.get("type")
        product_id = event.get("product_id")

        if event_type == "agent_done":
            if product_id in self._pending_products:
                channel, thread_ts = self._pending_products.pop(product_id)
                content = event.get("content", "")
                if content:
                    await self.send_long_message(channel, content, thread_ts=thread_ts)

        elif event_type == "activity_done":
            if not self.notification_channel_id:
                return
            workstream_name = event.get("workstream_name", "")
            if workstream_name:
                msg = f"✅ {workstream_name} complete. View the full report in Adjutant under Reports."
            else:
                summary = event.get("summary", "")
                msg = f"✅ Agent finished: {summary[:400]}" if summary else ""
            if msg:
                try:
                    await self._web_client.chat_postMessage(
                        channel=self.notification_channel_id,
                        text=msg,
                    )
                except Exception as e:
                    logger.warning("Slack notify activity_done failed: %s", e)

        elif event_type == "review_item_added":
            item = event.get("item", {})
            await self._send_review_item(item)

    async def _send_review_item(self, item: dict) -> None:
        if not self.notification_channel_id:
            return
        item_id = item.get("id")
        title = item.get("title", "Review item")
        description = item.get("description", "")
        risk_label = item.get("risk_label", "")

        text = f"*📋 Review Required*\n\n*{title}*"
        if risk_label:
            text += f"\n\n⚠️ {risk_label}"
        if description:
            text += f"\n\n{description}"
        if len(text) > self._MAX_BLOCK_LEN:
            text = text[:self._MAX_BLOCK_LEN - 3] + "…"

        blocks = [
            {"type": "section", "text": {"type": "mrkdwn", "text": text}},
            {
                "type": "actions",
                "block_id": f"review_{item_id}",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "✅ Approve"},
                        "style": "primary",
                        "action_id": f"approve:{item_id}",
                        "value": str(item_id),
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "❌ Reject"},
                        "style": "danger",
                        "action_id": f"reject:{item_id}",
                        "value": str(item_id),
                    },
                ],
            },
        ]
        try:
            await self._web_client.chat_postMessage(
                channel=self.notification_channel_id,
                text=f"Review Required: {title}",
                blocks=blocks,
            )
        except Exception as e:
            logger.warning("Slack _send_review_item failed: %s", e)

    async def _process_event_payload(self, payload: dict) -> None:
        """Dispatch a decoded Socket Mode payload to the appropriate handler."""
        payload_type = payload.get("type")
        if payload_type == "event_callback":
            await self._handle_event(payload)
        elif payload_type == "block_actions":
            await self._handle_block_actions(payload)

    async def _handle_event(self, payload: dict) -> None:
        event = payload.get("event", {})
        if event.get("type") != "app_mention":
            return

        raw_text = event.get("text", "")
        text = re.sub(r'<@[A-Z0-9]+>\s*', '', raw_text).strip()

        channel = event.get("channel", "")
        thread_ts = event.get("thread_ts") or event.get("ts", "")

        file_ref: str | None = None
        for f in event.get("files", []):
            url = f.get("url_private_download") or f.get("url_private")
            if url:
                try:
                    local_path, mime = await self._download_slack_file(url)
                    file_ref = f"[Attached file: {local_path} ({mime})]"
                    break
                except Exception:
                    pass

        if not text and not file_ref:
            return

        parts = [p for p in [file_ref, text] if p]
        directive_text = "\n\n".join(parts)

        self._pending_products[None] = (channel, thread_ts)
        await self._directive_callback(None, directive_text)

    async def _handle_block_actions(self, payload: dict) -> None:
        actions = payload.get("actions", [])
        if not actions:
            return
        action_id = actions[0].get("action_id", "")
        if ":" not in action_id:
            return
        action_str, item_id_str = action_id.split(":", 1)
        try:
            item_id = int(item_id_str)
        except ValueError:
            return

        channel_id = payload.get("channel", {}).get("id", "")
        msg_ts = payload.get("message", {}).get("ts")

        if action_str == "approve":
            self.resolve_review_fn(item_id, "approved")
            await self.broadcast_fn({"type": "review_resolved", "review_item_id": item_id, "action": "approved"})
            if msg_ts and channel_id:
                try:
                    await self._web_client.chat_update(
                        channel=channel_id, ts=msg_ts, text="✅ Approved", blocks=[]
                    )
                except Exception:
                    pass
            if self._on_review_approved_fn:
                await self._on_review_approved_fn(item_id)
        elif action_str == "reject":
            self.resolve_review_fn(item_id, "skipped")
            await self.broadcast_fn({"type": "review_resolved", "review_item_id": item_id, "action": "skipped"})
            if msg_ts and channel_id:
                try:
                    await self._web_client.chat_update(
                        channel=channel_id, ts=msg_ts, text="❌ Rejected", blocks=[]
                    )
                except Exception:
                    pass

    async def _download_slack_file(self, url: str) -> tuple[str, str]:
        from backend.uploads import save_uploaded_file
        filename = url.split("/")[-1].split("?")[0] or "slack_file"
        mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        async with httpx.AsyncClient(
            headers={"Authorization": f"Bearer {self.bot_token}"}, timeout=60
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
        local_path = save_uploaded_file(filename, resp.content)
        return str(local_path), mime

    async def start(self) -> None:
        """Connect via Slack Socket Mode and process events."""
        if not self.bot_token or not self.app_token:
            logger.info("Slack not configured — disabled")
            return

        from slack_sdk.socket_mode.websockets import SocketModeClient
        from slack_sdk.socket_mode.request import SocketModeRequest
        from slack_sdk.socket_mode.response import SocketModeResponse

        try:
            auth = await self._web_client.auth_test()
            self._bot_user_id = auth.get("user_id")
        except Exception as e:
            logger.warning("Slack auth_test failed: %s", e)
            return

        async def _handler(sm_client: SocketModeClient, req: SocketModeRequest) -> None:
            await sm_client.send_socket_mode_response(
                SocketModeResponse(envelope_id=req.envelope_id)
            )
            try:
                await self._process_event_payload(req.payload)
            except Exception as exc:
                logger.warning("Slack event handler error: %s", exc)

        sm_client = SocketModeClient(
            app_token=self.app_token,
            web_client=self._web_client,
        )
        sm_client.socket_mode_request_listeners.append(_handler)

        try:
            await sm_client.connect()
            logger.info("Slack Socket Mode connected as %s", self._bot_user_id)
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            try:
                await sm_client.disconnect()
            except Exception:
                pass
            raise
        except Exception as e:
            logger.warning("Slack Socket Mode error: %s", e)
            await asyncio.sleep(5)
```

- [ ] **Step 2: Run tests**

```bash
cd /home/justin/Code/Adjutant && python -m pytest tests/test_slack_bot.py -v
```

Expected: all tests pass.

- [ ] **Step 3: Commit**

```bash
git add backend/slack_bot.py tests/test_slack_bot.py
git commit -m "feat: implement SlackBot with Socket Mode and review button support"
```

---

## Task 5: DiscordBot — write failing tests

**Files:**
- Create: `tests/test_discord_bot.py`

- [ ] **Step 1: Write the test file**

```python
# tests/test_discord_bot.py
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.discord_bot import DiscordBot


def _make_bot(notification_channel_id=999):
    bot = DiscordBot(
        token="test-token",
        notification_channel_id=notification_channel_id,
        directive_callback=AsyncMock(),
        resolve_review_fn=MagicMock(),
        broadcast_fn=AsyncMock(),
    )
    bot._bot_user_id = 12345
    return bot


def _make_message(content="<@12345> hello", author_id=67890, channel_id=111, ts="1617000000"):
    msg = MagicMock()
    msg.content = content
    msg.author = MagicMock()
    msg.author.bot = False
    msg.author.id = author_id
    msg.channel = MagicMock()
    msg.channel.id = channel_id
    msg.id = ts
    thread = MagicMock()
    thread.send = AsyncMock()
    msg.create_thread = AsyncMock(return_value=thread)
    msg.reply = AsyncMock()
    return msg, thread


def _make_interaction(custom_id="approve:42"):
    interaction = MagicMock()
    interaction.type = MagicMock()
    interaction.type.value = 3  # component
    interaction.data = {"custom_id": custom_id}
    interaction.response = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.edit_original_response = AsyncMock()
    return interaction


# ── _on_message ───────────────────────────────────────────────────────────────

def test_on_message_routes_to_global_agent():
    bot = _make_bot()
    bot._client = MagicMock()
    bot._client.user.id = 12345
    msg, thread = _make_message("<@12345> hello world")
    # Simulate mentioned_in returning True
    bot._client.user = MagicMock()

    asyncio.run(bot._on_message(msg))
    bot._directive_callback.assert_awaited_once()
    args = bot._directive_callback.call_args[0]
    assert args[0] is None
    assert "hello world" in args[1]


def test_on_message_strips_mention_from_text():
    bot = _make_bot()
    bot._client = MagicMock()
    msg, thread = _make_message("<@12345>   update me on sales")
    asyncio.run(bot._on_message(msg))
    args = bot._directive_callback.call_args[0]
    assert args[1] == "update me on sales"


def test_on_message_bot_author_ignored():
    bot = _make_bot()
    bot._client = MagicMock()
    msg, _ = _make_message()
    msg.author.bot = True
    asyncio.run(bot._on_message(msg))
    bot._directive_callback.assert_not_awaited()


def test_on_message_empty_text_ignored():
    bot = _make_bot()
    bot._client = MagicMock()
    msg, _ = _make_message("<@12345>   ")
    asyncio.run(bot._on_message(msg))
    bot._directive_callback.assert_not_awaited()


def test_on_message_creates_thread_for_reply():
    bot = _make_bot()
    bot._client = MagicMock()
    msg, thread = _make_message("<@12345> do something")
    asyncio.run(bot._on_message(msg))
    msg.create_thread.assert_awaited_once()
    assert bot._pending_products[None] is thread


# ── _on_interaction ───────────────────────────────────────────────────────────

def test_on_interaction_approve():
    bot = _make_bot()
    interaction = _make_interaction("approve:42")
    asyncio.run(bot._on_interaction(interaction))
    bot.resolve_review_fn.assert_called_once_with(42, "approved")
    bot.broadcast_fn.assert_awaited_once()
    interaction.edit_original_response.assert_awaited_once()


def test_on_interaction_reject():
    bot = _make_bot()
    interaction = _make_interaction("reject:42")
    asyncio.run(bot._on_interaction(interaction))
    bot.resolve_review_fn.assert_called_once_with(42, "skipped")


def test_on_interaction_invalid_custom_id_ignored():
    bot = _make_bot()
    interaction = _make_interaction("no_colon_here")
    asyncio.run(bot._on_interaction(interaction))
    bot.resolve_review_fn.assert_not_called()


# ── notify ────────────────────────────────────────────────────────────────────

def test_notify_agent_done_sends_to_pending_thread():
    bot = _make_bot()
    thread = MagicMock()
    thread.send = AsyncMock()
    bot._pending_products[None] = thread
    asyncio.run(bot.notify({"type": "agent_done", "product_id": None, "content": "Done!"}))
    thread.send.assert_awaited()
    assert None not in bot._pending_products


def test_notify_agent_done_ignores_non_pending():
    bot = _make_bot()
    asyncio.run(bot.notify({"type": "agent_done", "product_id": None, "content": "Done!"}))
    # No error, nothing sent


def test_notify_review_item_skips_if_no_notification_channel():
    bot = _make_bot(notification_channel_id=0)
    item = {"id": 1, "title": "T", "description": "D", "risk_label": ""}
    asyncio.run(bot.notify({"type": "review_item_added", "item": item}))
    # Should not raise; no channel to send to


# ── send_long_message ─────────────────────────────────────────────────────────

def test_send_long_message_short_text_single_send():
    bot = _make_bot()
    target = MagicMock()
    target.send = AsyncMock()
    asyncio.run(bot.send_long_message(target, "Hello!"))
    target.send.assert_awaited_once_with("Hello!")


def test_send_long_message_splits_at_2000():
    bot = _make_bot()
    target = MagicMock()
    target.send = AsyncMock()
    chunk_a = "A" * 1800
    chunk_b = "B" * 1800
    long_text = chunk_a + "\n\n" + chunk_b
    asyncio.run(bot.send_long_message(target, long_text))
    assert target.send.await_count == 2
    first_text = target.send.call_args_list[0][0][0]
    assert first_text == chunk_a


def test_send_long_message_hard_splits_at_2000():
    bot = _make_bot()
    target = MagicMock()
    target.send = AsyncMock()
    long_text = "X" * 5000
    asyncio.run(bot.send_long_message(target, long_text))
    assert target.send.await_count == 3  # 2000 + 2000 + 1000
    for call in target.send.call_args_list:
        assert len(call[0][0]) <= 2000
```

- [ ] **Step 2: Run to confirm tests fail**

```bash
cd /home/justin/Code/Adjutant && python -m pytest tests/test_discord_bot.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'backend.discord_bot'`

---

## Task 6: DiscordBot — implement to pass tests

**Files:**
- Create: `backend/discord_bot.py`

- [ ] **Step 1: Create the implementation**

```python
# backend/discord_bot.py
"""Discord bot integration — Gateway WebSocket, @mention routing, review button handling."""
import asyncio
import logging
import mimetypes
import re
from typing import Callable, Awaitable

import httpx

logger = logging.getLogger(__name__)

_DISCORD_INTERACTION_COMPONENT = 3


class DiscordBot:
    _MAX_LEN = 2000

    def __init__(
        self,
        token: str,
        notification_channel_id: int,
        directive_callback: Callable[[str | None, str], Awaitable[None]],
        resolve_review_fn: Callable[[int, str], None],
        broadcast_fn: Callable[[dict], Awaitable[None]],
        on_review_approved_fn: Callable[[int], Awaitable[None]] | None = None,
    ):
        self._token = token
        self.notification_channel_id = notification_channel_id
        self._directive_callback = directive_callback
        self.resolve_review_fn = resolve_review_fn
        self.broadcast_fn = broadcast_fn
        self._on_review_approved_fn = on_review_approved_fn
        self._pending_products: dict[str | None, object] = {}
        self._bot_user_id: int | None = None
        self._client = None

    async def send_long_message(self, target, text: str) -> None:
        """Send text to a discord Messageable, splitting at 2000-char limit."""
        if len(text) <= self._MAX_LEN:
            await target.send(text)
            return
        remaining = text
        while remaining:
            if len(remaining) <= self._MAX_LEN:
                await target.send(remaining)
                break
            split_at = remaining.rfind('\n\n', 0, self._MAX_LEN)
            if split_at == -1:
                split_at = remaining.rfind('\n', 0, self._MAX_LEN)
            if split_at == -1:
                split_at = self._MAX_LEN
            await target.send(remaining[:split_at].rstrip())
            remaining = remaining[split_at:].lstrip()

    async def notify(self, event: dict) -> None:
        """Forward relevant backend events to Discord."""
        event_type = event.get("type")
        product_id = event.get("product_id")

        if event_type == "agent_done":
            if product_id in self._pending_products:
                thread = self._pending_products.pop(product_id)
                content = event.get("content", "")
                if content:
                    try:
                        await self.send_long_message(thread, content)
                    except Exception as e:
                        logger.warning("Discord notify agent_done failed: %s", e)

        elif event_type == "activity_done":
            if not self.notification_channel_id or not self._client:
                return
            try:
                channel = self._client.get_channel(self.notification_channel_id)
                if channel is None:
                    channel = await self._client.fetch_channel(self.notification_channel_id)
                workstream_name = event.get("workstream_name", "")
                if workstream_name:
                    msg = f"✅ {workstream_name} complete. View the full report in Adjutant under Reports."
                else:
                    summary = event.get("summary", "")
                    msg = f"✅ Agent finished: {summary[:400]}" if summary else ""
                if msg:
                    await channel.send(msg)
            except Exception as e:
                logger.warning("Discord notify activity_done failed: %s", e)

        elif event_type == "review_item_added":
            item = event.get("item", {})
            await self._send_review_item(item)

    async def _send_review_item(self, item: dict) -> None:
        if not self.notification_channel_id or not self._client:
            return
        import discord as _discord

        item_id = item.get("id")
        title = item.get("title", "Review item")
        description = item.get("description", "")
        risk_label = item.get("risk_label", "")

        text = f"📋 **Review Required**\n\n**{title}**"
        if risk_label:
            text += f"\n\n⚠️ {risk_label}"
        if description:
            text += f"\n\n{description}"
        if len(text) > self._MAX_LEN:
            text = text[:self._MAX_LEN - 3] + "…"

        class ReviewView(_discord.ui.View):
            def __init__(self_view):
                super().__init__(timeout=None)

            @_discord.ui.button(label="✅ Approve", style=_discord.ButtonStyle.green,
                                custom_id=f"approve:{item_id}")
            async def approve_btn(self_view, interaction: _discord.Interaction,
                                  button: _discord.ui.Button):
                await self._on_interaction(interaction)

            @_discord.ui.button(label="❌ Reject", style=_discord.ButtonStyle.red,
                                custom_id=f"reject:{item_id}")
            async def reject_btn(self_view, interaction: _discord.Interaction,
                                 button: _discord.ui.Button):
                await self._on_interaction(interaction)

        try:
            channel = self._client.get_channel(self.notification_channel_id)
            if channel is None:
                channel = await self._client.fetch_channel(self.notification_channel_id)
            await channel.send(text, view=ReviewView())
        except Exception as e:
            logger.warning("Discord _send_review_item failed: %s", e)

    async def _on_message(self, message) -> None:
        """Handle an incoming Discord message — called by the on_message event."""
        if not self._client:
            return
        if message.author.bot:
            return

        raw_text = message.content or ""
        text = re.sub(r'<@!?\d+>\s*', '', raw_text).strip()

        file_ref: str | None = None
        if hasattr(message, 'attachments') and message.attachments:
            att = message.attachments[0]
            try:
                local_path, mime = await self._download_attachment(att)
                file_ref = f"[Attached file: {local_path} ({mime})]"
            except Exception:
                pass

        if not text and not file_ref:
            return

        # Create a thread for the reply
        try:
            import discord as _discord
            if isinstance(message.channel, _discord.TextChannel):
                thread = await message.create_thread(
                    name="Adjutant", auto_archive_duration=60
                )
            else:
                thread = message.channel
        except Exception:
            thread = message.channel

        self._pending_products[None] = thread

        parts = [p for p in [file_ref, text] if p]
        await self._directive_callback(None, "\n\n".join(parts))

    async def _on_interaction(self, interaction) -> None:
        """Handle a Discord button interaction."""
        custom_id = ""
        if hasattr(interaction, "data") and interaction.data:
            custom_id = interaction.data.get("custom_id", "")

        if ":" not in custom_id:
            return
        action_str, item_id_str = custom_id.split(":", 1)
        try:
            item_id = int(item_id_str)
        except ValueError:
            return

        try:
            await interaction.response.defer()
        except Exception:
            pass

        if action_str == "approve":
            self.resolve_review_fn(item_id, "approved")
            await self.broadcast_fn({"type": "review_resolved", "review_item_id": item_id, "action": "approved"})
            try:
                await interaction.edit_original_response(content="✅ Approved", view=None)
            except Exception:
                pass
            if self._on_review_approved_fn:
                await self._on_review_approved_fn(item_id)
        elif action_str == "reject":
            self.resolve_review_fn(item_id, "skipped")
            await self.broadcast_fn({"type": "review_resolved", "review_item_id": item_id, "action": "skipped"})
            try:
                await interaction.edit_original_response(content="❌ Rejected", view=None)
            except Exception:
                pass

    async def _download_attachment(self, attachment) -> tuple[str, str]:
        from backend.uploads import save_uploaded_file
        filename = attachment.filename or "discord_file"
        mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.get(attachment.url)
            resp.raise_for_status()
        local_path = save_uploaded_file(filename, resp.content)
        return str(local_path), mime

    async def start(self) -> None:
        """Connect to Discord Gateway and process events."""
        if not self._token:
            logger.info("Discord not configured — disabled")
            return

        import discord as _discord

        intents = _discord.Intents.default()
        intents.message_content = True
        self._client = _discord.Client(intents=intents)

        @self._client.event
        async def on_ready():
            self._bot_user_id = self._client.user.id
            logger.info("Discord connected as %s", self._client.user)

        @self._client.event
        async def on_message(message: _discord.Message):
            if self._client.user not in message.mentions:
                return
            await self._on_message(message)

        @self._client.event
        async def on_interaction(interaction: _discord.Interaction):
            if interaction.type == _discord.InteractionType.component:
                await self._on_interaction(interaction)

        try:
            await self._client.start(self._token)
        except asyncio.CancelledError:
            try:
                await self._client.close()
            except Exception:
                pass
            raise
        except Exception as e:
            logger.warning("Discord connection error: %s", e)
            await asyncio.sleep(5)
```

- [ ] **Step 2: Run tests**

```bash
cd /home/justin/Code/Adjutant && python -m pytest tests/test_discord_bot.py -v
```

Expected: all tests pass.

- [ ] **Step 3: Commit**

```bash
git add backend/discord_bot.py tests/test_discord_bot.py
git commit -m "feat: implement DiscordBot with Gateway WebSocket and review button support"
```

---

## Task 7: Add Telegram enable/delete + all Slack/Discord API endpoints

**Files:**
- Modify: `backend/api.py`

- [ ] **Step 1: Add the EnabledRequest model and Telegram endpoints**

Find the line `# ── Telegram ──────` in `api.py` (around line 437). After the existing `TelegramTokenRequest` class and existing endpoints, add:

```python
class EnabledRequest(BaseModel):
    enabled: bool


@router.put("/telegram/enabled")
async def set_telegram_enabled(body: EnabledRequest, _=Depends(_auth)):
    from backend.db import set_agent_config, get_agent_config
    from backend import telegram_state
    set_agent_config("telegram_enabled", "true" if body.enabled else "false")
    if body.enabled:
        token, chat_id = _get_telegram_creds()
        await telegram_state.restart(token, chat_id)
    else:
        await telegram_state.restart("", "")
    return {"enabled": body.enabled}


@router.delete("/telegram")
async def delete_telegram(_=Depends(_auth)):
    from backend.db import set_agent_config
    from backend import telegram_state
    for key in ["telegram_bot_token", "telegram_chat_id", "telegram_enabled"]:
        set_agent_config(key, "")
    await telegram_state.restart("", "")
    return {"ok": True}
```

- [ ] **Step 2: Add Slack endpoints after the Telegram block**

```python
# ── Slack ─────────────────────────────────────────────────────────────────────

class SlackTokensRequest(BaseModel):
    bot_token: str
    app_token: str


class SlackChannelRequest(BaseModel):
    channel_id: str


def _get_slack_creds() -> tuple[str, str, str]:
    """Return (bot_token, app_token, notification_channel_id)."""
    from backend.db import get_agent_config
    cfg = get_agent_config()
    return (
        cfg.get("slack_bot_token", ""),
        cfg.get("slack_app_token", ""),
        cfg.get("slack_notification_channel_id", ""),
    )


@router.get("/slack/status")
async def get_slack_status(_=Depends(_auth)):
    from backend.db import get_agent_config
    bot_token, app_token, notif_channel = _get_slack_creds()
    cfg = get_agent_config()
    enabled = cfg.get("slack_enabled", "false") == "true"
    if not bot_token:
        return {"configured": False, "connected": False, "bot_username": None, "enabled": enabled}
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.post(
                "https://slack.com/api/auth.test",
                headers={"Authorization": f"Bearer {bot_token}"},
            )
            data = resp.json()
            if data.get("ok"):
                return {
                    "configured": True,
                    "connected": True,
                    "bot_username": data.get("bot_id") or data.get("user"),
                    "enabled": enabled,
                    "notification_channel_id": notif_channel,
                }
    except Exception:
        pass
    return {"configured": True, "connected": False, "bot_username": None, "enabled": enabled}


@router.put("/slack/tokens")
async def save_slack_tokens(body: SlackTokensRequest, _=Depends(_auth)):
    from backend.db import set_agent_config
    from backend import slack_state
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.post(
                "https://slack.com/api/auth.test",
                headers={"Authorization": f"Bearer {body.bot_token}"},
            )
            data = resp.json()
    except Exception:
        raise HTTPException(400, detail="Could not reach Slack API")
    if not data.get("ok"):
        raise HTTPException(400, detail=f"Invalid bot token: {data.get('error', 'unknown')}")
    set_agent_config("slack_bot_token", body.bot_token)
    set_agent_config("slack_app_token", body.app_token)
    set_agent_config("slack_enabled", "true")
    _, _, notif_channel = _get_slack_creds()
    await slack_state.restart(body.bot_token, body.app_token)
    return {"bot_username": data.get("user"), "bot_id": data.get("bot_id")}


@router.get("/slack/channels")
async def list_slack_channels(_=Depends(_auth)):
    bot_token, _, _ = _get_slack_creds()
    if not bot_token:
        raise HTTPException(400, detail="Slack not configured")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://slack.com/api/conversations.list",
                headers={"Authorization": f"Bearer {bot_token}"},
                params={"types": "public_channel,private_channel", "exclude_archived": "true", "limit": "200"},
            )
            data = resp.json()
    except Exception:
        raise HTTPException(502, detail="Could not reach Slack API")
    channels = [
        {"id": c["id"], "name": c["name"]}
        for c in data.get("channels", [])
        if c.get("is_member")
    ]
    return {"channels": channels}


@router.put("/slack/notification-channel")
async def save_slack_notification_channel(body: SlackChannelRequest, _=Depends(_auth)):
    from backend.db import set_agent_config
    from backend import slack_state
    set_agent_config("slack_notification_channel_id", body.channel_id)
    bot_token, app_token, _ = _get_slack_creds()
    await slack_state.restart(bot_token, app_token)
    return {"channel_id": body.channel_id}


@router.put("/slack/enabled")
async def set_slack_enabled(body: EnabledRequest, _=Depends(_auth)):
    from backend.db import set_agent_config
    from backend import slack_state
    set_agent_config("slack_enabled", "true" if body.enabled else "false")
    if body.enabled:
        bot_token, app_token, _ = _get_slack_creds()
        await slack_state.restart(bot_token, app_token)
    else:
        await slack_state.restart("", "")
    return {"enabled": body.enabled}


@router.delete("/slack")
async def delete_slack(_=Depends(_auth)):
    from backend.db import set_agent_config
    from backend import slack_state
    for key in ["slack_bot_token", "slack_app_token", "slack_notification_channel_id", "slack_enabled"]:
        set_agent_config(key, "")
    await slack_state.restart("", "")
    return {"ok": True}
```

- [ ] **Step 3: Add Discord endpoints**

```python
# ── Discord ───────────────────────────────────────────────────────────────────

class DiscordTokenRequest(BaseModel):
    token: str


class DiscordChannelRequest(BaseModel):
    channel_id: str


def _get_discord_creds() -> tuple[str, str]:
    """Return (token, notification_channel_id)."""
    from backend.db import get_agent_config
    cfg = get_agent_config()
    return (
        cfg.get("discord_bot_token", ""),
        cfg.get("discord_notification_channel_id", ""),
    )


@router.get("/discord/status")
async def get_discord_status(_=Depends(_auth)):
    from backend.db import get_agent_config
    token, notif_channel = _get_discord_creds()
    cfg = get_agent_config()
    enabled = cfg.get("discord_enabled", "false") == "true"
    if not token:
        return {"configured": False, "connected": False, "bot_username": None, "enabled": enabled}
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(
                "https://discord.com/api/v10/users/@me",
                headers={"Authorization": f"Bot {token}"},
            )
            data = resp.json()
            if resp.status_code == 200:
                return {
                    "configured": True,
                    "connected": True,
                    "bot_username": data.get("username"),
                    "enabled": enabled,
                    "notification_channel_id": notif_channel,
                }
    except Exception:
        pass
    return {"configured": True, "connected": False, "bot_username": None, "enabled": enabled}


@router.put("/discord/token")
async def save_discord_token(body: DiscordTokenRequest, _=Depends(_auth)):
    from backend.db import set_agent_config
    from backend import discord_state
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(
                "https://discord.com/api/v10/users/@me",
                headers={"Authorization": f"Bot {body.token}"},
            )
            data = resp.json()
    except Exception:
        raise HTTPException(400, detail="Could not reach Discord API")
    if resp.status_code != 200:
        raise HTTPException(400, detail=f"Invalid bot token: {data.get('message', 'unknown')}")
    set_agent_config("discord_bot_token", body.token)
    set_agent_config("discord_enabled", "true")
    await discord_state.restart(body.token)
    return {"bot_username": data.get("username")}


@router.get("/discord/channels")
async def list_discord_channels(_=Depends(_auth)):
    token, _ = _get_discord_creds()
    if not token:
        raise HTTPException(400, detail="Discord not configured")
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            guilds_resp = await client.get(
                "https://discord.com/api/v10/users/@me/guilds",
                headers={"Authorization": f"Bot {token}"},
            )
            guilds = guilds_resp.json()
    except Exception:
        raise HTTPException(502, detail="Could not reach Discord API")
    channels = []
    for guild in guilds[:10]:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                ch_resp = await client.get(
                    f"https://discord.com/api/v10/guilds/{guild['id']}/channels",
                    headers={"Authorization": f"Bot {token}"},
                )
                for ch in ch_resp.json():
                    if ch.get("type") == 0:  # GUILD_TEXT
                        channels.append({
                            "id": ch["id"],
                            "name": ch["name"],
                            "guild": guild.get("name", ""),
                        })
        except Exception:
            continue
    return {"channels": channels}


@router.put("/discord/notification-channel")
async def save_discord_notification_channel(body: DiscordChannelRequest, _=Depends(_auth)):
    from backend.db import set_agent_config
    from backend import discord_state
    set_agent_config("discord_notification_channel_id", body.channel_id)
    token, _ = _get_discord_creds()
    await discord_state.restart(token)
    return {"channel_id": body.channel_id}


@router.put("/discord/enabled")
async def set_discord_enabled(body: EnabledRequest, _=Depends(_auth)):
    from backend.db import set_agent_config
    from backend import discord_state
    set_agent_config("discord_enabled", "true" if body.enabled else "false")
    if body.enabled:
        token, _ = _get_discord_creds()
        await discord_state.restart(token)
    else:
        await discord_state.restart("")
    return {"enabled": body.enabled}


@router.delete("/discord")
async def delete_discord(_=Depends(_auth)):
    from backend.db import set_agent_config
    from backend import discord_state
    for key in ["discord_bot_token", "discord_notification_channel_id", "discord_enabled"]:
        set_agent_config(key, "")
    await discord_state.restart("")
    return {"ok": True}
```

- [ ] **Step 4: Verify the app still imports**

```bash
cd /home/justin/Code/Adjutant && python -c "from backend.api import router; print('OK')"
```

Expected: `OK`

- [ ] **Step 5: Run existing tests to confirm no regressions**

```bash
cd /home/justin/Code/Adjutant && python -m pytest tests/ -v --ignore=tests/test_slack_bot.py --ignore=tests/test_discord_bot.py
```

Expected: all previously passing tests still pass.

- [ ] **Step 6: Commit**

```bash
git add backend/api.py
git commit -m "feat: add Slack and Discord API endpoints plus Telegram enable/delete"
```

---

## Task 8: Wire all bots in main.py

**Files:**
- Modify: `backend/main.py`

- [ ] **Step 1: Add module-level bot variables**

Find the section around line 401 in `main.py`:

```python
_telegram_bot  = None
_telegram_task = None
_mcp_manager = None
```

Replace with:

```python
_telegram_bot  = None
_telegram_task = None
_slack_bot     = None
_slack_task    = None
_discord_bot   = None
_discord_task  = None
_mcp_manager = None
```

- [ ] **Step 2: Update `_broadcast` to notify all three bots**

Find the `_broadcast` function (around line 406). Replace:

```python
    if _telegram_bot is not None:
        try:
            await _telegram_bot.notify(event)
        except Exception:
            pass
```

With:

```python
    for _bot in (_telegram_bot, _slack_bot, _discord_bot):
        if _bot is not None:
            try:
                await _bot.notify(event)
            except Exception:
                pass
```

- [ ] **Step 3: Rename directive handler and update lifespan**

Rename `_handle_telegram_directive` to `_handle_messaging_directive` (it's reused by all three bots). Find it (around line 422) and change the function name:

```python
async def _handle_messaging_directive(product_id: str | None, content: str) -> None:
    """Inject a message from any messaging platform into the directive queue."""
    _ensure_worker(product_id)
    directive_id = uuid.uuid4().hex[:8]
    _directive_queues[product_id].append({"id": directive_id, "content": content})
    _worker_events[product_id].set()
    await _broadcast(_queue_payload(product_id))
```

- [ ] **Step 4: Update the lifespan function**

Find the `lifespan` function (around line 506). Replace the entire block from `global _telegram_bot, _mcp_manager, _telegram_task` through `telegram_state.register(_restart_telegram)` with:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _telegram_bot, _mcp_manager, _telegram_task
    global _slack_bot, _slack_task, _discord_bot, _discord_task
    from backend.scheduler import scheduler_loop, register_broadcast
    from backend.telegram import TelegramBot
    from backend.slack_bot import SlackBot
    from backend.discord_bot import DiscordBot
    from backend.mcp_manager import MCPManager
    from backend.db import list_all_mcp_servers, get_agent_config
    from backend import telegram_state, slack_state, discord_state
    register_broadcast(_broadcast)
    scheduler_task = asyncio.create_task(scheduler_loop(_broadcast, interval_seconds=60))

    _cfg = get_agent_config()

    # ── Telegram ──────────────────────────────────────────────────────────────
    tg_token   = os.environ.get("TELEGRAM_BOT_TOKEN") or _cfg.get("telegram_bot_token") or ""
    tg_chat_id = os.environ.get("TELEGRAM_CHAT_ID")   or _cfg.get("telegram_chat_id")   or ""
    tg_enabled = _cfg.get("telegram_enabled", "true") != "false"

    _telegram_bot = TelegramBot(
        token=tg_token if tg_enabled else "",
        chat_id=tg_chat_id if tg_enabled else "",
        directive_callback=_handle_messaging_directive,
        resolve_review_fn=resolve_review_item,
        broadcast_fn=_broadcast,
        on_review_approved_fn=_on_review_approved,
    )
    _telegram_task = asyncio.create_task(_telegram_bot.start())

    async def _restart_telegram(token: str, chat_id: str) -> None:
        global _telegram_bot, _telegram_task
        if _telegram_task and not _telegram_task.done():
            _telegram_task.cancel()
            try:
                await asyncio.wait_for(asyncio.shield(_telegram_task), timeout=2)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
        _telegram_bot = TelegramBot(
            token=token,
            chat_id=chat_id,
            directive_callback=_handle_messaging_directive,
            resolve_review_fn=resolve_review_item,
            broadcast_fn=_broadcast,
            on_review_approved_fn=_on_review_approved,
        )
        _telegram_task = asyncio.create_task(_telegram_bot.start())

    telegram_state.register(_restart_telegram)

    # ── Slack ─────────────────────────────────────────────────────────────────
    sl_bot_token = _cfg.get("slack_bot_token", "")
    sl_app_token = _cfg.get("slack_app_token", "")
    sl_notif_ch  = _cfg.get("slack_notification_channel_id", "")
    sl_enabled   = _cfg.get("slack_enabled", "false") == "true"

    _slack_bot = SlackBot(
        bot_token=sl_bot_token if sl_enabled else "",
        app_token=sl_app_token if sl_enabled else "",
        notification_channel_id=sl_notif_ch,
        directive_callback=_handle_messaging_directive,
        resolve_review_fn=resolve_review_item,
        broadcast_fn=_broadcast,
        on_review_approved_fn=_on_review_approved,
    )
    _slack_task = asyncio.create_task(_slack_bot.start())

    async def _restart_slack(bot_token: str, app_token: str) -> None:
        global _slack_bot, _slack_task
        if _slack_task and not _slack_task.done():
            _slack_task.cancel()
            try:
                await asyncio.wait_for(asyncio.shield(_slack_task), timeout=2)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
        _, _, notif_ch = (
            bot_token, app_token,
            get_agent_config().get("slack_notification_channel_id", ""),
        )
        _slack_bot = SlackBot(
            bot_token=bot_token,
            app_token=app_token,
            notification_channel_id=get_agent_config().get("slack_notification_channel_id", ""),
            directive_callback=_handle_messaging_directive,
            resolve_review_fn=resolve_review_item,
            broadcast_fn=_broadcast,
            on_review_approved_fn=_on_review_approved,
        )
        _slack_task = asyncio.create_task(_slack_bot.start())

    slack_state.register(_restart_slack)

    # ── Discord ───────────────────────────────────────────────────────────────
    dc_token    = _cfg.get("discord_bot_token", "")
    dc_notif_ch = _cfg.get("discord_notification_channel_id", "")
    dc_enabled  = _cfg.get("discord_enabled", "false") == "true"

    _discord_bot = DiscordBot(
        token=dc_token if dc_enabled else "",
        notification_channel_id=int(dc_notif_ch) if dc_notif_ch else 0,
        directive_callback=_handle_messaging_directive,
        resolve_review_fn=resolve_review_item,
        broadcast_fn=_broadcast,
        on_review_approved_fn=_on_review_approved,
    )
    _discord_task = asyncio.create_task(_discord_bot.start())

    async def _restart_discord(token: str) -> None:
        global _discord_bot, _discord_task
        if _discord_task and not _discord_task.done():
            _discord_task.cancel()
            try:
                await asyncio.wait_for(asyncio.shield(_discord_task), timeout=2)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
        notif_ch_str = get_agent_config().get("discord_notification_channel_id", "")
        _discord_bot = DiscordBot(
            token=token,
            notification_channel_id=int(notif_ch_str) if notif_ch_str else 0,
            directive_callback=_handle_messaging_directive,
            resolve_review_fn=resolve_review_item,
            broadcast_fn=_broadcast,
            on_review_approved_fn=_on_review_approved,
        )
        _discord_task = asyncio.create_task(_discord_bot.start())

    discord_state.register(_restart_discord)
```

- [ ] **Step 5: Update cleanup in lifespan to cancel all bot tasks**

Find the teardown block after `yield`:

```python
    tasks_to_cancel = [scheduler_task, _telegram_task, *_worker_tasks.values()]
```

Replace with:

```python
    tasks_to_cancel = [
        scheduler_task, _telegram_task, _slack_task, _discord_task,
        *_worker_tasks.values()
    ]
```

- [ ] **Step 6: Verify imports and startup**

```bash
cd /home/justin/Code/Adjutant && python -c "from backend.main import app; print('OK')"
```

Expected: `OK`

- [ ] **Step 7: Run all tests**

```bash
cd /home/justin/Code/Adjutant && python -m pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 8: Commit**

```bash
git add backend/main.py
git commit -m "feat: wire Slack and Discord bots into lifespan handler and broadcast"
```

---

## Task 9: Frontend — update api.ts with new calls

**Files:**
- Modify: `ui/src/api.ts`

- [ ] **Step 1: Add all new API calls to api.ts**

Find the `discoverTelegramChat` entry (around line 189) and add after it:

```typescript
  setTelegramEnabled: (pw: string, enabled: boolean) =>
    apiFetch<{ enabled: boolean }>('/api/telegram/enabled', pw, {
      method: 'PUT',
      body: JSON.stringify({ enabled }),
    }),

  deleteTelegram: (pw: string) =>
    apiFetch<{ ok: boolean }>('/api/telegram', pw, { method: 'DELETE' }),

  getSlackStatus: (pw: string) =>
    apiFetch<{
      configured: boolean; connected: boolean; bot_username: string | null;
      enabled: boolean; notification_channel_id: string;
    }>('/api/slack/status', pw),

  saveSlackTokens: (pw: string, bot_token: string, app_token: string) =>
    apiFetch<{ bot_username: string; bot_id: string }>('/api/slack/tokens', pw, {
      method: 'PUT',
      body: JSON.stringify({ bot_token, app_token }),
    }),

  getSlackChannels: (pw: string) =>
    apiFetch<{ channels: { id: string; name: string }[] }>('/api/slack/channels', pw),

  saveSlackNotificationChannel: (pw: string, channel_id: string) =>
    apiFetch<{ channel_id: string }>('/api/slack/notification-channel', pw, {
      method: 'PUT',
      body: JSON.stringify({ channel_id }),
    }),

  setSlackEnabled: (pw: string, enabled: boolean) =>
    apiFetch<{ enabled: boolean }>('/api/slack/enabled', pw, {
      method: 'PUT',
      body: JSON.stringify({ enabled }),
    }),

  deleteSlack: (pw: string) =>
    apiFetch<{ ok: boolean }>('/api/slack', pw, { method: 'DELETE' }),

  getDiscordStatus: (pw: string) =>
    apiFetch<{
      configured: boolean; connected: boolean; bot_username: string | null;
      enabled: boolean; notification_channel_id: string;
    }>('/api/discord/status', pw),

  saveDiscordToken: (pw: string, token: string) =>
    apiFetch<{ bot_username: string }>('/api/discord/token', pw, {
      method: 'PUT',
      body: JSON.stringify({ token }),
    }),

  getDiscordChannels: (pw: string) =>
    apiFetch<{ channels: { id: string; name: string; guild: string }[] }>(
      '/api/discord/channels', pw,
    ),

  saveDiscordNotificationChannel: (pw: string, channel_id: string) =>
    apiFetch<{ channel_id: string }>('/api/discord/notification-channel', pw, {
      method: 'PUT',
      body: JSON.stringify({ channel_id }),
    }),

  setDiscordEnabled: (pw: string, enabled: boolean) =>
    apiFetch<{ enabled: boolean }>('/api/discord/enabled', pw, {
      method: 'PUT',
      body: JSON.stringify({ enabled }),
    }),

  deleteDiscord: (pw: string) =>
    apiFetch<{ ok: boolean }>('/api/discord', pw, { method: 'DELETE' }),
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /home/justin/Code/Adjutant/ui && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add ui/src/api.ts
git commit -m "feat: add Slack, Discord, and Telegram enable/delete API calls to frontend"
```

---

## Task 10: Frontend — TelegramCard with enable toggle and delete

**Files:**
- Create: `ui/src/components/settings/integrations/TelegramCard.tsx`

- [ ] **Step 1: Create the directory**

```bash
mkdir -p /home/justin/Code/Adjutant/ui/src/components/settings/integrations
```

- [ ] **Step 2: Create TelegramCard.tsx**

```tsx
// ui/src/components/settings/integrations/TelegramCard.tsx
import { useEffect, useState } from 'react'
import { api } from '../../../api'

interface Props {
  password: string
}

interface TelegramStatus {
  configured: boolean
  connected: boolean
  bot_username: string | null
  enabled: boolean
}

export default function TelegramCard({ password }: Props) {
  const [status, setStatus] = useState<TelegramStatus | null>(null)
  const [token, setToken] = useState('')
  const [savingToken, setSavingToken] = useState(false)
  const [tokenError, setTokenError] = useState('')
  const [discovering, setDiscovering] = useState(false)
  const [discoverMsg, setDiscoverMsg] = useState('')
  const [showReconfigure, setShowReconfigure] = useState(false)
  const [toggling, setToggling] = useState(false)
  const [deleting, setDeleting] = useState(false)

  const reload = () => {
    api.getTelegramStatus(password).then(s => setStatus({ ...s, enabled: (s as any).enabled ?? true })).catch(() => {})
  }

  useEffect(() => { reload() }, [password])

  async function handleSaveToken() {
    if (!token.trim()) return
    setSavingToken(true)
    setTokenError('')
    try {
      await api.saveTelegramToken(password, token.trim())
      setToken('')
      setShowReconfigure(false)
      reload()
    } catch (e: unknown) {
      setTokenError((e as Error).message || 'Invalid token')
    } finally {
      setSavingToken(false)
    }
  }

  async function handleDiscover() {
    setDiscovering(true)
    setDiscoverMsg('')
    try {
      const { chat_id } = await api.discoverTelegramChat(password)
      if (chat_id) {
        setDiscoverMsg('Chat ID found! Bot is now connected.')
        reload()
      } else {
        setDiscoverMsg('No messages found yet — message your bot first, then try again.')
      }
    } catch (e: unknown) {
      setDiscoverMsg((e as Error).message || 'Failed to discover chat')
    } finally {
      setDiscovering(false)
    }
  }

  async function handleToggleEnabled() {
    if (!status) return
    setToggling(true)
    try {
      await api.setTelegramEnabled(password, !status.enabled)
      reload()
    } finally {
      setToggling(false)
    }
  }

  async function handleDelete() {
    if (!confirm('Disconnect Telegram? This will clear the bot token and chat ID.')) return
    setDeleting(true)
    try {
      await api.deleteTelegram(password)
      reload()
    } finally {
      setDeleting(false)
    }
  }

  const isConnected = status?.configured && status?.connected

  return (
    <div className="bg-adj-panel border border-adj-border rounded-md overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-adj-border">
        <div className="flex items-center gap-2">
          <span className="text-lg">✈️</span>
          <span className="text-sm font-bold text-adj-text-primary">Telegram</span>
          {isConnected && (
            <span className="text-xs font-mono text-emerald-400">@{status?.bot_username}</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {status?.configured && (
            <>
              <button
                onClick={handleToggleEnabled}
                disabled={toggling}
                className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors disabled:opacity-50 ${
                  status.enabled ? 'bg-adj-accent' : 'bg-adj-border'
                }`}
                title={status.enabled ? 'Disable' : 'Enable'}
              >
                <span className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform ${
                  status.enabled ? 'translate-x-4' : 'translate-x-1'
                }`} />
              </button>
              <button
                onClick={handleDelete}
                disabled={deleting}
                className="text-xs text-adj-text-muted hover:text-red-400 transition-colors disabled:opacity-50"
                title="Disconnect"
              >
                {deleting ? '…' : 'Disconnect'}
              </button>
            </>
          )}
        </div>
      </div>

      {/* Body */}
      <div className="p-4 space-y-4">
        {status === null ? (
          <p className="text-xs text-adj-text-faint">Checking status…</p>
        ) : isConnected && !showReconfigure ? (
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <span className={`w-2 h-2 rounded-full flex-shrink-0 ${status.enabled ? 'bg-emerald-500' : 'bg-adj-text-faint'}`} />
              <span className="text-sm text-adj-text-primary">
                {status.enabled ? 'Connected and active' : 'Connected but disabled'}
              </span>
            </div>
            <p className="text-xs text-adj-text-muted">
              Message your bot on Telegram to send directives from anywhere.
            </p>
            <button
              onClick={() => setShowReconfigure(true)}
              className="text-xs text-adj-text-muted hover:text-adj-text-secondary transition-colors"
            >
              Reconfigure token
            </button>
          </div>
        ) : status.configured && !isConnected && !showReconfigure ? (
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-amber-500 flex-shrink-0" />
              <span className="text-sm text-adj-text-secondary">
                Token saved as <span className="font-mono text-amber-400">@{status.bot_username}</span> — waiting for first message
              </span>
            </div>
            <div className="p-3 bg-adj-surface rounded-md text-xs text-adj-text-muted space-y-1.5">
              <p className="font-semibold text-adj-text-secondary">One more step:</p>
              <p>1. Open Telegram and message <span className="font-mono text-adj-text-secondary">@{status.bot_username}</span></p>
              <p>2. Send any message (e.g. "hello")</p>
              <p>3. Click <strong>Discover Chat</strong> below</p>
            </div>
            <button
              onClick={handleDiscover}
              disabled={discovering}
              className="px-4 py-2 bg-adj-accent text-white rounded-md text-sm font-semibold hover:bg-adj-accent-dark transition-colors disabled:opacity-50"
            >
              {discovering ? 'Searching…' : 'Discover Chat'}
            </button>
            {discoverMsg && (
              <p className={`text-xs ${discoverMsg.includes('found') ? 'text-emerald-400' : 'text-amber-400'}`}>
                {discoverMsg}
              </p>
            )}
          </div>
        ) : (
          <div className="space-y-4">
            {!showReconfigure && (
              <p className="text-xs text-adj-text-secondary">
                Connect Telegram to send directives and get notifications from anywhere.
              </p>
            )}
            <div className="p-3 bg-adj-surface rounded-md text-xs text-adj-text-muted space-y-1.5">
              <p className="font-semibold text-adj-text-secondary">Create a bot:</p>
              <p>Open Telegram → message <span className="font-mono text-adj-text-secondary">@BotFather</span> → send <span className="font-mono text-adj-text-secondary">/newbot</span> → copy the token.</p>
            </div>
            <div>
              <label className="block text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-1.5">
                Bot Token
              </label>
              <input
                type="password"
                value={token}
                onChange={e => { setToken(e.target.value); setTokenError('') }}
                placeholder="1234567890:ABCDEFghijklmnopqrstuvwxyz"
                className="w-full bg-adj-base border border-adj-border rounded-md px-3 py-2 text-sm text-adj-text-primary placeholder:text-adj-text-faint focus:outline-none focus:border-adj-accent font-mono transition-colors"
              />
              {tokenError && <p className="text-xs text-red-400 mt-1">{tokenError}</p>}
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={handleSaveToken}
                disabled={savingToken || !token.trim()}
                className="px-4 py-2 bg-adj-accent text-white rounded-md text-sm font-semibold hover:bg-adj-accent-dark transition-colors disabled:opacity-50"
              >
                {savingToken ? 'Verifying…' : 'Save Token'}
              </button>
              {showReconfigure && (
                <button
                  onClick={() => { setShowReconfigure(false); setToken('') }}
                  className="text-xs text-adj-text-muted hover:text-adj-text-secondary"
                >
                  Cancel
                </button>
              )}
            </div>
          </div>
        )}
        <a
          href="https://core.telegram.org/bots#how-do-i-create-a-bot"
          target="_blank"
          rel="noopener noreferrer"
          className="block text-xs text-adj-accent hover:underline"
        >
          Setup guide →
        </a>
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Commit**

```bash
git add ui/src/components/settings/integrations/TelegramCard.tsx
git commit -m "feat: add TelegramCard with enable toggle and disconnect button"
```

---

## Task 11: Frontend — SlackCard

**Files:**
- Create: `ui/src/components/settings/integrations/SlackCard.tsx`

- [ ] **Step 1: Create SlackCard.tsx**

```tsx
// ui/src/components/settings/integrations/SlackCard.tsx
import { useEffect, useState } from 'react'
import { api } from '../../../api'

interface Props {
  password: string
}

interface SlackStatus {
  configured: boolean
  connected: boolean
  bot_username: string | null
  enabled: boolean
  notification_channel_id: string
}

export default function SlackCard({ password }: Props) {
  const [status, setStatus] = useState<SlackStatus | null>(null)
  const [botToken, setBotToken] = useState('')
  const [appToken, setAppToken] = useState('')
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState('')
  const [showReconfigure, setShowReconfigure] = useState(false)
  const [channels, setChannels] = useState<{ id: string; name: string }[]>([])
  const [loadingChannels, setLoadingChannels] = useState(false)
  const [savingChannel, setSavingChannel] = useState(false)
  const [toggling, setToggling] = useState(false)
  const [deleting, setDeleting] = useState(false)

  const reload = () => {
    api.getSlackStatus(password).then(s => {
      setStatus(s)
      if (s.connected) loadChannels()
    }).catch(() => {})
  }

  const loadChannels = () => {
    setLoadingChannels(true)
    api.getSlackChannels(password)
      .then(r => setChannels(r.channels))
      .catch(() => {})
      .finally(() => setLoadingChannels(false))
  }

  useEffect(() => { reload() }, [password])

  async function handleSaveTokens() {
    if (!botToken.trim() || !appToken.trim()) return
    setSaving(true)
    setSaveError('')
    try {
      await api.saveSlackTokens(password, botToken.trim(), appToken.trim())
      setBotToken('')
      setAppToken('')
      setShowReconfigure(false)
      reload()
    } catch (e: unknown) {
      setSaveError((e as Error).message || 'Invalid tokens')
    } finally {
      setSaving(false)
    }
  }

  async function handleSelectChannel(channelId: string) {
    setSavingChannel(true)
    try {
      await api.saveSlackNotificationChannel(password, channelId)
      reload()
    } finally {
      setSavingChannel(false)
    }
  }

  async function handleToggleEnabled() {
    if (!status) return
    setToggling(true)
    try {
      await api.setSlackEnabled(password, !status.enabled)
      reload()
    } finally {
      setToggling(false)
    }
  }

  async function handleDelete() {
    if (!confirm('Disconnect Slack? This will clear all Slack credentials.')) return
    setDeleting(true)
    try {
      await api.deleteSlack(password)
      reload()
    } finally {
      setDeleting(false)
    }
  }

  const isConnected = status?.configured && status?.connected

  return (
    <div className="bg-adj-panel border border-adj-border rounded-md overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-adj-border">
        <div className="flex items-center gap-2">
          <span className="text-lg">💬</span>
          <span className="text-sm font-bold text-adj-text-primary">Slack</span>
          {isConnected && (
            <span className="text-xs text-emerald-400 font-mono">{status?.bot_username}</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {status?.configured && (
            <>
              <button
                onClick={handleToggleEnabled}
                disabled={toggling}
                className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors disabled:opacity-50 ${
                  status.enabled ? 'bg-adj-accent' : 'bg-adj-border'
                }`}
                title={status.enabled ? 'Disable' : 'Enable'}
              >
                <span className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform ${
                  status.enabled ? 'translate-x-4' : 'translate-x-1'
                }`} />
              </button>
              <button
                onClick={handleDelete}
                disabled={deleting}
                className="text-xs text-adj-text-muted hover:text-red-400 transition-colors disabled:opacity-50"
              >
                {deleting ? '…' : 'Disconnect'}
              </button>
            </>
          )}
        </div>
      </div>

      {/* Body */}
      <div className="p-4 space-y-4">
        {status === null ? (
          <p className="text-xs text-adj-text-faint">Checking status…</p>
        ) : isConnected && !showReconfigure ? (
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <span className={`w-2 h-2 rounded-full flex-shrink-0 ${status.enabled ? 'bg-emerald-500' : 'bg-adj-text-faint'}`} />
              <span className="text-sm text-adj-text-primary">
                {status.enabled ? 'Connected and active' : 'Connected but disabled'}
              </span>
            </div>
            <div>
              <label className="block text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-1.5">
                Notification Channel
              </label>
              {loadingChannels ? (
                <p className="text-xs text-adj-text-faint">Loading channels…</p>
              ) : (
                <select
                  value={status.notification_channel_id || ''}
                  onChange={e => handleSelectChannel(e.target.value)}
                  disabled={savingChannel}
                  className="w-full bg-adj-base border border-adj-border rounded-md px-3 py-2 text-sm text-adj-text-primary focus:outline-none focus:border-adj-accent transition-colors disabled:opacity-50"
                >
                  <option value="">— Select a channel —</option>
                  {channels.map(c => (
                    <option key={c.id} value={c.id}>#{c.name}</option>
                  ))}
                </select>
              )}
              <p className="text-xs text-adj-text-muted mt-1">
                Review items and activity summaries are sent here.
              </p>
            </div>
            <button
              onClick={() => setShowReconfigure(true)}
              className="text-xs text-adj-text-muted hover:text-adj-text-secondary transition-colors"
            >
              Reconfigure tokens
            </button>
          </div>
        ) : (
          <div className="space-y-4">
            {!showReconfigure && (
              <p className="text-xs text-adj-text-secondary">
                Connect Slack to interact with Adjutant from any channel. @mention the bot to send directives.
              </p>
            )}
            <div className="p-3 bg-adj-surface rounded-md text-xs text-adj-text-muted space-y-1">
              <p className="font-semibold text-adj-text-secondary">Two tokens required:</p>
              <p><span className="font-mono text-adj-text-secondary">xoxb-...</span> Bot Token — from OAuth &amp; Permissions</p>
              <p><span className="font-mono text-adj-text-secondary">xapp-...</span> App-Level Token — from Socket Mode</p>
            </div>
            <div>
              <label className="block text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-1.5">
                Bot Token (xoxb-...)
              </label>
              <input
                type="password"
                value={botToken}
                onChange={e => { setBotToken(e.target.value); setSaveError('') }}
                placeholder="xoxb-..."
                className="w-full bg-adj-base border border-adj-border rounded-md px-3 py-2 text-sm text-adj-text-primary placeholder:text-adj-text-faint focus:outline-none focus:border-adj-accent font-mono transition-colors"
              />
            </div>
            <div>
              <label className="block text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-1.5">
                App-Level Token (xapp-...)
              </label>
              <input
                type="password"
                value={appToken}
                onChange={e => { setAppToken(e.target.value); setSaveError('') }}
                placeholder="xapp-..."
                className="w-full bg-adj-base border border-adj-border rounded-md px-3 py-2 text-sm text-adj-text-primary placeholder:text-adj-text-faint focus:outline-none focus:border-adj-accent font-mono transition-colors"
              />
            </div>
            {saveError && <p className="text-xs text-red-400">{saveError}</p>}
            <div className="flex items-center gap-3">
              <button
                onClick={handleSaveTokens}
                disabled={saving || !botToken.trim() || !appToken.trim()}
                className="px-4 py-2 bg-adj-accent text-white rounded-md text-sm font-semibold hover:bg-adj-accent-dark transition-colors disabled:opacity-50"
              >
                {saving ? 'Verifying…' : 'Connect Slack'}
              </button>
              {showReconfigure && (
                <button
                  onClick={() => { setShowReconfigure(false); setBotToken(''); setAppToken('') }}
                  className="text-xs text-adj-text-muted hover:text-adj-text-secondary"
                >
                  Cancel
                </button>
              )}
            </div>
          </div>
        )}
        <a
          href="/docs/slack-setup.md"
          target="_blank"
          rel="noopener noreferrer"
          className="block text-xs text-adj-accent hover:underline"
        >
          Slack setup guide →
        </a>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add ui/src/components/settings/integrations/SlackCard.tsx
git commit -m "feat: add SlackCard with two-token setup and channel selector"
```

---

## Task 12: Frontend — DiscordCard

**Files:**
- Create: `ui/src/components/settings/integrations/DiscordCard.tsx`

- [ ] **Step 1: Create DiscordCard.tsx**

```tsx
// ui/src/components/settings/integrations/DiscordCard.tsx
import { useEffect, useState } from 'react'
import { api } from '../../../api'

interface Props {
  password: string
}

interface DiscordStatus {
  configured: boolean
  connected: boolean
  bot_username: string | null
  enabled: boolean
  notification_channel_id: string
}

export default function DiscordCard({ password }: Props) {
  const [status, setStatus] = useState<DiscordStatus | null>(null)
  const [token, setToken] = useState('')
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState('')
  const [showReconfigure, setShowReconfigure] = useState(false)
  const [channels, setChannels] = useState<{ id: string; name: string; guild: string }[]>([])
  const [loadingChannels, setLoadingChannels] = useState(false)
  const [savingChannel, setSavingChannel] = useState(false)
  const [toggling, setToggling] = useState(false)
  const [deleting, setDeleting] = useState(false)

  const reload = () => {
    api.getDiscordStatus(password).then(s => {
      setStatus(s)
      if (s.connected) loadChannels()
    }).catch(() => {})
  }

  const loadChannels = () => {
    setLoadingChannels(true)
    api.getDiscordChannels(password)
      .then(r => setChannels(r.channels))
      .catch(() => {})
      .finally(() => setLoadingChannels(false))
  }

  useEffect(() => { reload() }, [password])

  async function handleSaveToken() {
    if (!token.trim()) return
    setSaving(true)
    setSaveError('')
    try {
      await api.saveDiscordToken(password, token.trim())
      setToken('')
      setShowReconfigure(false)
      reload()
    } catch (e: unknown) {
      setSaveError((e as Error).message || 'Invalid token')
    } finally {
      setSaving(false)
    }
  }

  async function handleSelectChannel(channelId: string) {
    setSavingChannel(true)
    try {
      await api.saveDiscordNotificationChannel(password, channelId)
      reload()
    } finally {
      setSavingChannel(false)
    }
  }

  async function handleToggleEnabled() {
    if (!status) return
    setToggling(true)
    try {
      await api.setDiscordEnabled(password, !status.enabled)
      reload()
    } finally {
      setToggling(false)
    }
  }

  async function handleDelete() {
    if (!confirm('Disconnect Discord? This will clear all Discord credentials.')) return
    setDeleting(true)
    try {
      await api.deleteDiscord(password)
      reload()
    } finally {
      setDeleting(false)
    }
  }

  const isConnected = status?.configured && status?.connected

  return (
    <div className="bg-adj-panel border border-adj-border rounded-md overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-adj-border">
        <div className="flex items-center gap-2">
          <span className="text-lg">🎮</span>
          <span className="text-sm font-bold text-adj-text-primary">Discord</span>
          {isConnected && (
            <span className="text-xs text-emerald-400 font-mono">{status?.bot_username}</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {status?.configured && (
            <>
              <button
                onClick={handleToggleEnabled}
                disabled={toggling}
                className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors disabled:opacity-50 ${
                  status.enabled ? 'bg-adj-accent' : 'bg-adj-border'
                }`}
                title={status.enabled ? 'Disable' : 'Enable'}
              >
                <span className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform ${
                  status.enabled ? 'translate-x-4' : 'translate-x-1'
                }`} />
              </button>
              <button
                onClick={handleDelete}
                disabled={deleting}
                className="text-xs text-adj-text-muted hover:text-red-400 transition-colors disabled:opacity-50"
              >
                {deleting ? '…' : 'Disconnect'}
              </button>
            </>
          )}
        </div>
      </div>

      {/* Body */}
      <div className="p-4 space-y-4">
        {status === null ? (
          <p className="text-xs text-adj-text-faint">Checking status…</p>
        ) : isConnected && !showReconfigure ? (
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <span className={`w-2 h-2 rounded-full flex-shrink-0 ${status.enabled ? 'bg-emerald-500' : 'bg-adj-text-faint'}`} />
              <span className="text-sm text-adj-text-primary">
                {status.enabled ? 'Connected and active' : 'Connected but disabled'}
              </span>
            </div>
            <div>
              <label className="block text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-1.5">
                Notification Channel
              </label>
              {loadingChannels ? (
                <p className="text-xs text-adj-text-faint">Loading channels…</p>
              ) : (
                <select
                  value={status.notification_channel_id || ''}
                  onChange={e => handleSelectChannel(e.target.value)}
                  disabled={savingChannel}
                  className="w-full bg-adj-base border border-adj-border rounded-md px-3 py-2 text-sm text-adj-text-primary focus:outline-none focus:border-adj-accent transition-colors disabled:opacity-50"
                >
                  <option value="">— Select a channel —</option>
                  {channels.map(c => (
                    <option key={c.id} value={c.id}>
                      {c.guild ? `${c.guild} / ` : ''}#{c.name}
                    </option>
                  ))}
                </select>
              )}
              <p className="text-xs text-adj-text-muted mt-1">
                Review items and activity summaries are sent here.
              </p>
            </div>
            <button
              onClick={() => setShowReconfigure(true)}
              className="text-xs text-adj-text-muted hover:text-adj-text-secondary transition-colors"
            >
              Reconfigure token
            </button>
          </div>
        ) : (
          <div className="space-y-4">
            {!showReconfigure && (
              <p className="text-xs text-adj-text-secondary">
                Connect Discord to interact with Adjutant from any server channel. @mention the bot to send directives.
              </p>
            )}
            <div>
              <label className="block text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-1.5">
                Bot Token
              </label>
              <input
                type="password"
                value={token}
                onChange={e => { setToken(e.target.value); setSaveError('') }}
                placeholder="MTI3..."
                className="w-full bg-adj-base border border-adj-border rounded-md px-3 py-2 text-sm text-adj-text-primary placeholder:text-adj-text-faint focus:outline-none focus:border-adj-accent font-mono transition-colors"
              />
              {saveError && <p className="text-xs text-red-400 mt-1">{saveError}</p>}
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={handleSaveToken}
                disabled={saving || !token.trim()}
                className="px-4 py-2 bg-adj-accent text-white rounded-md text-sm font-semibold hover:bg-adj-accent-dark transition-colors disabled:opacity-50"
              >
                {saving ? 'Verifying…' : 'Connect Discord'}
              </button>
              {showReconfigure && (
                <button
                  onClick={() => { setShowReconfigure(false); setToken('') }}
                  className="text-xs text-adj-text-muted hover:text-adj-text-secondary"
                >
                  Cancel
                </button>
              )}
            </div>
          </div>
        )}
        <a
          href="/docs/discord-setup.md"
          target="_blank"
          rel="noopener noreferrer"
          className="block text-xs text-adj-accent hover:underline"
        >
          Discord setup guide →
        </a>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add ui/src/components/settings/integrations/DiscordCard.tsx
git commit -m "feat: add DiscordCard with token setup and channel selector"
```

---

## Task 13: Frontend — IntegrationsSettings and SettingsPage wiring

**Files:**
- Create: `ui/src/components/settings/IntegrationsSettings.tsx`
- Modify: `ui/src/components/SettingsPage.tsx`
- Delete: `ui/src/components/settings/RemoteAccessSettings.tsx`

- [ ] **Step 1: Create IntegrationsSettings.tsx**

```tsx
// ui/src/components/settings/IntegrationsSettings.tsx
import TelegramCard from './integrations/TelegramCard'
import SlackCard from './integrations/SlackCard'
import DiscordCard from './integrations/DiscordCard'

interface Props {
  password: string
}

export default function IntegrationsSettings({ password }: Props) {
  return (
    <div className="w-full">
      <h2 className="text-base font-bold text-adj-text-primary mb-1">Integrations</h2>
      <p className="text-xs text-adj-text-muted mb-6">
        Connect messaging platforms to interact with Adjutant from anywhere
      </p>
      <div className="space-y-4">
        <TelegramCard password={password} />
        <SlackCard password={password} />
        <DiscordCard password={password} />
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Update SettingsPage.tsx**

In `SettingsPage.tsx`, make three changes:

**Change 1** — swap the import (line ~12):
```typescript
// Remove:
import RemoteAccessSettings from './settings/RemoteAccessSettings'
// Add:
import IntegrationsSettings from './settings/IntegrationsSettings'
```

**Change 2** — update the section key and label (line ~54):
```typescript
// Remove:
  { key: 'remote-access',     label: 'Remote Access',     icon: '📡' },
// Add:
  { key: 'integrations',      label: 'Integrations',      icon: '🔗' },
```

**Change 3** — update the case in the render switch (line ~106):
```typescript
// Remove:
      case 'remote-access': return <RemoteAccessSettings {...common} />
// Add:
      case 'integrations': return <IntegrationsSettings {...common} />
```

- [ ] **Step 3: Delete old RemoteAccessSettings.tsx**

```bash
rm /home/justin/Code/Adjutant/ui/src/components/settings/RemoteAccessSettings.tsx
```

- [ ] **Step 4: Build the frontend to check for errors**

```bash
cd /home/justin/Code/Adjutant/ui && npm run build 2>&1 | tail -20
```

Expected: build succeeds with no TypeScript errors.

- [ ] **Step 5: Commit**

```bash
git add ui/src/components/settings/IntegrationsSettings.tsx \
        ui/src/components/settings/integrations/ \
        ui/src/components/SettingsPage.tsx
git rm ui/src/components/settings/RemoteAccessSettings.tsx
git commit -m "feat: replace Remote Access with Integrations section (Telegram + Slack + Discord cards)"
```

---

## Task 14: Create setup documentation

**Files:**
- Create: `docs/slack-setup.md`
- Create: `docs/discord-setup.md`

- [ ] **Step 1: Create docs/slack-setup.md**

```markdown
# Slack Setup Guide

This guide walks you through creating a Slack app and connecting it to Adjutant.

## Step 1 — Create a Slack App

1. Go to [api.slack.com/apps](https://api.slack.com/apps) and click **Create New App**
2. Choose **From scratch**
3. Name your app (e.g. "Adjutant") and select your workspace
4. Click **Create App**

## Step 2 — Enable Socket Mode

Socket Mode lets your app connect to Slack without a public URL.

1. In the left sidebar, click **Socket Mode**
2. Toggle **Enable Socket Mode** to ON
3. Click **Generate** to create an App-Level Token
4. Name it (e.g. "adjutant-socket") and click **Generate**
5. Copy the token — it starts with `xapp-`

## Step 3 — Add Bot Scopes

1. In the left sidebar, go to **OAuth & Permissions**
2. Scroll to **Bot Token Scopes** and add:
   - `app_mentions:read` — receive @mention events
   - `chat:write` — send messages
   - `channels:read` — list channels
   - `files:read` — access shared files

## Step 4 — Install the App to Your Workspace

1. Still in **OAuth & Permissions**, scroll to the top and click **Install to Workspace**
2. Authorize the app
3. Copy the **Bot User OAuth Token** — it starts with `xoxb-`

## Step 5 — Invite the Bot to Channels

In Slack, create or open a channel and type:

```
/invite @YourAppName
```

Do this for any channel where you want to use the bot, and for the notification channel.

## Step 6 — Connect in Adjutant

1. In Adjutant Settings → Integrations → Slack, paste your **Bot Token** (`xoxb-...`) and **App-Level Token** (`xapp-...`)
2. Click **Connect Slack**
3. Once connected, select your **Notification Channel** from the dropdown
4. @mention your bot in any channel to start sending directives
```

- [ ] **Step 2: Create docs/discord-setup.md**

```markdown
# Discord Setup Guide

This guide walks you through creating a Discord bot and connecting it to Adjutant.

## Step 1 — Create a Discord Application

1. Go to [discord.com/developers/applications](https://discord.com/developers/applications)
2. Click **New Application**
3. Name your application (e.g. "Adjutant") and click **Create**

## Step 2 — Add a Bot

1. In the left sidebar, click **Bot**
2. Click **Add Bot** and confirm
3. Under **Privileged Gateway Intents**, enable:
   - **Message Content Intent** — required to read message text
   - **Server Members Intent** — optional, for member lookups
4. Click **Save Changes**
5. Click **Reset Token**, confirm, and copy your bot token

## Step 3 — Generate an Invite URL

1. In the left sidebar, click **OAuth2 → URL Generator**
2. Under **Scopes**, check **bot**
3. Under **Bot Permissions**, check:
   - Send Messages
   - Read Message History
   - Create Public Threads
   - Use Application Commands
4. Copy the generated URL and open it in your browser to invite the bot to your server

## Step 4 — Create a Notification Channel

1. In your Discord server, create a text channel (e.g. `#adjutant-notifications`)
2. Ensure the bot has access: right-click the channel → **Edit Channel** → **Permissions** → add your bot with Send Messages permission

## Step 5 — Connect in Adjutant

1. In Adjutant Settings → Integrations → Discord, paste your **Bot Token**
2. Click **Connect Discord**
3. Once connected, select your **Notification Channel** from the dropdown
4. @mention your bot in any channel to start sending directives
```

- [ ] **Step 3: Commit**

```bash
git add docs/slack-setup.md docs/discord-setup.md
git commit -m "docs: add Slack and Discord setup guides"
```

---

## Self-Review

**Spec coverage check:**
- ✅ SlackBot class with Socket Mode — Task 4
- ✅ DiscordBot class with Gateway — Task 6
- ✅ Hot-reload state modules — Task 2
- ✅ Telegram enable/delete endpoints — Task 7
- ✅ All Slack API endpoints (6) — Task 7
- ✅ All Discord API endpoints (6) — Task 7
- ✅ Thread replies (Slack: thread_ts; Discord: create_thread) — Task 4 implementation
- ✅ @mention routing to global agent — Tasks 4, 6
- ✅ Review item buttons — Tasks 4, 6
- ✅ Long message handling (Slack: multi-block; Discord: split at 2000) — Tasks 3, 5
- ✅ Notification channel for proactive events — Tasks 4, 6
- ✅ File attachment handling — Tasks 4, 6
- ✅ Rename "Remote Access" → "Integrations" — Task 13
- ✅ Enable/disable toggle per platform — Tasks 7, 10, 11, 12
- ✅ Delete/disconnect per platform — Tasks 7, 10, 11, 12
- ✅ Setup guide links in UI cards — Tasks 10, 11, 12
- ✅ docs/slack-setup.md and docs/discord-setup.md — Task 14
- ✅ Python dependencies — Task 1
- ✅ main.py wiring — Task 8
- ✅ api.ts API calls — Task 9

**Type consistency check:**
- `SlackBot.notification_channel_id` → `str` (channel IDs are strings in Slack) — consistent across Tasks 4, 7, 8
- `DiscordBot.notification_channel_id` → `int` (channel IDs are ints in Discord) — consistent across Tasks 6, 7, 8
- `EnabledRequest` defined once in api.py, reused by Telegram/Slack/Discord enabled endpoints — Task 7
- `_handle_messaging_directive` renamed from `_handle_telegram_directive`, used for all three bots — Task 8
