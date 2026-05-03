# tests/test_hca_api.py
import importlib
import json
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_DB", str(tmp_path / "test.db"))
    monkeypatch.setenv("AGENT_PASSWORD", "secret")
    import backend.db as db_mod
    importlib.reload(db_mod)
    db_mod.init_db()
    with db_mod._conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO products (id, name, icon_label, color) "
            "VALUES ('p1', 'Acme', 'A', '#000')"
        )
    import backend.api as api_mod
    importlib.reload(api_mod)
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(api_mod.router)
    return TestClient(app), db_mod


HEADERS = {"X-Agent-Password": "secret"}


def test_get_hca_config_defaults(client):
    tc, _ = client
    r = tc.get("/api/hca/config", headers=HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert data["enabled"] == 0
    assert data["schedule"] == "weekly on mondays at 8am"
    assert data["pa_run_threshold"] == 10


def test_patch_hca_config(client):
    tc, _ = client
    r = tc.patch("/api/hca/config",
                 json={"enabled": True, "schedule": "every 3 days", "pa_run_threshold": 5},
                 headers=HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert data["enabled"] == 1
    assert data["schedule"] == "every 3 days"
    assert data["pa_run_threshold"] == 5


def test_patch_hca_config_channel_ids(client):
    tc, _ = client
    r = tc.patch("/api/hca/config",
                 json={"hca_slack_channel_id": "C123", "hca_discord_channel_id": "456"},
                 headers=HEADERS)
    assert r.status_code == 200


def test_get_hca_runs_empty(client):
    tc, _ = client
    r = tc.get("/api/hca/runs", headers=HEADERS)
    assert r.status_code == 200
    assert r.json() == []


def test_get_hca_runs_with_data(client):
    tc, db = client
    db.save_hca_run("schedule", "complete", [], "A brief")
    r = tc.get("/api/hca/runs", headers=HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["brief"] == "A brief"


def test_get_hca_run_by_id(client):
    tc, db = client
    run_id = db.save_hca_run("schedule", "complete", [], "Detail brief")
    r = tc.get(f"/api/hca/runs/{run_id}", headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["brief"] == "Detail brief"


def test_get_hca_run_not_found(client):
    tc, _ = client
    r = tc.get("/api/hca/runs/9999", headers=HEADERS)
    assert r.status_code == 404


def test_post_hca_trigger(client):
    tc, _ = client
    r = tc.post("/api/hca/trigger", headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["queued"] is True


def test_get_hca_directives(client):
    tc, db = client
    run_id = db.save_hca_run("schedule", "complete", [], "")
    db.create_hca_directive("p1", "Focus on enterprise", run_id)
    db.create_hca_directive(None, "Global directive", run_id)
    r = tc.get("/api/hca/directives", headers=HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2


def test_get_hca_directives_product_filter(client):
    tc, db = client
    run_id = db.save_hca_run("schedule", "complete", [], "")
    db.create_hca_directive("p1", "P1 directive", run_id)
    db.create_hca_directive(None, "Global directive", run_id)
    r = tc.get("/api/hca/directives?product_id=p1", headers=HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2  # p1 + global
    assert all(
        d["product_id"] == "p1" or d["product_id"] is None
        for d in data
    )


def test_delete_hca_directive(client):
    tc, db = client
    run_id = db.save_hca_run("schedule", "complete", [], "")
    d_id = db.create_hca_directive("p1", "Directive to retire", run_id)
    r = tc.delete(f"/api/hca/directives/{d_id}", headers=HEADERS)
    assert r.status_code == 204
    with db._conn() as conn:
        row = conn.execute("SELECT status FROM hca_directives WHERE id = ?", (d_id,)).fetchone()
    assert row["status"] == "retired"
