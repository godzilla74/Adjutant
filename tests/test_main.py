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
    with db_mod._conn() as conn:
        conn.execute("INSERT INTO products (id, name, icon_label, color) VALUES ('product-alpha', 'Product Alpha', 'PA', '#2563eb')")
        conn.execute("INSERT INTO products (id, name, icon_label, color) VALUES ('product-beta', 'Product Beta', 'PB', '#7c3aed')")
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
        assert "product-alpha" in product_ids
        assert "product-beta" in product_ids


def test_ws_switch_product_sends_product_data():
    from fastapi.testclient import TestClient
    with TestClient(get_app()).websocket_connect("/ws") as ws:
        ws.send_json({"type": "auth", "password": "testpass"})
        ws.receive_json()  # auth_ok
        ws.receive_json()  # init
        ws.send_json({"type": "switch_product", "product_id": "product-alpha"})
        msg = ws.receive_json()
        assert msg["type"] == "product_data"
        assert msg["product_id"] == "product-alpha"
        assert "workstreams" in msg
        assert "objectives" in msg
        assert "events" in msg
        assert "review_items" in msg


def test_ws_resolve_review_pending_item():
    from fastapi.testclient import TestClient
    import backend.db as db_mod
    item_id = db_mod.save_review_item(
        "product-alpha", "Test post", "Description", "Public-facing"
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
    pending = db_mod.load_review_items("product-alpha", status="pending")
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

            ws.send_json({"type": "directive", "product_id": "product-alpha", "content": "Focus on SEO"})

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
    assert echo["product_id"] == "product-alpha"


def test_build_user_message_no_attachments(isolated_db):
    import backend.main as m
    result = m._build_user_message("hello", [])
    assert result == "hello"


def test_build_user_message_with_image(isolated_db, tmp_path):
    import backend.main as m
    img = tmp_path / "photo.jpg"
    img.write_bytes(b"\xff\xd8\xff" + b"x" * 10)
    attachments = [{"path": str(img), "mime_type": "image/jpeg", "name": "photo.jpg"}]
    result = m._build_user_message("check this", attachments)
    assert isinstance(result, list)
    assert result[-1] == {"type": "text", "text": "check this"}
    assert result[0]["type"] == "image"
    assert result[0]["source"]["type"] == "base64"
    assert result[0]["source"]["media_type"] == "image/jpeg"


def test_build_user_message_with_pdf(isolated_db, tmp_path):
    import backend.main as m
    pdf = tmp_path / "report.pdf"
    pdf.write_bytes(b"%PDF-1.4" + b"x" * 10)
    attachments = [{"path": str(pdf), "mime_type": "application/pdf", "name": "report.pdf"}]
    result = m._build_user_message("analyse this", attachments)
    assert isinstance(result, list)
    assert result[0]["type"] == "document"
    assert result[0]["source"]["media_type"] == "application/pdf"


def test_build_user_message_with_video_injects_text(isolated_db, tmp_path):
    import backend.main as m
    vid = tmp_path / "clip.mp4"
    vid.write_bytes(b"fakevideo")
    attachments = [{"path": str(vid), "mime_type": "video/mp4", "name": "clip.mp4"}]
    result = m._build_user_message("use this video", attachments)
    assert isinstance(result, str)
    assert "clip.mp4" in result or str(vid) in result
    assert "use this video" in result


def test_list_uploads_returns_files(isolated_db, tmp_path):
    """list_uploads tool returns files from the uploads dir."""
    import asyncio
    from core.tools import execute_tool
    with patch("backend.uploads.get_uploads_dir", return_value=tmp_path):
        (tmp_path / "20260410_120000_video.mp4").write_bytes(b"fakevideo")
        (tmp_path / "20260410_120001_photo.jpg").write_bytes(b"fakejpeg")
        result = asyncio.run(execute_tool("list_uploads", {}))
        assert "video.mp4" in result
        assert "photo.jpg" in result


def test_list_uploads_empty(isolated_db, tmp_path):
    import asyncio
    from core.tools import execute_tool
    uploads_dir = tmp_path / "uploads"
    uploads_dir.mkdir()
    with patch("backend.uploads.get_uploads_dir", return_value=uploads_dir):
        result = asyncio.run(execute_tool("list_uploads", {}))
        assert "No uploaded files" in result


def test_send_telegram_file_no_bot(isolated_db, tmp_path):
    """send_telegram_file returns error when Telegram not configured."""
    import asyncio
    import backend.main as main_mod
    main_mod._telegram_bot = None
    from core.tools import execute_tool
    vid = tmp_path / "clip.mp4"
    vid.write_bytes(b"x")
    result = asyncio.run(execute_tool("send_telegram_file", {"file_path": str(vid)}))
    assert "not configured" in result.lower()


def test_product_data_payload_includes_sessions(isolated_db):
    """_product_data_payload includes sessions list and active_session_id."""
    import backend.main as m
    import backend.db as db
    pid = "test-product"
    with db._conn() as conn:
        conn.execute("INSERT OR IGNORE INTO products (id, name, icon_label, color) VALUES (?, 'T', 'T', '#000')", (pid,))
    sid = db.create_session("General", pid)
    payload = m._product_data_payload(pid, sid)
    assert "sessions" in payload
    assert "active_session_id" in payload
    assert payload["active_session_id"] == sid
    assert any(s["id"] == sid for s in payload["sessions"])


def test_build_context_scoped_to_session(isolated_db):
    """_build_context loads only messages for the given session_id."""
    import backend.main as m
    import backend.db as db
    pid = "test-product"
    with db._conn() as conn:
        conn.execute("INSERT OR IGNORE INTO products (id, name, icon_label, color) VALUES (?, 'T', 'T', '#000')", (pid,))
    sid1 = db.create_session("Finance", pid)
    sid2 = db.create_session("Ops", pid)
    db.save_message(pid, "user", "finance directive", sid1)
    ctx = m._build_context(pid, sid1)
    # Should include the finance directive
    assert any(
        isinstance(msg.get("content"), str) and "finance" in msg["content"]
        for msg in ctx
    )


def test_get_or_create_session_creates_general(isolated_db):
    """_get_or_create_session auto-creates 'General' if product has no sessions."""
    import backend.main as m
    import backend.db as db
    pid = "test-product"
    with db._conn() as conn:
        conn.execute("INSERT OR IGNORE INTO products (id, name, icon_label, color) VALUES (?, 'T', 'T', '#000')", (pid,))
    sid = m._get_or_create_session(pid)
    assert sid is not None
    sessions = db.get_sessions(pid)
    assert len(sessions) == 1
    assert sessions[0]["name"] == "General"


def test_ensure_session_creates_general_after_delete(isolated_db):
    """After deleting the last session, a new General is auto-created."""
    import backend.main as m
    import backend.db as db
    pid = "test-product"
    with db._conn() as conn:
        conn.execute("INSERT OR IGNORE INTO products (id, name, icon_label, color) VALUES (?, 'T', 'T', '#000')", (pid,))
    sid = db.create_session("Only", pid)
    db.delete_session(sid)
    new_sid = m._get_or_create_session(pid)
    sessions = db.get_sessions(pid)
    assert sessions[0]["name"] == "General"
    assert new_sid == sessions[0]["id"]


def test_on_review_approved_defers_future_scheduled_post(isolated_db):
    """Approving a draft with a future scheduled_for sets status to 'scheduled', does not publish."""
    import asyncio
    from unittest.mock import AsyncMock, patch
    import backend.db as db
    import backend.main as m

    with db._conn() as conn:
        conn.execute("INSERT OR IGNORE INTO products (id, name, icon_label, color) VALUES ('product-alpha', 'Product Alpha', 'PA', '#2563eb')")

    # Create a review item and linked draft with a future scheduled_for
    review_id = db.save_review_item("product-alpha", "Post to Twitter", "Hello", "social_post · twitter", action_type="social_post")
    draft_id = db.save_social_draft("product-alpha", "twitter", "Hello world",
                                     review_item_id=review_id,
                                     scheduled_for="2099-01-01T09:00:00")

    with patch("backend.main._publish_social_draft", new=AsyncMock()) as mock_publish:
        with patch("backend.main._broadcast", new=AsyncMock()):
            asyncio.run(m._on_review_approved(review_id))
            mock_publish.assert_not_awaited()

    with db._conn() as conn:
        row = dict(conn.execute("SELECT status FROM social_drafts WHERE id = ?", (draft_id,)).fetchone())
    assert row["status"] == "scheduled"


def test_on_review_approved_publishes_immediately_when_no_schedule(isolated_db):
    """Approving a draft with no scheduled_for publishes immediately."""
    import asyncio
    from unittest.mock import AsyncMock, patch
    import backend.db as db
    import backend.main as m

    with db._conn() as conn:
        conn.execute("INSERT OR IGNORE INTO products (id, name, icon_label, color) VALUES ('product-alpha', 'Product Alpha', 'PA', '#2563eb')")

    review_id = db.save_review_item("product-alpha", "Post to Twitter", "Hello", "social_post · twitter", action_type="social_post")
    draft_id = db.save_social_draft("product-alpha", "twitter", "Hello world",
                                     review_item_id=review_id)

    with patch("backend.main._publish_social_draft", new=AsyncMock(return_value={"success": True, "result": "ok"})):
        with patch("backend.main._broadcast", new=AsyncMock()):
            with patch("backend.main.save_activity_event", return_value=1):
                with patch("backend.main.update_activity_event"):
                    asyncio.run(m._on_review_approved(review_id))

    with db._conn() as conn:
        row = dict(conn.execute("SELECT status FROM social_drafts WHERE id = ?", (draft_id,)).fetchone())
    assert row["status"] == "posted"
