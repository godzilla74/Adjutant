import importlib
import io
import os
from unittest.mock import patch

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


def get_app():
    import backend.main as main_mod
    return main_mod.app


def auth_headers():
    return {"X-Agent-Password": "testpass"}


def test_upload_image_returns_metadata(tmp_path):
    with patch("backend.uploads.get_uploads_dir", return_value=tmp_path):
        from fastapi.testclient import TestClient
        client = TestClient(get_app())
        data = b"\xff\xd8\xff"  # JPEG magic bytes
        resp = client.post(
            "/api/upload",
            headers=auth_headers(),
            files={"file": ("photo.jpg", io.BytesIO(data), "image/jpeg")},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["mime_type"] == "image/jpeg"
        assert body["name"] == "photo.jpg"
        assert body["size"] == len(data)
        assert "photo.jpg" in body["path"]


def test_upload_requires_auth(tmp_path):
    with patch("backend.uploads.get_uploads_dir", return_value=tmp_path):
        from fastapi.testclient import TestClient
        client = TestClient(get_app())
        resp = client.post(
            "/api/upload",
            files={"file": ("photo.jpg", io.BytesIO(b"x"), "image/jpeg")},
        )
        assert resp.status_code == 401


def test_upload_rejects_oversized_image(tmp_path):
    with patch("backend.uploads.get_uploads_dir", return_value=tmp_path):
        from fastapi.testclient import TestClient
        client = TestClient(get_app())
        big = b"x" * (20 * 1024 * 1024 + 1)
        resp = client.post(
            "/api/upload",
            headers=auth_headers(),
            files={"file": ("big.jpg", io.BytesIO(big), "image/jpeg")},
        )
        assert resp.status_code == 413


def test_upload_video_accepted(tmp_path):
    with patch("backend.uploads.get_uploads_dir", return_value=tmp_path):
        from fastapi.testclient import TestClient
        client = TestClient(get_app())
        resp = client.post(
            "/api/upload",
            headers=auth_headers(),
            files={"file": ("clip.mp4", io.BytesIO(b"fakevideo"), "video/mp4")},
        )
        assert resp.status_code == 200
        assert resp.json()["mime_type"] == "video/mp4"
