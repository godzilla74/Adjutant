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
