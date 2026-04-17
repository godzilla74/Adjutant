# tests/test_oauth_endpoints.py
import importlib
import os
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


def test_get_google_oauth_settings_defaults(client):
    resp = client.get("/api/settings/google-oauth", headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()
    assert data["google_oauth_client_id"] == ""
    assert "google_oauth_client_secret" not in data or data["google_oauth_client_secret"] == ""


def test_update_google_oauth_settings(client):
    resp = client.put(
        "/api/settings/google-oauth",
        json={"google_oauth_client_id": "my-client-id", "google_oauth_client_secret": "my-secret"},
        headers=AUTH,
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_get_google_oauth_settings_after_update(client):
    client.put(
        "/api/settings/google-oauth",
        json={"google_oauth_client_id": "my-client-id", "google_oauth_client_secret": "my-secret"},
        headers=AUTH,
    )
    resp = client.get("/api/settings/google-oauth", headers=AUTH)
    assert resp.json()["google_oauth_client_id"] == "my-client-id"
    # Secret must never be returned
    assert resp.json().get("google_oauth_client_secret", "") == ""


def test_google_oauth_settings_requires_auth(client):
    resp = client.get("/api/settings/google-oauth")
    assert resp.status_code == 401
