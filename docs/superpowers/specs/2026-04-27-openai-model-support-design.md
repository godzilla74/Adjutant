# OpenAI Model Support Design

**Date:** 2026-04-27
**Goal:** Make OpenAI models selectable alongside Anthropic in Adjutant — connection global (existing OAuth flow), model selection per-product.

---

## Background

The agent loop, compaction, and prescreener are all hardcoded to the Anthropic SDK. The OpenAI OAuth flow already exists (`backend/openai_oauth.py`) and stores `openai_access_token` in `model_config`. Token usage logging (`record_token_usage`) already normalises both Anthropic and OpenAI usage objects via `_normalize_usage`. The DB and API layers are provider-agnostic; the gap is the inference layer.

Three Anthropic-specific call sites need to become provider-agnostic:
1. **Agent loop** — `_run_stream` in `backend/main.py` (streaming, tools, message history)
2. **Compaction** — `_maybe_compact` in `backend/main.py` (non-streaming, no tools)
3. **Prescreener** — `prescreen()` in `core/prescreener.py` (non-streaming, no tools)

---

## Architecture

### Provider Selection

The active provider for a call is determined by the model name at runtime:

```python
def get_provider_name(model: str) -> str:
    if model.startswith(("gpt-", "o1", "o3")):
        return "openai"
    return "anthropic"
```

No explicit provider field is stored — the model name is the source of truth.

### New File: `backend/provider.py`

Defines the `Provider` protocol and two implementations.

**Interface:**

```python
class Provider(Protocol):
    name: str  # "anthropic" | "openai"

    async def stream_agent(
        self,
        model: str,
        system: str | list,
        messages: list,
        tools: list,
        max_tokens: int,
        send_fn: Callable,
        extra_headers: dict | None,
        extra_body: dict | None,
    ) -> object:
        """Stream tokens via send_fn; return final message with .usage."""

    async def create(
        self,
        model: str,
        system: str,
        messages: list,
        max_tokens: int,
    ) -> object:
        """Non-streaming completion; return response with .usage and .content."""
```

**`AnthropicProvider`** — wraps the existing `anthropic.AsyncAnthropic()` client. Delegates to the current `client.messages.stream()` and `client.messages.create()` code paths unchanged.

**`OpenAIProvider`** — wraps `openai.AsyncOpenAI(api_key=...)`. Handles all format translation internally:

| Concern | Translation |
|---------|-------------|
| Tools | `input_schema` → `parameters`; wrap in `{"type": "function", "function": {...}}` |
| Message history | `tool_use` blocks → `tool_calls` on assistant; `tool_result` blocks → `{"role": "tool", ...}` messages |
| System prompt | If `system` is a list of content blocks (Anthropic cache format), extract and join text fields; inject as `{"role": "system", "content": joined_text}` prepended to messages |
| Cache control | Strip all `cache_control` fields before sending (from system blocks, message content blocks, and tools) |
| Remote MCP | Log a warning and skip `extra_headers`/`extra_body` (not supported by OpenAI) |
| Streaming | `chat.completions.create(stream=True)`; accumulate tool call chunks; return a normalised response object with `.usage` and `.content` |

**`get_openai_client()`** — reads `openai_access_token` from `get_agent_config()` and returns `openai.AsyncOpenAI(api_key=token)`. Raises `RuntimeError` if token is absent.

**`make_provider(model: str) -> Provider`** — factory that returns the appropriate provider for a model name.

---

## Per-Product Model Config

### DB Schema

Three nullable columns added to `products` (idempotent `ALTER TABLE`):

```sql
ALTER TABLE products ADD COLUMN agent_model       TEXT;
ALTER TABLE products ADD COLUMN subagent_model    TEXT;
ALTER TABLE products ADD COLUMN prescreener_model TEXT;
```

`NULL` means "use the global default from `model_config`."

### New DB Helper

```python
def get_product_model_config(product_id: str | None) -> dict:
    """Return resolved {agent_model, subagent_model, prescreener_model} for a product.
    Per-product values take precedence; falls back to global model_config defaults."""
```

### API Changes (`backend/api.py`)

`PUT /api/agent-config` gains an optional `product_id` field on the request body. When present, writes to the product's nullable columns. When absent, updates the global `model_config` as today.

`GET /api/agent-config` gains an optional `?product_id=` query param. Returns per-product resolved config when provided.

---

## Agent Loop Changes (`backend/main.py`)

At the start of `_agent_loop`, resolve the model config for the product and instantiate a provider:

```python
_model_cfg = get_product_model_config(product_id)
_agent_model = _model_cfg["agent_model"]
_prescreener_model = _model_cfg["prescreener_model"]
_provider = make_provider(_agent_model)
_pre_provider = make_provider(_prescreener_model)
```

**`_run_stream`** — updated signature to accept a `Provider` instead of using the module-level `client`. Delegates to `provider.stream_agent(...)`.

**Compaction** (`_maybe_compact`) — uses `make_provider(_prescreener_model)` and calls `provider.create(...)` instead of the hardcoded `client.messages.create(model="claude-haiku-4-5-20251001", ...)`.

**Prescreener** — `prescreen()` in `core/prescreener.py` changes its `client` parameter to accept a `Provider`. Internal call becomes `provider.create(...)`.

Token usage recording is unchanged: `_record_token_usage(product_id, call_type, provider.name, model, response.usage)`.

---

## Settings UI

### Supported Models

```python
ANTHROPIC_MODELS = [
    "claude-opus-4-7",
    "claude-sonnet-4-6",
    "claude-haiku-4-5-20251001",
]

OPENAI_MODELS = [
    "gpt-4o",
    "gpt-4o-mini",
    "o3-mini",
]
```

OpenAI options are shown only when `openai_access_token` is present in the config response.

### Global Model Settings (`AgentModelSettings.tsx`)

The three existing model dropdowns (Agent, Sub-agents, Pre-screener) are extended with an OpenAI option group. Dropdowns use `<optgroup>` to separate Anthropic and OpenAI sections. No other changes to this component.

### Per-Product Model Settings (`ProductModelSettings.tsx`)

New component added as a product-specific tab (`'product-model'`, label `'Model'`). Shows the same three dropdowns with a `"— Global default —"` entry at the top of each list. When selected, the per-product column is cleared to `NULL` and the current global value is shown as placeholder text. Saves via `PUT /api/agent-config` with `product_id`.

---

## Files Changed

| File | Action |
|------|--------|
| `backend/provider.py` | Create — `Provider` protocol, `AnthropicProvider`, `OpenAIProvider`, `make_provider`, `get_openai_client` |
| `backend/db.py` | Add 3 nullable model columns to `products`; add `get_product_model_config` |
| `backend/main.py` | Resolve per-product model config; pass provider to `_run_stream` and `_maybe_compact` |
| `core/prescreener.py` | Change `client` param to `Provider` |
| `backend/api.py` | Extend `GET`/`PUT /api/agent-config` with optional `product_id` |
| `ui/src/api.ts` | Update `getAgentConfig` / `updateAgentConfig` to accept optional `productId` |
| `ui/src/components/settings/AgentModelSettings.tsx` | Add OpenAI option groups to model dropdowns |
| `ui/src/components/settings/ProductModelSettings.tsx` | Create — per-product model override UI |
| `ui/src/components/SettingsPage.tsx` | Add `'product-model'` tab |

---

## Testing

- **`test_provider.py`** — unit tests for `OpenAIProvider` format translation (tools, messages, system prompt, cache control stripping) using mocked OpenAI client
- **`test_provider_anthropic.py`** — verify `AnthropicProvider` passes kwargs through unchanged
- **`test_product_model_config.py`** — verify per-product config resolution: per-product value wins; falls back to global when `NULL`
- **Regression** — full test suite passes

---

## Known Limitations

- Remote MCP servers (injected via `extra_headers`/`extra_body`) are silently skipped when provider is OpenAI. Built-in tools (Gmail, Calendar, social, etc.) work normally.
- Prompt cache (`cache_control`) is stripped for OpenAI calls — no cache savings when using OpenAI models.
- Switching a product's model mid-session works, but messages already in the DB are in Anthropic format. The translation handles this at runtime; no DB migration needed.

---

## Non-Goals

- LiteLLM or any other unified inference library
- Streaming token counts during a turn (deferred)
- Per-product cost estimation in the Usage UI (deferred)
