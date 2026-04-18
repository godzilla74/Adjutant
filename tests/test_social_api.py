import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch


def _mock_token():
    return patch("backend.social_api.get_valid_access_token", new=AsyncMock(return_value="fake-tok"))


def test_twitter_post():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"data": {"id": "123", "text": "Hello"}}
    mock_resp.raise_for_status = MagicMock()
    async def run():
        with _mock_token(), patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_cls.return_value = mock_client
            from backend.social_api import twitter_post
            result = json.loads(await twitter_post("p1", "Hello world"))
        assert result["posted"] is True
        assert result["post_id"] == "123"
    asyncio.run(run())


def test_linkedin_post():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"id": "urn:li:ugcPost:456"}
    mock_resp.raise_for_status = MagicMock()
    async def run():
        with _mock_token(), patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_cls.return_value = mock_client
            with patch("backend.db.get_oauth_connection", return_value={"email": "urn:li:person:abc"}):
                from backend.social_api import linkedin_post
                result = json.loads(await linkedin_post("p1", "Hello LinkedIn"))
        assert result["posted"] is True
        assert "456" in result["post_id"]
    asyncio.run(run())


def test_facebook_post():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"id": "111_222"}
    mock_resp.raise_for_status = MagicMock()
    async def run():
        with _mock_token(), patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_cls.return_value = mock_client
            with patch("backend.db.get_oauth_connection", return_value={"email": "page-123"}):
                from backend.social_api import facebook_post
                result = json.loads(await facebook_post("p1", "Hello Facebook"))
        assert result["posted"] is True
        assert result["post_id"] == "111_222"
    asyncio.run(run())


def test_instagram_post():
    container_resp = MagicMock()
    container_resp.json.return_value = {"id": "container-1"}
    container_resp.raise_for_status = MagicMock()
    publish_resp = MagicMock()
    publish_resp.json.return_value = {"id": "post-999"}
    publish_resp.raise_for_status = MagicMock()
    async def run():
        with _mock_token(), patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(side_effect=[container_resp, publish_resp])
            mock_cls.return_value = mock_client
            with patch("backend.db.get_oauth_connection", return_value={"email": "ig-456"}):
                from backend.social_api import instagram_post
                result = json.loads(await instagram_post("p1", "Hello Instagram", "https://example.com/img.jpg"))
        assert result["posted"] is True
        assert result["post_id"] == "post-999"
    asyncio.run(run())
