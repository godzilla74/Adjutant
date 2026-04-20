# backend/main.py
"""Adjutant — FastAPI backend (multi-product)."""

import asyncio
import base64
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
    create_workstream,
    create_objective,
    create_session,
    get_sessions,
    get_session_by_id,
    get_first_session,
    rename_session,
    delete_session,
    get_objective_by_id,
    set_objective_autonomous,
    get_objective_blocked_by_review,
    clear_objective_block,
    set_launch_wizard_active,
    get_product_config,
    create_product as _create_product_db,
)
from backend.api import router as api_router


async def _publish_social_draft(draft: dict) -> dict:
    platform = draft.get("platform", "")
    product_id = draft.get("product_id", "")
    text = draft.get("content", "")
    image_url = draft.get("image_url")
    from backend.social_api import twitter_post, linkedin_post, facebook_post, instagram_post
    try:
        if platform == "twitter":
            result = await twitter_post(product_id, text, image_url)
        elif platform == "linkedin":
            result = await linkedin_post(product_id, text, image_url)
        elif platform == "facebook":
            result = await facebook_post(product_id, text, image_url)
        elif platform == "instagram":
            if not image_url:
                return {"success": False, "error": "Instagram requires an image URL"}
            result = await instagram_post(product_id, text, image_url)
        else:
            return {"success": False, "error": f"Unknown platform: {platform}"}
        return {"success": True, "result": result}
    except RuntimeError as e:
        return {"success": False, "error": str(e)}
from core.config import get_system_prompt, get_global_system_prompt
from core.tools import execute_tool, get_tools_for_product, get_global_tools

init_db()

# Model config is read fresh per invocation in _agent_loop so settings changes
# take effect without a restart. These imports are needed at module level.
from backend.db import get_agent_config as _get_agent_config
import agents.runner as _runner

# ── WebSocket connection registry ─────────────────────────────────────────────

_connections: set[WebSocket] = set()

# ── Per-product directive queues ──────────────────────────────────────────────
# Each product has a queue of pending directives and at most one running task.

_directive_queues: dict[str | None, list[dict]] = {}   # {product_id: [{id, content}, ...]}
_current_directive: dict[str | None, dict | None] = {}  # {product_id: directive | None}
_running_tasks:    dict[str | None, asyncio.Task | None] = {}  # inner _agent_loop task
_worker_events:    dict[str | None, asyncio.Event] = {}
_worker_tasks:     dict[str | None, asyncio.Task] = {}

_telegram_bot  = None  # set in lifespan; module-level so _broadcast can reach it
_telegram_task = None  # module-level so hot-reload can cancel it
_mcp_manager = None  # set in lifespan; module-level so manage_mcp_server tool can reach it


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


async def _handle_telegram_directive(product_id: str | None, content: str) -> None:
    """Inject a Telegram message into the directive queue, same as the web UI."""
    _ensure_worker(product_id)
    directive_id = uuid.uuid4().hex[:8]
    _directive_queues[product_id].append({"id": directive_id, "content": content})
    _worker_events[product_id].set()
    await _broadcast(_queue_payload(product_id))


# ── First-run workspace bootstrap ────────────────────────────────────────────

async def _bootstrap_product_workspace() -> None:
    """On first install, generate contextual workstreams + objectives via AI.

    Only runs when ADJUTANT_SEED_PRODUCT_ID is set (i.e. installer context) and
    the product has no workstreams yet.  Safe to call on every startup — it
    exits immediately once workstreams exist.
    """
    import logging
    logger = logging.getLogger(__name__)

    product_id   = os.environ.get("ADJUTANT_SEED_PRODUCT_ID", "").strip()
    product_name = os.environ.get("ADJUTANT_SEED_PRODUCT_NAME", "").strip()
    product_desc = os.environ.get("ADJUTANT_SEED_PRODUCT_DESC", "").strip()

    if not product_id or not product_name:
        return  # dev environment — nothing to bootstrap

    if get_workstreams(product_id):
        return  # already bootstrapped

    try:
        ai = anthropic.AsyncAnthropic()
        response = await ai.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=600,
            messages=[{
                "role": "user",
                "content": (
                    f"You are setting up a business workspace for an AI executive assistant.\n\n"
                    f"Business: {product_name}\n"
                    f"Description: {product_desc or 'No description provided'}\n\n"
                    "Generate 3-5 relevant workstreams (ongoing operational areas) and "
                    "2-3 concrete starter objectives (measurable goals to get started).\n\n"
                    "Return JSON only, no explanation:\n"
                    '{"workstreams": ["Marketing", "Sales", "Product"], '
                    '"objectives": ['
                    '{"text": "Reach first 10 paying customers", "target": 10}, '
                    '{"text": "Launch MVP", "target": null}'
                    "]}"
                ),
            }],
        )
        data = json.loads(response.content[0].text)

        for i, name in enumerate(data.get("workstreams", [])):
            status = "running" if i < 2 else "paused"
            create_workstream(product_id, str(name), status)

        for obj in data.get("objectives", []):
            create_objective(
                product_id,
                text=str(obj.get("text", "")),
                progress_target=obj.get("target"),
            )

        logger.info("Bootstrapped workspace for %s: %d workstreams, %d objectives",
                    product_name, len(data.get("workstreams", [])), len(data.get("objectives", [])))

    except Exception as e:
        logger.warning("Workspace bootstrap failed (non-fatal): %s", e)


# ── App lifespan (starts scheduler) ──────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _telegram_bot, _mcp_manager, _telegram_task
    from backend.scheduler import scheduler_loop, register_broadcast
    from backend.telegram import TelegramBot
    from backend.mcp_manager import MCPManager
    from backend.db import list_all_mcp_servers, get_agent_config
    from backend import telegram_state
    register_broadcast(_broadcast)
    scheduler_task = asyncio.create_task(scheduler_loop(_broadcast, interval_seconds=60))

    _tg_cfg    = get_agent_config()
    tg_token   = os.environ.get("TELEGRAM_BOT_TOKEN") or _tg_cfg.get("telegram_bot_token") or ""
    tg_chat_id = os.environ.get("TELEGRAM_CHAT_ID")   or _tg_cfg.get("telegram_chat_id")   or ""

    _telegram_bot = TelegramBot(
        token=tg_token,
        chat_id=tg_chat_id,
        directive_callback=_handle_telegram_directive,
        resolve_review_fn=resolve_review_item,
        broadcast_fn=_broadcast,
    )
    _telegram_task = asyncio.create_task(_telegram_bot.start())

    async def _restart_telegram(token: str, chat_id: str) -> None:
        global _telegram_bot, _telegram_task
        if _telegram_task and not _telegram_task.done():
            _telegram_task.cancel()
            try:
                await asyncio.wait_for(asyncio.shield(_telegram_task), timeout=2)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
        _telegram_bot = TelegramBot(
            token=token,
            chat_id=chat_id,
            directive_callback=_handle_telegram_directive,
            resolve_review_fn=resolve_review_item,
            broadcast_fn=_broadcast,
        )
        _telegram_task = asyncio.create_task(_telegram_bot.start())

    telegram_state.register(_restart_telegram)

    _mcp_manager = MCPManager()
    stdio_servers = [s for s in list_all_mcp_servers() if s["type"] == "stdio" and s["enabled"]]
    await _mcp_manager.start(stdio_servers)

    await _bootstrap_product_workspace()

    yield

    await _mcp_manager.stop()
    tasks_to_cancel = [scheduler_task, _telegram_task, *_worker_tasks.values()]
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


def _get_or_create_session(product_id: str | None) -> str | None:
    """Return the first session for product_id, creating 'General' if none exist.

    Returns None if the product doesn't exist in the DB (e.g. in test environments
    without seeded products) to avoid FK constraint violations.
    """
    session = get_first_session(product_id)
    if session:
        return session["id"]
    try:
        return create_session("General", product_id)
    except Exception:
        return None


def _product_data_payload(product_id: str | None, active_session_id: str | None = None) -> dict:
    # Reconstruct chat history from stored messages for the active session
    if active_session_id is None:
        active_session_id = _get_or_create_session(product_id)
    raw_messages = load_messages(product_id, session_id=active_session_id, limit=100) if active_session_id else load_messages(product_id, limit=100)
    chat_history = []
    for msg in raw_messages:
        role = msg.get("role")
        content = msg.get("content")
        ts = msg.get("ts", "")
        if role == "user" and isinstance(content, str):
            chat_history.append({"type": "directive", "content": content, "ts": ts})
        elif role == "assistant" and isinstance(content, list):
            text = " ".join(
                b["text"] for b in content
                if isinstance(b, dict) and b.get("type") == "text" and b.get("text")
            ).strip()
            if text:
                chat_history.append({"type": "agent", "content": text, "ts": ts})
    sessions = get_sessions(product_id)
    config = get_product_config(product_id) if product_id else {}
    launch_wizard_active = (config or {}).get("launch_wizard_active", 0)
    return {
        "type": "product_data",
        "product_id": product_id,
        "sessions": sessions,
        "active_session_id": active_session_id,
        "workstreams": get_workstreams(product_id) if product_id else [],
        "objectives": get_objectives(product_id) if product_id else [],
        "events": load_activity_events(product_id) if product_id else [],
        "review_items": load_review_items(product_id) if product_id else [],
        "chat_history": chat_history,
        "launch_wizard_active": launch_wizard_active,
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


def _build_context(product_id: str | None, session_id: str | None = None) -> list[dict]:
    """Load context: optional summary block + last KEEP_RECENT messages, scoped to session."""
    purge_broken_tool_exchanges(product_id)  # clean DB before loading
    messages = load_messages(product_id, session_id=session_id, limit=KEEP_RECENT)
    # Strip 'ts' field — it's for UI display only, not a valid Anthropic API field
    messages = [{k: v for k, v in m.items() if k != 'ts'} for m in messages]
    messages = _sanitize_context(messages)
    summary = get_conversation_summary(product_id, session_id=session_id)
    if summary:
        messages = [
            {"role": "user",      "content": f"[Summary of previous conversation]\n{summary}"},
            {"role": "assistant", "content": "Understood — I have context from our prior conversations."},
        ] + messages
    return messages


def _build_user_message(content: str, attachments: list[dict]) -> str | list:
    """Build the user message for the Claude API.

    - No attachments → plain string (existing behaviour).
    - image/* or application/pdf → list of content blocks (file block + text block).
    - video/* or other → plain string with [Attached file: ...] prefix.
    """
    if not attachments:
        return content

    blocks: list[dict] = []
    video_refs: list[str] = []

    for att in attachments:
        path = att.get("path", "")
        mime = att.get("mime_type", "")
        name = att.get("name", path)

        if mime.startswith("image/") or mime == "application/pdf":
            try:
                data = base64.standard_b64encode(Path(path).read_bytes()).decode()
                block_type = "image" if mime.startswith("image/") else "document"
                blocks.append({
                    "type": block_type,
                    "source": {"type": "base64", "media_type": mime, "data": data},
                })
            except OSError:
                video_refs.append(f"[Attached file: {name} — could not read file]")
        else:
            video_refs.append(f"[Attached file: {name} ({path}) ({mime})]")

    if not blocks:
        # All attachments are videos/unknown — inject as text
        prefix = "\n".join(video_refs)
        return f"{prefix}\n\n{content}" if prefix else content

    # Mix of blocks and possibly video refs
    text_parts = video_refs + ([content] if content else [])
    if text_parts:
        blocks.append({"type": "text", "text": "\n\n".join(text_parts)})
    return blocks


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

async def _agent_loop(send_fn, product_id: str | None, messages: list, session_id: str | None = None) -> tuple[list, list]:
    """Run the agent loop. Returns (updated messages, new review items)."""
    if product_id is None:
        system = get_global_system_prompt(get_products())
    else:
        system = get_system_prompt(product_id)
    new_review_items: list[dict] = []

    # Load MCP servers for this product
    from backend.db import list_mcp_servers as _list_mcp_servers
    import json as _json_mcp
    _all_servers = _list_mcp_servers(product_id)
    _enabled_servers = [s for s in _all_servers if s["enabled"]]

    _remote_mcp = [
        {
            "type": "url",
            "url": s["url"],
            "name": s["name"],
            **(_json_mcp.loads(s["env"] or "{}")),
        }
        for s in _enabled_servers if s["type"] == "remote"
    ]
    _stdio_tools = _mcp_manager.get_tools() if _mcp_manager else []
    if product_id is None:
        _all_tools = get_global_tools() + _stdio_tools
    else:
        _all_tools = get_tools_for_product(product_id) + _stdio_tools

    # Read model config fresh so Settings changes take effect without restart
    _live_cfg = _get_agent_config()
    _agent_model = os.environ.get("AGENT_MODEL", _live_cfg["agent_model"])
    _runner.SUBAGENT_MODEL = os.environ.get("AGENT_SUBAGENT_MODEL", _live_cfg["subagent_model"])

    while True:
        accumulated_text = ""

        # Strip any thinking blocks from history — they require the thinking param
        # and would cause API errors without it
        clean_messages = []
        for msg in messages:
            if msg["role"] == "assistant" and isinstance(msg.get("content"), list):
                content = [b for b in msg["content"] if not (isinstance(b, dict) and b.get("type") == "thinking")]
                if content:
                    clean_messages.append({**msg, "content": content})
            else:
                clean_messages.append(msg)

        _stream_kwargs: dict = dict(
            model=_agent_model,
            max_tokens=8096,
            system=system,
            tools=_all_tools,
            messages=clean_messages,
        )
        if _remote_mcp:
            _stream_kwargs["extra_headers"] = {"anthropic-beta": "mcp-client-2025-04-04"}
            _stream_kwargs["extra_body"] = {"mcp_servers": _remote_mcp}

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

        try:
            final = await _run_stream(_stream_kwargs)
        except anthropic.BadRequestError as e:
            if _remote_mcp and "mcp" in str(e).lower():
                # One or more remote MCP servers are misconfigured; retry without them
                await send_fn({
                    "type": "error",
                    "message": "⚠ One or more remote MCP servers failed (check credentials in Settings → MCP Servers). Continuing without them.",
                })
                fallback = {k: v for k, v in _stream_kwargs.items() if k not in ("extra_body", "extra_headers")}
                accumulated_text = ""
                final = await _run_stream(fallback)
            else:
                raise

        if accumulated_text:
            ts = _ts()
            await send_fn({
                "type": "agent_done",
                "product_id": product_id,
                "content": accumulated_text,
                "ts": ts,
            })

        _BLOCK_KEYS = {
            "text":     {"type", "text"},
            "tool_use": {"type", "id", "name", "input"},
        }
        content_serializable = []
        for b in final.content:
            if hasattr(b, "model_dump"):
                d = b.model_dump()
                if d.get("type") == "thinking":
                    continue  # drop thinking blocks from history
                allowed = _BLOCK_KEYS.get(d.get("type", ""), set(d.keys()))
                content_serializable.append({k: v for k, v in d.items() if k in allowed})
            else:
                content_serializable.append(b)
        messages.append({"role": "assistant", "content": content_serializable})
        save_message(product_id, "assistant", content_serializable, session_id)

        if final.stop_reason != "tool_use":
            break

        # ── Execute all tool calls in parallel ───────────────────────────────
        tool_blocks = [b for b in final.content if b.type == "tool_use"]

        async def _run_one_tool(block) -> dict:
            """Execute one tool call and handle activity events / side-effects."""
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
                    # Must register before _broadcast so notify() sees it when agent_done fires
                    if _telegram_bot:
                        _telegram_bot._pending_products.add(target_id)
                    await _broadcast(_queue_payload(target_id))
                    out = f"Dispatched to {known[target_id]['name']}"
                return {"type": "tool_result", "tool_use_id": block.id, "content": out}

            is_agent_task = block.name == "delegate_task"
            is_review     = block.name == "create_review_item"
            ev_id = None

            if is_agent_task:
                headline   = block.input.get("task", block.name)
                rationale  = block.input.get("context", "")
                agent_type = block.input.get("agent_type", "general")
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
                if block.name.startswith("mcp__") and _mcp_manager is not None:
                    output = await _mcp_manager.execute_tool(block.name, block.input)
                else:
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
                    from backend.db import get_autonomy_config, resolve_review_item, set_auto_approve_at
                    from datetime import datetime, timedelta
                    action_type_val = block.input.get("action_type", "agent_review")
                    tier, window_minutes = get_autonomy_config(product_id, action_type_val)
                    if tier == "auto":
                        resolve_review_item(item_id, "approved")
                        await send_fn({"type": "review_resolved", "review_item_id": item_id, "action": "auto_approved"})
                    else:
                        if tier == "window":
                            deadline = datetime.utcnow() + timedelta(minutes=window_minutes or 10)
                            set_auto_approve_at(item_id, deadline)
                            deadline_str = deadline.isoformat(timespec="seconds") + "Z"
                        else:
                            deadline_str = None
                        item = {
                            "id": item_id,
                            "title": block.input.get("title", ""),
                            "description": block.input.get("description", ""),
                            "risk_label": block.input.get("risk_label", ""),
                            "action_type": action_type_val,
                            "auto_approve_at": deadline_str,
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
                    parsed    = json.loads(output)
                    review_id = parsed.get("review_item_id")
                    pid       = block.input.get("product_id", product_id)
                    if review_id:
                        from backend.db import get_autonomy_config, resolve_review_item, set_auto_approve_at
                        from datetime import datetime, timedelta
                        tier, window_minutes = get_autonomy_config(pid, "social_post")
                        if tier == "auto":
                            resolve_review_item(review_id, "approved")
                            await send_fn({"type": "review_resolved", "review_item_id": review_id, "action": "auto_approved"})
                        else:
                            if tier == "window":
                                deadline = datetime.utcnow() + timedelta(minutes=window_minutes or 10)
                                set_auto_approve_at(review_id, deadline)
                                deadline_str = deadline.isoformat(timespec="seconds") + "Z"
                            else:
                                deadline_str = None
                            item = {
                                "id": review_id,
                                "title": f"Post to {block.input.get('platform', '').capitalize()}",
                                "description": block.input.get("content", "")[:200],
                                "risk_label": f"Social post · {block.input.get('platform', '')} · public-facing",
                                "action_type": "social_post",
                                "auto_approve_at": deadline_str,
                                "status": "pending", "created_at": _ts(),
                            }
                            await send_fn({"type": "review_item_added", "product_id": pid, "item": item})
                            new_review_items.append(item)
                except (json.JSONDecodeError, KeyError):
                    pass

            if block.name == "report_wizard_progress":
                await send_fn({
                    "type": "wizard_progress",
                    "product_id": product_id,
                    "message": block.input.get("message", ""),
                })

            if block.name == "complete_launch":
                pid = block.input.get("product_id", product_id)
                await send_fn({
                    "type": "launch_complete",
                    "product_id": pid,
                    "summary": block.input.get("summary", ""),
                })
                await send_fn(_product_data_payload(pid))

            return {"type": "tool_result", "tool_use_id": block.id, "content": output}

        # Run all tool calls concurrently; results preserve original order
        tool_results = list(await asyncio.gather(*[_run_one_tool(b) for b in tool_blocks]))

        if tool_results:
            messages.append({"role": "user", "content": tool_results})
            save_message(product_id, "user", tool_results, session_id)

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

            session_id = directive.get("session_id") or _get_or_create_session(product_id)
            # Verify session still exists (may have been deleted while queued)
            if session_id and not get_session_by_id(session_id):
                session_id = _get_or_create_session(product_id)
            messages = _build_context(product_id, session_id=session_id)
            attachments = directive.get("attachments") or []
            user_message_content = _build_user_message(directive["content"], attachments)
            messages.append({"role": "user", "content": user_message_content})
            save_message(product_id, "user", directive["content"], session_id)

            try:
                inner = asyncio.create_task(_agent_loop(_broadcast, product_id, messages, session_id=session_id))
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


def _ensure_worker(product_id: str | None) -> None:
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

    active_product_id = ""
    active_session_id: str | None = None

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
                product_id = msg.get("product_id") or None  # null from JS → None (global)
                active_product_id = product_id
                active_session_id = _get_or_create_session(product_id)
                await _send(ws, _product_data_payload(product_id, active_session_id))
                if product_id is not None:
                    await _send(ws, _queue_payload(product_id))

            elif msg_type == "directive":
                product_id = msg.get("product_id") or None  # null from JS → None (global)
                if product_id is not None:
                    known_ids = {p["id"] for p in get_products()}
                    if product_id not in known_ids:
                        await _send(ws, {"type": "error", "message": f"Unknown product: {product_id}"})
                        continue
                active_product_id = product_id
                content = msg.get("content", "").strip()
                attachments = msg.get("attachments") or []
                if not content and not attachments:
                    continue

                # Echo to chat immediately so it appears in the feed right away
                await _send(ws, {
                    "type": "directive_echo",
                    "product_id": product_id,
                    "content": content,
                    "ts": _ts(),
                })

                # Save to directive history for replay (global directives have no product)
                if product_id is not None:
                    from backend.db import save_directive_history
                    save_directive_history(product_id, content)

                # Enqueue and ensure worker is running
                directive_id = uuid.uuid4().hex[:8]
                _ensure_worker(product_id)
                # Prefer session_id from the client message (client knows current session);
                # fall back to server-tracked active_session_id if not provided
                msg_session_id = msg.get("session_id") or active_session_id
                _directive_queues[product_id].append({
                    "id": directive_id,
                    "content": content,
                    "attachments": attachments,
                    "session_id": msg_session_id,
                })
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

            elif msg_type == "create_session":
                product_id = msg.get("product_id", active_product_id) or None
                name = (msg.get("name") or "New Session").strip()
                if not name:
                    name = "New Session"
                try:
                    new_sid = create_session(name, product_id)
                except Exception:
                    new_sid = create_session(name, active_product_id or None)
                active_session_id = new_sid
                all_sessions = get_sessions(product_id or active_product_id)
                session_obj = next(
                    (s for s in all_sessions if s["id"] == new_sid),
                    {"id": new_sid, "name": name, "product_id": product_id, "created_at": ""}
                )
                await _broadcast({"type": "session_created", "session": session_obj})
                # Also send switched so client loads the (empty) history
                await _send(ws, {"type": "session_switched", "session_id": new_sid, "chat_history": []})

            elif msg_type == "switch_session":
                new_sid = msg.get("session_id")
                if not new_sid:
                    continue
                session_obj = get_session_by_id(new_sid)
                if session_obj is None:
                    # Session was deleted; fall back to current session
                    continue
                active_session_id = new_sid
                session_product_id = session_obj.get("product_id") or active_product_id
                history = load_messages(session_product_id, session_id=new_sid, limit=100)
                chat_history = []
                for msg_item in history:
                    role = msg_item.get("role")
                    content = msg_item.get("content")
                    ts = msg_item.get("ts", "")
                    if role == "user" and isinstance(content, str):
                        chat_history.append({"type": "directive", "content": content, "ts": ts})
                    elif role == "assistant" and isinstance(content, list):
                        text = " ".join(
                            b["text"] for b in content
                            if isinstance(b, dict) and b.get("type") == "text" and b.get("text")
                        ).strip()
                        if text:
                            chat_history.append({"type": "agent", "content": text, "ts": ts})
                await _send(ws, {"type": "session_switched", "session_id": new_sid, "chat_history": chat_history})

            elif msg_type == "rename_session":
                sid = msg.get("session_id")
                name = (msg.get("name") or "").strip()
                if sid and name:
                    rename_session(sid, name)
                    await _broadcast({"type": "session_renamed", "session_id": sid, "name": name})

            elif msg_type == "delete_session":
                sid = msg.get("session_id")
                if not sid:
                    continue
                delete_session(sid)
                # Ensure at least one session exists
                next_sid = _get_or_create_session(active_product_id)
                if active_session_id == sid:
                    active_session_id = next_sid
                await _broadcast({"type": "session_deleted", "session_id": sid, "next_session_id": next_sid})

            elif msg_type == "launch_product":
                import re as _re
                name = (msg.get("name") or "").strip()
                if not name:
                    continue
                description = (msg.get("description") or "").strip()
                primary_goal = (msg.get("primary_goal") or "").strip()

                # Generate slug from name (lowercase, hyphens, no special chars)
                slug = _re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "product"
                existing_ids = {p["id"] for p in get_products()}
                base_slug = slug
                counter = 1
                while slug in existing_ids:
                    slug = f"{base_slug}-{counter}"
                    counter += 1

                icon_label = name[:2].upper()
                color = "#6366f1"  # default indigo

                _create_product_db(slug, name, icon_label, color)
                set_launch_wizard_active(slug, True)

                # Create dedicated wizard session
                wizard_session_id = create_session(f"Launch: {name}", slug)

                # Broadcast updated product list to all clients
                await _broadcast({"type": "init", "products": get_products()})

                # Send full product state to this client (wizard mode)
                await _send(ws, _product_data_payload(slug, wizard_session_id))

                # Signal this client to switch to the new product
                await _send(ws, {"type": "launch_started", "product_id": slug})

                # Fire wizard in background
                from backend.scheduler import _run_launch_wizard
                asyncio.create_task(
                    _run_launch_wizard(slug, wizard_session_id, description, primary_goal)
                )

            elif msg_type == "set_objective_autonomous":
                obj_id   = msg.get("objective_id")
                auto_val = msg.get("autonomous", False)
                if obj_id is None:
                    continue
                set_objective_autonomous(int(obj_id), bool(auto_val))
                obj = get_objective_by_id(int(obj_id))
                if obj:
                    await _broadcast(_product_data_payload(obj["product_id"]))

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
                                result = await _publish_social_draft(draft)
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

                    # Resume any autonomous objective that was blocked by this review
                    blocked_obj = get_objective_blocked_by_review(item_id)
                    if blocked_obj:
                        clear_objective_block(blocked_obj["id"])
                        from backend.scheduler import _run_objective_loop
                        asyncio.create_task(
                            _run_objective_loop(blocked_obj["product_id"], blocked_obj["id"])
                        )

            elif msg_type == "cancel_auto_approve":
                item_id = msg.get("review_item_id")
                if item_id:
                    from backend.db import clear_auto_approve_at, get_review_item_by_id
                    clear_auto_approve_at(item_id)
                    item = get_review_item_by_id(item_id)
                    if item:
                        await _broadcast({
                            "type": "review_item_updated",
                            "product_id": item["product_id"],
                            "item": item,
                        })

    except WebSocketDisconnect:
        pass
    finally:
        _connections.discard(ws)


# ── Static UI ──────────────────────────────────────────────────────────────────

if UI_DIST.exists():
    app.mount("/", StaticFiles(directory=UI_DIST, html=True), name="ui")
