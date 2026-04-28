# backend/provider.py
"""Provider abstraction — wraps Anthropic and OpenAI behind a uniform interface."""
from __future__ import annotations

import json
import logging
from typing import Callable

logger = logging.getLogger(__name__)


# ── Format translation helpers ─────────────────────────────────────────────────

def _extract_system_text(system: str | list) -> str:
    """Convert Anthropic system (str or list of content blocks) to a plain string."""
    if isinstance(system, str):
        return system
    parts = []
    for block in system:
        if isinstance(block, dict) and block.get("type") == "text":
            parts.append(block["text"])
    return "".join(parts)


def _translate_tools_to_openai(tools: list) -> list:
    """Convert Anthropic tool defs to OpenAI function-calling format."""
    result = []
    for t in tools:
        result.append({
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t.get("description", ""),
                "parameters": t["input_schema"],
            },
        })
    return result


def _translate_messages_to_openai(messages: list, system: str | list) -> list:
    """Convert Anthropic-format message history + system to OpenAI messages list."""
    result = []

    system_text = _extract_system_text(system)
    if system_text:
        result.append({"role": "system", "content": system_text})

    for msg in messages:
        role = msg["role"]
        content = msg["content"]

        if role == "user":
            if isinstance(content, str):
                result.append({"role": "user", "content": content})
            elif isinstance(content, list):
                # May be tool_result blocks or plain text blocks
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    btype = block.get("type")
                    if btype == "tool_result":
                        result.append({
                            "role": "tool",
                            "tool_call_id": block["tool_use_id"],
                            "content": str(block.get("content", "")),
                        })
                    elif btype == "text":
                        result.append({"role": "user", "content": block["text"]})

        elif role == "assistant":
            if isinstance(content, str):
                result.append({"role": "assistant", "content": content})
            elif isinstance(content, list):
                text_parts = []
                tool_calls = []
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    btype = block.get("type")
                    if btype == "text":
                        text_parts.append(block["text"])
                    elif btype == "tool_use":
                        tool_calls.append({
                            "id": block["id"],
                            "type": "function",
                            "function": {
                                "name": block["name"],
                                "arguments": json.dumps(block["input"]),
                            },
                        })
                oai_msg: dict = {"role": "assistant"}
                if text_parts:
                    oai_msg["content"] = "".join(text_parts)
                if tool_calls:
                    oai_msg["tool_calls"] = tool_calls
                result.append(oai_msg)

    return result


# ── Normalized response types for OpenAI ──────────────────────────────────────

class _OAITextBlock:
    __slots__ = ("type", "text")

    def __init__(self, text: str) -> None:
        self.type = "text"
        self.text = text

    def model_dump(self) -> dict:
        return {"type": "text", "text": self.text}


class _OAIToolUseBlock:
    __slots__ = ("type", "id", "name", "input")

    def __init__(self, id: str, name: str, input: dict) -> None:
        self.type = "tool_use"
        self.id = id
        self.name = name
        self.input = input

    def model_dump(self) -> dict:
        return {"type": "tool_use", "id": self.id, "name": self.name, "input": self.input}


class _OAIMessage:
    """Normalised OpenAI response that looks like an Anthropic Message to backend/main.py."""
    __slots__ = ("stop_reason", "usage", "content")

    def __init__(self, text: str, tool_calls: list[dict], usage, finish_reason: str) -> None:
        self.stop_reason = "tool_use" if finish_reason == "tool_calls" else "end_turn"
        self.usage = usage
        blocks: list = []
        if text:
            blocks.append(_OAITextBlock(text))
        for tc in tool_calls:
            fn = tc["function"]
            try:
                inp = json.loads(fn["arguments"] or "{}")
            except json.JSONDecodeError:
                inp = {}
            blocks.append(_OAIToolUseBlock(id=tc["id"], name=fn["name"], input=inp))
        self.content = blocks


class _OAICreateResponse:
    """Normalised OpenAI non-streaming response that looks like an Anthropic Message."""
    __slots__ = ("usage", "content")

    def __init__(self, text: str, usage) -> None:
        self.usage = usage
        self.content = [_OAITextBlock(text)]


# ── Provider selection ─────────────────────────────────────────────────────────

def get_provider_name(model: str) -> str:
    if model.startswith(("gpt-", "o1", "o3", "o4")):
        return "openai"
    return "anthropic"


def get_openai_client():
    """Return an AsyncOpenAI client using the OAuth token (same credential Codex CLI uses).
    Falls back to a direct Platform API key for users who have one but skipped OAuth."""
    from backend.db import get_agent_config
    from openai import AsyncOpenAI
    cfg = get_agent_config()
    key = cfg.get("openai_access_token", "") or cfg.get("openai_api_key", "")
    if not key:
        raise RuntimeError("OpenAI not connected. Connect via Settings → Agent Model.")
    return AsyncOpenAI(api_key=key)


# ── Provider implementations ───────────────────────────────────────────────────

class AnthropicProvider:
    name = "anthropic"

    def __init__(self, client) -> None:
        self._client = client

    async def stream_agent(
        self,
        model: str,
        system: str | list,
        messages: list,
        tools: list,
        max_tokens: int,
        on_text: Callable,
        extra_headers: dict | None = None,
        extra_body: dict | None = None,
    ) -> object:
        kwargs: dict = dict(
            model=model,
            max_tokens=max_tokens,
            system=system,
            tools=tools,
            messages=messages,
        )
        if extra_headers:
            kwargs["extra_headers"] = extra_headers
        if extra_body:
            kwargs["extra_body"] = extra_body
        async with self._client.messages.stream(**kwargs) as stream:
            async for event in stream:
                if (
                    event.type == "content_block_delta"
                    and event.delta.type == "text_delta"
                ):
                    await on_text(event.delta.text)
            return await stream.get_final_message()

    async def create(
        self,
        model: str,
        system: str,
        messages: list,
        max_tokens: int,
    ) -> object:
        kwargs: dict = dict(
            model=model,
            max_tokens=max_tokens,
            messages=messages,
        )
        if system:
            kwargs["system"] = system
        return await self._client.messages.create(**kwargs)


class OpenAIProvider:
    name = "openai"

    def __init__(self, client) -> None:
        self._client = client

    async def stream_agent(
        self,
        model: str,
        system: str | list,
        messages: list,
        tools: list,
        max_tokens: int,
        on_text: Callable,
        extra_headers: dict | None = None,
        extra_body: dict | None = None,
    ) -> object:
        if extra_headers or extra_body:
            logger.warning("OpenAIProvider: remote MCP (extra_headers/extra_body) is not supported; skipping")

        oai_messages = _translate_messages_to_openai(messages, system)
        oai_tools = _translate_tools_to_openai(tools)

        accumulated_text = ""
        tool_calls_acc: dict[int, dict] = {}
        finish_reason = "stop"
        final_usage = None

        kwargs: dict = dict(
            model=model,
            max_tokens=max_tokens,
            messages=oai_messages,
            stream=True,
            stream_options={"include_usage": True},
        )
        if oai_tools:
            kwargs["tools"] = oai_tools

        async with await self._client.chat.completions.create(**kwargs) as stream:
            async for chunk in stream:
                choice = chunk.choices[0] if chunk.choices else None
                if choice:
                    delta = choice.delta
                    if delta.content:
                        await on_text(delta.content)
                        accumulated_text += delta.content
                    if delta.tool_calls:
                        for tc in delta.tool_calls:
                            idx = tc.index
                            if idx not in tool_calls_acc:
                                tool_calls_acc[idx] = {
                                    "id": tc.id or "",
                                    "type": "function",
                                    "function": {"name": tc.function.name or "", "arguments": ""},
                                }
                            if tc.function.arguments:
                                tool_calls_acc[idx]["function"]["arguments"] += tc.function.arguments
                    if choice.finish_reason:
                        finish_reason = choice.finish_reason
                if chunk.usage:
                    final_usage = chunk.usage

        tool_calls = [tool_calls_acc[i] for i in sorted(tool_calls_acc)]
        return _OAIMessage(accumulated_text, tool_calls, final_usage, finish_reason)

    async def create(
        self,
        model: str,
        system: str,
        messages: list,
        max_tokens: int,
    ) -> object:
        oai_messages = _translate_messages_to_openai(messages, system)
        resp = await self._client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=oai_messages,
        )
        text = resp.choices[0].message.content or ""
        return _OAICreateResponse(text, resp.usage)


# ── Factory ────────────────────────────────────────────────────────────────────

def make_provider(model: str) -> "AnthropicProvider | OpenAIProvider":
    """Return the appropriate provider for the given model name."""
    if get_provider_name(model) == "openai":
        return OpenAIProvider(get_openai_client())
    import anthropic as _anthropic
    from backend.db import get_agent_config as _gac
    _key = _gac().get("anthropic_api_key") or None  # None → SDK reads env var
    return AnthropicProvider(_anthropic.AsyncAnthropic(api_key=_key))
