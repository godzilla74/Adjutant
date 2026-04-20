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


def test_get_global_tools_includes_dispatch():
    from core.tools import get_global_tools
    tools = get_global_tools()
    names = [t["name"] for t in tools]
    assert "dispatch_to_product" in names


def test_get_global_tools_excludes_social():
    from core.tools import get_global_tools
    tools = get_global_tools()
    names = [t["name"] for t in tools]
    assert "twitter_post" not in names
    assert "instagram_post" not in names
    assert "gmail_send" not in names


def test_dispatch_tool_schema():
    from core.tools import get_global_tools
    tools = get_global_tools()
    dispatch = next(t for t in tools if t["name"] == "dispatch_to_product")
    props = dispatch["input_schema"]["properties"]
    assert "product_id" in props
    assert "message" in props
    assert dispatch["input_schema"]["required"] == ["product_id", "message"]


def test_get_global_tools_has_expected_count():
    from core.tools import get_global_tools, _GLOBAL_BASE_TOOL_NAMES
    tools = get_global_tools()
    assert len(tools) == len(_GLOBAL_BASE_TOOL_NAMES) + 1
