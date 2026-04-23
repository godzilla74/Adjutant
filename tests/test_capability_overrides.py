# tests/test_capability_overrides.py
import importlib
import pytest


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_DB", str(tmp_path / "test.db"))
    import backend.db as db_mod
    importlib.reload(db_mod)
    db_mod.init_db()
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
