# OpenAI Model Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make OpenAI models (GPT-4o, GPT-4o-mini, o3-mini) selectable alongside Anthropic in Adjutant, with per-product model overrides and a provider abstraction layer that handles all format translation.

**Architecture:** New `backend/provider.py` defines `AnthropicProvider` and `OpenAIProvider` behind a shared interface. Provider is selected at runtime by model name. DB gains three nullable model columns on `products` for per-product overrides. Agent loop, compaction, and prescreener all route through the provider. Messages stay in Anthropic format in DB; OpenAI translation happens at call time.

**Tech Stack:** Python (FastAPI, SQLite, anthropic SDK, openai SDK v2), React/TypeScript (Vite, Tailwind)

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `backend/provider.py` | Create | `Provider` protocol, `AnthropicProvider`, `OpenAIProvider`, `make_provider`, `get_openai_client` |
| `backend/db.py` | Modify | Add 3 nullable model columns to `products`; add `get_product_model_config`, `set_product_model_config` |
| `backend/main.py` | Modify | Resolve per-product model config; use provider at all 3 call sites |
| `core/prescreener.py` | Modify | Change `client` param to `Provider`; call `provider.create()` |
| `backend/api.py` | Modify | Extend `GET`/`PUT /api/agent-config` with optional `product_id` |
| `requirements.txt` | Modify | Add `openai>=1.0.0` |
| `ui/src/api.ts` | Modify | Update `getAgentConfig`/`updateAgentConfig` to accept optional `productId`/`product_id` |
| `ui/src/components/settings/AgentModelSettings.tsx` | Modify | Add OpenAI `<optgroup>` to all three model dropdowns |
| `ui/src/components/settings/ProductModelSettings.tsx` | Create | Per-product model override UI |
| `ui/src/components/SettingsPage.tsx` | Modify | Add `'product-model'` tab |
| `tests/test_provider.py` | Create | Format translation unit tests for `OpenAIProvider` |
| `tests/test_product_model_config.py` | Create | Per-product config resolution tests |
| `tests/test_prescreener.py` | Modify | Update mocks from `client` to `Provider` |

---

### Task 1: Provider abstraction layer

**Files:**
- Create: `backend/provider.py`
- Create: `tests/test_provider.py`
- Modify: `requirements.txt`

- [ ] **Step 1: Add openai to requirements.txt**

Open `requirements.txt` and add after the `anthropic` line:

```
openai>=1.0.0
```

- [ ] **Step 2: Write failing tests**

Create `tests/test_provider.py`:

```python
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
```

- [ ] **Step 3: Run to verify they fail**

```bash
cd /home/justin/Code/Adjutant
.venv/bin/python -m pytest tests/test_provider.py -v 2>&1 | tail -15
```

Expected: all FAIL with `ImportError` — `backend.provider` does not exist yet.

- [ ] **Step 4: Create `backend/provider.py`**

```python
# backend/provider.py
"""Provider abstraction — wraps Anthropic and OpenAI behind a uniform interface."""
from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Callable, Protocol, runtime_checkable

if TYPE_CHECKING:
    pass

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
    if model.startswith(("gpt-", "o1", "o3")):
        return "openai"
    return "anthropic"


def get_openai_client():
    """Return an AsyncOpenAI client using the stored OAuth token. Raises RuntimeError if absent."""
    from backend.db import get_agent_config
    from openai import AsyncOpenAI
    token = get_agent_config().get("openai_access_token", "")
    if not token:
        raise RuntimeError("OpenAI access token not configured. Connect via Settings → Image Generation.")
    return AsyncOpenAI(api_key=token)


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
    return AnthropicProvider(_anthropic.AsyncAnthropic())
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
.venv/bin/python -m pytest tests/test_provider.py -v
```

Expected: all tests PASS.

- [ ] **Step 6: Run full suite for regressions**

```bash
.venv/bin/python -m pytest tests/ -q 2>&1 | tail -5
```

Expected: 4 pre-existing failures in `test_openai_oauth.py`, everything else passes.

- [ ] **Step 7: Commit**

```bash
git add backend/provider.py tests/test_provider.py requirements.txt
git commit -m "feat: add provider abstraction layer for Anthropic and OpenAI"
```

---

### Task 2: DB — per-product model columns and helpers

**Files:**
- Modify: `backend/db.py` (after the `set_agent_config` function, around line 1470)
- Create: `tests/test_product_model_config.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_product_model_config.py`:

```python
"""Tests for per-product model config resolution."""
import importlib
import pytest


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_DB", str(tmp_path / "test.db"))
    import backend.db as db_mod
    importlib.reload(db_mod)
    db_mod.init_db()
    return db_mod


def _seed_product(db, product_id="prod-1"):
    db.create_product(product_id, "Test Product", "T", "#fff")
    return product_id


def test_get_product_model_config_falls_back_to_global(db):
    pid = _seed_product(db)
    cfg = db.get_product_model_config(pid)
    assert cfg["agent_model"] == "claude-sonnet-4-6"
    assert cfg["subagent_model"] == "claude-sonnet-4-6"
    assert cfg["prescreener_model"] == "claude-haiku-4-5-20251001"


def test_get_product_model_config_none_product(db):
    cfg = db.get_product_model_config(None)
    assert cfg["agent_model"] == "claude-sonnet-4-6"


def test_set_product_model_config_overrides_global(db):
    pid = _seed_product(db)
    db.set_product_model_config(pid, agent_model="gpt-4o")
    cfg = db.get_product_model_config(pid)
    assert cfg["agent_model"] == "gpt-4o"
    # Other fields still fall back to global
    assert cfg["subagent_model"] == "claude-sonnet-4-6"


def test_set_product_model_config_clear_with_none(db):
    pid = _seed_product(db)
    db.set_product_model_config(pid, agent_model="gpt-4o")
    db.set_product_model_config(pid, agent_model=None)
    cfg = db.get_product_model_config(pid)
    assert cfg["agent_model"] == "claude-sonnet-4-6"  # back to global


def test_set_product_model_config_all_three(db):
    pid = _seed_product(db)
    db.set_product_model_config(
        pid,
        agent_model="gpt-4o",
        subagent_model="gpt-4o",
        prescreener_model="gpt-4o-mini",
    )
    cfg = db.get_product_model_config(pid)
    assert cfg["agent_model"] == "gpt-4o"
    assert cfg["subagent_model"] == "gpt-4o"
    assert cfg["prescreener_model"] == "gpt-4o-mini"
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd /home/justin/Code/Adjutant
.venv/bin/python -m pytest tests/test_product_model_config.py -v 2>&1 | tail -10
```

Expected: FAIL — `AttributeError: module 'backend.db' has no attribute 'get_product_model_config'`.

- [ ] **Step 3: Add nullable columns to `products` in `init_db()`**

In `backend/db.py`, find the section that adds idempotent ALTER TABLE columns (around line 226, after the `executescript` block). There's already a pattern for adding columns with try/except. Add the three model columns in the same style, after the existing `try: conn.execute("ALTER TABLE products ADD COLUMN launch_wizard_active ...")` block:

```python
        # Add per-product model override columns (idempotent)
        for col_name in ("agent_model", "subagent_model", "prescreener_model"):
            try:
                conn.execute(f"ALTER TABLE products ADD COLUMN {col_name} TEXT")
            except Exception:
                pass  # column already exists
```

- [ ] **Step 4: Add `get_product_model_config` and `set_product_model_config` to `backend/db.py`**

Add these two functions after `set_agent_config` (around line 1470):

```python
def get_product_model_config(product_id: str | None) -> dict:
    """Return resolved {agent_model, subagent_model, prescreener_model} for a product.
    Per-product values override global model_config defaults."""
    global_cfg = get_agent_config()
    defaults = {
        "agent_model":       global_cfg["agent_model"],
        "subagent_model":    global_cfg["subagent_model"],
        "prescreener_model": global_cfg["prescreener_model"],
    }
    if not product_id:
        return defaults
    with _conn() as conn:
        row = conn.execute(
            "SELECT agent_model, subagent_model, prescreener_model FROM products WHERE id = ?",
            (product_id,),
        ).fetchone()
    if not row:
        return defaults
    return {
        "agent_model":       row["agent_model"]       or defaults["agent_model"],
        "subagent_model":    row["subagent_model"]    or defaults["subagent_model"],
        "prescreener_model": row["prescreener_model"] or defaults["prescreener_model"],
    }


def set_product_model_config(
    product_id: str,
    agent_model: str | None = ...,
    subagent_model: str | None = ...,
    prescreener_model: str | None = ...,
) -> None:
    """Write per-product model overrides. Pass None to clear (revert to global default).
    Omit a parameter entirely to leave it unchanged (uses sentinel ... default)."""
    updates: dict[str, str | None] = {}
    if agent_model is not ...:
        updates["agent_model"] = agent_model or None
    if subagent_model is not ...:
        updates["subagent_model"] = subagent_model or None
    if prescreener_model is not ...:
        updates["prescreener_model"] = prescreener_model or None
    if not updates:
        return
    sets = ", ".join(f"{k} = ?" for k in updates)
    with _conn() as conn:
        conn.execute(
            f"UPDATE products SET {sets} WHERE id = ?",
            (*updates.values(), product_id),
        )
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
.venv/bin/python -m pytest tests/test_product_model_config.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 6: Run full suite for regressions**

```bash
.venv/bin/python -m pytest tests/ -q 2>&1 | tail -5
```

Expected: 4 pre-existing failures in `test_openai_oauth.py`, everything else passes.

- [ ] **Step 7: Commit**

```bash
git add backend/db.py tests/test_product_model_config.py
git commit -m "feat: add per-product model config columns and helpers"
```

---

### Task 3: Agent loop wiring

**Files:**
- Modify: `core/prescreener.py`
- Modify: `backend/main.py`
- Modify: `tests/test_prescreener.py`

- [ ] **Step 1: Update `core/prescreener.py` — change `client` to `provider`**

Replace the entire file content with:

```python
"""Haiku pre-screener: classify user messages and select tool groups before Sonnet."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from backend.provider import AnthropicProvider, OpenAIProvider

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are a routing agent for an AI executive assistant. Given a user message, decide how to handle it.

Return JSON only — no prose, no markdown. One of two shapes:

If you can answer directly without any tools or data access:
{"route": "haiku", "response": "your full answer here"}

If the main agent is needed:
{"route": "sonnet", "tool_groups": ["core", "email"]}

Route to haiku ONLY for: greetings, simple factual questions answerable without data access, \
conversational acknowledgments, or short replies requiring no tools.

Route to sonnet for: anything requiring tool use, task execution, accessing email/calendar/notes, \
managing objectives or workstreams, complex reasoning, or anything you are uncertain about.

Always include "core" in tool_groups. Only include groups from the available list provided.\
"""


@dataclass
class PrescreerResult:
    """Routing decision from the prescreener: respond directly or delegate to Sonnet."""
    route: Literal["haiku", "sonnet"]
    tool_groups: list[str] = field(default_factory=list)
    response: str | None = None
    usage: object | None = None


def _fallback(available_groups: list[str]) -> PrescreerResult:
    return PrescreerResult(route="sonnet", tool_groups=list({"core"} | set(available_groups)))


async def prescreen(
    message: str,
    available_groups: list[str],
    provider: "AnthropicProvider | OpenAIProvider",
    model: str,
) -> PrescreerResult:
    """Classify a user message and return routing + tool group selection.

    Falls back to route=sonnet with all available_groups on any error.
    """
    system = _SYSTEM_PROMPT + f"\n\nAvailable tool groups: {available_groups}"
    try:
        resp = await provider.create(
            model=model,
            system=system,
            messages=[{"role": "user", "content": message}],
            max_tokens=512,
        )
        data = json.loads(resp.content[0].text.strip())
        route = data.get("route")

        if route == "haiku":
            response = data.get("response", "")
            if not isinstance(response, str):
                return _fallback(available_groups)
            return PrescreerResult(route="haiku", response=response, usage=resp.usage)

        if route == "sonnet":
            groups = data.get("tool_groups", [])
            if not isinstance(groups, list):
                return _fallback(available_groups)
            valid = set(available_groups)
            merged = list({"core"} | (set(groups) & valid))
            return PrescreerResult(route="sonnet", tool_groups=merged, usage=resp.usage)

        return _fallback(available_groups)

    except Exception:
        logger.debug("Prescreener fallback triggered", exc_info=True)
        return _fallback(available_groups)
```

- [ ] **Step 2: Update `tests/test_prescreener.py` — switch mocks from `client` to `Provider`**

The existing tests mock `client.messages.create`. They must now mock a `Provider` object. Replace the test file content with:

```python
"""Tests for the Haiku pre-screener."""
import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock


def _make_response(text: str):
    """Build a mock that looks like a Provider.create() response."""
    from backend.provider import _OAITextBlock
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
```

- [ ] **Step 3: Verify prescreener tests still pass**

```bash
cd /home/justin/Code/Adjutant
.venv/bin/python -m pytest tests/test_prescreener.py -v
```

Expected: all tests PASS.

- [ ] **Step 4: Wire provider into `backend/main.py`**

**4a. Add imports** — in `backend/main.py`, find the `from backend.db import (...)` block and add `get_product_model_config` to it:

```python
from backend.db import (
    ...
    record_token_usage as _record_token_usage,
    get_product_model_config as _get_product_model_config,
)
```

**4b. Replace the model config read in `_agent_loop`** — find this block (around line 808):

```python
    # Read model config fresh so Settings changes take effect without restart
    _live_cfg = _get_agent_config()
    _agent_model = os.environ.get("AGENT_MODEL", _live_cfg["agent_model"])
    _runner.SUBAGENT_MODEL = os.environ.get("AGENT_SUBAGENT_MODEL", _live_cfg["subagent_model"])
```

Replace it with:

```python
    # Read model config fresh so Settings changes take effect without restart
    from backend.provider import make_provider as _make_provider
    _model_cfg = _get_product_model_config(product_id)
    _agent_model = os.environ.get("AGENT_MODEL", _model_cfg["agent_model"])
    _runner.SUBAGENT_MODEL = os.environ.get("AGENT_SUBAGENT_MODEL", _model_cfg["subagent_model"])
    _prescreener_model = os.environ.get("AGENT_PRESCREENER_MODEL", _model_cfg["prescreener_model"])
    _provider = _make_provider(_agent_model)
    _pre_provider = _make_provider(_prescreener_model)
```

**4c. Update the prescreener call** — find this block (around line 826):

```python
            _prescreener_model = os.environ.get(
                "AGENT_PRESCREENER_MODEL",
                _live_cfg.get("prescreener_model", "claude-haiku-4-5-20251001")
            )
            _pre = await _prescreen(_last_user_msg_for_prescreener, _available_groups, client, _prescreener_model)
            _record_token_usage(product_id, "prescreener", "anthropic", _prescreener_model, _pre.usage)
```

Replace it with:

```python
            _pre = await _prescreen(_last_user_msg_for_prescreener, _available_groups, _pre_provider, _prescreener_model)
            _record_token_usage(product_id, "prescreener", _pre_provider.name, _prescreener_model, _pre.usage)
```

**4d. Replace `_run_stream`** — find the inner `_run_stream` function (around line 871):

```python
        async def _run_stream(kwargs: dict) -> object:
            nonlocal accumulated_text
            async with client.messages.stream(**kwargs) as stream:
                async for event in stream:
                    if (
                        event.type == "content_block_delta"
                        and event.delta.type == "text_delta"
                    ):
                        await send_fn({"type": "agent_token", "product_id": product_id, "content": event.delta.text})
                        accumulated_text += event.delta.text
                return await stream.get_final_message()
```

Replace it with:

```python
        async def _run_stream(kwargs: dict) -> object:
            nonlocal accumulated_text

            async def _on_text(text: str) -> None:
                nonlocal accumulated_text
                await send_fn({"type": "agent_token", "product_id": product_id, "content": text})
                accumulated_text += text

            return await _provider.stream_agent(
                model=kwargs["model"],
                system=kwargs["system"],
                messages=kwargs["messages"],
                tools=kwargs.get("tools", []),
                max_tokens=kwargs["max_tokens"],
                on_text=_on_text,
                extra_headers=kwargs.get("extra_headers"),
                extra_body=kwargs.get("extra_body"),
            )
```

**4e. Update the two `_record_token_usage` calls after `_run_stream`** — find (around line 885):

```python
            _record_token_usage(product_id, "agent", "anthropic", _agent_model, final.usage)
```

Replace both occurrences with:

```python
            _record_token_usage(product_id, "agent", _provider.name, _agent_model, final.usage)
```

**4f. Update `_maybe_compact`** — find this block (around line 728):

```python
    resp = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": (
                ...
            ),
        }],
    )
    _record_token_usage(product_id, "compaction", "anthropic", "claude-haiku-4-5-20251001", resp.usage)
```

Replace it with:

```python
    from backend.provider import make_provider as _make_provider_compact
    from backend.db import get_product_model_config as _get_pmc
    _compact_cfg = _get_pmc(product_id)
    _compact_model = _compact_cfg["prescreener_model"]
    _compact_provider = _make_provider_compact(_compact_model)
    resp = await _compact_provider.create(
        model=_compact_model,
        system="",
        messages=[{
            "role": "user",
            "content": (
                f"You are summarizing a conversation between a user and {_agent_name}, an AI executive assistant. "
                "Produce a compact context block covering: decisions made, tasks assigned or completed, "
                "key facts shared about products/workstreams/goals, ongoing work, and any user preferences. "
                "Be concise but comprehensive — this summary replaces the full history.\n\n"
                f"{context_block}{transcript}"
            ),
        }],
        max_tokens=1024,
    )
    _record_token_usage(product_id, "compaction", _compact_provider.name, _compact_model, resp.usage)
```

- [ ] **Step 5: Run full suite for regressions**

```bash
.venv/bin/python -m pytest tests/ -q 2>&1 | tail -5
```

Expected: 4 pre-existing failures in `test_openai_oauth.py`, everything else passes.

- [ ] **Step 6: Commit**

```bash
git add core/prescreener.py backend/main.py tests/test_prescreener.py
git commit -m "feat: wire provider abstraction into agent loop, compaction, and prescreener"
```

---

### Task 4: API changes

**Files:**
- Modify: `backend/api.py`
- Modify: `tests/test_token_usage.py` (add one API test for product_id param)

- [ ] **Step 1: Write a failing test**

Add to the end of `tests/test_token_usage.py`:

```python
def test_agent_config_per_product(api_client, tmp_path, monkeypatch):
    """GET /api/agent-config?product_id= returns per-product resolved config."""
    # Create a product first
    resp = api_client.post(
        "/api/products",
        json={"id": "test-p1", "name": "Test", "icon_label": "T", "color": "#fff"},
        headers={"X-Agent-Password": "testpw"},
    )
    # GET per-product config — should return global defaults
    resp = api_client.get(
        "/api/agent-config?product_id=test-p1",
        headers={"X-Agent-Password": "testpw"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "agent_model" in body
    assert "subagent_model" in body
    assert "prescreener_model" in body

    # PUT per-product override
    resp = api_client.put(
        "/api/agent-config",
        json={"product_id": "test-p1", "agent_model": "gpt-4o"},
        headers={"X-Agent-Password": "testpw"},
    )
    assert resp.status_code == 200
    assert resp.json()["agent_model"] == "gpt-4o"

    # GET again — should reflect the override
    resp = api_client.get(
        "/api/agent-config?product_id=test-p1",
        headers={"X-Agent-Password": "testpw"},
    )
    assert resp.json()["agent_model"] == "gpt-4o"
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd /home/justin/Code/Adjutant
.venv/bin/python -m pytest tests/test_token_usage.py::test_agent_config_per_product -v
```

Expected: FAIL — the current endpoint ignores `product_id`.

- [ ] **Step 3: Update `backend/api.py`**

Find the `AgentConfigUpdate` model and `get_agent_config_api`/`update_agent_config_api` functions. Replace them with:

```python
class AgentConfigUpdate(BaseModel):
    agent_model:       str | None = None
    subagent_model:    str | None = None
    prescreener_model: str | None = None
    agent_name:        str | None = None
    product_id:        str | None = None  # when set, writes per-product override


@router.get("/agent-config")
def get_agent_config_api(product_id: str | None = None, _=Depends(_auth)):
    from backend.db import get_agent_config, get_product_model_config
    if product_id:
        global_cfg = get_agent_config()
        model_cfg = get_product_model_config(product_id)
        return {**global_cfg, **model_cfg}
    return get_agent_config()


@router.put("/agent-config")
def update_agent_config_api(body: AgentConfigUpdate, _=Depends(_auth)):
    from backend.db import set_agent_config, get_agent_config, get_product_model_config, set_product_model_config
    import agents.runner as runner
    import backend.main as main_module

    if body.product_id:
        set_product_model_config(
            body.product_id,
            **({} if body.agent_model is None else {"agent_model": body.agent_model}),
            **({} if body.subagent_model is None else {"subagent_model": body.subagent_model}),
            **({} if body.prescreener_model is None else {"prescreener_model": body.prescreener_model}),
        )
        return get_product_model_config(body.product_id)

    if body.agent_model is not None:
        set_agent_config("agent_model", body.agent_model)
        main_module.AGENT_MODEL = body.agent_model

    if body.subagent_model is not None:
        set_agent_config("subagent_model", body.subagent_model)
        runner.SUBAGENT_MODEL = body.subagent_model

    if body.prescreener_model is not None:
        set_agent_config("prescreener_model", body.prescreener_model)

    if body.agent_name is not None:
        set_agent_config("agent_name", body.agent_name)

    return get_agent_config()
```

- [ ] **Step 4: Run all token usage tests**

```bash
.venv/bin/python -m pytest tests/test_token_usage.py -v
```

Expected: all 10 tests PASS.

- [ ] **Step 5: Run full suite for regressions**

```bash
.venv/bin/python -m pytest tests/ -q 2>&1 | tail -5
```

Expected: 4 pre-existing failures in `test_openai_oauth.py`, everything else passes.

- [ ] **Step 6: Commit**

```bash
git add backend/api.py tests/test_token_usage.py
git commit -m "feat: extend agent-config API with per-product model override support"
```

---

### Task 5: Settings UI

**Files:**
- Modify: `ui/src/api.ts`
- Modify: `ui/src/components/settings/AgentModelSettings.tsx`
- Create: `ui/src/components/settings/ProductModelSettings.tsx`
- Modify: `ui/src/components/SettingsPage.tsx`

- [ ] **Step 1: Update `ui/src/api.ts`**

Find the `getAgentConfig` and `updateAgentConfig` entries (around line 104) and replace them with:

```typescript
  getAgentConfig: (pw: string, productId?: string) =>
    apiFetch<{
      agent_model: string
      subagent_model: string
      prescreener_model: string
      agent_name: string
      openai_access_token?: string
    }>(`/api/agent-config${productId ? `?product_id=${encodeURIComponent(productId)}` : ''}`, pw),

  updateAgentConfig: (pw: string, data: {
    agent_model?: string
    subagent_model?: string
    prescreener_model?: string
    agent_name?: string
    product_id?: string
  }) =>
    apiFetch<{
      agent_model: string
      subagent_model: string
      prescreener_model: string
      agent_name: string
    }>('/api/agent-config', pw, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
```

- [ ] **Step 2: Update `AgentModelSettings.tsx` — add OpenAI option groups**

Replace the entire file with:

```tsx
import { useEffect, useState } from 'react'
import { api } from '../../api'

interface Props {
  password: string
}

const ANTHROPIC_OPTIONS = [
  { value: 'claude-opus-4-7',           label: 'Opus 4.7 (best)' },
  { value: 'claude-sonnet-4-6',         label: 'Sonnet 4.6 (fast)' },
  { value: 'claude-haiku-4-5-20251001', label: 'Haiku 4.5 (cheap)' },
]

const OPENAI_OPTIONS = [
  { value: 'gpt-4o',      label: 'GPT-4o' },
  { value: 'gpt-4o-mini', label: 'GPT-4o mini' },
  { value: 'o3-mini',     label: 'o3-mini' },
]

export default function AgentModelSettings({ password }: Props) {
  const [agentModel, setAgentModel] = useState('claude-sonnet-4-6')
  const [subagentModel, setSubagentModel] = useState('claude-sonnet-4-6')
  const [prescreenerModel, setPrescreenerModel] = useState('claude-haiku-4-5-20251001')
  const [agentName, setAgentName] = useState('Adjutant')
  const [hasOpenAI, setHasOpenAI] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    api.getAgentConfig(password)
      .then(cfg => {
        setAgentModel(cfg.agent_model)
        setSubagentModel(cfg.subagent_model)
        setPrescreenerModel(cfg.prescreener_model)
        setAgentName(cfg.agent_name)
        setHasOpenAI(Boolean(cfg.openai_access_token))
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [password])

  async function save() {
    setSaving(true)
    try {
      await api.updateAgentConfig(password, {
        agent_model: agentModel,
        subagent_model: subagentModel,
        prescreener_model: prescreenerModel,
        agent_name: agentName,
      })
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } finally {
      setSaving(false)
    }
  }

  const inputCls = 'w-full bg-adj-panel border border-adj-border rounded-md px-3 py-2 text-sm text-adj-text-primary focus:outline-none focus:border-adj-accent transition-colors'

  if (loading) return <p className="text-adj-text-muted text-sm">Loading…</p>

  const ModelSelect = ({ value, onChange }: { value: string; onChange: (v: string) => void }) => (
    <select value={value} onChange={e => onChange(e.target.value)} className={inputCls}>
      <optgroup label="Anthropic">
        {ANTHROPIC_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
      </optgroup>
      {hasOpenAI && (
        <optgroup label="OpenAI">
          {OPENAI_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
        </optgroup>
      )}
    </select>
  )

  return (
    <div className="w-full">
      <h2 className="text-base font-bold text-adj-text-primary mb-1">Agent Model</h2>
      <p className="text-xs text-adj-text-muted mb-6">Configure model selection and assistant name</p>

      <div className="flex flex-col gap-4">
        <div>
          <label className="block text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-1.5">
            Assistant Name
          </label>
          <input
            type="text"
            value={agentName}
            onChange={e => setAgentName(e.target.value)}
            placeholder="Adjutant"
            className={inputCls}
          />
        </div>

        <div>
          <label className="block text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-1.5">
            Main Agent Model
          </label>
          <ModelSelect value={agentModel} onChange={setAgentModel} />
        </div>

        <div>
          <label className="block text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-1.5">
            Sub-agents (research, email, etc.)
          </label>
          <ModelSelect value={subagentModel} onChange={setSubagentModel} />
        </div>

        <div>
          <label className="block text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-1.5">
            Pre-screener (message routing)
          </label>
          <ModelSelect value={prescreenerModel} onChange={setPrescreenerModel} />
        </div>
      </div>

      <div className="mt-6">
        <button
          onClick={save}
          disabled={saving}
          className="px-5 py-2 bg-adj-accent text-white rounded-md text-sm font-semibold hover:bg-adj-accent-dark transition-colors disabled:opacity-50"
        >
          {saved ? '✓ Saved' : saving ? 'Saving…' : 'Save Changes'}
        </button>
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Create `ui/src/components/settings/ProductModelSettings.tsx`**

```tsx
import { useEffect, useRef, useState } from 'react'
import { api } from '../../api'

interface Props {
  password: string
  productId: string
}

const ANTHROPIC_OPTIONS = [
  { value: 'claude-opus-4-7',           label: 'Opus 4.7 (best)' },
  { value: 'claude-sonnet-4-6',         label: 'Sonnet 4.6 (fast)' },
  { value: 'claude-haiku-4-5-20251001', label: 'Haiku 4.5 (cheap)' },
]

const OPENAI_OPTIONS = [
  { value: 'gpt-4o',      label: 'GPT-4o' },
  { value: 'gpt-4o-mini', label: 'GPT-4o mini' },
  { value: 'o3-mini',     label: 'o3-mini' },
]

const ALL_OPTIONS = [...ANTHROPIC_OPTIONS, ...OPENAI_OPTIONS]

export default function ProductModelSettings({ password, productId }: Props) {
  const [agentModel, setAgentModel] = useState('')
  const [subagentModel, setSubagentModel] = useState('')
  const [prescreenerModel, setPrescreenerModel] = useState('')
  const [globalDefaults, setGlobalDefaults] = useState({ agent_model: '', subagent_model: '', prescreener_model: '' })
  const [hasOpenAI, setHasOpenAI] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const genRef = useRef(0)

  useEffect(() => {
    const gen = ++genRef.current
    setLoading(true)
    setError(null)
    Promise.all([
      api.getAgentConfig(password, productId),
      api.getAgentConfig(password),
    ])
      .then(([productCfg, globalCfg]) => {
        if (gen !== genRef.current) return
        setAgentModel(productCfg.agent_model)
        setSubagentModel(productCfg.subagent_model)
        setPrescreenerModel(productCfg.prescreener_model)
        setGlobalDefaults({
          agent_model: globalCfg.agent_model,
          subagent_model: globalCfg.subagent_model,
          prescreener_model: globalCfg.prescreener_model,
        })
        setHasOpenAI(Boolean(globalCfg.openai_access_token))
      })
      .catch(() => { if (gen === genRef.current) setError('Failed to load model settings.') })
      .finally(() => { if (gen === genRef.current) setLoading(false) })
  }, [password, productId])

  async function save() {
    setSaving(true)
    try {
      await api.updateAgentConfig(password, {
        product_id: productId,
        agent_model: agentModel,
        subagent_model: subagentModel,
        prescreener_model: prescreenerModel,
      })
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } finally {
      setSaving(false)
    }
  }

  const inputCls = 'w-full bg-adj-panel border border-adj-border rounded-md px-3 py-2 text-sm text-adj-text-primary focus:outline-none focus:border-adj-accent transition-colors'

  if (loading) return <p className="text-adj-text-muted text-sm">Loading…</p>
  if (error) return <p className="text-red-400 text-sm">{error}</p>

  const ModelSelect = ({
    value, onChange, globalDefault,
  }: { value: string; onChange: (v: string) => void; globalDefault: string }) => {
    const defaultLabel = ALL_OPTIONS.find(o => o.value === globalDefault)?.label ?? globalDefault
    return (
      <select value={value} onChange={e => onChange(e.target.value)} className={inputCls}>
        <option value="">— Global default ({defaultLabel}) —</option>
        <optgroup label="Anthropic">
          {ANTHROPIC_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
        </optgroup>
        {hasOpenAI && (
          <optgroup label="OpenAI">
            {OPENAI_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </optgroup>
        )}
      </select>
    )
  }

  return (
    <div className="w-full">
      <h2 className="text-base font-bold text-adj-text-primary mb-1">Model</h2>
      <p className="text-xs text-adj-text-muted mb-6">Override the global model defaults for this product</p>

      <div className="flex flex-col gap-4">
        <div>
          <label className="block text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-1.5">
            Main Agent Model
          </label>
          <ModelSelect value={agentModel} onChange={setAgentModel} globalDefault={globalDefaults.agent_model} />
        </div>

        <div>
          <label className="block text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-1.5">
            Sub-agents
          </label>
          <ModelSelect value={subagentModel} onChange={setSubagentModel} globalDefault={globalDefaults.subagent_model} />
        </div>

        <div>
          <label className="block text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-1.5">
            Pre-screener
          </label>
          <ModelSelect value={prescreenerModel} onChange={setPrescreenerModel} globalDefault={globalDefaults.prescreener_model} />
        </div>
      </div>

      <div className="mt-6">
        <button
          onClick={save}
          disabled={saving}
          className="px-5 py-2 bg-adj-accent text-white rounded-md text-sm font-semibold hover:bg-adj-accent-dark transition-colors disabled:opacity-50"
        >
          {saved ? '✓ Saved' : saving ? 'Saving…' : 'Save Changes'}
        </button>
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Update `ui/src/components/SettingsPage.tsx`**

**4a.** Add `'product-model'` to the `Tab` type (line 18):

```typescript
export type Tab =
  | 'overview' | 'workstreams' | 'objectives' | 'autonomy'
  | 'connections' | 'social' | 'product-mcp' | 'product-model'
  | 'agent-model' | 'google-oauth' | 'remote-access' | 'mcp' | 'image-generation' | 'usage'
```

**4b.** Add import near the other settings imports (after the `TokenUsageSettings` import):

```typescript
import ProductModelSettings from './settings/ProductModelSettings'
```

**4c.** Add to `PRODUCT_TABS` array (after the `'autonomy'` entry):

```typescript
const PRODUCT_TABS: { key: Tab; label: string; icon: string }[] = [
  { key: 'overview',       label: 'Overview',    icon: '◻' },
  { key: 'workstreams',    label: 'Workstreams', icon: '⟳' },
  { key: 'objectives',     label: 'Objectives',  icon: '◎' },
  { key: 'autonomy',       label: 'Autonomy',    icon: '🛡' },
  { key: 'product-model',  label: 'Model',       icon: '🤖' },
]
```

**4d.** Add case to `renderContent()` switch (after `case 'autonomy':`):

```typescript
      case 'product-model': return <ProductModelSettings {...productCommon} />
```

- [ ] **Step 5: Build the UI**

```bash
cd /home/justin/Code/Adjutant/ui
npm run build 2>&1 | tail -10
```

Expected: build succeeds with no TypeScript errors.

- [ ] **Step 6: Commit**

```bash
cd /home/justin/Code/Adjutant
git add ui/src/api.ts \
        ui/src/components/settings/AgentModelSettings.tsx \
        ui/src/components/settings/ProductModelSettings.tsx \
        ui/src/components/SettingsPage.tsx
git commit -m "feat: add OpenAI model options and per-product model settings UI"
```

---

## Self-Review

### Spec coverage

- ✅ `backend/provider.py` — `Provider` protocol, `AnthropicProvider`, `OpenAIProvider`, `make_provider`, `get_openai_client` — Task 1
- ✅ Tools: `input_schema` → `parameters`, wrap in function type — Task 1 `_translate_tools_to_openai`
- ✅ Messages: `tool_use` → `tool_calls`, `tool_result` → `tool` role — Task 1 `_translate_messages_to_openai`
- ✅ System: list of content blocks → joined text string — Task 1 `_extract_system_text`
- ✅ Cache control: stripped from tools and message content — Task 1 translation helpers
- ✅ Remote MCP: warning logged, skipped — Task 1 `OpenAIProvider.stream_agent`
- ✅ `get_provider_name` infers provider from model name — Task 1
- ✅ 3 nullable model columns on `products` — Task 2
- ✅ `get_product_model_config` resolves per-product with global fallback — Task 2
- ✅ `set_product_model_config` writes per-product values (None clears to global) — Task 2
- ✅ `prescreen()` takes `Provider` instead of `client` — Task 3
- ✅ `_run_stream` delegates to `_provider.stream_agent` — Task 3
- ✅ Compaction uses per-product `prescreener_model` via provider — Task 3
- ✅ `_record_token_usage` uses `provider.name` not hardcoded `"anthropic"` — Task 3
- ✅ `GET /api/agent-config?product_id=` returns resolved per-product config — Task 4
- ✅ `PUT /api/agent-config` with `product_id` writes per-product overrides — Task 4
- ✅ `getAgentConfig` / `updateAgentConfig` accept optional `productId`/`product_id` — Task 5
- ✅ `AgentModelSettings` shows OpenAI optgroup when `openai_access_token` present — Task 5
- ✅ `ProductModelSettings` component with "Global default" option — Task 5
- ✅ `'product-model'` tab in `PRODUCT_TABS` — Task 5

### Placeholder scan

None found.

### Type consistency

- `set_product_model_config` uses `...` sentinel — consistent with Python's `inspect.Parameter.empty` pattern
- `_OAIMessage.stop_reason` is `"tool_use"` when `finish_reason == "tool_calls"` — matches what `backend/main.py` checks (`if final.stop_reason != "tool_use": break`)
- `provider.name` is `"anthropic"` or `"openai"` — matches `_normalize_usage` provider check in `backend/db.py`
- `resp.content[0].text` works for both `AnthropicProvider.create()` (returns Anthropic Message) and `OpenAIProvider.create()` (returns `_OAICreateResponse`) — consistent
