# tests/test_social_oauth.py
import asyncio
import importlib
import os
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

os.environ.setdefault("AGENT_PASSWORD", "testpass")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_DB", str(tmp_path / "test.db"))
    import backend.db as db_mod
    importlib.reload(db_mod)
    db_mod.init_db()
    return db_mod


def test_social_credential_keys_have_defaults(db):
    config = db.get_agent_config()
    assert "twitter_client_id" in config
    assert "twitter_client_secret" in config
    assert "linkedin_client_id" in config
    assert "linkedin_client_secret" in config
    assert "meta_app_id" in config
    assert "meta_app_secret" in config
    assert config["twitter_client_id"] == ""
    assert config["meta_app_id"] == ""



def test_build_twitter_auth_url(db):
    db.set_agent_config("twitter_client_id", "tw-cid")
    from backend.social_oauth import build_authorization_url
    url = build_authorization_url("prod-1", "twitter", "tw-cid")
    assert "twitter.com" in url
    assert "tw-cid" in url
    assert "code_challenge" in url


def test_build_linkedin_auth_url(db):
    from backend.social_oauth import build_authorization_url
    url = build_authorization_url("prod-1", "linkedin", "li-cid")
    assert "linkedin.com" in url
    assert "li-cid" in url


def test_build_meta_auth_url(db):
    from backend.social_oauth import build_authorization_url
    url = build_authorization_url("prod-1", "meta", "meta-app-id")
    assert "facebook.com" in url
    assert "meta-app-id" in url


def test_build_authorization_url_unknown_service():
    from backend.social_oauth import build_authorization_url
    with pytest.raises(ValueError, match="Unknown service"):
        build_authorization_url("prod-1", "badservice", "cid")


def test_twitter_exchange_code_for_tokens():
    async def run():
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "access_token": "tw-access",
            "refresh_token": "tw-refresh",
            "expires_in": 7200,
            "scope": "tweet.write users.read",
        }
        mock_resp.raise_for_status = MagicMock()
        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_cls.return_value = mock_client
            from backend.social_oauth import exchange_code_for_tokens
            result = await exchange_code_for_tokens("mycode", "twitter", "cid", "csec", code_verifier="verifier123")
        assert result["access_token"] == "tw-access"
    asyncio.run(run())


def test_linkedin_exchange_code_for_tokens():
    async def run():
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "access_token": "li-access",
            "expires_in": 5184000,
            "scope": "w_member_social",
        }
        mock_resp.raise_for_status = MagicMock()
        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_cls.return_value = mock_client
            from backend.social_oauth import exchange_code_for_tokens
            result = await exchange_code_for_tokens("mycode", "linkedin", "cid", "csec")
        assert result["access_token"] == "li-access"
    asyncio.run(run())
