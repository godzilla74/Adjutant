# tests/test_google_oauth.py
import asyncio
import json
import base64
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


def test_build_authorization_url_gmail():
    from backend.google_oauth import build_authorization_url
    url = build_authorization_url("prod-1", "gmail", "client-id-123")
    assert url.startswith("https://accounts.google.com/o/oauth2/v2/auth")
    assert "client_id=client-id-123" in url
    assert "gmail" in url
    assert "access_type=offline" in url
    assert "prompt=consent" in url
    # State must decode back to correct product_id + service
    from urllib.parse import urlparse, parse_qs
    params = parse_qs(urlparse(url).query)
    state = params["state"][0]
    # state may have padding stripped — add it back
    padded = state + "==" * ((4 - len(state) % 4) % 4)
    decoded = json.loads(base64.urlsafe_b64decode(padded).decode())
    assert decoded["product_id"] == "prod-1"
    assert decoded["service"] == "gmail"


def test_build_authorization_url_calendar():
    from backend.google_oauth import build_authorization_url
    url = build_authorization_url("prod-2", "google_calendar", "cid")
    assert "calendar" in url


def test_build_authorization_url_invalid_service():
    from backend.google_oauth import build_authorization_url
    with pytest.raises(ValueError, match="Unknown service"):
        build_authorization_url("prod-1", "invalid_service", "cid")


def test_exchange_code_for_tokens():
    from backend.google_oauth import exchange_code_for_tokens
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "access_token": "acc", "refresh_token": "ref", "expires_in": 3600, "scope": "s"
    }
    mock_response.raise_for_status = MagicMock()
    async def run():
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client
            return await exchange_code_for_tokens("code123", "cid", "csec")
    result = asyncio.run(run())
    assert result["access_token"] == "acc"
    assert result["refresh_token"] == "ref"


def test_refresh_access_token():
    from backend.google_oauth import refresh_access_token
    mock_response = MagicMock()
    mock_response.json.return_value = {"access_token": "new_acc", "expires_in": 3600}
    mock_response.raise_for_status = MagicMock()
    async def run():
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client
            return await refresh_access_token("ref_tok", "cid", "csec")
    result = asyncio.run(run())
    assert result["access_token"] == "new_acc"


def test_get_user_email():
    from backend.google_oauth import get_user_email
    mock_response = MagicMock()
    mock_response.json.return_value = {"email": "user@example.com"}
    mock_response.raise_for_status = MagicMock()
    async def run():
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client
            return await get_user_email("tok123")
    email = asyncio.run(run())
    assert email == "user@example.com"
