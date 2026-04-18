# tests/test_social_oauth.py
import importlib
import os
import pytest

os.environ.setdefault("AGENT_PASSWORD", "testpass")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_DB", str(tmp_path / "test.db"))
    import backend.db as db_mod
    importlib.reload(db_mod)
    db_mod.init_db()
    return db_mod


def test_social_credential_keys_have_defaults(db):
    config = db.get_agent_config()
    assert "twitter_client_id" in config
    assert "twitter_client_secret" in config
    assert "linkedin_client_id" in config
    assert "linkedin_client_secret" in config
    assert "meta_app_id" in config
    assert "meta_app_secret" in config
    assert config["twitter_client_id"] == ""
    assert config["meta_app_id"] == ""
