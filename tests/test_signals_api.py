import importlib
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_DB", str(tmp_path / "test.db"))
    monkeypatch.setenv("AGENT_PASSWORD", "test-secret")
    import backend.db as db_mod
    importlib.reload(db_mod)
    db_mod.init_db()
    with db_mod._conn() as conn:
        conn.execute("INSERT OR IGNORE INTO products (id, name, icon_label, color) VALUES ('p1', 'P1', 'P', '#000')")
    import backend.api as api_mod
    importlib.reload(api_mod)
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(api_mod.router)
    return TestClient(app), db_mod


HEADERS = {"X-Agent-Password": "test-secret"}


def test_create_and_list_tags_api(client):
    tc, db = client
    r = tc.post("/api/tags", json={"name": "social:linkedin", "description": "LinkedIn"}, headers=HEADERS)
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "social:linkedin"

    r2 = tc.get("/api/tags", headers=HEADERS)
    assert r2.status_code == 200
    assert len(r2.json()) == 1


def test_update_tag_api(client):
    tc, db = client
    tag_id = db.create_tag("social:linkedin", "Old")
    r = tc.patch(f"/api/tags/{tag_id}", json={"name": "social:linkedin-post"}, headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["name"] == "social:linkedin-post"


def test_delete_tag_api(client):
    tc, db = client
    tag_id = db.create_tag("social:linkedin", "Test")
    r = tc.delete(f"/api/tags/{tag_id}", headers=HEADERS)
    assert r.status_code == 204
    assert db.list_tags() == []


def test_tag_requires_auth(client):
    tc, _ = client
    r = tc.get("/api/tags")
    assert r.status_code == 401


def test_create_and_list_signals_api(client):
    tc, db = client
    tag_id = db.create_tag("social:linkedin", "LinkedIn")
    r = tc.post("/api/products/p1/signals", json={
        "tag_id": tag_id,
        "content_type": "run_report",
        "content_id": 1,
        "note": "Great LinkedIn angle",
    }, headers=HEADERS)
    assert r.status_code == 201
    s = r.json()
    assert s["tag_name"] == "social:linkedin"
    assert s["note"] == "Great LinkedIn angle"
    assert s["consumed_at"] is None

    r2 = tc.get("/api/products/p1/signals", headers=HEADERS)
    assert r2.status_code == 200
    assert len(r2.json()) == 1


def test_list_signals_with_prefix(client):
    tc, db = client
    tag1 = db.create_tag("social:linkedin", "LinkedIn")
    tag2 = db.create_tag("email:customers", "Email")
    db.create_signal(tag_id=tag1, content_type="run_report", content_id=1,
                     product_id="p1", tagged_by="agent", note="Social")
    db.create_signal(tag_id=tag2, content_type="run_report", content_id=2,
                     product_id="p1", tagged_by="agent", note="Email")
    r = tc.get("/api/products/p1/signals?tag_prefix=social:", headers=HEADERS)
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_consume_signal_api(client):
    tc, db = client
    tag_id = db.create_tag("social:linkedin", "LinkedIn")
    sig_id = db.create_signal(tag_id=tag_id, content_type="run_report", content_id=1,
                               product_id="p1", tagged_by="agent", note="Test")
    r = tc.post(f"/api/products/p1/signals/{sig_id}/consume", headers=HEADERS)
    assert r.status_code == 200
    signals = db.get_signals(product_id="p1", tag_prefix="social:")
    assert signals == []


def test_signals_scoped_to_product(client):
    tc, db = client
    tag_id = db.create_tag("social:linkedin", "LinkedIn")
    db.create_signal(tag_id=tag_id, content_type="run_report", content_id=1,
                     product_id="p1", tagged_by="agent", note="For p1")
    r = tc.get("/api/products/p1/signals", headers=HEADERS)
    assert len(r.json()) == 1
