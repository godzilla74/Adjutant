# tests/test_google_api.py
import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _mock_token():
    """Patch get_valid_access_token to return a fake token."""
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
