# Global Telegram Directive Routing — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Route all Telegram messages through a global agent that either answers cross-product queries directly or dispatches to the right product agent — no "for X:" prefix required.

**Architecture:** All Telegram messages enter a `product_id=None` global queue. A global agent runs with a system prompt listing all products; it answers directly for cross-product queries and calls `dispatch_to_product(product_id, message)` to enqueue work on a specific product's worker. The product agent handles execution and sends the Telegram reply.

**Tech Stack:** Python, FastAPI, Anthropic SDK, SQLite (existing stack — no new dependencies)

---

### Task 1: Add `get_global_system_prompt` to `core/config.py`

**Files:**
- Modify: `core/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_config.py`:

```python
def test_global_system_prompt_lists_products(monkeypatch):
    monkeypatch.setenv("AGENT_NAME", "Hannah")
    monkeypatch.setenv("AGENT_OWNER_NAME", "Justin")
    monkeypatch.delenv("AGENT_OWNER_BIO", raising=False)
    import core.config as mod
    import importlib
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
    import importlib
    importlib.reload(mod)
    prompt = mod.get_global_system_prompt([])
    assert "no products configured" in prompt
```

- [ ] **Step 2: Run to confirm failure**

```
pytest tests/test_config.py::test_global_system_prompt_lists_products -v
```

Expected: `AttributeError: module 'core.config' has no attribute 'get_global_system_prompt'`

- [ ] **Step 3: Implement `get_global_system_prompt` in `core/config.py`**

Add after the existing `get_system_prompt` function:

```python
def get_global_system_prompt(products: list[dict]) -> str:
    agent_name = os.environ.get("AGENT_NAME", "Hannah")
    owner_name = os.environ.get("AGENT_OWNER_NAME", "the user")
    owner_bio = os.environ.get("AGENT_OWNER_BIO", "")
    current_dt = datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")

    if products:
        product_lines = []
        for p in products:
            try:
                from backend.db import get_workstreams, get_objectives
                ws = get_workstreams(p["id"])
                obj = get_objectives(p["id"])
                ws_summary = ", ".join(w["name"] for w in ws[:3]) or "none"
                obj_summary = ", ".join(o["text"][:50] for o in obj[:2]) or "none"
                product_lines.append(
                    f'- {p["name"]} (id: {p["id"]}) | workstreams: {ws_summary} | objectives: {obj_summary}'
                )
            except Exception:
                product_lines.append(f'- {p["name"]} (id: {p["id"]})')
        products_section = "\n".join(product_lines)
    else:
        products_section = "(no products configured yet)"

    return f"""You are {agent_name}, the AI Executive Assistant to {owner_name}.

{owner_bio}

## Your Role
You operate at the global level across all products. You:
- Answer cross-product queries directly (status summaries, general questions, anything spanning multiple products)
- Route product-specific directives to the right product agent via dispatch_to_product
- Take initiative; if you see something actionable, say so

## Products
{products_section}

## Routing Guidelines
- If the message clearly relates to one specific product, acknowledge briefly ("On it" or "Forwarding to [Product]"), then call dispatch_to_product.
- If the message is general, cross-product, or you are unsure, answer directly.
- After dispatching, do not add further commentary — the product agent will respond.

## Tools Available
- **dispatch_to_product** — Route a directive to a specific product agent for execution.
- **delegate_task** — Spawn a sub-agent for research, analysis, or complex autonomous work.
- **get_datetime** — Get the current date and time.
- **save_note / read_notes** — Persist and retrieve notes across conversations.
- **create_product / update_product / delete_product** — Manage products.
- **create_workstream / update_workstream_status / delete_workstream** — Manage workstreams.
- **create_objective / update_objective / delete_objective** — Manage objectives.

## Communication Style
- Professional, direct, and concise — {owner_name} is busy
- Lead with the answer or action, not background

## Current Date & Time
{current_dt}
"""
```

- [ ] **Step 4: Run tests to confirm pass**

```
pytest tests/test_config.py -v
```

Expected: all tests pass including the two new ones.

- [ ] **Step 5: Commit**

```bash
git add core/config.py tests/test_config.py
git commit -m "feat: add get_global_system_prompt for global Telegram agent"
```

---

### Task 2: Add `dispatch_to_product` tool schema and `get_global_tools()` to `core/tools.py`

**Files:**
- Modify: `core/tools.py`
- Test: `tests/test_config.py` (tool schema shape)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_config.py`:

```python
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
```

- [ ] **Step 2: Run to confirm failure**

```
pytest tests/test_config.py::test_get_global_tools_includes_dispatch -v
```

Expected: `ImportError: cannot import name 'get_global_tools' from 'core.tools'`

- [ ] **Step 3: Add `_DISPATCH_TOOL` and `get_global_tools()` to `core/tools.py`**

Add after the `TOOLS_DEFINITIONS.extend(_load_extensions())` line (currently line 579):

```python
_DISPATCH_TOOL = {
    "name": "dispatch_to_product",
    "description": (
        "Route a directive to a specific product agent for execution. "
        "Use when the message clearly targets one product. "
        "Acknowledge briefly before calling this tool (e.g. 'On it' or 'Forwarding to [Product]')."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "product_id": {
                "type": "string",
                "description": "The id of the target product (from the products list in your system prompt)",
            },
            "message": {
                "type": "string",
                "description": "The full directive to send to the product agent",
            },
        },
        "required": ["product_id", "message"],
    },
}

_GLOBAL_BASE_TOOL_NAMES = {
    "delegate_task", "save_note", "read_notes", "get_datetime",
    "create_product", "update_product", "delete_product",
    "create_workstream", "update_workstream_status", "delete_workstream",
    "create_objective", "update_objective", "delete_objective",
}


def get_global_tools() -> list[dict]:
    """Tools available to the global (product_id=None) agent."""
    base = [t for t in TOOLS_DEFINITIONS if t["name"] in _GLOBAL_BASE_TOOL_NAMES]
    return base + [_DISPATCH_TOOL]
```

- [ ] **Step 4: Run tests to confirm pass**

```
pytest tests/test_config.py::test_get_global_tools_includes_dispatch tests/test_config.py::test_get_global_tools_excludes_social tests/test_config.py::test_dispatch_tool_schema -v
```

Expected: all three pass.

- [ ] **Step 5: Commit**

```bash
git add core/tools.py tests/test_config.py
git commit -m "feat: add dispatch_to_product tool and get_global_tools() for global agent"
```

---

### Task 3: Use global prompt and tools in `_agent_loop` when `product_id is None`

**Files:**
- Modify: `backend/main.py` (lines ~519–541)

No new tests needed — this wires existing pieces together; integration behaviour is tested end-to-end.

- [ ] **Step 1: Update the import line at the top of `backend/main.py`**

Find the line that imports from `core.tools` (search for `get_tools_for_product`). Add `get_global_tools` to the same import:

```python
from core.tools import execute_tool, get_tools_for_product, get_global_tools, NOTES_DIR
```

(Exact existing import may vary — add `get_global_tools` to it.)

- [ ] **Step 2: Replace the system prompt and tools lines in `_agent_loop`**

Find these two lines near the top of `_agent_loop` (around line 521 and 540):

```python
    system = get_system_prompt(product_id)
```
and
```python
    _all_tools = get_tools_for_product(product_id) + _stdio_tools
```

Replace with:

```python
    if product_id is None:
        system = get_global_system_prompt(get_products())
    else:
        system = get_system_prompt(product_id)
```
and
```python
    if product_id is None:
        _all_tools = get_global_tools() + _stdio_tools
    else:
        _all_tools = get_tools_for_product(product_id) + _stdio_tools
```

- [ ] **Step 3: Add `get_global_system_prompt` to the config import**

Find the line that imports from `core.config` (search for `get_system_prompt`). Add `get_global_system_prompt`:

```python
from core.config import get_system_prompt, get_global_system_prompt
```

- [ ] **Step 4: Verify the server starts without errors**

```
python -c "import backend.main; print('OK')"
```

Expected: `OK` with no import errors.

- [ ] **Step 5: Commit**

```bash
git add backend/main.py
git commit -m "feat: use global system prompt and tools in agent loop when product_id is None"
```

---

### Task 4: Handle `dispatch_to_product` in `_run_one_tool`

**Files:**
- Modify: `backend/main.py` (`_run_one_tool` closure inside `_agent_loop`, around line 631)

- [ ] **Step 1: Add the `dispatch_to_product` handler at the top of `_run_one_tool`**

Inside `_agent_loop`, find `async def _run_one_tool(block) -> dict:` and add this block as the **first thing** in the function body, before the `is_agent_task` line:

```python
        async def _run_one_tool(block) -> dict:
            # Handle dispatch_to_product directly — needs access to main.py queues
            if block.name == "dispatch_to_product":
                target_id = block.input.get("product_id", "")
                msg = block.input.get("message", "")
                known = {p["id"]: p for p in get_products()}
                if target_id not in known:
                    out = f"Unknown product_id '{target_id}'. Valid IDs: {list(known.keys())}"
                else:
                    _ensure_worker(target_id)
                    directive_id = uuid.uuid4().hex[:8]
                    _directive_queues[target_id].append({"id": directive_id, "content": msg})
                    _worker_events[target_id].set()
                    if _telegram_bot:
                        _telegram_bot._pending_products.add(target_id)
                    await _broadcast(_queue_payload(target_id))
                    out = f"Dispatched to {known[target_id]['name']}"
                return {"type": "tool_result", "tool_use_id": block.id, "content": out}

            is_agent_task = block.name == "delegate_task"
            # ... rest of existing function unchanged
```

- [ ] **Step 2: Verify the import for `uuid` is present**

`uuid` is already imported at the top of `backend/main.py` (`import uuid`). Confirm:

```
grep "^import uuid" backend/main.py
```

Expected: `import uuid`

- [ ] **Step 3: Commit**

```bash
git add backend/main.py
git commit -m "feat: execute dispatch_to_product tool — enqueue to product worker and track pending"
```

---

### Task 5: Simplify `TelegramBot` — remove product routing

**Files:**
- Modify: `backend/telegram.py`

- [ ] **Step 1: Update `TelegramBot.__init__` — remove `products_fn` and `last_active_product_fn`**

Replace the `__init__` signature and body:

```python
    def __init__(
        self,
        token: str,
        chat_id: str,
        directive_callback: Callable[[str | None, str], Awaitable[None]],
        resolve_review_fn: Callable[[int, str], None],
        broadcast_fn: Callable[[dict], Awaitable[None]],
    ):
        self.token = token
        self.chat_id = str(chat_id)
        self._directive_callback = directive_callback
        self.resolve_review_fn = resolve_review_fn
        self.broadcast_fn = broadcast_fn
        self._offset = 0
        self._pending_products: set[str | None] = set()
        self._review_message_ids: dict[int, int] = {}
```

- [ ] **Step 2: Simplify `_handle_message` — remove product routing**

Find the section in `_handle_message` starting from `# Build directive text` to the end of the function. Replace everything after `directive_text = "\n\n".join(parts)` with:

```python
        self._pending_products.add(None)
        await self.send_typing()
        await self._directive_callback(None, directive_text)
```

Delete these lines that are no longer needed:
- `products = self._products_fn()`
- `product_id, clean_text = _parse_product_id(directive_text, products)`
- All the `if product_id is None` / `known_ids` / error-message logic

- [ ] **Step 3: Remove `_parse_product_id` from `backend/telegram.py`**

Delete the entire `_parse_product_id` function (lines 14–32) and its `import re` if `re` is no longer used elsewhere in the file.

Check if `re` is used anywhere else:

```
grep -n "re\." backend/telegram.py
```

If `re` is only used in `_parse_product_id`, remove `import re` too.

- [ ] **Step 4: Commit**

```bash
git add backend/telegram.py
git commit -m "feat: route all Telegram messages to global agent — remove product prefix parsing"
```

---

### Task 6: Update `TelegramBot` instantiation and remove `_last_active_product`

**Files:**
- Modify: `backend/main.py`

- [ ] **Step 1: Remove the `_last_active_product` global**

Find and delete:

```python
_last_active_product: str = ""
```

- [ ] **Step 2: Remove `_last_active_product` assignment from `_handle_telegram_directive`**

Find `_handle_telegram_directive` and remove:

```python
    global _last_active_product
    _last_active_product = product_id
```

- [ ] **Step 3: Remove `_last_active_product` from the WebSocket handler**

Search for any remaining references:

```
grep -n "_last_active_product" backend/main.py
```

Remove all remaining assignments (typically in the WebSocket message handler around line 897–899).

- [ ] **Step 4: Update both `TelegramBot` instantiation sites**

There are two places where `TelegramBot(...)` is called (one in `lifespan`, one in `_restart_telegram`). In each, remove:

```python
        products_fn=get_products,
        last_active_product_fn=lambda: _last_active_product,
```

Both calls should look like:

```python
    _telegram_bot = TelegramBot(
        token=tg_token,
        chat_id=tg_chat_id,
        directive_callback=_handle_telegram_directive,
        resolve_review_fn=resolve_review_item,
        broadcast_fn=_broadcast,
    )
```

- [ ] **Step 5: Verify no remaining references**

```
grep -n "_last_active_product\|products_fn\|last_active_product_fn" backend/main.py
```

Expected: no output.

- [ ] **Step 6: Commit**

```bash
git add backend/main.py
git commit -m "refactor: remove _last_active_product and simplify TelegramBot instantiation"
```

---

### Task 7: Update `tests/test_telegram.py`

**Files:**
- Modify: `tests/test_telegram.py`

- [ ] **Step 1: Update `_make_bot` helper and remove `_parse_product_id` tests**

Delete the five `_parse_product_id` test functions (`test_parse_product_id_*`) and the `PRODUCTS` constant.

Update the import line — `_parse_product_id` is gone:

```python
from backend.telegram import TelegramBot
```

Update `_make_bot()`:

```python
def _make_bot():
    """Return a TelegramBot with all callables mocked."""
    bot = TelegramBot(
        token="test-token",
        chat_id="123456",
        directive_callback=AsyncMock(),
        resolve_review_fn=MagicMock(),
        broadcast_fn=AsyncMock(),
    )
    bot.send_message    = AsyncMock(return_value=99)
    bot.send_typing     = AsyncMock()
    bot.edit_message    = AsyncMock()
    bot.answer_callback = AsyncMock()
    return bot
```

- [ ] **Step 2: Update `test_handle_message_injects_directive`**

Replace the existing test with one that checks the new behaviour (no product prefix, always routes to `None`):

```python
def test_handle_message_routes_to_global_agent():
    bot = _make_bot()
    message = {
        "from": {"id": 123456},
        "text": "Hello, what's going on?",
    }
    asyncio.run(bot._handle_message(message))
    bot._directive_callback.assert_awaited_once_with(None, "Hello, what's going on?")
    assert None in bot._pending_products


def test_handle_message_product_prefix_also_routes_to_global():
    """Old 'for X:' prefix is no longer parsed — global agent handles routing."""
    bot = _make_bot()
    message = {
        "from": {"id": 123456},
        "text": "for Alpha: update me",
    }
    asyncio.run(bot._handle_message(message))
    bot._directive_callback.assert_awaited_once_with(None, "for Alpha: update me")
```

- [ ] **Step 3: Update media tests to expect `None` product_id**

In `test_handle_message_video_downloads_and_injects`, replace:

```python
    assert call_args[0] == "alpha"
```

with:

```python
    assert call_args[0] is None
```

In `test_handle_message_photo_downloads_and_injects`, the test checks `call_args[0][1]` (the text) — this still passes. Also check that `call_args[0][0] is None`:

```python
    assert bot._directive_callback.call_args[0][0] is None
    text = bot._directive_callback.call_args[0][1]
    assert "look at this" in text
```

- [ ] **Step 4: Add test for `notify` with global agent (`product_id=None`)**

```python
def test_notify_agent_done_global_agent():
    bot = _make_bot()
    bot._pending_products.add(None)
    asyncio.run(bot.notify({"type": "agent_done", "product_id": None, "content": "Summary across all products."}))
    bot.send_message.assert_awaited_once_with("Summary across all products.")
    assert None not in bot._pending_products
```

- [ ] **Step 5: Run full test suite**

```
pytest tests/test_telegram.py tests/test_config.py -v
```

Expected: all tests pass.

- [ ] **Step 6: Run the broader test suite to check for regressions**

```
pytest tests/ -v --tb=short
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add tests/test_telegram.py
git commit -m "test: update telegram tests for global agent routing"
```
