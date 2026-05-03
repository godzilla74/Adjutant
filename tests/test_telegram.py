# tests/test_telegram.py
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.telegram import TelegramBot


# ── TelegramBot helpers ──────────────────────────────────────────────────────

def _make_bot():
    """Return a TelegramBot with all callables mocked."""
    bot = TelegramBot(
        token="test-token",
        chat_id="123456",
        directive_callback=AsyncMock(),
        resolve_review_fn=MagicMock(),
        broadcast_fn=AsyncMock(),
    )
    bot.send_message    = AsyncMock(return_value=99)
    bot.send_typing     = AsyncMock()
    bot.edit_message    = AsyncMock()
    bot.answer_callback = AsyncMock()
    return bot


def test_notify_agent_done_sends_for_pending_product():
    bot = _make_bot()
    bot._pending_products.add("alpha")
    asyncio.run(bot.notify({"type": "agent_done", "product_id": "alpha", "content": "Done!"}))
    bot.send_message.assert_awaited_once_with("Done!", chat_id=None)
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


def test_notify_agent_done_global_agent():
    bot = _make_bot()
    bot._pending_products.add(None)
    asyncio.run(bot.notify({"type": "agent_done", "product_id": None, "content": "Summary across all products."}))
    bot.send_message.assert_awaited_once_with("Summary across all products.", chat_id=None)
    assert None not in bot._pending_products


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


def test_handle_message_routes_to_global_agent():
    bot = _make_bot()
    message = {
        "from": {"id": 123456},
        "text": "Hello, what's going on?",
    }
    asyncio.run(bot._handle_message(message))
    bot._directive_callback.assert_awaited_once_with(None, "Hello, what's going on?")
    assert None in bot._pending_products


def test_handle_message_product_prefix_also_routes_to_global():
    """Old 'for X:' prefix is no longer parsed — global agent handles routing."""
    bot = _make_bot()
    message = {
        "from": {"id": 123456},
        "text": "for Alpha: update me",
    }
    asyncio.run(bot._handle_message(message))
    bot._directive_callback.assert_awaited_once_with(None, "for Alpha: update me")
    assert None in bot._pending_products


def test_handle_message_empty_text_ignored():
    bot = _make_bot()
    message = {"from": {"id": 123456}, "text": "   "}
    asyncio.run(bot._handle_message(message))
    bot._directive_callback.assert_not_awaited()


def test_handle_message_wrong_chat_id_ignored():
    bot = _make_bot()
    message = {"from": {"id": 999999}, "text": "hello"}
    asyncio.run(bot._handle_message(message))
    bot._directive_callback.assert_not_awaited()


def test_handle_message_video_downloads_and_injects(tmp_path):
    """Receiving a video message downloads the file and injects a reference."""
    bot = _make_bot()

    async def fake_download(file_id):
        dest = tmp_path / "20260410_120000_video.mp4"
        dest.write_bytes(b"fakevideo")
        return str(dest), "video/mp4"

    bot._download_telegram_file = fake_download

    message = {
        "from": {"id": 123456},
        "text": "",
        "video": {"file_id": "abc123", "mime_type": "video/mp4"},
    }
    asyncio.run(bot._handle_message(message))

    bot._directive_callback.assert_awaited_once()
    call_args = bot._directive_callback.call_args[0]
    assert call_args[0] is None
    assert "video/mp4" in call_args[1] or "mp4" in call_args[1]


def test_handle_message_photo_downloads_and_injects(tmp_path):
    """Receiving a photo downloads and injects a reference."""
    bot = _make_bot()

    async def fake_download(file_id):
        dest = tmp_path / "20260410_120000_photo.jpg"
        dest.write_bytes(b"fakejpeg")
        return str(dest), "image/jpeg"

    bot._download_telegram_file = fake_download

    message = {
        "from": {"id": 123456},
        "text": "look at this",
        "photo": [{"file_id": "ph1", "file_size": 100}, {"file_id": "ph2", "file_size": 500}],
    }
    asyncio.run(bot._handle_message(message))

    bot._directive_callback.assert_awaited_once()
    assert bot._directive_callback.call_args[0][0] is None
    text = bot._directive_callback.call_args[0][1]
    assert "look at this" in text


def test_send_document_calls_api(tmp_path):
    """send_document sends the file via Telegram sendDocument."""
    bot = _make_bot()

    test_file = tmp_path / "test.pdf"
    test_file.write_bytes(b"%PDF fake")

    with patch("httpx.AsyncClient") as mock_client:
        mock_instance = MagicMock()
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=False)
        mock_instance.post = AsyncMock(return_value=MagicMock())
        mock_client.return_value = mock_instance
        asyncio.run(bot.send_document(str(test_file)))
        mock_instance.post.assert_awaited_once()
        call_url = mock_instance.post.call_args[0][0]
        assert "sendDocument" in call_url


def test_send_video_falls_back_to_document_for_large_files(tmp_path):
    """Files over 50MB are sent as documents, not videos."""
    bot = _make_bot()
    big_file = tmp_path / "big.mp4"
    big_file.write_bytes(b"x")

    with patch("pathlib.Path.stat") as mock_stat:
        mock_stat.return_value.st_size = 60 * 1024 * 1024  # 60 MB
        bot.send_document = AsyncMock()
        asyncio.run(bot.send_video(str(big_file)))
        bot.send_document.assert_awaited_once_with(str(big_file))


def test_send_long_message_splits_at_paragraph_break():
    """Messages over 4096 chars are split into multiple sends, preferring paragraph breaks."""
    bot = _make_bot()
    chunk_a = "A" * 3000
    chunk_b = "B" * 3000
    long_text = chunk_a + "\n\n" + chunk_b
    asyncio.run(bot.send_long_message(long_text))
    assert bot.send_message.await_count == 2
    first_call_text = bot.send_message.call_args_list[0][0][0]
    assert first_call_text == chunk_a


def test_send_long_message_hard_splits_when_no_newline():
    """Hard-splits at 4096 chars when there are no newline opportunities."""
    bot = _make_bot()
    long_text = "X" * 9000
    asyncio.run(bot.send_long_message(long_text))
    assert bot.send_message.await_count == 3  # 4096 + 4096 + 808
    for call in bot.send_message.call_args_list:
        assert len(call[0][0]) <= 4096


def test_send_long_message_short_text_single_send():
    """Short text sends in one message."""
    bot = _make_bot()
    asyncio.run(bot.send_long_message("Hello!"))
    bot.send_message.assert_awaited_once_with("Hello!", chat_id=None)


def _make_raw_bot():
    """Return a TelegramBot without send_message mocked (for testing send_message itself)."""
    return TelegramBot(
        token="test-token",
        chat_id="123456",
        directive_callback=AsyncMock(),
        resolve_review_fn=MagicMock(),
        broadcast_fn=AsyncMock(),
    )


def _mock_httpx_post(bot_method, *args, **kwargs):
    """Run bot_method with httpx.AsyncClient patched. Returns the mock post call."""
    with patch("httpx.AsyncClient") as mock_client:
        mock_instance = MagicMock()
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=False)
        resp_mock = MagicMock()
        resp_mock.json.return_value = {"ok": True, "result": {"message_id": 1}}
        mock_instance.post = AsyncMock(return_value=resp_mock)
        mock_client.return_value = mock_instance
        asyncio.run(bot_method(*args, **kwargs))
        return mock_instance.post


def test_send_message_uses_override_chat_id():
    bot = _make_raw_bot()
    post_mock = _mock_httpx_post(bot.send_message, "Hello", chat_id="OTHER_CHAT")
    call_json = post_mock.call_args.kwargs["json"]
    assert call_json["chat_id"] == "OTHER_CHAT"


def test_send_message_uses_self_chat_id_by_default():
    bot = _make_raw_bot()
    post_mock = _mock_httpx_post(bot.send_message, "Hello")
    call_json = post_mock.call_args.kwargs["json"]
    assert call_json["chat_id"] == bot.chat_id


def test_notify_activity_done_uses_per_product_chat():
    bot = _make_bot()
    with patch("backend.db.get_orchestrator_config",
               return_value={"slack_channel_id": None, "discord_channel_id": None, "telegram_chat_id": "-1001"}):
        asyncio.run(bot.notify({"type": "activity_done", "product_id": "p1", "summary": "Done"}))
    call_kwargs = bot.send_message.call_args.kwargs
    assert call_kwargs["chat_id"] == "-1001"


def test_notify_activity_done_falls_back_to_global_chat():
    bot = _make_bot()
    with patch("backend.db.get_orchestrator_config",
               return_value={"slack_channel_id": None, "discord_channel_id": None, "telegram_chat_id": None}):
        asyncio.run(bot.notify({"type": "activity_done", "product_id": "p1", "summary": "Done"}))
    call_kwargs = bot.send_message.call_args.kwargs
    assert call_kwargs["chat_id"] == bot.chat_id
