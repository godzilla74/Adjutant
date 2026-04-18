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


def test_start_oauth_flow_no_client_id(client):
    """Returns 400 when no client ID is configured."""
    resp = client.get("/api/products/prod-1/oauth/start/gmail", headers=AUTH)
    assert resp.status_code == 400
    assert "Client ID" in resp.json()["detail"]


def test_start_oauth_flow_invalid_service(client):
    client.put(
        "/api/settings/google-oauth",
        json={"google_oauth_client_id": "cid", "google_oauth_client_secret": "csec"},
        headers=AUTH,
    )
    resp = client.get("/api/products/prod-1/oauth/start/bad_service", headers=AUTH)
    assert resp.status_code == 422


def test_start_oauth_flow_returns_auth_url(client):
    import backend.db as db_mod
    with db_mod._conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO products (id, name, icon_label, color) "
            "VALUES ('prod-1', 'Prod 1', 'P1', '#000')"
        )
    client.put(
        "/api/settings/google-oauth",
        json={"google_oauth_client_id": "my-cid", "google_oauth_client_secret": "csec"},
        headers=AUTH,
    )
    resp = client.get("/api/products/prod-1/oauth/start/gmail", headers=AUTH)
    assert resp.status_code == 200
    assert "auth_url" in resp.json()
    assert "accounts.google.com" in resp.json()["auth_url"]


def test_list_oauth_connections_empty(client):
    import backend.db as db_mod
    with db_mod._conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO products (id, name, icon_label, color) "
            "VALUES ('prod-1', 'Prod 1', 'P1', '#000')"
        )
    resp = client.get("/api/products/prod-1/oauth/connections", headers=AUTH)
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_oauth_connections_returns_connections(client):
    import backend.db as db_mod
    with db_mod._conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO products (id, name, icon_label, color) "
            "VALUES ('prod-1', 'Prod 1', 'P1', '#000')"
        )
    db_mod.save_oauth_connection("prod-1", "gmail", "a@x.com", "tok", "ref", "2099-01-01T00:00:00+00:00", "s")
    resp = client.get("/api/products/prod-1/oauth/connections", headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["service"] == "gmail"
    assert data[0]["email"] == "a@x.com"


def test_delete_oauth_connection(client):
    import backend.db as db_mod
    from unittest.mock import patch, AsyncMock
    with db_mod._conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO products (id, name, icon_label, color) "
            "VALUES ('prod-1', 'Prod 1', 'P1', '#000')"
        )
    db_mod.save_oauth_connection("prod-1", "gmail", "a@x.com", "tok", "ref", "2099-01-01T00:00:00+00:00", "s")
    with patch("backend.google_oauth.revoke_token", new=AsyncMock()):
        resp = client.delete("/api/products/prod-1/oauth/gmail", headers=AUTH)
    assert resp.status_code == 204
    assert db_mod.get_oauth_connection("prod-1", "gmail") is None


def test_get_social_settings_defaults(client):
    resp = client.get("/api/settings/social-accounts", headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()
    assert data["twitter_client_id"] == ""
    assert data["linkedin_client_id"] == ""
    assert data["meta_app_id"] == ""
    # Secrets must never be returned
    assert data.get("twitter_client_secret", "") == ""
    assert data.get("linkedin_client_secret", "") == ""
    assert data.get("meta_app_secret", "") == ""


def test_update_social_settings(client):
    resp = client.put(
        "/api/settings/social-accounts",
        json={"twitter_client_id": "tw-id", "twitter_client_secret": "tw-sec"},
        headers=AUTH,
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_social_settings_persists(client):
    client.put(
        "/api/settings/social-accounts",
        json={"linkedin_client_id": "li-id", "linkedin_client_secret": "li-sec"},
        headers=AUTH,
    )
    resp = client.get("/api/settings/social-accounts", headers=AUTH)
    assert resp.json()["linkedin_client_id"] == "li-id"
    assert resp.json().get("linkedin_client_secret", "") == ""


def test_start_social_oauth_no_credentials(client):
    resp = client.get("/api/products/prod-1/oauth/start/twitter", headers=AUTH)
    assert resp.status_code == 400
    assert "Twitter" in resp.json()["detail"]


def test_start_social_oauth_returns_url(client):
    import backend.db as db_mod
    with db_mod._conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO products (id, name, icon_label, color) "
            "VALUES ('prod-1', 'Prod 1', 'P1', '#000')"
        )
    client.put(
        "/api/settings/social-accounts",
        json={"twitter_client_id": "tw-id", "twitter_client_secret": "tw-sec"},
        headers=AUTH,
    )
    resp = client.get("/api/products/prod-1/oauth/start/twitter", headers=AUTH)
    assert resp.status_code == 200
    assert "twitter.com" in resp.json()["auth_url"]
