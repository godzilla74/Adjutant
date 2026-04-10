import sys
from pathlib import Path
from unittest.mock import patch

import pytest


def test_get_uploads_dir_linux(tmp_path):
    with patch("sys.platform", "linux"), \
         patch("pathlib.Path.home", return_value=tmp_path):
        from backend import uploads
        import importlib; importlib.reload(uploads)
        d = uploads.get_uploads_dir()
        assert d == tmp_path / ".local" / "share" / "Adjutant" / "uploads"


def test_get_uploads_dir_mac(tmp_path):
    with patch("sys.platform", "darwin"), \
         patch("pathlib.Path.home", return_value=tmp_path):
        from backend import uploads
        import importlib; importlib.reload(uploads)
        d = uploads.get_uploads_dir()
        assert d == tmp_path / "Library" / "Application Support" / "Adjutant" / "uploads"


def test_save_uploaded_file_creates_file(tmp_path):
    with patch("backend.uploads.get_uploads_dir", return_value=tmp_path):
        from backend import uploads
        path = uploads.save_uploaded_file("test.mp4", b"fakevideo")
        assert path.exists()
        assert path.read_bytes() == b"fakevideo"
        assert "test.mp4" in path.name


def test_save_uploaded_file_timestamp_prefix(tmp_path):
    with patch("backend.uploads.get_uploads_dir", return_value=tmp_path):
        from backend import uploads
        path = uploads.save_uploaded_file("promo.mp4", b"x")
        # Filename format: YYYYMMDD_HHMMSS_promo.mp4
        assert path.name.count("_") >= 2
        parts = path.name.split("_")
        assert len(parts[0]) == 8  # YYYYMMDD
        assert parts[0].isdigit()


def test_save_uploaded_file_sanitizes_name(tmp_path):
    with patch("backend.uploads.get_uploads_dir", return_value=tmp_path):
        from backend import uploads
        path = uploads.save_uploaded_file("my file (1).pdf", b"pdf")
        assert " " not in path.name
        assert "(" not in path.name
