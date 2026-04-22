import importlib
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture(autouse=True)
def reset_tools(tmp_path_factory, monkeypatch):
    db_path = tmp_path_factory.mktemp("db") / "test.db"
    monkeypatch.setenv("AGENT_DB", str(db_path))
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


@pytest.mark.asyncio
async def test_generate_image_no_token_returns_error():
    import core.tools as tools_mod
    importlib.reload(tools_mod)
    result = await tools_mod.execute_tool("generate_image", {"prompt": "a sunset"})
    assert "not configured" in result.lower()


@pytest.mark.asyncio
async def test_generate_image_returns_localhost_url(tmp_path, monkeypatch):
    import core.tools as tools_mod
    importlib.reload(tools_mod)
    import backend.db as db_mod
    db_mod.set_agent_config("openai_access_token", "sk-test")
    monkeypatch.setenv("HANNAH_PORT", "8001")

    fake_image_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100

    openai_resp = MagicMock()
    openai_resp.status_code = 200
    openai_resp.json.return_value = {"data": [{"url": "https://oai.com/img/abc.png"}]}
    openai_resp.raise_for_status = MagicMock()

    img_resp = MagicMock()
    img_resp.status_code = 200
    img_resp.content = fake_image_bytes
    img_resp.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_cls, \
         patch("backend.uploads.get_uploads_dir", return_value=tmp_path):
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=openai_resp)
        mock_client.get = AsyncMock(return_value=img_resp)
        mock_cls.return_value = mock_client
        result = await tools_mod.execute_tool("generate_image", {"prompt": "a sunset"})

    assert result.startswith("http://localhost:8001/uploads/")
    assert result.endswith(".png")
    # Verify file was saved
    saved_files = list(tmp_path.iterdir())
    assert len(saved_files) == 1
    assert saved_files[0].read_bytes() == fake_image_bytes


@pytest.mark.asyncio
async def test_generate_image_api_failure_returns_error(monkeypatch):
    import core.tools as tools_mod
    importlib.reload(tools_mod)
    import backend.db as db_mod
    import httpx
    db_mod.set_agent_config("openai_access_token", "sk-test")

    with patch("httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(side_effect=httpx.HTTPStatusError(
            "error", request=MagicMock(), response=MagicMock(status_code=401, text="Unauthorized")
        ))
        mock_cls.return_value = mock_client
        result = await tools_mod.execute_tool("generate_image", {"prompt": "a sunset"})

    assert "failed" in result.lower() or "error" in result.lower()
