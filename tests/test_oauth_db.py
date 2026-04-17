import importlib
import pytest


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_DB", str(tmp_path / "test.db"))
    import backend.db as db_mod
    importlib.reload(db_mod)
    db_mod.init_db()
    with db_mod._conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO products (id, name, icon_label, color) "
            "VALUES ('prod-1', 'Prod 1', 'P1', '#000000')"
        )
    return db_mod


def test_save_and_get_oauth_connection(db):
    db.save_oauth_connection(
        product_id="prod-1", service="gmail", email="user@example.com",
        access_token="access123", refresh_token="refresh456",
        token_expiry="2099-01-01T00:00:00+00:00", scopes="gmail.send gmail.readonly",
    )
    row = db.get_oauth_connection("prod-1", "gmail")
    assert row is not None
    assert row["email"] == "user@example.com"
    assert row["access_token"] == "access123"
    assert row["service"] == "gmail"


def test_get_oauth_connection_missing_returns_none(db):
    assert db.get_oauth_connection("prod-1", "gmail") is None


def test_save_oauth_connection_upserts(db):
    db.save_oauth_connection("prod-1", "gmail", "a@x.com", "tok1", "ref1", "2099-01-01T00:00:00+00:00", "s1")
    db.save_oauth_connection("prod-1", "gmail", "b@x.com", "tok2", "ref2", "2099-01-01T00:00:00+00:00", "s2")
    row = db.get_oauth_connection("prod-1", "gmail")
    assert row["email"] == "b@x.com"
    assert row["access_token"] == "tok2"


def test_delete_oauth_connection(db):
    db.save_oauth_connection("prod-1", "gmail", "a@x.com", "t", "r", "2099-01-01T00:00:00+00:00", "s")
    db.delete_oauth_connection("prod-1", "gmail")
    assert db.get_oauth_connection("prod-1", "gmail") is None


def test_list_oauth_connections(db):
    db.save_oauth_connection("prod-1", "gmail", "a@x.com", "t", "r", "2099-01-01T00:00:00+00:00", "s")
    db.save_oauth_connection("prod-1", "google_calendar", "a@x.com", "t2", "r2", "2099-01-01T00:00:00+00:00", "s2")
    conns = db.list_oauth_connections("prod-1")
    services = {c["service"] for c in conns}
    assert services == {"gmail", "google_calendar"}


def test_list_oauth_connections_empty(db):
    assert db.list_oauth_connections("prod-1") == []


def test_google_oauth_keys_have_defaults(db):
    config = db.get_agent_config()
    assert "google_oauth_client_id" in config
    assert "google_oauth_client_secret" in config
    assert config["google_oauth_client_id"] == ""
    assert config["google_oauth_client_secret"] == ""
