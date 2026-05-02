# tests/test_orchestrator_api.py
import importlib
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


def test_get_orchestrator_config_defaults(client):
    tc, _ = client
    r = tc.get("/api/products/p1/orchestrator/config", headers=HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert data["enabled"] == 0
    assert data["schedule"] == "daily at 8am"
    assert data["signal_threshold"] == 5
    assert data["autonomy_settings"]["route_signal"] == "autonomous"


def test_patch_orchestrator_config(client):
    tc, _ = client
    r = tc.patch("/api/products/p1/orchestrator/config",
                 json={"enabled": True, "schedule": "every 6 hours"},
                 headers=HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert data["enabled"] == 1
    assert data["schedule"] == "every 6 hours"


def test_patch_orchestrator_config_autonomy(client):
    tc, _ = client
    r = tc.patch("/api/products/p1/orchestrator/config",
                 json={"autonomy_settings": {"update_mission": "approval_required"}},
                 headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["autonomy_settings"]["update_mission"] == "approval_required"


def test_list_orchestrator_runs_empty(client):
    tc, _ = client
    r = tc.get("/api/products/p1/orchestrator/runs", headers=HEADERS)
    assert r.status_code == 200
    assert r.json() == []


def test_list_orchestrator_runs_with_data(client):
    tc, db = client
    db.save_orchestrator_run("p1", "schedule", "complete", [], "Test brief")
    r = tc.get("/api/products/p1/orchestrator/runs", headers=HEADERS)
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["brief"] == "Test brief"


def test_get_orchestrator_run_detail(client):
    tc, db = client
    run_id = db.save_orchestrator_run("p1", "schedule", "complete",
                                       [{"action": "consume_signal", "_status": "applied"}],
                                       "Brief detail")
    r = tc.get(f"/api/products/p1/orchestrator/runs/{run_id}", headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["brief"] == "Brief detail"
    assert r.json()["decisions"][0]["action"] == "consume_signal"


def test_get_orchestrator_run_wrong_product_404(client):
    tc, db = client
    run_id = db.save_orchestrator_run("p1", "schedule", "complete", [], "")
    with db._conn() as conn:
        conn.execute("INSERT OR IGNORE INTO products (id, name, icon_label, color) VALUES ('p2','B','B','#fff')")
    r = tc.get(f"/api/products/p2/orchestrator/runs/{run_id}", headers=HEADERS)
    assert r.status_code == 404


def test_trigger_orchestrator(client):
    tc, db = client
    r = tc.post("/api/products/p1/orchestrator/trigger", headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["queued"] is True
    cfg = db.get_orchestrator_config("p1")
    assert cfg["next_run_at"] is not None
