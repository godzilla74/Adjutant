# tests/test_mcp_manager.py
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.mcp_manager import MCPManager, fetch_remote_tools


def _make_mock_tool(name: str, description: str = "A tool", schema: dict | None = None):
    tool = MagicMock()
    tool.name = name
    tool.description = description
    tool.inputSchema = schema or {"type": "object", "properties": {}}
    return tool


STDIO_CONFIG = {
    "id": 1,
    "name": "TestServer",
    "type": "stdio",
    "command": "npx",
    "args": '["@test/server"]',
    "env": "{}",
    "scope": "global",
    "product_id": None,
    "enabled": 1,
}


@pytest.fixture
def manager():
    return MCPManager()


def test_get_tools_empty_initially(manager):
    assert manager.get_tools() == []


def test_execute_tool_unknown_returns_error(manager):
    result = asyncio.run(manager.execute_tool("mcp__unknown__tool", {}))
    assert "Unknown MCP tool" in result


def test_execute_tool_no_session_returns_error(manager):
    manager._tool_to_server["mcp__test__tool"] = (99, "tool")
    result = asyncio.run(manager.execute_tool("mcp__test__tool", {}))
    assert "not currently connected" in result


def test_register_tools_namespaces_correctly(manager):
    mock_tool = _make_mock_tool("get_contacts")
    manager._register_tools(1, "GoHighLevel", [mock_tool])
    tools = manager.get_tools()
    assert len(tools) == 1
    assert tools[0]["name"] == "mcp__gohighlevel__get_contacts"
    assert tools[0]["description"] == "A tool"


def test_register_tools_server_name_with_spaces(manager):
    mock_tool = _make_mock_tool("search")
    manager._register_tools(1, "My Server", [mock_tool])
    tools = manager.get_tools()
    assert tools[0]["name"] == "mcp__my_server__search"


def test_tool_to_server_mapping_tracks_original_name(manager):
    mock_tool = _make_mock_tool("send_email")
    manager._register_tools(2, "MailService", [mock_tool])
    assert "mcp__mailservice__send_email" in manager._tool_to_server
    server_id, original = manager._tool_to_server["mcp__mailservice__send_email"]
    assert server_id == 2
    assert original == "send_email"


def test_clear_tools_removes_server_tools(manager):
    mock_tool = _make_mock_tool("get_contacts")
    manager._register_tools(1, "GoHighLevel", [mock_tool])
    manager._clear_tools(1)
    assert manager.get_tools() == []
    assert len(manager._tool_to_server) == 0


def test_clear_tools_only_removes_target_server(manager):
    manager._register_tools(1, "ServerA", [_make_mock_tool("tool_a")])
    manager._register_tools(2, "ServerB", [_make_mock_tool("tool_b")])
    manager._clear_tools(1)
    tools = manager.get_tools()
    assert len(tools) == 1
    assert tools[0]["name"] == "mcp__serverb__tool_b"


def test_execute_tool_calls_session(manager):
    mock_tool = _make_mock_tool("get_contacts")
    manager._register_tools(1, "GoHighLevel", [mock_tool])

    content_block = MagicMock()
    content_block.text = "Contact list"
    mock_result = MagicMock()
    mock_result.content = [content_block]

    mock_session = AsyncMock()
    mock_session.call_tool = AsyncMock(return_value=mock_result)
    manager._sessions[1] = mock_session

    result = asyncio.run(manager.execute_tool("mcp__gohighlevel__get_contacts", {"query": "test"}))
    mock_session.call_tool.assert_awaited_once_with("get_contacts", {"query": "test"})
    assert result == "Contact list"


def test_execute_tool_empty_content_returns_placeholder(manager):
    manager._register_tools(1, "Server", [_make_mock_tool("do_thing")])
    mock_result = MagicMock()
    mock_result.content = []
    mock_session = AsyncMock()
    mock_session.call_tool = AsyncMock(return_value=mock_result)
    manager._sessions[1] = mock_session
    result = asyncio.run(manager.execute_tool("mcp__server__do_thing", {}))
    assert result == "(no output)"


def test_remove_server_clears_tools_and_session(manager):
    manager._register_tools(1, "Server", [_make_mock_tool("tool1")])
    manager._sessions[1] = AsyncMock()
    asyncio.run(manager.remove_server(1))
    assert manager.get_tools() == []
    assert 1 not in manager._sessions


# ── fetch_remote_tools ────────────────────────────────────────────────────────

def _make_remote_tool(name: str, description: str = "A tool"):
    tool = MagicMock()
    tool.name = name
    tool.description = description
    tool.inputSchema = {"type": "object", "properties": {}}
    return tool


@pytest.mark.asyncio
async def test_fetch_remote_tools_returns_tool_list():
    mock_result = MagicMock()
    mock_result.tools = [_make_remote_tool("create_contact", "Create a contact")]

    mock_session = AsyncMock()
    mock_session.initialize = AsyncMock()
    mock_session.list_tools = AsyncMock(return_value=mock_result)

    mock_client_session = MagicMock()
    mock_client_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_client_session.__aexit__ = AsyncMock(return_value=None)

    mock_sse = MagicMock()
    mock_sse.__aenter__ = AsyncMock(return_value=(AsyncMock(), AsyncMock()))
    mock_sse.__aexit__ = AsyncMock(return_value=None)

    with patch("mcp.client.sse.sse_client", return_value=mock_sse), \
         patch("mcp.ClientSession", return_value=mock_client_session):
        tools = await fetch_remote_tools("https://example.com/mcp", {"x-api-key": "test"})

    assert len(tools) == 1
    assert tools[0]["name"] == "create_contact"
    assert tools[0]["description"] == "Create a contact"
    assert "input_schema" in tools[0]


@pytest.mark.asyncio
async def test_fetch_remote_tools_returns_empty_on_error():
    with patch("mcp.client.sse.sse_client", side_effect=Exception("Connection refused")):
        tools = await fetch_remote_tools("https://bad-url.com/mcp", {})
    assert tools == []
