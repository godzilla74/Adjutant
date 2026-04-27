"""Tests for token optimization helpers: tool groups, datetime injection, cache_control."""
import pytest


# ── Tool Groups ───────────────────────────────────────────────────────────────

def test_tool_groups_contains_expected_groups():
    from core.tools import TOOL_GROUPS
    assert set(TOOL_GROUPS.keys()) == {"core", "email", "calendar", "social", "management", "system"}


def test_tool_groups_core_has_essential_tools():
    from core.tools import TOOL_GROUPS
    core = TOOL_GROUPS["core"]
    assert "delegate_task" in core
    assert "save_note" in core
    assert "read_notes" in core
    assert "create_review_item" in core


def test_tool_groups_email_tools():
    from core.tools import TOOL_GROUPS
    assert TOOL_GROUPS["email"] == {"gmail_search", "gmail_read", "gmail_send", "gmail_draft"}


def test_tool_groups_calendar_tools():
    from core.tools import TOOL_GROUPS
    assert TOOL_GROUPS["calendar"] == {"calendar_list_events", "calendar_create_event", "calendar_find_free_time"}


def test_tool_groups_social_tools():
    from core.tools import TOOL_GROUPS
    social = TOOL_GROUPS["social"]
    assert "twitter_post" in social
    assert "draft_social_post" in social
    assert "generate_image" in social
    assert "search_stock_photo" in social


def test_get_tools_for_groups_always_includes_core(monkeypatch):
    from unittest.mock import patch
    from core.tools import get_tools_for_groups, TOOL_GROUPS

    # Patch get_tools_for_product to return a fixed list of all-groups tools
    fake_tools = [{"name": n} for group in TOOL_GROUPS.values() for n in group]
    with patch("core.tools.get_tools_for_product", return_value=fake_tools), \
         patch("core.tools.get_extensions_for_product", return_value=[]):
        result = get_tools_for_groups(["social"], "prod-1")

    names = {t["name"] for t in result}
    # core tools always present
    assert "delegate_task" in names
    assert "save_note" in names
    # requested group present
    assert "twitter_post" in names
    # unrequested groups excluded
    assert "gmail_send" not in names
    assert "calendar_list_events" not in names


def test_get_tools_for_groups_includes_extensions(monkeypatch):
    from unittest.mock import patch
    from core.tools import get_tools_for_groups, TOOL_GROUPS

    fake_core = [{"name": n} for n in TOOL_GROUPS["core"]]
    fake_ext = [{"name": "my_custom_tool"}]
    with patch("core.tools.get_tools_for_product", return_value=fake_core + fake_ext), \
         patch("core.tools.get_extensions_for_product", return_value=fake_ext):
        result = get_tools_for_groups(["core"], "prod-1")

    names = {t["name"] for t in result}
    assert "my_custom_tool" in names


def test_get_tools_for_groups_unknown_group_ignored(monkeypatch):
    from unittest.mock import patch
    from core.tools import get_tools_for_groups, TOOL_GROUPS

    fake_tools = [{"name": n} for n in TOOL_GROUPS["core"]]
    with patch("core.tools.get_tools_for_product", return_value=fake_tools), \
         patch("core.tools.get_extensions_for_product", return_value=[]):
        # "nonexistent" group should not cause an error
        result = get_tools_for_groups(["core", "nonexistent"], "prod-1")

    assert len(result) > 0  # core tools still returned


# ── DB + API config ───────────────────────────────────────────────────────────

def test_agent_config_defaults_include_prescreener_model():
    from backend.db import _AGENT_CONFIG_DEFAULTS
    assert "prescreener_model" in _AGENT_CONFIG_DEFAULTS
    assert _AGENT_CONFIG_DEFAULTS["prescreener_model"] == "claude-haiku-4-5-20251001"


def test_get_agent_config_returns_prescreener_model():
    from backend.db import get_agent_config
    cfg = get_agent_config()
    assert "prescreener_model" in cfg
    assert cfg["prescreener_model"] == "claude-haiku-4-5-20251001"


# ── Datetime injection ────────────────────────────────────────────────────────

def test_inject_datetime_prepends_to_first_user_message():
    from backend.main import _inject_datetime
    messages = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi"},
        {"role": "user", "content": "second message"},
    ]
    result = _inject_datetime(messages)
    assert result[0]["content"].startswith("[Current datetime:")
    assert "hello" in result[0]["content"]
    # Only first user message modified
    assert result[2]["content"] == "second message"


def test_inject_datetime_does_not_mutate_input():
    from backend.main import _inject_datetime
    original = [{"role": "user", "content": "hello"}]
    result = _inject_datetime(original)
    assert original[0]["content"] == "hello"
    assert result[0]["content"] != "hello"


def test_inject_datetime_handles_list_content():
    from backend.main import _inject_datetime
    messages = [
        {"role": "user", "content": [{"type": "text", "text": "hello"}]},
    ]
    result = _inject_datetime(messages)
    content = result[0]["content"]
    assert isinstance(content, list)
    assert content[0]["type"] == "text"
    assert "[Current datetime:" in content[0]["text"]
    assert content[1] == {"type": "text", "text": "hello"}


def test_inject_datetime_no_user_message_unchanged():
    from backend.main import _inject_datetime
    messages = [{"role": "assistant", "content": "hello"}]
    result = _inject_datetime(messages)
    assert result[0]["content"] == "hello"


# ── cache_control blocks ──────────────────────────────────────────────────────

def test_add_cache_control_wraps_system_as_list():
    from backend.main import _add_cache_control
    system_list, tools = _add_cache_control("my system prompt", [{"name": "tool_a"}, {"name": "tool_b"}])
    assert isinstance(system_list, list)
    assert system_list[0]["type"] == "text"
    assert system_list[0]["text"] == "my system prompt"
    assert system_list[0]["cache_control"] == {"type": "ephemeral"}


def test_add_cache_control_adds_to_last_tool_only():
    from backend.main import _add_cache_control
    original_tools = [{"name": "tool_a"}, {"name": "tool_b"}]
    _, tools = _add_cache_control("prompt", original_tools)
    assert "cache_control" not in tools[0]
    assert tools[1]["cache_control"] == {"type": "ephemeral"}


def test_add_cache_control_does_not_mutate_original_tools():
    from backend.main import _add_cache_control
    original_tools = [{"name": "tool_a"}, {"name": "tool_b"}]
    _, tools = _add_cache_control("prompt", original_tools)
    assert "cache_control" not in original_tools[1]


def test_add_cache_control_empty_tools_returns_empty():
    from backend.main import _add_cache_control
    system_list, tools = _add_cache_control("prompt", [])
    assert tools == []
    assert system_list[0]["cache_control"] == {"type": "ephemeral"}


# ── Available groups ──────────────────────────────────────────────────────────

def test_compute_available_groups_no_oauth():
    from backend.main import _compute_available_groups
    from unittest.mock import patch
    with patch("backend.main.list_oauth_connections", return_value=[]):
        groups = _compute_available_groups("prod-1")
    assert "core" in groups
    assert "management" in groups
    assert "system" in groups
    assert "email" not in groups
    assert "calendar" not in groups
    assert "social" not in groups


def test_compute_available_groups_with_gmail():
    from backend.main import _compute_available_groups
    from unittest.mock import patch
    with patch("backend.main.list_oauth_connections", return_value=[{"service": "gmail"}]):
        groups = _compute_available_groups("prod-1")
    assert "email" in groups


def test_compute_available_groups_with_social():
    from backend.main import _compute_available_groups
    from unittest.mock import patch
    with patch("backend.main.list_oauth_connections", return_value=[{"service": "twitter"}]):
        groups = _compute_available_groups("prod-1")
    assert "social" in groups
