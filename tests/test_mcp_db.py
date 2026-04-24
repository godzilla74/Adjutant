# tests/test_mcp_db.py
import importlib
import pytest


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_DB", str(tmp_path / "test.db"))
    import backend.db as db_mod
    importlib.reload(db_mod)
    db_mod.init_db()
    return db_mod


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_DB", str(tmp_path / "test.db"))
    import backend.db as db_mod
    importlib.reload(db_mod)
    db_mod.init_db()
    return db_mod


def test_add_and_get_global_mcp_server(db):
    sid = db.add_mcp_server(
        name="GoHighLevel", type="remote",
        url="https://services.leadconnectorhq.com/mcp/sse",
        command=None, args=None,
        env='{"authorization_token": "Bearer test"}',
        scope="global", product_id=None,
    )
    assert isinstance(sid, int)
    server = db.get_mcp_server(sid)
    assert server["name"] == "GoHighLevel"
    assert server["type"] == "remote"
    assert server["scope"] == "global"
    assert server["product_id"] is None
    assert server["enabled"] == 1


def test_add_product_scoped_mcp_server(db):
    sid = db.add_mcp_server(
        name="ProductBot", type="remote",
        url="https://example.com/mcp",
        command=None, args=None, env=None,
        scope="product", product_id="test-product",
    )
    server = db.get_mcp_server(sid)
    assert server["scope"] == "product"
    assert server["product_id"] == "test-product"


def test_list_mcp_servers_includes_globals_and_product(db):
    db.add_mcp_server(
        name="GlobalBot", type="remote", url="https://global.example.com",
        command=None, args=None, env=None, scope="global", product_id=None,
    )
    db.add_mcp_server(
        name="ProductBot", type="remote", url="https://product.example.com",
        command=None, args=None, env=None, scope="product", product_id="test-product",
    )
    servers = db.list_mcp_servers("test-product")
    names = [s["name"] for s in servers]
    assert "GlobalBot" in names
    assert "ProductBot" in names


def test_list_mcp_servers_excludes_other_product(db):
    db.add_mcp_server(
        name="OtherOnly", type="remote", url="https://other.example.com",
        command=None, args=None, env=None, scope="product", product_id="other-product",
    )
    servers = db.list_mcp_servers("test-product")
    names = [s["name"] for s in servers]
    assert "OtherOnly" not in names


def test_update_mcp_server_disabled(db):
    sid = db.add_mcp_server(
        name="Test", type="remote", url="https://example.com",
        command=None, args=None, env=None, scope="global", product_id=None,
    )
    db.update_mcp_server(sid, enabled=False)
    server = db.get_mcp_server(sid)
    assert server["enabled"] == 0


def test_delete_mcp_server(db):
    sid = db.add_mcp_server(
        name="ToDelete", type="remote", url="https://example.com",
        command=None, args=None, env=None, scope="global", product_id=None,
    )
    db.delete_mcp_server(sid)
    assert db.get_mcp_server(sid) is None


def test_list_all_mcp_servers(db):
    db.add_mcp_server(
        name="GlobalOne", type="remote", url="https://a.example.com",
        command=None, args=None, env=None, scope="global", product_id=None,
    )
    db.add_mcp_server(
        name="ProductOne", type="stdio", url=None,
        command="npx", args='["@test/server"]', env=None,
        scope="product", product_id="test-product",
    )
    all_servers = db.list_all_mcp_servers()
    names = [s["name"] for s in all_servers]
    assert "GlobalOne" in names
    assert "ProductOne" in names


def test_add_stdio_mcp_server(db):
    sid = db.add_mcp_server(
        name="Filesystem", type="stdio",
        url=None, command="npx",
        args='["@modelcontextprotocol/server-filesystem", "/home"]',
        env='{"PATH": "/usr/bin"}',
        scope="global", product_id=None,
    )
    server = db.get_mcp_server(sid)
    assert server["type"] == "stdio"
    assert server["command"] == "npx"
    assert '"@modelcontextprotocol/server-filesystem"' in server["args"]


# ── Extension permissions tests ───────────────────────────────────────────────

from backend.db import (
    add_extension_permission, get_product_extension_names,
    list_all_extensions_with_permissions, set_extension_enabled,
    set_extension_scope,
)


def test_add_extension_permission_global(tmp_db):
    add_extension_permission("my_tool", "global", "")
    perms = list_all_extensions_with_permissions()
    assert any(p["extension_name"] == "my_tool" and p["scope"] == "global" for p in perms)


def test_get_product_extension_names_includes_global(tmp_db):
    add_extension_permission("global_tool", "global", "")
    names = get_product_extension_names("prod_1")
    assert "global_tool" in names


def test_get_product_extension_names_includes_product_scoped(tmp_db):
    add_extension_permission("product_tool", "product", "prod_1")
    names = get_product_extension_names("prod_1")
    assert "product_tool" in names


def test_get_product_extension_names_excludes_other_product(tmp_db):
    add_extension_permission("other_tool", "product", "prod_2")
    names = get_product_extension_names("prod_1")
    assert "other_tool" not in names


def test_set_extension_enabled_false(tmp_db):
    add_extension_permission("my_tool", "global", "")
    set_extension_enabled("my_tool", "", False)
    names = get_product_extension_names("any_product")
    assert "my_tool" not in names


def test_set_extension_scope_global_to_product(tmp_db):
    add_extension_permission("my_tool", "global", "")
    set_extension_scope("my_tool", "product", "prod_1")
    names_prod1 = get_product_extension_names("prod_1")
    names_prod2 = get_product_extension_names("prod_2")
    assert "my_tool" in names_prod1
    assert "my_tool" not in names_prod2
