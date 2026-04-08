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

    import backend.bootstrap as bootstrap_mod
    import backend.db as db_mod
    importlib.reload(bootstrap_mod)  # re-runs load_dotenv with the new ADJUTANT_CONFIG
    importlib.reload(db_mod)         # re-reads AGENT_DB now that it's been loaded

    assert str(db_mod.DB_PATH) == str(db_file)
