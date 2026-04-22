import importlib
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture(autouse=True)
def reset_tools(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_DB", str(tmp_path / "test.db"))
    import backend.db as db_mod
    importlib.reload(db_mod)
    db_mod.init_db()


def _make_pexels_response(url: str):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "photos": [{"src": {"large2x": url}}]
    }
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


@pytest.mark.asyncio
async def test_search_stock_photo_returns_url():
    import core.tools as tools_mod
    importlib.reload(tools_mod)
    import backend.db as db_mod
    db_mod.set_agent_config("pexels_api_key", "test-key")

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=_make_pexels_response("https://pexels.com/photo.jpg"))
        mock_client_cls.return_value = mock_client
        result = await tools_mod.execute_tool("search_stock_photo", {"query": "sunset"})

    assert result == "https://pexels.com/photo.jpg"


@pytest.mark.asyncio
async def test_search_stock_photo_no_key_returns_error():
    import core.tools as tools_mod
    importlib.reload(tools_mod)
    result = await tools_mod.execute_tool("search_stock_photo", {"query": "sunset"})
    assert "not configured" in result.lower()


@pytest.mark.asyncio
async def test_search_stock_photo_no_results():
    import core.tools as tools_mod
    importlib.reload(tools_mod)
    import backend.db as db_mod
    db_mod.set_agent_config("pexels_api_key", "test-key")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"photos": []}
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client
        result = await tools_mod.execute_tool("search_stock_photo", {"query": "xyzzy"})

    assert "no" in result.lower() or "not found" in result.lower()


@pytest.mark.asyncio
async def test_search_stock_photo_api_error_returns_error():
    import core.tools as tools_mod
    importlib.reload(tools_mod)
    import backend.db as db_mod
    import httpx
    db_mod.set_agent_config("pexels_api_key", "bad-key")

    mock_resp = MagicMock()
    mock_resp.status_code = 401
    error = httpx.HTTPStatusError("Unauthorized", request=MagicMock(), response=mock_resp)

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(side_effect=error)
        mock_client_cls.return_value = mock_client
        result = await tools_mod.execute_tool("search_stock_photo", {"query": "sunset"})

    assert "error" in result.lower() or "failed" in result.lower()
