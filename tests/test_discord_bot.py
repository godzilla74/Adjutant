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
    msg, thread = _make_message("<@12345> hello world")
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
    bot.broadcast_fn.assert_awaited_once()
    interaction.edit_original_response.assert_awaited_once()


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
    thread.send.assert_awaited_once_with("Done!")
    assert None not in bot._pending_products


def test_notify_agent_done_ignores_non_pending():
    bot = _make_bot()
    asyncio.run(bot.notify({"type": "agent_done", "product_id": None, "content": "Done!"}))
    assert bot._pending_products == {}


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


# ── per-product Discord channel routing ──────────────────────────────────────

def test_notify_activity_done_uses_per_product_discord_channel():
    bot = _make_bot()
    mock_channel = MagicMock()
    mock_channel.send = AsyncMock()
    bot._client = MagicMock()
    bot._client.get_channel = MagicMock(return_value=mock_channel)
    with patch("backend.db.get_orchestrator_config",
               return_value={"slack_channel_id": None, "discord_channel_id": "99999", "telegram_chat_id": None}):
        asyncio.run(bot.notify({"type": "activity_done", "product_id": "p1", "summary": "Done"}))
    bot._client.get_channel.assert_called_with(99999)
    mock_channel.send.assert_awaited_once()


def test_notify_activity_done_falls_back_to_global_discord_channel():
    bot = _make_bot()
    mock_channel = MagicMock()
    mock_channel.send = AsyncMock()
    bot._client = MagicMock()
    bot._client.get_channel = MagicMock(return_value=mock_channel)
    with patch("backend.db.get_orchestrator_config",
               return_value={"slack_channel_id": None, "discord_channel_id": None, "telegram_chat_id": None}):
        asyncio.run(bot.notify({"type": "activity_done", "product_id": "p1", "summary": "Done"}))
    bot._client.get_channel.assert_called_with(bot.notification_channel_id)


def test_notify_review_item_uses_per_product_discord_channel():
    bot = _make_bot()
    mock_channel = MagicMock()
    mock_channel.send = AsyncMock()
    bot._client = MagicMock()
    bot._client.get_channel = MagicMock(return_value=mock_channel)
    item = {"id": 10, "title": "T", "description": "", "risk_label": ""}
    with patch("backend.db.get_orchestrator_config",
               return_value={"slack_channel_id": None, "discord_channel_id": "99999", "telegram_chat_id": None}):
        asyncio.run(bot.notify({"type": "review_item_added", "product_id": "p1", "item": item}))
    bot._client.get_channel.assert_called_with(99999)
