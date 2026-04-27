"""Tests for the Haiku pre-screener."""
import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _make_anthropic_response(text: str):
    """Build a minimal mock that looks like an anthropic Message."""
    content_block = MagicMock()
    content_block.text = text
    msg = MagicMock()
    msg.content = [content_block]
    return msg


@pytest.mark.asyncio
async def test_prescreen_haiku_route():
    from core.prescreener import prescreen, PrescreerResult
    payload = json.dumps({"route": "haiku", "response": "Hello there!"})
    client = MagicMock()
    client.messages.create = AsyncMock(return_value=_make_anthropic_response(payload))

    result = await prescreen("hi", ["core"], client, "claude-haiku-4-5-20251001")

    assert result.route == "haiku"
    assert result.response == "Hello there!"
    assert result.tool_groups == []


@pytest.mark.asyncio
async def test_prescreen_sonnet_route():
    from core.prescreener import prescreen
    payload = json.dumps({"route": "sonnet", "tool_groups": ["core", "email"]})
    client = MagicMock()
    client.messages.create = AsyncMock(return_value=_make_anthropic_response(payload))

    result = await prescreen("check my email", ["core", "email", "calendar"], client, "claude-haiku-4-5-20251001")

    assert result.route == "sonnet"
    assert "core" in result.tool_groups
    assert "email" in result.tool_groups
    assert result.response is None


@pytest.mark.asyncio
async def test_prescreen_core_always_in_sonnet_groups():
    from core.prescreener import prescreen
    # Haiku forgot to include core
    payload = json.dumps({"route": "sonnet", "tool_groups": ["email"]})
    client = MagicMock()
    client.messages.create = AsyncMock(return_value=_make_anthropic_response(payload))

    result = await prescreen("send email", ["core", "email"], client, "claude-haiku-4-5-20251001")

    assert "core" in result.tool_groups


@pytest.mark.asyncio
async def test_prescreen_filters_unavailable_groups():
    from core.prescreener import prescreen
    # Haiku requests "social" but it's not in available_groups
    payload = json.dumps({"route": "sonnet", "tool_groups": ["core", "social"]})
    client = MagicMock()
    client.messages.create = AsyncMock(return_value=_make_anthropic_response(payload))

    result = await prescreen("post something", ["core", "email"], client, "claude-haiku-4-5-20251001")

    assert "social" not in result.tool_groups


@pytest.mark.asyncio
async def test_prescreen_json_error_falls_back_to_sonnet():
    from core.prescreener import prescreen
    client = MagicMock()
    client.messages.create = AsyncMock(return_value=_make_anthropic_response("not valid json at all"))

    result = await prescreen("hi", ["core", "email"], client, "claude-haiku-4-5-20251001")

    assert result.route == "sonnet"
    assert "core" in result.tool_groups
    assert "email" in result.tool_groups


@pytest.mark.asyncio
async def test_prescreen_api_exception_falls_back_to_sonnet():
    from core.prescreener import prescreen
    client = MagicMock()
    client.messages.create = AsyncMock(side_effect=Exception("network error"))

    result = await prescreen("hi", ["core", "email"], client, "claude-haiku-4-5-20251001")

    assert result.route == "sonnet"
    assert "core" in result.tool_groups


@pytest.mark.asyncio
async def test_prescreen_unknown_route_falls_back_to_sonnet():
    from core.prescreener import prescreen
    payload = json.dumps({"route": "unknown", "tool_groups": ["core"]})
    client = MagicMock()
    client.messages.create = AsyncMock(return_value=_make_anthropic_response(payload))

    result = await prescreen("hi", ["core"], client, "claude-haiku-4-5-20251001")

    assert result.route == "sonnet"
