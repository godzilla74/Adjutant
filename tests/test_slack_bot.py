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


# ── per-product channel routing ───────────────────────────────────────────────

def test_notify_activity_done_uses_per_product_channel():
    bot = _make_bot()
    with patch("backend.db.get_orchestrator_config",
               return_value={"slack_channel_id": "C_PRODUCT", "discord_channel_id": None, "telegram_chat_id": None}):
        asyncio.run(bot.notify({"type": "activity_done", "product_id": "p1", "summary": "Done"}))
    bot._web_client.chat_postMessage.assert_awaited_once()
    assert bot._web_client.chat_postMessage.call_args.kwargs["channel"] == "C_PRODUCT"


def test_notify_activity_done_falls_back_to_global_channel():
    bot = _make_bot()
    with patch("backend.db.get_orchestrator_config",
               return_value={"slack_channel_id": None, "discord_channel_id": None, "telegram_chat_id": None}):
        asyncio.run(bot.notify({"type": "activity_done", "product_id": "p1", "summary": "Done"}))
    bot._web_client.chat_postMessage.assert_awaited_once()
    assert bot._web_client.chat_postMessage.call_args.kwargs["channel"] == "C_NOTIF"


def test_notify_review_item_uses_per_product_channel():
    bot = _make_bot()
    item = {"id": 10, "title": "T", "description": "", "risk_label": ""}
    with patch("backend.db.get_orchestrator_config",
               return_value={"slack_channel_id": "C_PRODUCT", "discord_channel_id": None, "telegram_chat_id": None}):
        asyncio.run(bot.notify({"type": "review_item_added", "product_id": "p1", "item": item}))
    assert bot._web_client.chat_postMessage.call_args.kwargs["channel"] == "C_PRODUCT"


def test_notify_orchestrator_run_complete_uses_per_product_channel():
    bot = _make_bot()
    with patch("backend.db.get_orchestrator_config",
               return_value={"slack_channel_id": "C_PRODUCT", "discord_channel_id": None, "telegram_chat_id": None}):
        asyncio.run(bot.notify({
            "type": "orchestrator_run_complete", "product_id": "p1",
            "brief_preview": "All good", "pending_approval_count": 0,
        }))
    assert bot._web_client.chat_postMessage.call_args.kwargs["channel"] == "C_PRODUCT"
