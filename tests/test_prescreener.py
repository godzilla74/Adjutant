"""Tests for the Haiku pre-screener."""
import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock


def _make_response(text: str):
    """Build a mock that looks like a Provider.create() response."""
    resp = MagicMock()
    resp.content = [MagicMock()]
    resp.content[0].text = text
    resp.usage = MagicMock()
    return resp


def _make_provider(text: str):
    """Return a mock Provider whose create() returns the given text."""
    provider = MagicMock()
    provider.create = AsyncMock(return_value=_make_response(text))
    return provider


@pytest.mark.asyncio
async def test_prescreen_haiku_route():
    from core.prescreener import prescreen, PrescreerResult
    payload = json.dumps({"route": "haiku", "response": "Hello there!"})
    provider = _make_provider(payload)

    result = await prescreen("hi", ["core"], provider, "claude-haiku-4-5-20251001")

    assert result.route == "haiku"
    assert result.response == "Hello there!"
    assert result.tool_groups == []


@pytest.mark.asyncio
async def test_prescreen_sonnet_route():
    from core.prescreener import prescreen
    payload = json.dumps({"route": "sonnet", "tool_groups": ["core", "email"]})
    provider = _make_provider(payload)

    result = await prescreen("check my email", ["core", "email", "calendar"], provider, "claude-haiku-4-5-20251001")

    assert result.route == "sonnet"
    assert "core" in result.tool_groups
    assert "email" in result.tool_groups
    assert "calendar" not in result.tool_groups


@pytest.mark.asyncio
async def test_prescreen_filters_invalid_groups():
    from core.prescreener import prescreen
    payload = json.dumps({"route": "sonnet", "tool_groups": ["core", "email", "nonexistent"]})
    provider = _make_provider(payload)

    result = await prescreen("check email", ["core", "email"], provider, "claude-haiku-4-5-20251001")

    assert "nonexistent" not in result.tool_groups


@pytest.mark.asyncio
async def test_prescreen_fallback_on_invalid_json():
    from core.prescreener import prescreen
    provider = _make_provider("not json at all")

    result = await prescreen("hello", ["core", "email"], provider, "claude-haiku-4-5-20251001")

    assert result.route == "sonnet"
    assert "core" in result.tool_groups


@pytest.mark.asyncio
async def test_prescreen_fallback_on_exception():
    from core.prescreener import prescreen
    provider = MagicMock()
    provider.create = AsyncMock(side_effect=Exception("network error"))

    result = await prescreen("hello", ["core"], provider, "claude-haiku-4-5-20251001")

    assert result.route == "sonnet"


@pytest.mark.asyncio
async def test_prescreen_always_includes_core():
    from core.prescreener import prescreen
    payload = json.dumps({"route": "sonnet", "tool_groups": ["email"]})
    provider = _make_provider(payload)

    result = await prescreen("check email", ["core", "email"], provider, "model")

    assert "core" in result.tool_groups


@pytest.mark.asyncio
async def test_prescreen_haiku_invalid_response_type():
    from core.prescreener import prescreen
    payload = json.dumps({"route": "haiku", "response": 42})
    provider = _make_provider(payload)

    result = await prescreen("hi", ["core"], provider, "model")

    assert result.route == "sonnet"  # fallback


@pytest.mark.asyncio
async def test_prescreen_unknown_route():
    from core.prescreener import prescreen
    payload = json.dumps({"route": "unknown"})
    provider = _make_provider(payload)

    result = await prescreen("hi", ["core"], provider, "model")

    assert result.route == "sonnet"
