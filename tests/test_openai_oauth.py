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
    import hashlib, base64, urllib.parse
    url = oai.build_auth_url()
    parsed = urllib.parse.urlparse(url)
    params = urllib.parse.parse_qs(parsed.query)
    state = params["state"][0]
    verifier = oai.pop_verifier(state)
    assert verifier is not None
    digest = hashlib.sha256(verifier.encode()).digest()
    expected_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    assert expected_challenge in url


def test_pop_verifier_clears_state():
    import backend.openai_oauth as oai
    importlib.reload(oai)
    url = oai.build_auth_url()
    import urllib.parse
    params = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    state = params["state"][0]
    v1 = oai.pop_verifier(state)
    v2 = oai.pop_verifier(state)
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
    importlib.reload(oai)
    resp = client.get("/api/openai-oauth/callback?code=abc123&state=nonexistent")
    assert resp.status_code == 200
    assert "oauth_error" in resp.text


def test_callback_missing_state_returns_error(client):
    resp = client.get("/api/openai-oauth/callback?code=abc123")
    assert resp.status_code == 200
    assert "oauth_error" in resp.text


def test_image_generation_settings_default(client):
    resp = client.get("/api/settings/image-generation", headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()
    assert data["pexels_configured"] is False
    assert data["openai_connected"] is False


def test_image_generation_settings_save_pexels_key(client):
    resp = client.put(
        "/api/settings/image-generation",
        json={"pexels_api_key": "mykey123"},
        headers=AUTH,
    )
    assert resp.status_code == 200
    # Verify it's now configured
    resp2 = client.get("/api/settings/image-generation", headers=AUTH)
    assert resp2.json()["pexels_configured"] is True


def test_run_oauth_flow_blocking_returns_false_on_timeout(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_DB", str(tmp_path / "test.db"))
    import importlib
    import backend.db as db_mod
    importlib.reload(db_mod)
    db_mod.init_db()

    import backend.openai_oauth as oai_mod
    importlib.reload(oai_mod)

    monkeypatch.setattr(oai_mod, "build_auth_url", lambda: "https://fake-auth-url")
    monkeypatch.setattr(oai_mod, "start_callback_server", lambda: None)

    import time as time_mod
    call_n = [0]
    def fake_time():
        call_n[0] += 1
        # First call sets deadline (deadline = 0 + 1 = 1), subsequent calls return 9999
        return 0.0 if call_n[0] == 1 else 9999.0
    monkeypatch.setattr(time_mod, "sleep", lambda s: None)
    monkeypatch.setattr(time_mod, "time", fake_time)

    result = oai_mod.run_oauth_flow_blocking(timeout_seconds=1)
    assert result is False


def test_run_oauth_flow_blocking_returns_true_when_token_stored(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_DB", str(tmp_path / "test.db"))
    import importlib
    import backend.db as db_mod
    importlib.reload(db_mod)
    db_mod.init_db()

    import backend.openai_oauth as oai_mod
    importlib.reload(oai_mod)

    monkeypatch.setattr(oai_mod, "build_auth_url", lambda: "https://fake-auth-url")
    monkeypatch.setattr(oai_mod, "start_callback_server", lambda: None)

    import time as time_mod
    sleep_calls = [0]
    def fake_sleep(s):
        sleep_calls[0] += 1
        if sleep_calls[0] == 1:
            db_mod.set_agent_config("openai_access_token", "sk-openai-test")
    monkeypatch.setattr(time_mod, "sleep", fake_sleep)

    times = iter([0.0, 1.0, 2.0, 3.0, 4.0])
    monkeypatch.setattr(time_mod, "time", lambda: next(times))

    result = oai_mod.run_oauth_flow_blocking(timeout_seconds=300)
    assert result is True
