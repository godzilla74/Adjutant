# backend/provider.py
"""Provider abstraction — wraps Anthropic, OpenAI Platform, and ChatGPT OAuth behind a uniform interface."""
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


def _translate_messages_to_responses_api(messages: list, system: str | list) -> tuple[str, list]:
    """Convert Anthropic-format messages to ChatGPT Responses API input format.

    Returns (system_text, input_items). Tool calls and tool results become
    top-level items in the input array rather than nested in message content.
    """
    system_text = _extract_system_text(system)
    input_items: list = []

    for msg in messages:
        role = msg["role"]
        content = msg["content"]

        if role == "user":
            if isinstance(content, str):
                input_items.append({"role": "user", "content": content})
            elif isinstance(content, list):
                text_parts = []
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    btype = block.get("type")
                    if btype == "text":
                        text_parts.append(block["text"])
                    elif btype == "tool_result":
                        if text_parts:
                            input_items.append({"role": "user", "content": " ".join(text_parts)})
                            text_parts = []
                        output = block.get("content", "")
                        if isinstance(output, list):
                            output = " ".join(
                                b.get("text", "") for b in output if isinstance(b, dict)
                            )
                        input_items.append({
                            "type": "function_call_output",
                            "call_id": block["tool_use_id"],
                            "output": str(output),
                        })
                if text_parts:
                    input_items.append({"role": "user", "content": " ".join(text_parts)})

        elif role == "assistant":
            if isinstance(content, str):
                input_items.append({"role": "assistant", "content": content})
            elif isinstance(content, list):
                text_blocks = []
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    btype = block.get("type")
                    if btype == "text" and block["text"]:
                        text_blocks.append({"type": "output_text", "text": block["text"]})
                    elif btype == "tool_use":
                        input_items.append({
                            "type": "function_call",
                            "call_id": block["id"],
                            "name": block["name"],
                            "arguments": json.dumps(block["input"]),
                        })
                if text_blocks:
                    input_items.append({"role": "assistant", "content": text_blocks})

    return system_text, input_items


def _translate_tools_to_responses_api(tools: list) -> list:
    """Convert Anthropic tool defs to Responses API function format."""
    return [
        {
            "type": "function",
            "name": t["name"],
            "description": t.get("description", ""),
            "parameters": t["input_schema"],
        }
        for t in tools
    ]


# ── Normalized response types ──────────────────────────────────────────────────

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


class _SimpleUsage:
    __slots__ = ("input_tokens", "output_tokens")

    def __init__(self, input_tokens: int, output_tokens: int) -> None:
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


# ── Provider selection helpers ─────────────────────────────────────────────────

def get_provider_name(model: str) -> str:
    if model.startswith(("gpt-", "o1", "o3", "o4")):
        return "openai"
    return "anthropic"


def _is_chatgpt_jwt(token: str) -> bool:
    """Return True if token is a ChatGPT OAuth JWT rather than an sk-... Platform key."""
    parts = token.split(".")
    return len(parts) == 3 and token.startswith("eyJ")


def _extract_account_id(token: str) -> str:
    """Extract chatgpt_account_id from the JWT payload without signature validation."""
    try:
        import base64
        payload_b64 = token.split(".")[1]
        payload_b64 += "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        return payload.get("https://api.openai.com/auth", {}).get("chatgpt_account_id", "")
    except Exception:
        return ""


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
    """Provider for OpenAI Platform API (api.openai.com) — requires Platform API credits."""
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


_CODEX_MODELS = ["codex-mini-latest", "o4-mini", "o3-mini", "o3"]

# Models the chatgpt.com Codex endpoint does not support — map to the default.
_CODEX_MODEL_REMAP = {
    "gpt-4o":      "codex-mini-latest",
    "gpt-4o-mini": "codex-mini-latest",
    "gpt-4":       "codex-mini-latest",
    "gpt-4-turbo": "codex-mini-latest",
}


class ChatGPTProvider:
    """Provider for ChatGPT Plus/Pro OAuth users.

    Calls https://chatgpt.com/backend-api/codex/responses — the same endpoint
    the Codex CLI uses — so no OpenAI Platform API credits are required.
    Auth uses the JWT access token from the OAuth flow with the chatgpt-account-id
    extracted from the token's claims.
    """
    name = "openai"
    _BASE_URL = "https://chatgpt.com/backend-api/codex/responses"

    def __init__(self, access_token: str, account_id: str) -> None:
        self._token = access_token
        self._account_id = account_id

    def _resolve_model(self, model: str) -> str:
        remapped = _CODEX_MODEL_REMAP.get(model)
        if remapped:
            logger.info("ChatGPTProvider: %s is not supported by Codex backend, using %s", model, remapped)
            return remapped
        return model

    def _headers(self, stream: bool = False) -> dict:
        h = {
            "Authorization": f"Bearer {self._token}",
            "content-type": "application/json",
            "originator": "codex_cli_rs",
        }
        if self._account_id:
            h["chatgpt-account-id"] = self._account_id
        if stream:
            h["accept"] = "text/event-stream"
            h["OpenAI-Beta"] = "responses=experimental"
        return h

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
        import httpx

        if extra_headers or extra_body:
            logger.warning("ChatGPTProvider: remote MCP (extra_headers/extra_body) is not supported; skipping")

        system_text, input_items = _translate_messages_to_responses_api(messages, system)
        body: dict = {
            "model": self._resolve_model(model),
            "store": False,
            "stream": True,
            "instructions": system_text,
            "input": input_items,
            "text": {"verbosity": "low"},
        }
        if tools:
            body["tools"] = _translate_tools_to_responses_api(tools)
            body["tool_choice"] = "auto"
            body["parallel_tool_calls"] = True

        logger.debug("[ChatGPTProvider] stream_agent body: %s", json.dumps(body)[:1000])
        accumulated_text = ""
        function_calls: dict[str, dict] = {}  # call_id → {id, name, arguments}
        finish_reason = "stop"
        final_usage = None

        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST",
                self._BASE_URL,
                json=body,
                headers=self._headers(stream=True),
            ) as response:
                if response.status_code >= 400:
                    body_text = await response.aread()
                    raise RuntimeError(f"ChatGPT API {response.status_code}: {body_text.decode()[:500]}")
                async for raw_line in response.aiter_lines():
                    if not raw_line or raw_line.startswith(":"):
                        continue
                    if raw_line.startswith("data: "):
                        data_str = raw_line[6:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            event = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue

                        etype = event.get("type", "")

                        if etype == "response.output_text.delta":
                            delta = event.get("delta", "")
                            if delta:
                                await on_text(delta)
                                accumulated_text += delta

                        elif etype == "response.output_item.added":
                            item = event.get("item", {})
                            if item.get("type") == "function_call":
                                call_id = item.get("id") or item.get("call_id", "")
                                function_calls[call_id] = {
                                    "id": call_id,
                                    "name": item.get("name", ""),
                                    "arguments": "",
                                }

                        elif etype == "response.function_call_arguments.delta":
                            item_id = event.get("item_id", "")
                            if item_id in function_calls:
                                function_calls[item_id]["arguments"] += event.get("delta", "")

                        elif etype == "response.output_item.done":
                            item = event.get("item", {})
                            if item.get("type") == "function_call":
                                call_id = item.get("id") or item.get("call_id", "")
                                if call_id in function_calls:
                                    function_calls[call_id]["arguments"] = item.get(
                                        "arguments",
                                        function_calls[call_id]["arguments"],
                                    )

                        elif etype == "response.completed":
                            resp = event.get("response", {})
                            usage_raw = resp.get("usage", {})
                            final_usage = _SimpleUsage(
                                usage_raw.get("input_tokens", 0),
                                usage_raw.get("output_tokens", 0),
                            )
                            if function_calls:
                                finish_reason = "tool_calls"

        tool_call_list = [
            {
                "id": fc["id"],
                "type": "function",
                "function": {"name": fc["name"], "arguments": fc["arguments"]},
            }
            for fc in function_calls.values()
        ]
        return _OAIMessage(accumulated_text, tool_call_list, final_usage, finish_reason)

    async def create(
        self,
        model: str,
        system: str,
        messages: list,
        max_tokens: int,
    ) -> object:
        import httpx

        system_text, input_items = _translate_messages_to_responses_api(messages, system)
        body = {
            "model": self._resolve_model(model),
            "store": False,
            "stream": False,
            "instructions": system_text,
            "input": input_items,
        }

        logger.debug("[ChatGPTProvider] create body: %s", json.dumps(body)[:1000])
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                self._BASE_URL,
                json=body,
                headers=self._headers(stream=False),
            )
            if response.status_code >= 400:
                raise RuntimeError(f"ChatGPT API {response.status_code}: {response.text[:500]}")
            data = response.json()

        text = ""
        for item in data.get("output", []):
            if item.get("type") == "message":
                for part in item.get("content", []):
                    if part.get("type") == "output_text":
                        text += part.get("text", "")

        usage_raw = data.get("usage", {})
        return _OAICreateResponse(
            text,
            _SimpleUsage(usage_raw.get("input_tokens", 0), usage_raw.get("output_tokens", 0)),
        )


# ── Factory ────────────────────────────────────────────────────────────────────

def get_openai_client():
    """Return an AsyncOpenAI client for Platform API users (sk-... key required).
    Only used when openai_access_token is a real Platform API key, not a ChatGPT JWT."""
    from backend.db import get_agent_config
    from openai import AsyncOpenAI
    cfg = get_agent_config()
    key = cfg.get("openai_access_token", "") or cfg.get("openai_api_key", "")
    if not key:
        raise RuntimeError("OpenAI not connected. Connect via Settings → Agent Model.")
    return AsyncOpenAI(api_key=key)


def make_provider(model: str) -> "AnthropicProvider | OpenAIProvider | ChatGPTProvider":
    """Return the appropriate provider for the given model name.

    OpenAI routing:
      - JWT access_token (ChatGPT Plus OAuth) → ChatGPTProvider (chatgpt.com backend, no Platform credits needed)
      - sk-... access_token (Platform OAuth exchange succeeded) → OpenAIProvider
      - sk-... api_key only (no OAuth) → OpenAIProvider
    """
    if get_provider_name(model) == "openai":
        from backend.db import get_agent_config as _gac
        cfg = _gac()
        access_token = cfg.get("openai_access_token", "")
        api_key = cfg.get("openai_api_key", "")

        if access_token and _is_chatgpt_jwt(access_token):
            account_id = cfg.get("openai_account_id", "") or _extract_account_id(access_token)
            return ChatGPTProvider(access_token, account_id)

        # access_token is a real sk-... key (Platform OAuth exchange succeeded)
        if access_token:
            from openai import AsyncOpenAI
            return OpenAIProvider(AsyncOpenAI(api_key=access_token))

        # Direct Platform API key, no OAuth
        if api_key:
            from openai import AsyncOpenAI
            return OpenAIProvider(AsyncOpenAI(api_key=api_key))

        raise RuntimeError("OpenAI not connected. Connect via Settings → Agent Model.")

    import anthropic as _anthropic
    from backend.db import get_agent_config as _gac
    _key = _gac().get("anthropic_api_key") or None  # None → SDK reads env var
    return AnthropicProvider(_anthropic.AsyncAnthropic(api_key=_key))
