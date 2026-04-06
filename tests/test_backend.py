# ~/Code/MissionControl/tests/test_backend.py
import os

os.environ.setdefault("HANNAH_PASSWORD", "testpass")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")

from fastapi.testclient import TestClient
from backend.main import app


def test_ws_auth_success():
    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "auth", "password": "testpass"})
        data = ws.receive_json()
        assert data["type"] == "auth_ok"


def test_ws_auth_failure():
    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "auth", "password": "wrong"})
        data = ws.receive_json()
        assert data["type"] == "auth_fail"


from backend.db import init_db, save_message, load_messages, save_event, load_events


def test_message_round_trip(tmp_path, monkeypatch):
    monkeypatch.setenv("HANNAH_DB", str(tmp_path / "test.db"))
    import importlib, backend.db as db_mod
    importlib.reload(db_mod)  # pick up new DB_PATH
    db_mod.init_db()
    db_mod.save_message("user", "hello")
    db_mod.save_message("assistant", [{"type": "text", "text": "hi"}])
    msgs = db_mod.load_messages()
    assert msgs[0]["role"] == "user"
    assert msgs[0]["content"] == "hello"
    assert msgs[1]["role"] == "assistant"


def test_event_round_trip(tmp_path, monkeypatch):
    monkeypatch.setenv("HANNAH_DB", str(tmp_path / "test.db"))
    import importlib, backend.db as db_mod
    importlib.reload(db_mod)
    db_mod.init_db()
    ev = {"type": "user_message", "content": "hello", "ts": "2026-04-06T12:00:00"}
    db_mod.save_event(ev)
    events = db_mod.load_events()
    assert events[0] == ev
