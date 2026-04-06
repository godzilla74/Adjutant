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


from unittest.mock import AsyncMock, MagicMock, patch


def test_ws_echoes_user_message():
    """After auth, sending a message emits user_message then hannah_done."""
    client = TestClient(app)

    # Build a fake delta event so accumulated_text is non-empty → hannah_done fires
    delta = MagicMock()
    delta.type = "content_block_delta"
    delta.delta = MagicMock()
    delta.delta.type = "text_delta"
    delta.delta.text = "Hi there"

    async def _aiter_with_delta():
        yield delta

    mock_stream = MagicMock()
    mock_stream.__aenter__ = AsyncMock(return_value=mock_stream)
    mock_stream.__aexit__ = AsyncMock(return_value=False)
    mock_stream.__aiter__ = lambda self: _aiter_with_delta().__aiter__()

    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = "Hi there"
    text_block.model_dump = MagicMock(return_value={"type": "text", "text": "Hi there"})

    final = MagicMock()
    final.stop_reason = "end_turn"
    final.content = [text_block]
    mock_stream.get_final_message = AsyncMock(return_value=final)

    with patch("backend.main.client.messages.stream", return_value=mock_stream):
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "auth", "password": "testpass"})
            ws.receive_json()  # auth_ok
            ws.receive_json()  # history event

            ws.send_json({"type": "message", "content": "Hello"})

            # Expect: user_message, hannah_token, hannah_done
            events = []
            for _ in range(3):
                try:
                    events.append(ws.receive_json())
                except Exception:
                    break

    types = [e["type"] for e in events]
    assert "user_message" in types
    assert "hannah_done" in types
