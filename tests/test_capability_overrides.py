# tests/test_capability_overrides.py
import importlib
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(db, monkeypatch):
    monkeypatch.setenv("AGENT_PASSWORD", "testpw")
    from backend.api import router
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_post_capability_slot_creates(client, db):
    resp = client.post(
        "/api/capability-slots",
        json={"name": "crm_contacts", "label": "Contact Management", "built_in_tools": []},
        headers={"X-Agent-Password": "testpw"},
    )
    assert resp.status_code == 201
    assert resp.json()["ok"] is True
    slots = db.list_capability_slot_definitions()
    assert any(s["name"] == "crm_contacts" for s in slots)


def test_post_capability_slot_duplicate_returns_400(client, db):
    resp = client.post(
        "/api/capability-slots",
        json={"name": "social_post", "label": "Dupe", "built_in_tools": []},
        headers={"X-Agent-Password": "testpw"},
    )
    assert resp.status_code == 400


def test_delete_capability_slot_custom(client, db):
    db.create_capability_slot_definition("crm_contacts", "Contact Management", [])
    resp = client.delete(
        "/api/capability-slots/crm_contacts",
        headers={"X-Agent-Password": "testpw"},
    )
    assert resp.status_code == 204
    slots = db.list_capability_slot_definitions()
    assert not any(s["name"] == "crm_contacts" for s in slots)


def test_delete_capability_slot_system_returns_400(client, db):
    resp = client.delete(
        "/api/capability-slots/social_post",
        headers={"X-Agent-Password": "testpw"},
    )
    assert resp.status_code == 400


def test_delete_capability_slot_not_found_returns_400(client):
    resp = client.delete(
        "/api/capability-slots/does_not_exist",
        headers={"X-Agent-Password": "testpw"},
    )
    assert resp.status_code == 400


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_DB", str(tmp_path / "test.db"))
    import backend.db as db_mod
    importlib.reload(db_mod)
    db_mod.init_db()
    db_mod.create_product("prod-1", "Product One", "P1", "#ff0000")
    db_mod.create_product("prod-2", "Product Two", "P2", "#0000ff")
    return db_mod


def test_list_capability_slot_definitions_returns_system_slots(db):
    slots = db.list_capability_slot_definitions()
    names = [s["name"] for s in slots]
    assert "social_post" in names
    assert "email_send" in names


def test_list_capability_slot_definitions_shape(db):
    slots = db.list_capability_slot_definitions()
    social = next(s for s in slots if s["name"] == "social_post")
    assert social["label"] == "Social Posting"
    assert isinstance(social["built_in_tools"], list)
    assert "twitter_post" in social["built_in_tools"]
    assert social["is_system"] == 1


def test_create_capability_slot_definition(db):
    db.create_capability_slot_definition("crm_contacts", "Contact Management", [])
    slots = db.list_capability_slot_definitions()
    names = [s["name"] for s in slots]
    assert "crm_contacts" in names
    slot = next(s for s in slots if s["name"] == "crm_contacts")
    assert slot["label"] == "Contact Management"
    assert slot["built_in_tools"] == []
    assert slot["is_system"] == 0


def test_create_capability_slot_definition_duplicate_raises(db):
    import sqlite3 as _sqlite3
    with pytest.raises(_sqlite3.IntegrityError):
        db.create_capability_slot_definition("social_post", "Dupe", [])


def test_delete_capability_slot_definition_custom(db):
    db.create_capability_slot_definition("crm_contacts", "Contact Management", [])
    db.delete_capability_slot_definition("crm_contacts")
    slots = db.list_capability_slot_definitions()
    assert "crm_contacts" not in [s["name"] for s in slots]


def test_delete_capability_slot_definition_system_raises(db):
    with pytest.raises(ValueError, match="system slot"):
        db.delete_capability_slot_definition("social_post")


def test_init_db_seeding_is_idempotent(db):
    import backend.db as db_mod
    db_mod.init_db()  # second call — must not fail or duplicate
    slots = db.list_capability_slot_definitions()
    social = [s for s in slots if s["name"] == "social_post"]
    assert len(social) == 1


def test_set_and_list_capability_override(db):
    db.set_capability_override("prod-1", "social_post", "gohighlevel", ["mcp__gohighlevel__social_media_post"])
    overrides = db.list_capability_overrides("prod-1")
    assert len(overrides) == 1
    assert overrides[0]["capability_slot"] == "social_post"
    assert overrides[0]["mcp_server_name"] == "gohighlevel"
    assert overrides[0]["mcp_tool_names"] == ["mcp__gohighlevel__social_media_post"]


def test_set_override_is_upsert(db):
    db.set_capability_override("prod-1", "social_post", "server-a", ["mcp__server-a__post"])
    db.set_capability_override("prod-1", "social_post", "server-b", ["mcp__server-b__post"])
    overrides = db.list_capability_overrides("prod-1")
    assert len(overrides) == 1
    assert overrides[0]["mcp_server_name"] == "server-b"


def test_delete_capability_override(db):
    db.set_capability_override("prod-1", "social_post", "gohighlevel", ["mcp__gohighlevel__post"])
    db.delete_capability_override("prod-1", "social_post")
    assert db.list_capability_overrides("prod-1") == []


def test_list_overrides_scoped_to_product(db):
    db.set_capability_override("prod-1", "social_post", "server-a", ["mcp__server-a__post"])
    db.set_capability_override("prod-2", "social_post", "server-b", ["mcp__server-b__post"])
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


def test_capability_slots_covers_social_tools(db):
    slots = db.list_capability_slot_definitions()
    social = next((s for s in slots if s["name"] == "social_post"), None)
    assert social is not None
    assert "twitter_post" in social["built_in_tools"]
    assert "linkedin_post" in social["built_in_tools"]
    assert "facebook_post" in social["built_in_tools"]
    assert "instagram_post" in social["built_in_tools"]


def test_override_context_connected_server_suppresses_tools(db):
    db.set_capability_override("prod-1", "social_post", "ghl", ["mcp__ghl__social_post"])
    from core.tools import get_capability_override_context
    suppress, disconnected = get_capability_override_context("prod-1", connected_mcp_servers={"ghl"})
    assert "twitter_post" in suppress
    assert "linkedin_post" in suppress
    assert disconnected == {}


def test_override_context_disconnected_server_marks_tools(db):
    db.set_capability_override("prod-1", "social_post", "ghl", ["mcp__ghl__social_post"])
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
            disconnected_overrides={"twitter_post": "ghl"},
        )
        block = MagicMock()
        block.name = "some_other_tool"
        block.input = {}
        block.id = "tu_789"
        result = await interceptor(block)
        assert result is None

    asyncio.run(run())


def test_manage_capability_slots_list(db):
    from core.tools import execute_tool
    result = asyncio.run(execute_tool("manage_capability_slots", {"action": "list"}))
    assert "social_post" in result
    assert "Social Posting" in result


def test_manage_capability_slots_create(db):
    from core.tools import execute_tool
    result = asyncio.run(execute_tool("manage_capability_slots", {
        "action": "create",
        "name": "crm_contacts",
        "label": "Contact Management",
    }))
    assert "created" in result.lower()
    slots = db.list_capability_slot_definitions()
    assert any(s["name"] == "crm_contacts" for s in slots)


def test_manage_capability_slots_create_duplicate_returns_error(db):
    from core.tools import execute_tool
    asyncio.run(execute_tool("manage_capability_slots", {
        "action": "create",
        "name": "crm_contacts",
        "label": "CRM",
    }))
    result = asyncio.run(execute_tool("manage_capability_slots", {
        "action": "create",
        "name": "crm_contacts",
        "label": "CRM Again",
    }))
    assert "already exists" in result.lower() or "error" in result.lower()


def test_manage_capability_slots_delete_custom(db):
    from core.tools import execute_tool
    asyncio.run(execute_tool("manage_capability_slots", {
        "action": "create",
        "name": "crm_contacts",
        "label": "Contact Management",
    }))
    result = asyncio.run(execute_tool("manage_capability_slots", {
        "action": "delete",
        "name": "crm_contacts",
    }))
    assert "deleted" in result.lower()
    slots = db.list_capability_slot_definitions()
    assert not any(s["name"] == "crm_contacts" for s in slots)


def test_manage_capability_slots_delete_system_returns_error(db):
    from core.tools import execute_tool
    result = asyncio.run(execute_tool("manage_capability_slots", {
        "action": "delete",
        "name": "social_post",
    }))
    assert "system" in result.lower() or "cannot" in result.lower()


def test_manage_capability_slots_delete_nonexistent_returns_error(db):
    from core.tools import execute_tool
    result = asyncio.run(execute_tool("manage_capability_slots", {
        "action": "delete",
        "name": "does_not_exist",
    }))
    assert "error" in result.lower() or "not found" in result.lower()


def test_delete_capability_slot_also_removes_overrides(db):
    db.create_capability_slot_definition("crm_contacts", "Contact Management", [])
    db.set_capability_override("prod-1", "crm_contacts", "some-server", ["mcp__some__tool"])
    db.delete_capability_slot_definition("crm_contacts")
    overrides = db.list_capability_overrides("prod-1")
    assert not any(o["capability_slot"] == "crm_contacts" for o in overrides)


def test_set_and_list_capability_override_multi_tool(db):
    db.set_capability_override("prod-1", "social_post", "ghl", ["create-post", "edit-post", "get-post"])
    overrides = db.list_capability_overrides("prod-1")
    assert len(overrides) == 1
    assert overrides[0]["capability_slot"] == "social_post"
    assert overrides[0]["mcp_server_name"] == "ghl"
    assert overrides[0]["mcp_tool_names"] == ["create-post", "edit-post", "get-post"]


def test_set_override_single_tool_list(db):
    db.set_capability_override("prod-1", "email_send", "myserver", ["send-email"])
    overrides = db.list_capability_overrides("prod-1")
    assert overrides[0]["mcp_tool_names"] == ["send-email"]


def test_set_override_upsert_replaces_tool_list(db):
    db.set_capability_override("prod-1", "social_post", "server-a", ["tool-a"])
    db.set_capability_override("prod-1", "social_post", "server-b", ["tool-b", "tool-c"])
    overrides = db.list_capability_overrides("prod-1")
    assert len(overrides) == 1
    assert overrides[0]["mcp_server_name"] == "server-b"
    assert overrides[0]["mcp_tool_names"] == ["tool-b", "tool-c"]


def test_capability_override_migration_preserves_existing_rows():
    """Migration converts existing mcp_tool_name rows to single-element mcp_tool_names lists."""
    import sqlite3
    import tempfile
    import os
    import json as _json

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        tmp_path = f.name
    try:
        conn = sqlite3.connect(tmp_path)
        conn.row_factory = sqlite3.Row
        # Create old schema with mcp_tool_name (singular)
        conn.execute("""
            CREATE TABLE mcp_capability_overrides (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id TEXT NOT NULL,
                capability_slot TEXT NOT NULL,
                mcp_server_name TEXT NOT NULL,
                mcp_tool_name TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE(product_id, capability_slot)
            )
        """)
        conn.execute(
            "INSERT INTO mcp_capability_overrides (product_id, capability_slot, mcp_server_name, mcp_tool_name) VALUES (?, ?, ?, ?)",
            ("prod-1", "social_post", "ghl", "mcp__ghl__social_post"),
        )
        conn.commit()
        conn.close()

        # Patch DB_PATH to use the temp file, run migration
        import backend.db as db_module
        original_path = db_module.DB_PATH
        db_module.DB_PATH = tmp_path
        try:
            db_module.migrate_capability_overrides_to_tool_names()
            rows = db_module.list_capability_overrides("prod-1")
            assert len(rows) == 1
            assert isinstance(rows[0]["mcp_tool_names"], list)
            assert rows[0]["mcp_tool_names"] == ["mcp__ghl__social_post"]
        finally:
            db_module.DB_PATH = original_path
    finally:
        os.unlink(tmp_path)
