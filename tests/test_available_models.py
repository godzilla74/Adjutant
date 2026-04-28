import importlib
import json
import datetime
import pytest
from fastapi.testclient import TestClient


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


def test_is_chat_model_filter():
    import backend.api as api_mod
    assert api_mod._is_chat_model("gpt-4o") is True
    assert api_mod._is_chat_model("gpt-4o-mini") is True
    assert api_mod._is_chat_model("o3-mini") is True
    assert api_mod._is_chat_model("dall-e-3") is False
    assert api_mod._is_chat_model("whisper-1") is False
    assert api_mod._is_chat_model("tts-1") is False
    assert api_mod._is_chat_model("text-embedding-3-small") is False
    assert api_mod._is_chat_model("gpt-4o-realtime-preview") is False
    assert api_mod._is_chat_model("gpt-4o-audio-preview") is False


def test_cache_miss_triggers_fetch(client, monkeypatch):
    import backend.api as api_mod
    called = [False]
    def fake_fetch():
        called[0] = True
        return {"anthropic": ["claude-test"], "openai": []}
    monkeypatch.setattr(api_mod, "_fetch_models_sync", fake_fetch)

    resp = client.get("/api/available-models", headers=AUTH)
    assert resp.status_code == 200
    assert called[0] is True
    assert resp.json()["anthropic"] == ["claude-test"]


def test_cache_hit_skips_fetch(client, monkeypatch):
    import backend.api as api_mod, backend.db as db_mod
    fresh = {"anthropic": ["cached-model"], "openai": []}
    db_mod.set_agent_config("available_models_cache", json.dumps(fresh))
    db_mod.set_agent_config(
        "available_models_cache_updated_at",
        datetime.datetime.utcnow().isoformat(),
    )
    called = [False]
    def fake_fetch():
        called[0] = True
        return {"anthropic": ["other"], "openai": []}
    monkeypatch.setattr(api_mod, "_fetch_models_sync", fake_fetch)

    resp = client.get("/api/available-models", headers=AUTH)
    assert resp.status_code == 200
    assert called[0] is False
    assert resp.json()["anthropic"] == ["cached-model"]


def test_stale_cache_returned_on_fetch_failure(client, monkeypatch):
    import backend.api as api_mod, backend.db as db_mod
    stale = {"anthropic": ["stale-model"], "openai": []}
    old_ts = (datetime.datetime.utcnow() - datetime.timedelta(hours=2)).isoformat()
    db_mod.set_agent_config("available_models_cache", json.dumps(stale))
    db_mod.set_agent_config("available_models_cache_updated_at", old_ts)

    def raise_error():
        raise RuntimeError("network error")
    monkeypatch.setattr(api_mod, "_fetch_models_sync", raise_error)

    resp = client.get("/api/available-models", headers=AUTH)
    assert resp.status_code == 200
    assert resp.json()["anthropic"] == ["stale-model"]


def test_refresh_busts_cache_and_fetches(client, monkeypatch):
    import backend.api as api_mod, backend.db as db_mod
    fresh = {"anthropic": ["old-cached"], "openai": []}
    db_mod.set_agent_config("available_models_cache", json.dumps(fresh))
    db_mod.set_agent_config(
        "available_models_cache_updated_at",
        datetime.datetime.utcnow().isoformat(),
    )
    called = [False]
    def fake_fetch():
        called[0] = True
        return {"anthropic": ["freshly-fetched"], "openai": []}
    monkeypatch.setattr(api_mod, "_fetch_models_sync", fake_fetch)

    resp = client.post("/api/available-models/refresh", headers=AUTH)
    assert resp.status_code == 200
    assert called[0] is True
    assert resp.json()["anthropic"] == ["freshly-fetched"]
