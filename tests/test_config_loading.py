# tests/test_config_loading.py
import importlib
import os
import pytest
from pathlib import Path


def test_adjutant_config_env_var_is_loaded(tmp_path, monkeypatch):
    """ADJUTANT_CONFIG env var path must be loaded so backend.db sees the vars."""
    config_file = tmp_path / "config.env"
    db_file = tmp_path / "test.db"
    config_file.write_text(f"AGENT_DB={db_file}\nAGENT_PASSWORD=testpass\n")

    monkeypatch.setenv("ADJUTANT_CONFIG", str(config_file))
    monkeypatch.delenv("AGENT_DB", raising=False)

    # Reload db module so it picks up env from the config file
    import backend.db as db_mod
    importlib.reload(db_mod)

    assert str(db_mod.DB_PATH) == str(db_file)
