# Global Telegram Directive Routing

**Date:** 2026-04-20
**Status:** Approved

## Problem

Telegram messages currently require the user to prefix with `"for <ProductName>: <message>"` or fall back to a hardcoded `_last_active_product`. This is friction-heavy and breaks for new users. The system should route messages intelligently without any user-side formatting.

## Goal

All Telegram messages are handled at the global level. A global agent decides whether to answer directly (cross-product queries) or dispatch to a specific product agent.

## Architecture

### Data Flow

```
Telegram message
    ↓
global queue (product_id=None)
    ↓
global agent (_agent_loop with global system prompt)
    ↓
    ├── answer directly (cross-product queries, status summaries)
    │       ↓
    │   Telegram reply
    │
    └── dispatch_to_product(product_id, message)
            ↓
        product queue → product agent
            ↓
        Telegram reply
```

The `_parse_product_id` function and `_last_active_product` fallback are removed from the Telegram path. Web UI routing (which always sends an explicit `product_id`) is unchanged.

## Components

### `core/config.py` — `get_global_system_prompt(products)`

New function. Builds a system prompt for the global agent that:
- Retains the base Hannah persona
- Lists all products by name, id, and a brief summary of their workstreams/objectives
- Instructs the agent to dispatch product-specific directives via `dispatch_to_product`, and to acknowledge briefly ("On it" / "Forwarding to [Product]") before doing so
- Instructs the agent to answer cross-product queries (summaries, status, general questions) directly

When `product_id is None`, `_agent_loop` uses this prompt instead of the per-product prompt.

### `core/tools.py` — `dispatch_to_product` tool schema

```json
{
  "name": "dispatch_to_product",
  "description": "Route a directive to a specific product agent for execution. Use when the message clearly targets one product. Acknowledge briefly before calling this tool.",
  "input_schema": {
    "type": "object",
    "properties": {
      "product_id": { "type": "string", "description": "ID of the target product" },
      "message": { "type": "string", "description": "The directive to enqueue for the product agent" }
    },
    "required": ["product_id", "message"]
  }
}
```

Tool is only injected when `product_id is None` (global context).

### `backend/main.py` — three changes

1. **Global system prompt**: when `product_id is None` in `_agent_loop`, call `get_global_system_prompt(get_products())` instead of the per-product prompt.

2. **Tool executor**: handle `dispatch_to_product` in the tool execution block:
   - Validate `product_id` against `get_products()`; return error string to agent if invalid
   - Call `_ensure_worker(product_id)` and enqueue the message into `_directive_queues[product_id]`
   - Return `"Dispatched to {product_name}"` as tool result

3. **Remove `_last_active_product`**: delete the global variable, all assignments, and the `last_active_product_fn` parameter from both `TelegramBot` instantiations.

### `backend/telegram.py` — simplified message handler

Replace:
```python
product_id, clean_text = _parse_product_id(directive_text, products)
if product_id is None:
    product_id = self._last_active_product_fn()
known_ids = {p["id"] for p in products}
if product_id not in known_ids and products:
    product_id = products[0]["id"]
if product_id not in known_ids:
    ...error...
    return
```

With:
```python
await self._directive_callback(None, directive_text)
return
```

Remove `products_fn`, `last_active_product_fn` parameters from `TelegramBot.__init__` and both instantiation sites in `main.py`.

Event forwarding (`agent_done`, `activity_done`, `review_item_added`) is unchanged — it already works for any product including `None`.

## Edge Cases

| Case | Handling |
|---|---|
| `dispatch_to_product` with unknown `product_id` | Tool returns error string; agent recovers, may ask user or try again |
| No products configured | Global agent answers directly, informs user no products are set up |
| Global agent closing text after dispatch | Prompt-instructed to be brief ("On it"); user receives brief ack + full product agent reply |
| Concurrent Telegram messages | Global queue serializes like product queues — one at a time |
| Web UI product routing | Unchanged — always sends explicit `product_id` via WebSocket |
| Review item approval/rejection buttons | Unchanged — handled by `_handle_callback`, not the directive path |

## What Is Removed

- `_parse_product_id` function (`telegram.py`)
- `_last_active_product` global variable and all assignments (`main.py`)
- `products_fn` and `last_active_product_fn` parameters from `TelegramBot` (`telegram.py`, `main.py`)
- The "for ProductName: message" convention from the user-facing experience
