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
