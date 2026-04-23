# tests/test_capability_overrides.py
import importlib
import pytest


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_DB", str(tmp_path / "test.db"))
    import backend.db as db_mod
    importlib.reload(db_mod)
    db_mod.init_db()
    db_mod.create_product("prod-1", "Product One", "P1", "#ff0000")
    db_mod.create_product("prod-2", "Product Two", "P2", "#0000ff")
    return db_mod


def test_set_and_list_capability_override(db):
    db.set_capability_override("prod-1", "social_post", "gohighlevel", "mcp__gohighlevel__social_media_post")
    overrides = db.list_capability_overrides("prod-1")
    assert len(overrides) == 1
    assert overrides[0]["capability_slot"] == "social_post"
    assert overrides[0]["mcp_server_name"] == "gohighlevel"
    assert overrides[0]["mcp_tool_name"] == "mcp__gohighlevel__social_media_post"


def test_set_override_is_upsert(db):
    db.set_capability_override("prod-1", "social_post", "server-a", "mcp__server-a__post")
    db.set_capability_override("prod-1", "social_post", "server-b", "mcp__server-b__post")
    overrides = db.list_capability_overrides("prod-1")
    assert len(overrides) == 1
    assert overrides[0]["mcp_server_name"] == "server-b"


def test_delete_capability_override(db):
    db.set_capability_override("prod-1", "social_post", "gohighlevel", "mcp__gohighlevel__post")
    db.delete_capability_override("prod-1", "social_post")
    assert db.list_capability_overrides("prod-1") == []


def test_list_overrides_scoped_to_product(db):
    db.set_capability_override("prod-1", "social_post", "server-a", "mcp__server-a__post")
    db.set_capability_override("prod-2", "social_post", "server-b", "mcp__server-b__post")
    assert len(db.list_capability_overrides("prod-1")) == 1
    assert db.list_capability_overrides("prod-1")[0]["mcp_server_name"] == "server-a"


def test_mcp_manager_get_connected_server_names():
    from backend.mcp_manager import MCPManager
    mgr = MCPManager()
    mgr._sessions[1] = object()
    mgr._server_id_to_name[1] = "ghl"
    assert mgr.get_connected_server_names() == {"ghl"}


def test_mcp_manager_get_connected_server_names_excludes_disconnected():
    from backend.mcp_manager import MCPManager
    mgr = MCPManager()
    # Server 1 connected, server 2 registered but not in _sessions
    mgr._sessions[1] = object()
    mgr._server_id_to_name[1] = "ghl"
    mgr._server_id_to_name[2] = "other"
    result = mgr.get_connected_server_names()
    assert "ghl" in result
    assert "other" not in result


def test_mcp_manager_get_tools_for_server():
    from backend.mcp_manager import MCPManager
    mgr = MCPManager()
    mgr._sessions[1] = object()
    mgr._server_id_to_name[1] = "ghl"
    mgr._tool_to_server["mcp__ghl__post"] = (1, "post")
    mgr._tool_defs["mcp__ghl__post"] = {"name": "mcp__ghl__post", "description": "Post", "input_schema": {}}
    mgr._tool_to_server["mcp__ghl__contact"] = (1, "contact")
    mgr._tool_defs["mcp__ghl__contact"] = {"name": "mcp__ghl__contact", "description": "Contact", "input_schema": {}}
    tools = mgr.get_tools_for_server("ghl")
    names = [t["name"] for t in tools]
    assert "mcp__ghl__post" in names
    assert "mcp__ghl__contact" in names
    assert len(tools) == 2


def test_mcp_manager_get_tools_for_server_unknown_returns_empty():
    from backend.mcp_manager import MCPManager
    mgr = MCPManager()
    assert mgr.get_tools_for_server("nonexistent") == []


def test_capability_slots_covers_social_tools():
    from core.tools import CAPABILITY_SLOTS
    assert "social_post" in CAPABILITY_SLOTS
    social_tools = CAPABILITY_SLOTS["social_post"]
    assert "twitter_post" in social_tools
    assert "linkedin_post" in social_tools
    assert "facebook_post" in social_tools
    assert "instagram_post" in social_tools


def test_override_context_connected_server_suppresses_tools(db):
    db.set_capability_override("prod-1", "social_post", "ghl", "mcp__ghl__social_post")
    from core.tools import get_capability_override_context
    suppress, disconnected = get_capability_override_context("prod-1", connected_mcp_servers={"ghl"})
    assert "twitter_post" in suppress
    assert "linkedin_post" in suppress
    assert disconnected == {}


def test_override_context_disconnected_server_marks_tools(db):
    db.set_capability_override("prod-1", "social_post", "ghl", "mcp__ghl__social_post")
    from core.tools import get_capability_override_context
    suppress, disconnected = get_capability_override_context("prod-1", connected_mcp_servers=set())
    assert suppress == set()
    assert disconnected["twitter_post"] == "ghl"
    assert disconnected["linkedin_post"] == "ghl"


def test_override_context_no_overrides(db):
    from core.tools import get_capability_override_context
    suppress, disconnected = get_capability_override_context("prod-1", connected_mcp_servers=set())
    assert suppress == set()
    assert disconnected == {}


import asyncio
from unittest.mock import MagicMock


def test_preflight_intercept_disconnected_server():
    """Interceptor must return a reconnect prompt when override server is disconnected."""
    async def run():
        from backend.main import _build_preflight_interceptor
        interceptor = _build_preflight_interceptor(
            product_id="prod-1",
            disconnected_overrides={"twitter_post": "ghl"},
        )
        block = MagicMock()
        block.name = "twitter_post"
        block.input = {}
        block.id = "tu_123"
        result = await interceptor(block)
        assert result is not None
        assert "ghl" in result["content"]
        assert "disconnected" in result["content"].lower()
        assert result["tool_use_id"] == "tu_123"

    asyncio.run(run())


def test_preflight_intercept_force_builtin_bypasses():
    """force_builtin=True must cause interceptor to return None (proceed normally)."""
    async def run():
        from backend.main import _build_preflight_interceptor
        interceptor = _build_preflight_interceptor(
            product_id="prod-1",
            disconnected_overrides={"twitter_post": "ghl"},
        )
        block = MagicMock()
        block.name = "twitter_post"
        block.input = {"force_builtin": True, "text": "hello"}
        block.id = "tu_456"
        result = await interceptor(block)
        assert result is None

    asyncio.run(run())


def test_preflight_intercept_unregistered_tool_passes_through():
    """Tools not in disconnected_overrides must return None."""
    async def run():
        from backend.main import _build_preflight_interceptor
        interceptor = _build_preflight_interceptor(
            product_id="prod-1",
            disconnected_overrides={"twitter_post": "ghl"},
        )
        block = MagicMock()
        block.name = "some_other_tool"
        block.input = {}
        block.id = "tu_789"
        result = await interceptor(block)
        assert result is None

    asyncio.run(run())
