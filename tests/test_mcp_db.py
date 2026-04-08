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
        scope="product", product_id="retainerops",
    )
    server = db.get_mcp_server(sid)
    assert server["scope"] == "product"
    assert server["product_id"] == "retainerops"


def test_list_mcp_servers_includes_globals_and_product(db):
    db.add_mcp_server(
        name="GlobalBot", type="remote", url="https://global.example.com",
        command=None, args=None, env=None, scope="global", product_id=None,
    )
    db.add_mcp_server(
        name="ProductBot", type="remote", url="https://product.example.com",
        command=None, args=None, env=None, scope="product", product_id="retainerops",
    )
    servers = db.list_mcp_servers("retainerops")
    names = [s["name"] for s in servers]
    assert "GlobalBot" in names
    assert "ProductBot" in names


def test_list_mcp_servers_excludes_other_product(db):
    db.add_mcp_server(
        name="BullsiOnly", type="remote", url="https://bullsi.example.com",
        command=None, args=None, env=None, scope="product", product_id="bullsi",
    )
    servers = db.list_mcp_servers("retainerops")
    names = [s["name"] for s in servers]
    assert "BullsiOnly" not in names


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
        scope="product", product_id="retainerops",
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
