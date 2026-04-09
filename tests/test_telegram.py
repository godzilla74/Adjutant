# tests/test_telegram.py
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.telegram import TelegramBot, _parse_product_id

PRODUCTS = [
    {"id": "alpha",   "name": "Alpha"},
    {"id": "beta",    "name": "Beta"},
]


# ── _parse_product_id ────────────────────────────────────────────────────────

def test_parse_product_id_with_prefix():
    pid, msg = _parse_product_id("for Alpha: what's the status?", PRODUCTS)
    assert pid == "alpha"
    assert msg == "what's the status?"


def test_parse_product_id_case_insensitive():
    pid, msg = _parse_product_id("FOR ALPHA: hello", PRODUCTS)
    assert pid == "alpha"
    assert msg == "hello"


def test_parse_product_id_partial_match():
    pid, msg = _parse_product_id("for alph: update me", PRODUCTS)
    assert pid == "alpha"
    assert msg == "update me"


def test_parse_product_id_no_prefix():
    pid, msg = _parse_product_id("just a plain message", PRODUCTS)
    assert pid is None
    assert msg == "just a plain message"


def test_parse_product_id_no_match():
    pid, msg = _parse_product_id("for unknown-product: hello", PRODUCTS)
    assert pid is None
    assert msg == "for unknown-product: hello"


# ── TelegramBot helpers ──────────────────────────────────────────────────────

def _make_bot():
    """Return a TelegramBot with all callables mocked."""
    bot = TelegramBot(
        token="test-token",
        chat_id="123456",
        directive_callback=AsyncMock(),
        products_fn=lambda: PRODUCTS,
        last_active_product_fn=lambda: "alpha",
        resolve_review_fn=MagicMock(),
        broadcast_fn=AsyncMock(),
    )
    bot.send_message  = AsyncMock(return_value=99)
    bot.send_typing   = AsyncMock()
    bot.edit_message  = AsyncMock()
    bot.answer_callback = AsyncMock()
    return bot


def test_notify_agent_done_sends_for_pending_product():
    bot = _make_bot()
    bot._pending_products.add("alpha")
    asyncio.run(bot.notify({"type": "agent_done", "product_id": "alpha", "content": "Done!"}))
    bot.send_message.assert_awaited_once_with("Done!")
    assert "alpha" not in bot._pending_products


def test_notify_agent_done_ignores_non_pending():
    bot = _make_bot()
    asyncio.run(bot.notify({"type": "agent_done", "product_id": "alpha", "content": "Done!"}))
    bot.send_message.assert_not_awaited()


def test_notify_activity_done_always_sends():
    bot = _make_bot()
    asyncio.run(bot.notify({"type": "activity_done", "product_id": "alpha", "summary": "Research complete."}))
    bot.send_message.assert_awaited_once()
    call_text = bot.send_message.call_args[0][0]
    assert "Research complete." in call_text


def test_notify_review_item_sends_with_buttons():
    bot = _make_bot()
    item = {"id": 42, "title": "Email to client", "description": "Send invoice.", "risk_label": "financial"}
    asyncio.run(bot.notify({"type": "review_item_added", "product_id": "alpha", "item": item}))
    bot.send_message.assert_awaited_once()
    _, kwargs = bot.send_message.call_args
    markup = json.loads(kwargs["reply_markup"]) if isinstance(kwargs.get("reply_markup"), str) else kwargs.get("reply_markup")
    buttons = markup["inline_keyboard"][0]
    assert any("approve:42" in b["callback_data"] for b in buttons)
    assert any("reject:42"  in b["callback_data"] for b in buttons)


def test_handle_callback_approve_resolves_item():
    bot = _make_bot()
    callback = {
        "id": "cb1",
        "from": {"id": 123456},
        "data": "approve:42",
        "message": {"message_id": 99},
    }
    asyncio.run(bot._handle_callback(callback))
    bot.resolve_review_fn.assert_called_once_with(42, "approved")
    bot.broadcast_fn.assert_awaited_once()
    bot.edit_message.assert_awaited_once_with(99, "✅ Approved")


def test_handle_callback_reject_resolves_item():
    bot = _make_bot()
    callback = {
        "id": "cb2",
        "from": {"id": 123456},
        "data": "reject:42",
        "message": {"message_id": 99},
    }
    asyncio.run(bot._handle_callback(callback))
    bot.resolve_review_fn.assert_called_once_with(42, "skipped")
    bot.edit_message.assert_awaited_once_with(99, "❌ Rejected")


def test_handle_callback_wrong_chat_id_ignored():
    bot = _make_bot()
    callback = {
        "id": "cb3",
        "from": {"id": 999999},  # different chat ID
        "data": "approve:42",
        "message": {"message_id": 99},
    }
    asyncio.run(bot._handle_callback(callback))
    bot.resolve_review_fn.assert_not_called()


def test_handle_message_injects_directive():
    bot = _make_bot()
    message = {
        "from": {"id": 123456},
        "text": "for Alpha: update me",
    }
    asyncio.run(bot._handle_message(message))
    bot._directive_callback.assert_awaited_once_with("alpha", "update me")
    assert "alpha" in bot._pending_products


def test_handle_message_wrong_chat_id_ignored():
    bot = _make_bot()
    message = {"from": {"id": 999999}, "text": "hello"}
    asyncio.run(bot._handle_message(message))
    bot._directive_callback.assert_not_awaited()
