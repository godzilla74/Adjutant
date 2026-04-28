import importlib
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_DB", str(tmp_path / "test.db"))
    import backend.db as db_mod
    importlib.reload(db_mod)
    db_mod.init_db()
    return db_mod


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_DB", str(tmp_path / "test.db"))
    monkeypatch.setenv("AGENT_PASSWORD", "testpw")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    import backend.db as db_mod
    importlib.reload(db_mod)
    db_mod.init_db()
    import backend.api as api_mod
    importlib.reload(api_mod)
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(api_mod.router)
    return TestClient(app)


AUTH = {"X-Agent-Password": "testpw"}


def test_new_config_keys_exist_with_empty_defaults(db):
    cfg = db.get_agent_config()
    assert cfg["anthropic_api_key"] == ""
    assert cfg["available_models_cache"] == ""
    assert cfg["available_models_cache_updated_at"] == ""


def test_get_anthropic_key_unconfigured(client):
    resp = client.get("/api/settings/anthropic-key", headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()
    assert data["configured"] is False
    assert data["masked"] == ""


def test_put_anthropic_key_stores_and_returns_masked(client):
    resp = client.put(
        "/api/settings/anthropic-key",
        json={"key": "sk-ant-api03-ABCDEFGHIJKLMNOP"},
        headers=AUTH,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["configured"] is True
    assert data["masked"] == "sk-ant-...MNOP"


def test_get_anthropic_key_after_put_returns_masked(client):
    client.put("/api/settings/anthropic-key", json={"key": "sk-ant-api03-TESTKEYVALUE"}, headers=AUTH)
    resp = client.get("/api/settings/anthropic-key", headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()
    assert data["configured"] is True
    assert data["masked"] == "sk-ant-...ALUE"


def test_get_anthropic_key_env_var_fallback(client, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-env-WXYZ")
    resp = client.get("/api/settings/anthropic-key", headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()
    assert data["configured"] is True
    assert data["masked"] == "sk-ant-...WXYZ"
