# tests/test_config.py
import importlib
import pytest


@pytest.fixture
def config_mod(monkeypatch):
    monkeypatch.setenv("AGENT_NAME", "Aria")
    monkeypatch.setenv("AGENT_OWNER_NAME", "Sarah")
    monkeypatch.setenv("AGENT_OWNER_BIO", "Sarah runs a boutique marketing agency.")
    import core.config as mod
    importlib.reload(mod)
    return mod


def test_system_prompt_uses_agent_name(config_mod):
    prompt = config_mod.get_system_prompt("test-product")
    assert "Aria" in prompt
    assert "Hannah" not in prompt


def test_system_prompt_uses_owner_name(config_mod):
    prompt = config_mod.get_system_prompt("test-product")
    assert "Sarah" in prompt


def test_system_prompt_uses_owner_bio(config_mod):
    prompt = config_mod.get_system_prompt("test-product")
    assert "boutique marketing agency" in prompt


def test_system_prompt_defaults_to_hannah(monkeypatch):
    monkeypatch.delenv("AGENT_NAME", raising=False)
    monkeypatch.delenv("AGENT_OWNER_NAME", raising=False)
    monkeypatch.delenv("AGENT_OWNER_BIO", raising=False)
    import core.config as mod
    importlib.reload(mod)
    prompt = mod.get_system_prompt("test-product")
    assert "Hannah" in prompt


def test_global_system_prompt_lists_products(monkeypatch):
    monkeypatch.setenv("AGENT_NAME", "Hannah")
    monkeypatch.setenv("AGENT_OWNER_NAME", "Justin")
    monkeypatch.delenv("AGENT_OWNER_BIO", raising=False)
    import core.config as mod
    importlib.reload(mod)
    products = [
        {"id": "acme", "name": "Acme"},
        {"id": "beta", "name": "Beta"},
    ]
    prompt = mod.get_global_system_prompt(products)
    assert "acme" in prompt
    assert "Acme" in prompt
    assert "beta" in prompt
    assert "dispatch_to_product" in prompt


def test_global_system_prompt_no_products(monkeypatch):
    monkeypatch.delenv("AGENT_NAME", raising=False)
    import core.config as mod
    importlib.reload(mod)
    prompt = mod.get_global_system_prompt([])
    assert "no products configured" in prompt
