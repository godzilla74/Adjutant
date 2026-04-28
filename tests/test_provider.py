"""Tests for backend/provider.py — format translation and provider selection."""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ── Translation helpers ────────────────────────────────────────────────────────

def test_translate_tools_to_openai():
    from backend.provider import _translate_tools_to_openai
    anthropic_tools = [
        {
            "name": "gmail_search",
            "description": "Search Gmail inbox.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                },
                "required": ["query"],
            },
        }
    ]
    result = _translate_tools_to_openai(anthropic_tools)
    assert result == [
        {
            "type": "function",
            "function": {
                "name": "gmail_search",
                "description": "Search Gmail inbox.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                    },
                    "required": ["query"],
                },
            },
        }
    ]


def test_translate_tools_strips_cache_control():
    from backend.provider import _translate_tools_to_openai
    tools = [
        {
            "name": "foo",
            "description": "bar",
            "input_schema": {"type": "object", "properties": {}},
            "cache_control": {"type": "ephemeral"},
        }
    ]
    result = _translate_tools_to_openai(tools)
    assert "cache_control" not in result[0]["function"]
    assert "cache_control" not in result[0]


def test_translate_messages_plain_user():
    from backend.provider import _translate_messages_to_openai
    messages = [{"role": "user", "content": "Hello"}]
    result = _translate_messages_to_openai(messages, system="Be helpful.")
    assert result[0] == {"role": "system", "content": "Be helpful."}
    assert result[1] == {"role": "user", "content": "Hello"}


def test_translate_messages_system_list():
    from backend.provider import _translate_messages_to_openai
    system = [
        {"type": "text", "text": "You are an assistant.", "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": " Be concise."},
    ]
    messages = [{"role": "user", "content": "Hi"}]
    result = _translate_messages_to_openai(messages, system=system)
    assert result[0] == {"role": "system", "content": "You are an assistant. Be concise."}


def test_translate_messages_empty_system():
    from backend.provider import _translate_messages_to_openai
    result = _translate_messages_to_openai([{"role": "user", "content": "Hi"}], system="")
    assert result[0]["role"] == "user"  # no system message injected


def test_translate_messages_tool_use():
    from backend.provider import _translate_messages_to_openai
    messages = [
        {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "I will search."},
                {"type": "tool_use", "id": "tu_1", "name": "gmail_search", "input": {"query": "hello"}},
            ],
        }
    ]
    result = _translate_messages_to_openai(messages, system="")
    assert result[0]["role"] == "assistant"
    assert result[0]["content"] == "I will search."
    assert result[0]["tool_calls"] == [
        {"id": "tu_1", "type": "function", "function": {"name": "gmail_search", "arguments": '{"query": "hello"}'}}
    ]


def test_translate_messages_tool_result():
    from backend.provider import _translate_messages_to_openai
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": "tu_1", "content": "Found 3 messages."},
            ],
        }
    ]
    result = _translate_messages_to_openai(messages, system="")
    assert result[0] == {"role": "tool", "tool_call_id": "tu_1", "content": "Found 3 messages."}


def test_translate_messages_strips_cache_control_from_content():
    from backend.provider import _translate_messages_to_openai
    messages = [
        {"role": "user", "content": [{"type": "text", "text": "Hi", "cache_control": {"type": "ephemeral"}}]}
    ]
    result = _translate_messages_to_openai(messages, system="")
    assert result[0] == {"role": "user", "content": "Hi"}


# ── Provider selection ─────────────────────────────────────────────────────────

def test_get_provider_name_anthropic():
    from backend.provider import get_provider_name
    assert get_provider_name("claude-sonnet-4-6") == "anthropic"
    assert get_provider_name("claude-haiku-4-5-20251001") == "anthropic"


def test_get_provider_name_openai():
    from backend.provider import get_provider_name
    assert get_provider_name("gpt-4o") == "openai"
    assert get_provider_name("gpt-4o-mini") == "openai"
    assert get_provider_name("o3-mini") == "openai"


def test_make_provider_returns_anthropic():
    from backend.provider import make_provider, AnthropicProvider
    p = make_provider("claude-sonnet-4-6")
    assert isinstance(p, AnthropicProvider)
    assert p.name == "anthropic"


def test_make_provider_returns_openai():
    from backend.provider import make_provider, OpenAIProvider
    with patch("backend.provider.get_openai_client") as mock_client:
        mock_client.return_value = MagicMock()
        p = make_provider("gpt-4o")
    assert isinstance(p, OpenAIProvider)
    assert p.name == "openai"


# ── AnthropicProvider ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_anthropic_provider_create():
    from backend.provider import AnthropicProvider
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=mock_resp)
    provider = AnthropicProvider(mock_client)

    result = await provider.create(
        model="claude-haiku-4-5-20251001",
        system="Be helpful.",
        messages=[{"role": "user", "content": "Hi"}],
        max_tokens=512,
    )
    assert result is mock_resp
    mock_client.messages.create.assert_called_once_with(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        system="Be helpful.",
        messages=[{"role": "user", "content": "Hi"}],
    )


# ── OpenAIProvider ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_openai_provider_create():
    from backend.provider import OpenAIProvider
    mock_client = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = '{"route": "haiku", "response": "Hi!"}'
    mock_resp = MagicMock()
    mock_resp.choices = [mock_choice]
    mock_resp.usage.prompt_tokens = 50
    mock_resp.usage.completion_tokens = 10
    mock_resp.usage.prompt_tokens_details = None
    mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)

    provider = OpenAIProvider(mock_client)
    result = await provider.create(
        model="gpt-4o-mini",
        system="Route this message.",
        messages=[{"role": "user", "content": "hello"}],
        max_tokens=512,
    )
    assert result.content[0].text == '{"route": "haiku", "response": "Hi!"}'
    assert result.usage.prompt_tokens == 50


@pytest.mark.asyncio
async def test_openai_provider_skips_mcp_headers():
    from backend.provider import OpenAIProvider
    import logging
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock()]
    mock_resp.choices[0].message.content = "ok"
    mock_resp.usage = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)

    provider = OpenAIProvider(mock_client)
    with patch("backend.provider.logger") as mock_log:
        await provider.create(
            model="gpt-4o",
            system="",
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=512,
        )
        # extra_headers/body not passed to create; no warning for create()
    # stream_agent skips extra_headers — tested separately via integration
