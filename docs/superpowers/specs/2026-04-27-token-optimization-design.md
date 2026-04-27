# Token Optimization Design

**Date:** 2026-04-27
**Goal:** Reduce Anthropic API token costs via three independent optimizations: prompt caching, tool list pruning, and Haiku pre-screening.

---

## Background

Current per-call token profile (approximate):
- System prompt: ~1,300 tokens (sent in full every turn, fully static except datetime injection)
- Tool definitions: ~15,000–25,000 tokens (all tools sent every call regardless of relevance)
- Conversation history: last 10 messages (existing compaction already in place)

None of these are cached today. The system prompt datetime injection (`datetime.now()`) prevents caching by making the prompt change every turn.

---

## Approach: Three Independent Layers

Each optimization is independent and falls back gracefully. They are ordered by implementation dependency: caching must come first (datetime move is a prerequisite), tool groups second (prescreener depends on them), prescreener third.

**Provider note:** All three features are designed to accommodate future OpenAI support. Tool pruning is provider-agnostic. Caching blocks are gated on Anthropic provider. The prescreener model is configurable via `AGENT_PRESCREENER_MODEL` env var.

---

## Layer 1: Prompt Caching

### Datetime move

`core/config.py` `get_system_prompt()` currently injects `datetime.now()` into the system prompt, making it dynamic. This is removed. The system prompt becomes fully static.

Datetime is injected instead as a prefix on the first user message in the assembled conversation context, inside `_agent_loop()` in `backend/main.py`:

```
[Current datetime: Monday, April 27, 2026 at 2:30 PM]

<actual user message>
```

This is prepended to the first message with `role == "user"` in the context list before the API call. If the content is a string, it's prepended directly. If it's a list of content blocks, a text block is inserted at position 0.

### Cache control blocks

When provider is Anthropic, two cache breakpoints are added per call:

**System prompt** — passed as a content block list instead of a plain string:
```python
system = [
    {
        "type": "text",
        "text": static_system_prompt,
        "cache_control": {"type": "ephemeral"}
    }
]
```

**Tool list** — `cache_control` added to the last tool definition (a copy, never mutating the source):
```python
tools = list(tools)  # shallow copy
tools[-1] = {**tools[-1], "cache_control": {"type": "ephemeral"}}
```

Both are static across sessions so cache hits begin on turn 2. The Anthropic ephemeral cache TTL is 5 minutes — sufficient for all interactive sessions.

### Fallback

If the messages API rejects the cache_control format (e.g., wrong API version), the existing `BadRequestError` retry path in `_agent_loop()` already retries without MCP servers. We add a second retry that strips `cache_control` blocks — reverting `system` back to a plain string and removing the `cache_control` key from the last tool dict — before re-raising, so a bad cache config never breaks a user session.

---

## Layer 2: Tool Groups

### Group definitions

`core/tools.py` gains a new `TOOL_GROUPS` dict mapping group name → set of tool names:

| Group | Tools |
|-------|-------|
| `core` | `delegate_task`, `save_note`, `read_notes`, `create_review_item`, `get_datetime`, `shell_task`, `list_uploads`, `send_telegram_file`, `schedule_next_run` |
| `email` | `gmail_search`, `gmail_read`, `gmail_send`, `gmail_draft` |
| `calendar` | `calendar_list_events`, `calendar_create_event`, `calendar_find_free_time` |
| `social` | `draft_social_post`, `twitter_post`, `linkedin_post`, `facebook_post`, `instagram_post`, `generate_image`, `search_stock_photo` |
| `management` | `create_product`, `update_product`, `delete_product`, `create_workstream`, `update_workstream_status`, `delete_workstream`, `create_objective`, `update_objective`, `update_objective_progress`, `delete_objective`, `set_objective_autonomous` |
| `system` | `add_agent_tool`, `find_skill`, `install_skill`, `restart_server`, `manage_mcp_server`, `manage_capability_slots`, `report_wizard_progress`, `complete_launch` |

### New function

```python
def get_tools_for_groups(groups: list[str], product_id: str | None) -> list[dict]:
```

Filters the full tool list to only tools whose names appear in the union of the requested groups (always including `core`), then appends any enabled extensions for the product. MCP tools are appended unchanged (they come from live server discovery and are always included when available).

The existing `get_tools_for_product()` remains for compatibility but is no longer called from the main agent loop — it is replaced by `get_tools_for_groups()` with groups supplied by the prescreener.

### Available groups per product

Before calling the prescreener, `_agent_loop()` computes which groups are available for the current product based on OAuth connections:

```python
_SOCIAL_PLATFORMS = {"twitter", "linkedin", "facebook", "instagram"}

available_groups = ["core", "management", "system"]
if "gmail" in oauth_connections:
    available_groups.append("email")
if "google_calendar" in oauth_connections:
    available_groups.append("calendar")
if oauth_connections & _SOCIAL_PLATFORMS:
    available_groups.append("social")
```

**Scope:** This applies only to product agents (`product_id` is not None). The global agent (product_id=None) continues to use `get_global_tools()` unchanged and is not passed through the prescreener.

This list is passed to the prescreener so it only suggests groups that actually have tools available.

---

## Layer 3: Haiku Pre-screener

### New file: `core/prescreener.py`

```python
PRESCREENER_MODEL = os.environ.get("AGENT_PRESCREENER_MODEL", "claude-haiku-4-5-20251001")

@dataclass
class PrescreerResult:
    route: Literal["haiku", "sonnet"]
    tool_groups: list[str]
    response: str | None
```

Single async function:

```python
async def prescreen(
    message: str,
    available_groups: list[str],
    client: anthropic.AsyncAnthropic,
) -> PrescreerResult:
```

Makes one non-streaming `messages.create()` call to Haiku with `max_tokens=512`. Returns `PrescreerResult`. On any exception or malformed JSON, returns the fallback result.

### Haiku system prompt

```
You are a routing agent for an AI executive assistant. Given a user message, decide how to handle it.

Return JSON only — no prose, no markdown. One of two shapes:

If you can answer directly (no tools needed):
{"route": "haiku", "response": "your full answer here"}

If the main agent is needed:
{"route": "sonnet", "tool_groups": ["core", "email"]}

Route to haiku ONLY for: greetings, simple factual questions answerable without data access,
conversational acknowledgments, or short replies requiring no tools.

Route to sonnet for: anything requiring tool use, task execution, accessing email/calendar/notes,
managing objectives or workstreams, complex reasoning, or anything you are uncertain about.

Available tool groups: {available_groups}
Only include groups from that list in tool_groups. Always include "core".
```

### Wiring in `backend/main.py`

At the start of `_agent_loop()`, before the Sonnet loop:

1. Call `prescreen(latest_user_message, available_groups, client)`
2. If `result.route == "haiku"`: save the response as an assistant message, emit to WebSocket, return. No Sonnet call.
3. If `result.route == "sonnet"`: call `get_tools_for_groups(result.tool_groups, product_id)` and proceed into the existing agent loop with the pruned tool list.

The "latest user message" is the last message in the context with `role == "user"`, extracted before the API call.

### Fallback

```python
_FALLBACK = PrescreerResult(route="sonnet", tool_groups=available_groups, response=None)
```

Any exception, JSON decode error, missing keys, or unexpected `route` value returns the fallback. Behavior is identical to the current system — all tools loaded, Sonnet runs. No user-visible impact.

---

## Files Changed

| File | Change |
|------|--------|
| `core/config.py` | Remove datetime from `get_system_prompt()`; make prompt fully static |
| `core/tools.py` | Add `TOOL_GROUPS` dict; add `get_tools_for_groups()` |
| `core/prescreener.py` | New file — `PrescreerResult`, `prescreen()` |
| `backend/main.py` | Datetime injection, cache_control blocks, prescreener wiring |

---

## Testing

- **Caching:** Unit test that `_build_api_params()` (or equivalent) produces a system list with `cache_control` block; that the last tool has `cache_control`; that original tool dicts are not mutated.
- **Datetime injection:** Unit test that the first user message in context receives the datetime prefix; that subsequent user messages are unchanged.
- **Tool groups:** Unit test `get_tools_for_groups()` — given a group list, only tools from those groups are returned; `core` is always present; extensions are appended.
- **Prescreener:** Mock the Haiku API call; test JSON parse success (haiku route, sonnet route); test malformed JSON fallback; test exception fallback; test that `core` is always in tool_groups on sonnet route.
- **Integration:** Existing test suite must continue to pass — no behavioral regression.

---

## Non-Goals

- Provider abstraction layer (deferred to OpenAI feature)
- Token usage logging/metrics (separate concern)
- Changing compaction behavior (already working)
- Removing `get_tools_for_product()` (kept for compatibility)
