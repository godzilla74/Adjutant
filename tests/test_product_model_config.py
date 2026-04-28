"""Tests for per-product model config resolution."""
import importlib
import pytest


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_DB", str(tmp_path / "test.db"))
    import backend.db as db_mod
    importlib.reload(db_mod)
    db_mod.init_db()
    return db_mod


def _seed_product(db, product_id="prod-1"):
    db.create_product(product_id, "Test Product", "T", "#fff")
    return product_id


def test_get_product_model_config_falls_back_to_global(db):
    pid = _seed_product(db)
    cfg = db.get_product_model_config(pid)
    assert cfg["agent_model"] == "claude-sonnet-4-6"
    assert cfg["subagent_model"] == "claude-sonnet-4-6"
    assert cfg["prescreener_model"] == "claude-haiku-4-5-20251001"


def test_get_product_model_config_none_product(db):
    cfg = db.get_product_model_config(None)
    assert cfg["agent_model"] == "claude-sonnet-4-6"


def test_set_product_model_config_overrides_global(db):
    pid = _seed_product(db)
    db.set_product_model_config(pid, agent_model="gpt-4o")
    cfg = db.get_product_model_config(pid)
    assert cfg["agent_model"] == "gpt-4o"
    # Other fields still fall back to global
    assert cfg["subagent_model"] == "claude-sonnet-4-6"


def test_set_product_model_config_clear_with_none(db):
    pid = _seed_product(db)
    db.set_product_model_config(pid, agent_model="gpt-4o")
    db.set_product_model_config(pid, agent_model=None)
    cfg = db.get_product_model_config(pid)
    assert cfg["agent_model"] == "claude-sonnet-4-6"  # back to global


def test_set_product_model_config_all_three(db):
    pid = _seed_product(db)
    db.set_product_model_config(
        pid,
        agent_model="gpt-4o",
        subagent_model="gpt-4o",
        prescreener_model="gpt-4o-mini",
    )
    cfg = db.get_product_model_config(pid)
    assert cfg["agent_model"] == "gpt-4o"
    assert cfg["subagent_model"] == "gpt-4o"
    assert cfg["prescreener_model"] == "gpt-4o-mini"
