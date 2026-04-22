import importlib
import pytest
from fastapi.testclient import TestClient


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


def test_pkce_challenge_is_sha256_of_verifier():
    import backend.openai_oauth as oai
    importlib.reload(oai)
    import hashlib, base64
    url = oai.build_auth_url()
    verifier = oai.pop_verifier()
    assert verifier is not None
    digest = hashlib.sha256(verifier.encode()).digest()
    expected_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    assert expected_challenge in url


def test_pop_verifier_clears_state():
    import backend.openai_oauth as oai
    importlib.reload(oai)
    oai.build_auth_url()
    v1 = oai.pop_verifier()
    v2 = oai.pop_verifier()
    assert v1 is not None
    assert v2 is None


def test_start_returns_auth_url(client):
    resp = client.get("/api/openai-oauth/start", headers=AUTH)
    assert resp.status_code == 200
    assert "auth_url" in resp.json()
    assert "auth.openai.com" in resp.json()["auth_url"]


def test_status_not_connected_by_default(client):
    resp = client.get("/api/openai-oauth/status", headers=AUTH)
    assert resp.status_code == 200
    assert resp.json() == {"connected": False}


def test_disconnect_clears_token(client, monkeypatch):
    import backend.db as db_mod
    db_mod.set_agent_config("openai_access_token", "sk-test")
    resp = client.delete("/api/openai-oauth/disconnect", headers=AUTH)
    assert resp.status_code == 200
    cfg = db_mod.get_agent_config()
    assert cfg.get("openai_access_token") == ""


def test_status_connected_after_token_set(client, monkeypatch):
    import backend.db as db_mod
    db_mod.set_agent_config("openai_access_token", "sk-real")
    resp = client.get("/api/openai-oauth/status", headers=AUTH)
    assert resp.json() == {"connected": True}


def test_callback_missing_code_returns_html_error(client):
    resp = client.get("/api/openai-oauth/callback")
    assert resp.status_code == 200
    assert "oauth_error" in resp.text


def test_callback_with_error_param_returns_html_error(client):
    resp = client.get("/api/openai-oauth/callback?error=access_denied")
    assert resp.status_code == 200
    assert "oauth_error" in resp.text
    assert "access_denied" in resp.text


def test_callback_without_pending_verifier_returns_error(client):
    import backend.openai_oauth as oai
    importlib.reload(oai)  # clear any pending verifier
    resp = client.get("/api/openai-oauth/callback?code=abc123")
    assert resp.status_code == 200
    assert "expired" in resp.text.lower() or "oauth_error" in resp.text
