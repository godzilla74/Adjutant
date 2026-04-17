# tests/test_google_api.py
import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _mock_token():
    return patch(
        "backend.google_api.get_valid_access_token",
        new=AsyncMock(return_value="fake_token"),
    )


def test_gmail_search_returns_message_ids():
    from backend.google_api import gmail_search
    payload = {"messages": [{"id": "msg1"}, {"id": "msg2"}]}
    mock_resp = MagicMock()
    mock_resp.json.return_value = payload
    mock_resp.raise_for_status = MagicMock()
    async def run():
        with _mock_token(), patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_cls.return_value = mock_client
            return json.loads(await gmail_search("p1", "from:test@example.com"))
    result = asyncio.run(run())
    assert result["message_ids"] == ["msg1", "msg2"]
    assert result["count"] == 2


def test_gmail_search_no_results():
    from backend.google_api import gmail_search
    mock_resp = MagicMock()
    mock_resp.json.return_value = {}
    mock_resp.raise_for_status = MagicMock()
    async def run():
        with _mock_token(), patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_cls.return_value = mock_client
            return await gmail_search("p1", "nothing")
    result = asyncio.run(run())
    assert result == "No messages found."


def test_gmail_send_returns_confirmation():
    from backend.google_api import gmail_send
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"id": "sent-id", "threadId": "thread-1"}
    mock_resp.raise_for_status = MagicMock()
    async def run():
        with _mock_token(), patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_cls.return_value = mock_client
            return json.loads(await gmail_send("p1", "to@x.com", "Subject", "Body"))
    result = asyncio.run(run())
    assert result["sent"] is True
    assert result["message_id"] == "sent-id"


def test_gmail_draft_returns_draft_id():
    from backend.google_api import gmail_draft
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"id": "draft-1"}
    mock_resp.raise_for_status = MagicMock()
    async def run():
        with _mock_token(), patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_cls.return_value = mock_client
            return json.loads(await gmail_draft("p1", "to@x.com", "Subject", "Body"))
    result = asyncio.run(run())
    assert result["draft_id"] == "draft-1"
    assert result["created"] is True


# ── _extract_body tests ────────────────────────────────────────────────────────

import base64

def _encode(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode()).decode()


def test_extract_body_flat_text_plain():
    from backend.google_api import _extract_body
    payload = {
        "mimeType": "text/plain",
        "body": {"data": _encode("Hello world")},
    }
    assert _extract_body(payload) == "Hello world"


def test_extract_body_nested_multipart():
    from backend.google_api import _extract_body
    payload = {
        "mimeType": "multipart/mixed",
        "parts": [
            {
                "mimeType": "text/plain",
                "body": {"data": _encode("Nested body")},
            }
        ],
    }
    assert _extract_body(payload) == "Nested body"


def test_extract_body_no_text_plain():
    from backend.google_api import _extract_body
    payload = {
        "mimeType": "multipart/mixed",
        "parts": [
            {
                "mimeType": "text/html",
                "body": {"data": _encode("<p>HTML only</p>")},
            }
        ],
    }
    assert _extract_body(payload) == ""


# ── gmail_read tests ───────────────────────────────────────────────────────────

def _make_gmail_message_payload(body_text: str) -> dict:
    return {
        "id": "msg-abc",
        "threadId": "thread-abc",
        "payload": {
            "mimeType": "multipart/mixed",
            "headers": [
                {"name": "From", "value": "sender@example.com"},
                {"name": "To", "value": "recipient@example.com"},
                {"name": "Subject", "value": "Test Subject"},
                {"name": "Date", "value": "Thu, 17 Apr 2026 10:00:00 +0000"},
            ],
            "parts": [
                {
                    "mimeType": "text/plain",
                    "body": {"data": _encode(body_text)},
                }
            ],
        },
    }


def test_gmail_read_returns_correct_fields():
    from backend.google_api import gmail_read
    api_payload = _make_gmail_message_payload("This is the email body.")
    mock_resp = MagicMock()
    mock_resp.json.return_value = api_payload
    mock_resp.raise_for_status = MagicMock()
    async def run():
        with _mock_token(), patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_cls.return_value = mock_client
            return json.loads(await gmail_read("p1", "msg-abc"))
    result = asyncio.run(run())
    assert result["from"] == "sender@example.com"
    assert result["to"] == "recipient@example.com"
    assert result["subject"] == "Test Subject"
    assert result["date"] == "Thu, 17 Apr 2026 10:00:00 +0000"
    assert result["body"] == "This is the email body."


def test_gmail_read_body_capped_at_3000_chars():
    from backend.google_api import gmail_read
    long_body = "x" * 5000
    api_payload = _make_gmail_message_payload(long_body)
    mock_resp = MagicMock()
    mock_resp.json.return_value = api_payload
    mock_resp.raise_for_status = MagicMock()
    async def run():
        with _mock_token(), patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_cls.return_value = mock_client
            return json.loads(await gmail_read("p1", "msg-abc"))
    result = asyncio.run(run())
    assert len(result["body"]) == 3000


def test_calendar_list_events():
    from backend.google_api import calendar_list_events
    events_payload = {"items": [
        {
            "id": "evt1",
            "summary": "Standup",
            "start": {"dateTime": "2026-04-18T09:00:00Z"},
            "end": {"dateTime": "2026-04-18T09:30:00Z"},
            "attendees": [{"email": "a@x.com"}],
        }
    ]}
    mock_resp = MagicMock()
    mock_resp.json.return_value = events_payload
    mock_resp.raise_for_status = MagicMock()
    async def run():
        with patch("backend.google_oauth.get_valid_access_token", new=AsyncMock(return_value="tok")), \
             patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_cls.return_value = mock_client
            return json.loads(await calendar_list_events("p1", "2026-04-18T00:00:00Z", "2026-04-18T23:59:59Z"))
    result = asyncio.run(run())
    assert result["count"] == 1
    assert result["events"][0]["summary"] == "Standup"
    assert result["events"][0]["attendees"] == ["a@x.com"]


def test_calendar_create_event():
    from backend.google_api import calendar_create_event
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"id": "new-evt", "htmlLink": "https://cal.google.com/evt"}
    mock_resp.raise_for_status = MagicMock()
    async def run():
        with patch("backend.google_oauth.get_valid_access_token", new=AsyncMock(return_value="tok")), \
             patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_cls.return_value = mock_client
            return json.loads(await calendar_create_event(
                "p1", "Team Sync", "2026-04-18T10:00:00Z", "2026-04-18T10:30:00Z",
                attendees=["b@x.com"],
            ))
    result = asyncio.run(run())
    assert result["created"] is True
    assert result["event_id"] == "new-evt"
