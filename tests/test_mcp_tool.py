# tests/test_mcp_tool.py
import asyncio
import importlib
import pytest
from unittest.mock import patch


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_DB", str(tmp_path / "test.db"))
    import backend.db as db_mod
    importlib.reload(db_mod)
    db_mod.init_db()
    return db_mod


def _run(coro):
    return asyncio.run(coro)


def test_manage_mcp_server_tool_in_definitions():
    from core.tools import TOOLS_DEFINITIONS
    names = [t["name"] for t in TOOLS_DEFINITIONS]
    assert "manage_mcp_server" in names


def test_manage_mcp_server_in_executor(db, monkeypatch):
    monkeypatch.setenv("AGENT_DB", str(db.DB_PATH))
    with patch("backend.main._mcp_manager", None, create=True):
        from core.tools import execute_tool
        result = _run(execute_tool("manage_mcp_server", {"action": "list"}))
    assert isinstance(result, str)


def test_list_action_no_servers(db, monkeypatch):
    monkeypatch.setenv("AGENT_DB", str(db.DB_PATH))
    with patch("backend.main._mcp_manager", None, create=True):
        from core.tools import _manage_mcp_server
        result = _run(_manage_mcp_server(action="list"))
    assert "No MCP servers" in result


def test_add_remote_server(db, monkeypatch):
    monkeypatch.setenv("AGENT_DB", str(db.DB_PATH))
    with patch("backend.main._mcp_manager", None, create=True):
        from core.tools import _manage_mcp_server
        result = _run(_manage_mcp_server(
            action="add",
            name="GoHighLevel",
            type="remote",
            url="https://services.leadconnectorhq.com/mcp/sse",
            env={"authorization_token": "Bearer test"},
            scope="global",
        ))
    assert "added" in result.lower()
    servers = db.list_all_mcp_servers()
    assert any(s["name"] == "GoHighLevel" for s in servers)


def test_add_requires_url_for_remote(db, monkeypatch):
    monkeypatch.setenv("AGENT_DB", str(db.DB_PATH))
    with patch("backend.main._mcp_manager", None, create=True):
        from core.tools import _manage_mcp_server
        result = _run(_manage_mcp_server(
            action="add", name="Test", type="remote", scope="global",
        ))
    assert "url is required" in result.lower()


def test_add_requires_command_for_stdio(db, monkeypatch):
    monkeypatch.setenv("AGENT_DB", str(db.DB_PATH))
    with patch("backend.main._mcp_manager", None, create=True):
        from core.tools import _manage_mcp_server
        result = _run(_manage_mcp_server(
            action="add", name="Test", type="stdio", scope="global",
        ))
    assert "command is required" in result.lower()


def test_remove_server(db, monkeypatch):
    monkeypatch.setenv("AGENT_DB", str(db.DB_PATH))
    sid = db.add_mcp_server(
        name="ToRemove", type="remote", url="https://example.com",
        command=None, args=None, env=None, scope="global", product_id=None,
    )
    with patch("backend.main._mcp_manager", None, create=True):
        from core.tools import _manage_mcp_server
        result = _run(_manage_mcp_server(action="remove", server_id=sid))
    assert "Removed" in result
    assert db.get_mcp_server(sid) is None


def test_enable_disable_server(db, monkeypatch):
    monkeypatch.setenv("AGENT_DB", str(db.DB_PATH))
    sid = db.add_mcp_server(
        name="TestServer", type="remote", url="https://example.com",
        command=None, args=None, env=None, scope="global", product_id=None,
    )
    with patch("backend.main._mcp_manager", None, create=True):
        from core.tools import _manage_mcp_server
        _run(_manage_mcp_server(action="disable", server_id=sid))
        assert db.get_mcp_server(sid)["enabled"] == 0
        _run(_manage_mcp_server(action="enable", server_id=sid))
        assert db.get_mcp_server(sid)["enabled"] == 1
