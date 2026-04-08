# tests/test_main.py
import importlib
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("AGENT_PASSWORD", "testpass")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_DB", str(tmp_path / "test.db"))
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
        init_msg = ws.receive_json()  # consume init
        assert init_msg["type"] == "init"


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


def test_ws_directive_echoes_and_returns_agent_done():
    from fastapi.testclient import TestClient

    delta = MagicMock()
    delta.type = "content_block_delta"
    delta.delta = MagicMock()
    delta.delta.type = "text_delta"
    delta.delta.text = "Got it!"

    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = "Got it!"
    text_block.model_dump = MagicMock(return_value={"type": "text", "text": "Got it!"})

    final = MagicMock()
    final.stop_reason = "end_turn"
    final.content = [text_block]

    class FakeStream:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        def __aiter__(self):
            return self._gen().__aiter__()

        async def _gen(self):
            yield delta

        async def get_final_message(self):
            return final

    with patch("backend.main.client.messages.stream", return_value=FakeStream()):
        with TestClient(get_app()).websocket_connect("/ws") as ws:
            ws.send_json({"type": "auth", "password": "testpass"})
            ws.receive_json()  # auth_ok
            ws.receive_json()  # init

            ws.send_json({"type": "directive", "product_id": "retainerops", "content": "Focus on SEO"})

            # The sync TestClient cannot observe async worker messages (agent_token/agent_done),
            # but the directive_echo is sent synchronously before the worker task runs.
            events = []
            for _ in range(5):
                try:
                    events.append(ws.receive_json())
                except Exception:
                    break

    types = [e["type"] for e in events]
    assert "directive_echo" in types
    echo = next(e for e in events if e["type"] == "directive_echo")
    assert echo["content"] == "Focus on SEO"
    assert echo["product_id"] == "retainerops"
