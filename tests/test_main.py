# tests/test_main.py
import importlib
import json
import os

import pytest

os.environ.setdefault("HANNAH_PASSWORD", "testpass")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setenv("HANNAH_DB", str(tmp_path / "test.db"))
    import backend.db as db_mod
    importlib.reload(db_mod)
    db_mod.init_db()
    import backend.main as main_mod
    importlib.reload(main_mod)
    return main_mod


def get_app():
    import backend.main as main_mod
    return main_mod.app


def test_ws_auth_ok():
    from fastapi.testclient import TestClient
    with TestClient(get_app()).websocket_connect("/ws") as ws:
        ws.send_json({"type": "auth", "password": "testpass"})
        msg = ws.receive_json()
        assert msg["type"] == "auth_ok"


def test_ws_auth_fail():
    from fastapi.testclient import TestClient
    with TestClient(get_app()).websocket_connect("/ws") as ws:
        ws.send_json({"type": "auth", "password": "wrong"})
        msg = ws.receive_json()
        assert msg["type"] == "auth_fail"


def test_ws_init_sends_products():
    from fastapi.testclient import TestClient
    with TestClient(get_app()).websocket_connect("/ws") as ws:
        ws.send_json({"type": "auth", "password": "testpass"})
        ws.receive_json()  # auth_ok
        init_msg = ws.receive_json()
        assert init_msg["type"] == "init"
        product_ids = [p["id"] for p in init_msg["products"]]
        assert "retainerops" in product_ids
        assert "ignitara" in product_ids


def test_ws_switch_product_sends_product_data():
    from fastapi.testclient import TestClient
    with TestClient(get_app()).websocket_connect("/ws") as ws:
        ws.send_json({"type": "auth", "password": "testpass"})
        ws.receive_json()  # auth_ok
        ws.receive_json()  # init
        ws.send_json({"type": "switch_product", "product_id": "ignitara"})
        msg = ws.receive_json()
        assert msg["type"] == "product_data"
        assert msg["product_id"] == "ignitara"
        assert "workstreams" in msg
        assert "objectives" in msg
        assert "events" in msg
        assert "review_items" in msg


def test_ws_resolve_review_pending_item():
    from fastapi.testclient import TestClient
    import backend.db as db_mod
    item_id = db_mod.save_review_item(
        "retainerops", "Test post", "Description", "Public-facing"
    )
    with TestClient(get_app()).websocket_connect("/ws") as ws:
        ws.send_json({"type": "auth", "password": "testpass"})
        ws.receive_json()  # auth_ok
        ws.receive_json()  # init
        ws.send_json({"type": "resolve_review", "review_item_id": item_id, "action": "approved"})
        msg = ws.receive_json()
        assert msg["type"] == "review_resolved"
        assert msg["review_item_id"] == item_id
        assert msg["action"] == "approved"
    pending = db_mod.load_review_items("retainerops", status="pending")
    assert all(i["id"] != item_id for i in pending)
