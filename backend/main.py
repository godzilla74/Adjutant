# backend/main.py
"""Adjutant — FastAPI backend (multi-product)."""

import asyncio
import json
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

import anthropic
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

# local — bootstrap MUST be first; it runs load_dotenv() before any other local import
import backend.bootstrap  # noqa: F401 — side-effect import
from backend.db import (
    get_products,
    get_workstreams,
    get_objectives,
    get_social_draft_by_review_item,
    update_social_draft_status,
    init_db,
    load_activity_events,
    load_messages,
    load_review_items,
    resolve_review_item,
    save_activity_event,
    save_message,
    update_activity_event,
    count_messages,
    get_oldest_message_ids,
    delete_messages_by_ids,
    get_conversation_summary,
    save_conversation_summary,
    get_messages_for_summary,
    purge_broken_tool_exchanges,
    cancel_running_events,
)
from backend.social_poster import publish_social_draft
from backend.api import router as api_router
from core.config import get_system_prompt
from core.tools import TOOLS_DEFINITIONS, execute_tool

init_db()

# Model config — loaded from DB at startup, hot-reloadable via API
from backend.db import get_agent_config as _get_agent_config
_mc = _get_agent_config()
AGENT_MODEL: str = os.environ.get("AGENT_MODEL", _mc["agent_model"])
import agents.runner as _runner
_runner.SUBAGENT_MODEL = os.environ.get("AGENT_SUBAGENT_MODEL", _mc["subagent_model"])

# ── WebSocket connection registry ─────────────────────────────────────────────

_connections: set[WebSocket] = set()

# ── Per-product directive queues ──────────────────────────────────────────────
# Each product has a queue of pending directives and at most one running task.

_directive_queues: dict[str, list[dict]] = {}   # {product_id: [{id, content}, ...]}
_current_directive: dict[str, dict | None] = {}  # {product_id: directive | None}
_running_tasks:    dict[str, asyncio.Task | None] = {}  # inner _agent_loop task
_worker_events:    dict[str, asyncio.Event] = {}
_worker_tasks:     dict[str, asyncio.Task] = {}

_last_active_product: str = "retainerops"
_telegram_bot = None  # set in lifespan; module-level so _broadcast can reach it


async def _broadcast(event: dict) -> None:
    """Push an event to every connected WebSocket client."""
    dead: set[WebSocket] = set()
    for ws in _connections:
        try:
            await ws.send_text(json.dumps(event))
        except Exception:
            dead.add(ws)
    _connections.difference_update(dead)
    if _telegram_bot is not None:
        try:
            await _telegram_bot.notify(event)
        except Exception:
            pass


async def _handle_telegram_directive(product_id: str, content: str) -> None:
    """Inject a Telegram message into the directive queue, same as the web UI."""
    global _last_active_product
    _last_active_product = product_id
    _ensure_worker(product_id)
    directive_id = uuid.uuid4().hex[:8]
    _directive_queues[product_id].append({"id": directive_id, "content": content})
    _worker_events[product_id].set()
    await _broadcast(_queue_payload(product_id))


# ── App lifespan (starts scheduler) ──────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _telegram_bot
    from backend.scheduler import scheduler_loop, register_broadcast
    from backend.telegram import TelegramBot
    register_broadcast(_broadcast)
    scheduler_task = asyncio.create_task(scheduler_loop(_broadcast, interval_seconds=60))

    _telegram_bot = TelegramBot(
        token=os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        chat_id=os.environ.get("TELEGRAM_CHAT_ID", ""),
        directive_callback=_handle_telegram_directive,
        products_fn=get_products,
        last_active_product_fn=lambda: _last_active_product,
        resolve_review_fn=resolve_review_item,
        broadcast_fn=_broadcast,
    )
    telegram_task = asyncio.create_task(_telegram_bot.start())

    yield

    tasks_to_cancel = [scheduler_task, telegram_task, *_worker_tasks.values()]
    for t in tasks_to_cancel:
        t.cancel()
    await asyncio.gather(*tasks_to_cancel, return_exceptions=True)


app = FastAPI(lifespan=lifespan)
app.include_router(api_router)

UI_DIST = Path(__file__).parent.parent / "ui" / "dist"

AGENT_PASSWORD = os.environ.get("AGENT_PASSWORD", "")
client = anthropic.AsyncAnthropic()


def _ts() -> str:
    """UTC timestamp matching SQLite's datetime('now') format for consistent sort order."""
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


async def _send(ws: WebSocket, event: dict) -> None:
    await ws.send_text(json.dumps(event))


def _product_data_payload(product_id: str) -> dict:
    return {
        "type": "product_data",
        "product_id": product_id,
        "workstreams": get_workstreams(product_id),
        "objectives": get_objectives(product_id),
        "events": load_activity_events(product_id),
        "review_items": load_review_items(product_id),
    }


# ── Conversation compaction ────────────────────────────────────────────────────

COMPACT_THRESHOLD = 20   # compact when DB has more than this many messages
KEEP_RECENT      = 10   # always keep this many recent messages verbatim


def _sanitize_context(messages: list[dict]) -> list[dict]:
    """
    Remove any incomplete tool exchanges from a message list so the Claude API
    won't reject it. Two passes:
      1. Mark and remove any assistant message with tool_use that isn't immediately
         followed by a user message containing all the matching tool_result blocks,
         plus the orphaned tool_result message that follows it.
      2. Trim from the front until the list starts with a plain user text message.
    """
    # Pass 1: find incomplete tool exchanges
    bad: set[int] = set()
    for i, msg in enumerate(messages):
        if msg["role"] != "assistant":
            continue
        content = msg.get("content", "")
        if not isinstance(content, list):
            continue
        tool_ids = {b["id"] for b in content if isinstance(b, dict) and b.get("type") == "tool_use"}
        if not tool_ids:
            continue
        next_i = i + 1
        next_content = messages[next_i].get("content", "") if next_i < len(messages) else ""
        result_ids = set()
        if isinstance(next_content, list):
            result_ids = {b.get("tool_use_id") for b in next_content
                          if isinstance(b, dict) and b.get("type") == "tool_result"}
        if not tool_ids.issubset(result_ids):
            bad.add(i)
            if next_i < len(messages):
                bad.add(next_i)

    messages = [m for i, m in enumerate(messages) if i not in bad]

    # Pass 2: trim front to a clean user text message
    for i, msg in enumerate(messages):
        if msg["role"] != "user":
            continue
        content = msg.get("content", "")
        if isinstance(content, str):
            return messages[i:]
        if isinstance(content, list) and any(
            isinstance(b, dict) and b.get("type") == "text" for b in content
        ):
            return messages[i:]
    return []


def _build_context(product_id: str) -> list[dict]:
    """Load context: optional summary block + last KEEP_RECENT messages."""
    purge_broken_tool_exchanges(product_id)  # clean DB before loading
    messages = load_messages(product_id, limit=KEEP_RECENT)
    messages = _sanitize_context(messages)
    summary = get_conversation_summary(product_id)
    if summary:
        messages = [
            {"role": "user",      "content": f"[Summary of previous conversation]\n{summary}"},
            {"role": "assistant", "content": "Understood — I have context from our prior conversations."},
        ] + messages
    return messages


async def _maybe_compact(product_id: str) -> None:
    """If DB has > COMPACT_THRESHOLD messages, summarize the oldest batch via Haiku."""
    total = count_messages(product_id)
    if total <= COMPACT_THRESHOLD:
        return

    # Identify messages to summarize (everything except the most recent KEEP_RECENT)
    n_to_summarize = total - KEEP_RECENT
    ids_to_remove = get_oldest_message_ids(product_id, n_to_summarize)
    if not ids_to_remove:
        return

    # Guard: don't split a tool-use exchange at the boundary.
    # If the last message being removed is an assistant with tool_use blocks,
    # walk n_to_summarize back until we end on a complete exchange
    # (i.e., the last removed message is an assistant text response).
    all_msgs_to_check = get_messages_for_summary(product_id, ids_to_remove[-1])
    while all_msgs_to_check:
        last = all_msgs_to_check[-1]
        content = last.get("content", "")
        is_tool_use_msg = (
            last["role"] == "assistant" and
            isinstance(content, list) and
            any(isinstance(b, dict) and b.get("type") == "tool_use" for b in content)
        )
        is_orphan_tool_result = (
            last["role"] == "user" and
            isinstance(content, list) and
            all(isinstance(b, dict) and b.get("type") == "tool_result" for b in content)
        )
        if is_tool_use_msg or is_orphan_tool_result:
            all_msgs_to_check = all_msgs_to_check[:-1]
            ids_to_remove = ids_to_remove[:-1]
        else:
            break

    if not ids_to_remove:
        return

    # Prepend existing summary so the new one is cumulative
    existing = get_conversation_summary(product_id)
    context_block = (f"[Existing summary]\n{existing}\n\n[New messages to incorporate]\n" if existing
                     else "[Messages to summarize]\n")

    transcript = "\n".join(
        f"{m['role'].upper()}: {m['content'] if isinstance(m['content'], str) else json.dumps(m['content'])}"
        for m in all_msgs_to_check
    )

    from backend.db import get_agent_config as _gac
    _agent_name = _gac()["agent_name"]
    resp = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
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
    )
    new_summary = resp.content[0].text.strip()
    save_conversation_summary(product_id, new_summary)
    delete_messages_by_ids(product_id, ids_to_remove)


# ── Agent agentic loop ────────────────────────────────────────────────────────

async def _agent_loop(send_fn, product_id: str, messages: list) -> tuple[list, list]:
    """Run the agent loop. Returns (updated messages, new review items)."""
    system = get_system_prompt(product_id)
    new_review_items: list[dict] = []

    while True:
        accumulated_text = ""

        async with client.messages.stream(
            model=AGENT_MODEL,
            max_tokens=8096,
            system=system,
            tools=TOOLS_DEFINITIONS,
            messages=messages,
            thinking={"type": "adaptive"},
        ) as stream:
            async for event in stream:
                if (
                    event.type == "content_block_delta"
                    and event.delta.type == "text_delta"
                ):
                    await send_fn({"type": "agent_token", "product_id": product_id, "content": event.delta.text})
                    accumulated_text += event.delta.text

            final = await stream.get_final_message()

        if accumulated_text:
            ts = _ts()
            await send_fn({
                "type": "agent_done",
                "product_id": product_id,
                "content": accumulated_text,
                "ts": ts,
            })

        _BLOCK_KEYS = {
            "thinking": {"type", "thinking", "signature"},
            "text":     {"type", "text"},
            "tool_use": {"type", "id", "name", "input"},
        }
        content_serializable = []
        for b in final.content:
            if hasattr(b, "model_dump"):
                d = b.model_dump()
                allowed = _BLOCK_KEYS.get(d.get("type", ""), set(d.keys()))
                content_serializable.append({k: v for k, v in d.items() if k in allowed})
            else:
                content_serializable.append(b)
        messages.append({"role": "assistant", "content": content_serializable})
        save_message(product_id, "assistant", content_serializable)

        if final.stop_reason != "tool_use":
            break

        # ── Execute all tool calls in parallel ───────────────────────────────
        tool_blocks = [b for b in final.content if b.type == "tool_use"]

        async def _run_one_tool(block) -> dict:
            """Execute one tool call and handle activity events / side-effects."""
            is_agent_task = block.name in ("delegate_task", "email_task")
            is_review     = block.name == "create_review_item"
            ev_id = None

            if is_agent_task:
                headline   = block.input.get("task", block.name)
                rationale  = block.input.get("context", "")
                agent_type = block.input.get(
                    "agent_type", "email" if block.name == "email_task" else "general"
                )
                ev_id = save_activity_event(
                    product_id=product_id, agent_type=agent_type,
                    headline=headline, rationale=rationale, status="running",
                )
                await send_fn({
                    "type": "activity_started", "product_id": product_id,
                    "id": ev_id, "agent_type": agent_type,
                    "headline": headline, "rationale": rationale, "ts": _ts(),
                })

            try:
                result = await execute_tool(block.name, block.input)
                output = result if isinstance(result, str) else json.dumps(result)
            except Exception as exc:
                output = f"Error in {block.name}: {exc}"

            if is_agent_task and ev_id is not None:
                summary = output[:8000].rstrip() + ("…" if len(output) > 8000 else "")
                update_activity_event(ev_id, status="done", summary=summary)
                await send_fn({
                    "type": "activity_done", "product_id": product_id,
                    "id": ev_id, "summary": summary, "ts": _ts(),
                })

            if is_review:
                try:
                    parsed  = json.loads(output)
                    item_id = parsed["id"]
                    item = {
                        "id": item_id,
                        "title": block.input.get("title", ""),
                        "description": block.input.get("description", ""),
                        "risk_label": block.input.get("risk_label", ""),
                        "status": "pending", "created_at": _ts(),
                    }
                    await send_fn({"type": "review_item_added", "product_id": product_id, "item": item})
                    new_review_items.append(item)
                except (json.JSONDecodeError, KeyError):
                    pass

            if block.name in ("create_objective", "update_objective"):
                await send_fn(_product_data_payload(block.input.get("product_id", product_id)))
            if block.name in ("create_product", "update_product", "delete_product"):
                await send_fn({"type": "init", "products": get_products()})
            if block.name in ("create_workstream", "update_workstream_status", "delete_workstream", "delete_objective"):
                await send_fn(_product_data_payload(block.input.get("product_id", product_id)))
            if block.name == "draft_social_post":
                try:
                    parsed     = json.loads(output)
                    review_id  = parsed.get("review_item_id")
                    pid        = block.input.get("product_id", product_id)
                    if review_id:
                        item = {
                            "id": review_id,
                            "title": f"Post to {block.input.get('platform', '').capitalize()}",
                            "description": block.input.get("content", "")[:200],
                            "risk_label": f"Social post · {block.input.get('platform', '')} · public-facing",
                            "status": "pending", "created_at": _ts(),
                        }
                        await send_fn({"type": "review_item_added", "product_id": pid, "item": item})
                except (json.JSONDecodeError, KeyError):
                    pass

            return {"type": "tool_result", "tool_use_id": block.id, "content": output}

        # Run all tool calls concurrently; results preserve original order
        tool_results = list(await asyncio.gather(*[_run_one_tool(b) for b in tool_blocks]))

        if tool_results:
            messages.append({"role": "user", "content": tool_results})
            save_message(product_id, "user", tool_results)

    return messages, new_review_items


# ── Per-product directive workers ─────────────────────────────────────────────

def _queue_payload(product_id: str) -> dict:
    return {
        "type": "queue_update",
        "product_id": product_id,
        "current": _current_directive.get(product_id),
        "queued": list(_directive_queues.get(product_id, [])),
    }


async def _product_worker(product_id: str) -> None:
    """Processes directives sequentially for one product, forever."""
    event = _worker_events[product_id]
    while True:
        await event.wait()
        event.clear()

        while _directive_queues.get(product_id):
            directive = _directive_queues[product_id].pop(0)
            _current_directive[product_id] = directive
            await _broadcast(_queue_payload(product_id))

            messages = _build_context(product_id)
            messages.append({"role": "user", "content": directive["content"]})
            save_message(product_id, "user", directive["content"])

            try:
                inner = asyncio.create_task(_agent_loop(_broadcast, product_id, messages))
                _running_tasks[product_id] = inner
                await inner
            except asyncio.CancelledError:
                if inner.cancelled():
                    # Inner task was cancelled by user — continue to next directive
                    pass
                else:
                    # Worker itself is being shut down — propagate
                    inner.cancel()
                    raise
            except Exception as exc:
                import traceback; traceback.print_exc()
                await _broadcast({"type": "error", "message": f"Agent error: {exc}"})
            finally:
                _running_tasks[product_id] = None
                _current_directive[product_id] = None
                try:
                    await _maybe_compact(product_id)
                except Exception:
                    pass
                await _broadcast(_queue_payload(product_id))


def _ensure_worker(product_id: str) -> None:
    """Start a worker for product_id if one isn't already running."""
    if product_id not in _worker_events:
        _worker_events[product_id] = asyncio.Event()
    if product_id not in _directive_queues:
        _directive_queues[product_id] = []
    if product_id not in _current_directive:
        _current_directive[product_id] = None

    existing = _worker_tasks.get(product_id)
    if existing is None or existing.done():
        _worker_tasks[product_id] = asyncio.create_task(_product_worker(product_id))


# ── WebSocket endpoint ─────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    _connections.add(ws)

    if not AGENT_PASSWORD:
        await _send(ws, {"type": "auth_fail", "reason": "AGENT_PASSWORD not set"})
        await ws.close()
        return

    try:
        msg = await ws.receive_json()
    except Exception:
        await ws.close()
        return

    if msg.get("type") != "auth" or msg.get("password") != AGENT_PASSWORD:
        await _send(ws, {"type": "auth_fail", "reason": "Invalid password"})
        await ws.close()
        return

    await _send(ws, {"type": "auth_ok"})
    await _send(ws, {"type": "init", "products": get_products()})

    active_product_id = "retainerops"

    # Send current queue state for all active products on connect
    for pid, directive in _current_directive.items():
        if directive or _directive_queues.get(pid):
            await _send(ws, _queue_payload(pid))

    try:
        while True:
            msg = await ws.receive_json()
            msg_type = msg.get("type")

            if msg_type == "get_products":
                await _send(ws, {"type": "init", "products": get_products()})

            elif msg_type == "switch_product":
                product_id = msg.get("product_id", "retainerops")
                active_product_id = product_id
                await _send(ws, _product_data_payload(product_id))
                # Also send current queue state for this product
                await _send(ws, _queue_payload(product_id))

            elif msg_type == "directive":
                product_id = msg.get("product_id", active_product_id)
                known_ids = {p["id"] for p in get_products()}
                if product_id not in known_ids:
                    await _send(ws, {"type": "error", "message": f"Unknown product: {product_id}"})
                    continue
                active_product_id = product_id
                global _last_active_product
                _last_active_product = product_id
                content = msg.get("content", "").strip()
                if not content:
                    continue

                # Echo to chat immediately so it appears in the feed right away
                await _send(ws, {
                    "type": "directive_echo",
                    "product_id": product_id,
                    "content": content,
                    "ts": _ts(),
                })

                # Save to directive history for replay
                from backend.db import save_directive_history
                save_directive_history(product_id, content)

                # Enqueue and ensure worker is running
                directive_id = uuid.uuid4().hex[:8]
                _ensure_worker(product_id)
                _directive_queues[product_id].append({"id": directive_id, "content": content})
                _worker_events[product_id].set()
                await _broadcast(_queue_payload(product_id))

            elif msg_type == "cancel_directive":
                product_id = msg.get("product_id", active_product_id)
                directive_id = msg.get("directive_id")
                if not directive_id:
                    continue

                # Remove from queue if pending
                if product_id in _directive_queues:
                    _directive_queues[product_id] = [
                        d for d in _directive_queues[product_id] if d["id"] != directive_id
                    ]

                # Cancel if currently running
                current = _current_directive.get(product_id)
                if current and current["id"] == directive_id:
                    task = _running_tasks.get(product_id)
                    if task and not task.done():
                        task.cancel()
                    # Mark any stuck running events as done so they clear from the UI
                    cancelled_ids = cancel_running_events(product_id)
                    for ev_id in cancelled_ids:
                        await _broadcast({
                            "type": "activity_done",
                            "product_id": product_id,
                            "id": ev_id,
                            "summary": "Cancelled.",
                            "ts": _ts(),
                        })

                await _broadcast(_queue_payload(product_id))

            elif msg_type == "resolve_review":
                item_id = msg.get("review_item_id")
                action = msg.get("action")  # 'approved' | 'skipped'
                if item_id and action in ("approved", "skipped"):
                    resolve_review_item(item_id, action)
                    await _send(ws, {
                        "type": "review_resolved",
                        "review_item_id": item_id,
                        "action": action,
                    })

                    # If this was a social post approval, publish it
                    if action == "approved":
                        draft = get_social_draft_by_review_item(item_id)
                        if draft:
                            platform = draft.get("platform", "unknown")
                            pid = draft.get("product_id", active_product_id)

                            # Show posting activity in the feed
                            event_id = save_activity_event(
                                product_id=pid,
                                agent_type="social",
                                headline=f"Publishing to {platform.capitalize()}",
                                rationale="Social post approved — publishing now",
                                status="running",
                            )
                            await _send(ws, {
                                "type": "activity_started",
                                "product_id": pid,
                                "id": event_id,
                                "agent_type": "social",
                                "headline": f"Publishing to {platform.capitalize()}",
                                "rationale": "Social post approved — publishing now",
                                "ts": _ts(),
                            })

                            try:
                                result = await publish_social_draft(draft)
                            except Exception as exc:
                                result = {"success": False, "error": str(exc)}

                            new_status = "posted" if result["success"] else "failed"
                            update_social_draft_status(draft["id"], new_status, result.get("post_url"))

                            if result["success"]:
                                summary = f"Posted to {platform.capitalize()}. {result.get('post_url', '')}"
                            else:
                                summary = f"Failed to post: {result.get('error', 'Unknown error')}"

                            update_activity_event(event_id, status="done", summary=summary)
                            await _send(ws, {
                                "type": "activity_done",
                                "product_id": pid,
                                "id": event_id,
                                "summary": summary,
                                "ts": _ts(),
                            })

    except WebSocketDisconnect:
        pass
    finally:
        _connections.discard(ws)


# ── Static UI ──────────────────────────────────────────────────────────────────

if UI_DIST.exists():
    app.mount("/", StaticFiles(directory=UI_DIST, html=True), name="ui")
