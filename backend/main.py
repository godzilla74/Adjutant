# backend/main.py
"""Adjutant — FastAPI backend (multi-product)."""

import asyncio
import base64
import json
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

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
    list_oauth_connections,
    record_token_usage as _record_token_usage,
    get_product_model_config as _get_product_model_config,
)
from backend.api import router as api_router


def _inject_datetime(messages: list[dict]) -> list[dict]:
    """Prepend current datetime to the last user message so the system prompt stays static."""
    prefix = f"[Current datetime: {datetime.now().strftime('%A, %B %d, %Y at %I:%M %p')}]\n\n"
    result = list(messages)
    for i in range(len(result) - 1, -1, -1):
        msg = result[i]
        if msg["role"] == "user":
            if isinstance(msg.get("content"), str):
                result[i] = {**msg, "content": prefix + msg["content"]}
            elif isinstance(msg.get("content"), list):
                result[i] = {**msg, "content": [{"type": "text", "text": prefix}] + list(msg["content"])}
            break
    return result


def _add_cache_control(system_text: str, tools: list[dict]) -> tuple[list[dict], list[dict]]:
    """Wrap system prompt as a cached content block and mark the last tool as cached."""
    system_list = [{"type": "text", "text": system_text, "cache_control": {"type": "ephemeral"}}]
    if not tools:
        return system_list, []
    tools_out = list(tools)
    tools_out[-1] = {**tools_out[-1], "cache_control": {"type": "ephemeral"}}
    return system_list, tools_out


_SOCIAL_PLATFORMS = {"twitter", "linkedin", "facebook", "instagram"}


def _compute_available_groups(product_id: str) -> list[str]:
    """Return tool group names available for this product based on OAuth connections."""
    connections = {c["service"] for c in list_oauth_connections(product_id)}
    groups = ["core", "management", "system"]
    if "gmail" in connections:
        groups.append("email")
    if "google_calendar" in connections:
        groups.append("calendar")
    if connections & _SOCIAL_PLATFORMS:
        groups.append("social")
    return groups


async def _do_publish_draft(draft: dict) -> None:
    """Fire a social draft immediately: saves activity events and calls _publish_social_draft."""
    pid = draft.get("product_id")
    platform = draft.get("platform", "unknown")
    event_id = save_activity_event(
        product_id=pid, agent_type="social",
        headline=f"Publishing to {platform.capitalize()}",
        rationale="Social post approved — publishing now",
        status="running",
    )
    await _broadcast({"type": "activity_started", "product_id": pid, "id": event_id,
                      "agent_type": "social", "headline": f"Publishing to {platform.capitalize()}",
                      "rationale": "Social post approved — publishing now", "ts": _ts()})
    try:
        result = await _publish_social_draft(draft)
    except Exception as exc:
        result = {"success": False, "error": str(exc)}
    new_status = "posted" if result["success"] else "failed"
    update_social_draft_status(draft["id"], new_status, result.get("post_url"))
    summary = (f"Posted to {platform.capitalize()}. {result.get('post_url', '')}"
               if result["success"] else f"Failed to post: {result.get('error', 'Unknown error')}")
    update_activity_event(event_id, status="done", summary=summary)
    await _broadcast({"type": "activity_done", "product_id": pid, "id": event_id,
                      "summary": summary, "ts": _ts()})


async def _on_review_approved(item_id: int) -> None:
    """Publish a linked social draft (if any) and resume blocked objectives after approval."""
    draft = get_social_draft_by_review_item(item_id)
    if draft:
        scheduled_for = draft.get("scheduled_for")
        if scheduled_for:
            try:
                fire_at = datetime.fromisoformat(scheduled_for)
            except ValueError:
                fire_at = None
            if fire_at:
                now = datetime.now(timezone.utc)
                fire_at_cmp = fire_at.replace(tzinfo=timezone.utc) if fire_at.tzinfo is None else fire_at
                is_future = fire_at_cmp > now
            else:
                is_future = False
            if is_future:
                # Defer — scheduler will publish when the time comes
                update_social_draft_status(draft["id"], "scheduled")
                pid = draft.get("product_id")
                platform = draft.get("platform", "unknown")
                await _broadcast({
                    "type": "activity_done",
                    "product_id": pid,
                    "id": None,
                    "summary": f"Scheduled {platform.capitalize()} post for {scheduled_for}",
                    "ts": _ts(),
                })
            else:
                await _do_publish_draft(draft)
        else:
            await _do_publish_draft(draft)
        return

    blocked_obj = get_objective_blocked_by_review(item_id)
    if blocked_obj:
        clear_objective_block(blocked_obj["id"])
        from backend.scheduler import _run_objective_loop
        asyncio.create_task(_run_objective_loop(blocked_obj["product_id"], blocked_obj["id"]))
        return

    # No social draft and no blocked objective
    from backend.db import get_review_item_by_id
    review = get_review_item_by_id(item_id)
    if not review:
        return

    # Email items: require a stored payload for direct execution
    if review.get("action_type") == "email":
        payload_raw = review.get("payload")
        params = None
        if payload_raw:
            try:
                params = json.loads(payload_raw)
            except (ValueError, KeyError):
                params = None

        pid = review["product_id"]
        if params and params.get("to") and params.get("subject") and params.get("body"):
            # Full payload present — execute directly without spawning an agent
            event_id = save_activity_event(
                product_id=pid,
                agent_type="email",
                headline=f"Sending: {review['title']}",
                rationale=review.get("description", ""),
                status="running",
            )
            await _broadcast({"type": "activity_started", "product_id": pid, "id": event_id,
                              "agent_type": "email", "headline": f"Sending: {review['title']}",
                              "rationale": review.get("description", ""), "ts": _ts()})
            try:
                from backend.google_api import gmail_send
                await gmail_send(
                    pid, params["to"], params["subject"], params["body"],
                    params.get("thread_id"),
                )
                summary = f"Sent to {params['to']}"
            except Exception as exc:
                summary = f"Failed to send: {exc}"
            update_activity_event(event_id, status="done", summary=summary)
            await _broadcast({"type": "activity_done", "product_id": pid, "id": event_id,
                              "summary": summary, "ts": _ts()})
        else:
            # No payload (legacy item created before payload column existed) — cannot recover
            event_id = save_activity_event(
                product_id=pid,
                agent_type="email",
                headline=f"Cannot send: {review['title']}",
                rationale="This review item was created before full email content was stored. The original email body is not available.",
                status="done",
            )
            await _broadcast({"type": "activity_done", "product_id": pid, "id": event_id,
                              "summary": "Cannot send: email body not stored (legacy item). Please compose and send the email manually.",
                              "ts": _ts()})
        return

    # Generic fallback: spawn task agent for any other action_type
    if review.get("action_type"):
        from backend.scheduler import _run_approved_review_task
        asyncio.create_task(_run_approved_review_task(review["product_id"], review))


_BROWSER_OUTCOME_SUFFIX = (
    "\n\nWhen finished, respond with exactly one of these two lines as your final line:\n"
    "SUCCESS: <post URL or 'posted'>\n"
    "FAILED: <brief reason>"
)

def _parse_browser_result(raw: str) -> dict:
    """Parse a browser_task result. execute_tool wraps output in JSON; unwrap first."""
    text = raw
    try:
        parsed = json.loads(raw)
        text = parsed.get("result") or parsed.get("error") or raw
    except (json.JSONDecodeError, TypeError):
        pass
    for line in reversed(text.strip().splitlines()):
        line = line.strip()
        if line.startswith("SUCCESS:"):
            url = line[len("SUCCESS:"):].strip()
            return {"success": True, "post_url": url if url and url != "posted" else None, "result": text}
        if line.startswith("FAILED:"):
            reason = line[len("FAILED:"):].strip()
            return {"success": False, "error": reason or "Browser task reported failure"}
    # No structured outcome line — surface the actual text so the user sees what happened
    return {"success": False, "error": text.strip()[:400] if text else "Browser task returned no output"}


def _inject_creds(task: str, cred: dict | None) -> str:
    """Append login credentials to a browser task prompt if available."""
    if cred and cred.get("username"):
        detail = (
            f"username/email: {cred['username']}, "
            f"password: {cred.get('password', '')}"
        )
        if cred.get("handle"):
            detail += f", phone/handle: {cred['handle']}"
        task += (
            f"\n\nLogin credentials — {detail}. "
            f"Use these to fill the login form directly. "
            f"Do NOT use 'Sign in with Google' or other OAuth flows. "
            f"If prompted for a phone number or username to verify your identity, "
            f"use the phone/handle value provided above."
        )
    return task


async def _browser_post(task_text: str, cred: dict | None) -> dict:
    """Run a browser task with optional credential injection and parse the result."""
    task_text = _inject_creds(task_text, cred)
    task_text += _BROWSER_OUTCOME_SUFFIX
    return _parse_browser_result(await execute_tool("browser_task", {"task": task_text}))


async def _publish_social_draft(draft: dict) -> dict:
    """Post an approved social draft. Browser mode (with credentials) takes priority over OAuth API."""
    from backend.social_api import twitter_post, linkedin_post, facebook_post, instagram_post
    from backend.db import get_oauth_connection, get_browser_credential
    platform = draft.get("platform", "")
    product_id = draft.get("product_id", "")
    text = draft.get("content", "")
    image_url = draft.get("image_url") or None

    cred = get_browser_credential(product_id, platform)
    browser_active = bool(cred and cred.get("active"))

    try:
        if platform == "twitter":
            if browser_active:
                task = (
                    f"Post the following tweet on X (twitter.com).\n\n"
                    f"Steps:\n"
                    f"1. Navigate to https://x.com/compose/tweet\n"
                    f"2. Click inside the tweet text area to focus it\n"
                    f"3. Type the following tweet text EXACTLY — do NOT press any keyboard shortcuts "
                    f"(no Ctrl+B, no formatting keys) while the compose box is focused:\n\n"
                    f"{text}\n\n"
                    f"4. Before posting, verify the text in the compose box matches the above exactly\n"
                    f"5. Click the Post button"
                )
                if image_url:
                    task += f"\n\nAlso attach this media before posting: {image_url}"
                return await _browser_post(task, cred)
            elif get_oauth_connection(product_id, "twitter"):
                return {"success": True, "result": await twitter_post(product_id, text, image_url)}
            else:
                task = (
                    f"Post the following tweet on X (twitter.com).\n\n"
                    f"Steps:\n"
                    f"1. Navigate to https://x.com/compose/tweet\n"
                    f"2. Click inside the tweet text area to focus it\n"
                    f"3. Type the following tweet text EXACTLY — do NOT press any keyboard shortcuts "
                    f"(no Ctrl+B, no formatting keys) while the compose box is focused:\n\n"
                    f"{text}\n\n"
                    f"4. Before posting, verify the text in the compose box matches the above exactly\n"
                    f"5. Click the Post button"
                )
                if image_url:
                    task += f"\n\nAlso attach this media before posting: {image_url}"
                return await _browser_post(task, None)
        elif platform == "linkedin":
            if browser_active:
                task = f"Post the following to LinkedIn (linkedin.com).\n\nPost text:\n{text}"
                if image_url:
                    task += f"\n\nAttach this image: {image_url}"
                return await _browser_post(task, cred)
            elif get_oauth_connection(product_id, "linkedin"):
                return {"success": True, "result": await linkedin_post(product_id, text, image_url)}
            else:
                task = f"Post the following to LinkedIn (linkedin.com).\n\nPost text:\n{text}"
                if image_url:
                    task += f"\n\nAttach this image: {image_url}"
                return await _browser_post(task, None)
        elif platform == "facebook":
            if browser_active:
                task = f"Post the following to Facebook (facebook.com).\n\nPost text:\n{text}"
                if image_url:
                    task += f"\n\nAttach this image: {image_url}"
                return await _browser_post(task, cred)
            elif get_oauth_connection(product_id, "facebook"):
                return {"success": True, "result": await facebook_post(product_id, text, image_url)}
            else:
                task = f"Post the following to Facebook (facebook.com).\n\nPost text:\n{text}"
                if image_url:
                    task += f"\n\nAttach this image: {image_url}"
                return await _browser_post(task, None)
        elif platform == "instagram":
            if not image_url:
                return {"success": False, "error": "Instagram requires an image URL"}
            if browser_active:
                task = (
                    f"Post the following to Instagram (instagram.com).\n\n"
                    f"Caption:\n{text}\n\nImage URL: {image_url}\n\n"
                    f"Download or use the image at that URL for the post."
                )
                return await _browser_post(task, cred)
            elif get_oauth_connection(product_id, "instagram"):
                return {"success": True, "result": await instagram_post(product_id, text, image_url)}
            else:
                task = (
                    f"Post the following to Instagram (instagram.com).\n\n"
                    f"Caption:\n{text}\n\nImage URL: {image_url}\n\n"
                    f"Download or use the image at that URL for the post."
                )
                return await _browser_post(task, None)
        else:
            return {"success": False, "error": f"Unknown platform: {platform}"}
    except RuntimeError as e:
        return {"success": False, "error": str(e)}
from core.config import get_system_prompt, get_global_system_prompt
from core.tools import execute_tool, get_tools_for_product, get_tools_for_groups, get_global_tools, get_capability_override_context
from core.prescreener import prescreen as _prescreen

init_db()

# Model config is read fresh per invocation in _agent_loop so settings changes
# take effect without a restart. These imports are needed at module level.
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
        from backend.provider import make_provider, get_provider_name
        from backend.db import get_agent_config
        _cfg = get_agent_config()
        _agent_model = _cfg.get("agent_model", "claude-haiku-4-5-20251001")
        _bootstrap_model = (
            "gpt-4o-mini" if get_provider_name(_agent_model) == "openai"
            else "claude-haiku-4-5-20251001"
        )
        _provider = make_provider(_bootstrap_model)
        response = await _provider.create(
            model=_bootstrap_model,
            system="",
            messages=[{
                "role": "user",
                "content": (
                    f"You are setting up a business workspace for an AI chief of staff.\n\n"
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
        on_review_approved_fn=_on_review_approved,
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
            on_review_approved_fn=_on_review_approved,
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


async def _maybe_compact(product_id: str | None) -> None:
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
    from backend.provider import make_provider as _make_provider_compact
    _agent_name = _gac()["agent_name"]
    _compact_cfg = _get_product_model_config(product_id)
    _compact_model = _compact_cfg["prescreener_model"]
    _compact_provider = _make_provider_compact(_compact_model)
    resp = await _compact_provider.create(
        model=_compact_model,
        system="",
        messages=[{
            "role": "user",
            "content": (
                f"You are summarizing a conversation between a user and {_agent_name}, an AI chief of staff. "
                "Produce a compact context block covering: decisions made, tasks assigned or completed, "
                "key facts shared about products/workstreams/goals, ongoing work, and any user preferences. "
                "Be concise but comprehensive — this summary replaces the full history.\n\n"
                f"{context_block}{transcript}"
            ),
        }],
        max_tokens=1024,
    )
    _record_token_usage(product_id, "compaction", _compact_provider.name, _compact_model, resp.usage)
    new_summary = resp.content[0].text.strip()
    save_conversation_summary(product_id, new_summary)
    delete_messages_by_ids(product_id, ids_to_remove)


# ── Pre-flight interceptor ────────────────────────────────────────────────────

def _build_preflight_interceptor(disconnected_overrides: dict[str, str]):
    """Return an async callable that checks for disconnected MCP overrides before tool dispatch.

    Returns None if the tool should proceed normally, or a tool_result dict with a
    reconnect/fallback prompt if the override server is disconnected.
    """
    async def check(block) -> dict | None:
        server_name = disconnected_overrides.get(block.name)
        if server_name is None:
            return None
        if block.input.get("force_builtin"):
            return None
        msg = (
            f"The MCP server '{server_name}' configured to handle this action is currently "
            f"disconnected. Would you like to: (1) reconnect it in Settings → MCP Servers, "
            f"or (2) proceed using the built-in tool by re-calling with force_builtin=true?"
        )
        return {"type": "tool_result", "tool_use_id": block.id, "content": msg}
    return check


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
    _enabled_remote_servers = [
        (s, _json_mcp.loads(s["env"] or "{}"))
        for s in _all_servers if s["enabled"] and s["type"] == "remote"
    ]
    _stdio_tools = _mcp_manager.get_tools() if _mcp_manager else []
    if product_id is None:
        _all_tools = get_global_tools() + _stdio_tools
        _disconnected_overrides: dict[str, str] = {}
    else:
        _connected_server_names = _mcp_manager.get_connected_server_names() if _mcp_manager else set()
        _suppress, _disconnected_overrides = get_capability_override_context(product_id, _connected_server_names)
        _base_tools = get_tools_for_product(product_id)
        _all_tools = [t for t in _base_tools if t["name"] not in _suppress] + _stdio_tools

    _preflight = _build_preflight_interceptor(_disconnected_overrides)

    # Read model config fresh so Settings changes take effect without restart
    from backend.provider import make_provider as _make_provider
    _model_cfg = _get_product_model_config(product_id)
    _agent_model = os.environ.get("AGENT_MODEL", _model_cfg["agent_model"])
    _runner.SUBAGENT_MODEL = os.environ.get("AGENT_SUBAGENT_MODEL", _model_cfg["subagent_model"])
    _prescreener_model = os.environ.get("AGENT_PRESCREENER_MODEL", _model_cfg["prescreener_model"])
    _provider = _make_provider(_agent_model)
    _pre_provider = _make_provider(_prescreener_model)

    # Build provider-appropriate remote MCP entries
    def _build_anthropic_mcp_entry(s: dict, env: dict) -> dict:
        url = s["url"]
        # Embed extra headers as query params — Anthropic only supports authorization_token
        extra_hdrs: dict = env.get("headers") or {}
        if extra_hdrs:
            from urllib.parse import urlparse, urlunparse, parse_qs, urlencode as _ue
            parsed = urlparse(url)
            existing = parse_qs(parsed.query, keep_blank_values=True)
            for k, v in extra_hdrs.items():
                if k not in existing:
                    existing[k] = [v]
            url = urlunparse(parsed._replace(query=_ue({k: v[0] for k, v in existing.items()})))
        entry: dict = {"type": "url", "url": url, "name": s["name"]}
        raw = env.get("authorization_token") or env.get("authorization")
        if isinstance(raw, dict):
            raw = raw.get("token", "")
        if raw:
            # Anthropic constructs "Authorization: Bearer <authorization_token>" itself,
            # so provide only the raw token — strip any Bearer prefix already present.
            if raw.lower().startswith("bearer "):
                raw = raw[7:]
            entry["authorization_token"] = raw
        return entry

    def _build_openai_mcp_entry(s: dict, env: dict) -> dict:
        import re as _re
        headers: dict = {}
        raw = env.get("authorization_token") or env.get("authorization")
        if isinstance(raw, dict):
            raw = raw.get("token", "")
        if raw:
            token = raw if raw.lower().startswith("bearer ") else f"Bearer {raw}"
            headers["Authorization"] = token
        # Pass extra headers (locationId, etc.) natively — OpenAI MCP supports arbitrary headers
        extra_hdrs: dict = env.get("headers") or {}
        headers.update(extra_hdrs)
        # Also pick up top-level env keys that aren't auth/headers (e.g. locationId stored flat)
        skip = {"authorization_token", "authorization", "headers"}
        for k, v in env.items():
            if k not in skip and k not in headers:
                headers[k] = v
        label = _re.sub(r"[^a-z0-9_-]", "_", s["name"].lower())[:64]
        entry: dict = {"type": "mcp", "server_label": label, "server_url": s["url"], "require_approval": "never"}
        if headers:
            entry["headers"] = headers
        return entry

    _remote_mcp: list = []
    _openai_mcp_tools: list = []
    for _s, _env in _enabled_remote_servers:
        if _provider.name == "anthropic":
            _entry = _build_anthropic_mcp_entry(_s, _env)
            _remote_mcp.append(_entry)
            print(f"[mcp] anthropic entry: name={_entry['name']} url={_entry['url']} has_token={'authorization_token' in _entry}", flush=True)
        else:
            _entry = _build_openai_mcp_entry(_s, _env)
            _openai_mcp_tools.append(_entry)
            print(f"[mcp] openai entry: label={_entry['server_label']} url={_entry['server_url']} headers={list(_entry.get('headers', {}).keys())}", flush=True)

    # Extract last user message for prescreener BEFORE datetime injection
    _last_user_msg_for_prescreener = next(
        (m["content"] for m in reversed(messages)
         if m["role"] == "user" and isinstance(m.get("content"), str)),
        "",
    )
    messages = _inject_datetime(messages)

    # Pre-screen user message with a cheap model to route simple replies
    # and prune the tool list. Only applies to product agents.
    if product_id is not None:
        _available_groups = _compute_available_groups(product_id)
        if _last_user_msg_for_prescreener:
            _pre = await _prescreen(_last_user_msg_for_prescreener, _available_groups, _pre_provider, _prescreener_model)
            _record_token_usage(product_id, "prescreener", _pre_provider.name, _prescreener_model, _pre.usage)

            if _pre.route == "haiku":
                _ts_val = _ts()
                await send_fn({"type": "agent_token", "product_id": product_id, "content": _pre.response})
                await send_fn({"type": "agent_done", "product_id": product_id, "content": _pre.response, "ts": _ts_val})
                messages = messages + [{"role": "assistant", "content": _pre.response, "ts": _ts_val}]
                save_message(product_id, "assistant", _pre.response, session_id)
                return messages, new_review_items

            # Sonnet route: replace _all_tools with pruned list
            _pruned = get_tools_for_groups(_pre.tool_groups, product_id)
            _all_tools = [t for t in _pruned if t["name"] not in _suppress] + _stdio_tools

    while True:
        accumulated_text = ""

        # Strip block types that are invalid as API inputs.
        # - thinking: requires the thinking param which we don't set
        # - mcp_tool_use / mcp_tool_result: valid in responses but not accepted as history input
        _STRIP_TYPES = {"thinking", "mcp_tool_use", "mcp_tool_result"}
        clean_messages = []
        for msg in messages:
            if isinstance(msg.get("content"), list):
                content = [b for b in msg["content"] if not (isinstance(b, dict) and b.get("type") in _STRIP_TYPES)]
                if content:
                    clean_messages.append({**msg, "content": content})
            else:
                clean_messages.append(msg)

        _system_cached, _tools_cached = _add_cache_control(system, _all_tools)
        _stream_kwargs: dict = dict(
            model=_agent_model,
            max_tokens=8096,
            system=_system_cached,
            tools=_tools_cached,
            messages=clean_messages,
        )
        if _remote_mcp:
            _stream_kwargs["extra_headers"] = {"anthropic-beta": "mcp-client-2025-04-04"}
            _stream_kwargs["extra_body"] = {"mcp_servers": _remote_mcp}
        if _openai_mcp_tools:
            _stream_kwargs["openai_mcp_tools"] = _openai_mcp_tools

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
                openai_mcp_tools=kwargs.get("openai_mcp_tools"),
            )

        import anthropic as _anthropic
        _has_mcp = bool(_remote_mcp or _openai_mcp_tools)
        try:
            final = await _run_stream(_stream_kwargs)
            _record_token_usage(product_id, "agent", _provider.name, _agent_model, final.usage)
        except (_anthropic.BadRequestError, RuntimeError) as e:
            if _has_mcp and ("mcp" in str(e).lower() or "400" in str(e)):
                print(f"[mcp] Error with remote MCP servers: {e}", flush=True)
                await send_fn({
                    "type": "error",
                    "message": f"⚠ One or more remote MCP servers failed: {e}. Continuing without them.",
                })
                fallback = {k: v for k, v in _stream_kwargs.items()
                            if k not in ("extra_body", "extra_headers", "openai_mcp_tools")}
                accumulated_text = ""
                final = await _run_stream(fallback)
                _record_token_usage(product_id, "agent", _provider.name, _agent_model, final.usage)
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
        _DROP_TYPES = {"thinking", "mcp_tool_use", "mcp_tool_result"}
        content_serializable = []
        for b in final.content:
            if hasattr(b, "model_dump"):
                d = b.model_dump()
                if d.get("type") in _DROP_TYPES:
                    continue
                allowed = _BLOCK_KEYS.get(d.get("type", ""), set(d.keys()))
                content_serializable.append({k: v for k, v in d.items() if k in allowed})
            else:
                content_serializable.append(b)
        if content_serializable:
            messages.append({"role": "assistant", "content": content_serializable})
            save_message(product_id, "assistant", content_serializable, session_id)

        if final.stop_reason != "tool_use":
            break

        # ── Execute all tool calls in parallel ───────────────────────────────
        # mcp_tool_use blocks are handled server-side by Anthropic; only dispatch
        # regular tool_use blocks ourselves.
        tool_blocks = [b for b in final.content if b.type == "tool_use"]
        if not tool_blocks:
            break  # stop_reason was tool_use but all calls were MCP (server-side)

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

            # Pre-flight: check for disconnected MCP override BEFORE writing any activity events
            intercepted = await _preflight(block)
            if intercepted is not None:
                return intercepted

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
                    result = await execute_tool(block.name, block.input, product_id=product_id)
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
                                "scheduled_for": parsed.get("scheduled_for"),
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

def _queue_payload(product_id: str | None) -> dict:
    return {
        "type": "queue_update",
        "product_id": product_id,
        "current": _current_directive.get(product_id),
        "queued": list(_directive_queues.get(product_id, [])),
    }


async def _product_worker(product_id: str | None) -> None:
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

                    if action == "approved":
                        await _on_review_approved(item_id)

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

# Serve generated/uploaded images
from backend.uploads import get_uploads_dir as _get_uploads_dir
app.mount("/uploads", StaticFiles(directory=str(_get_uploads_dir())), name="uploads")

if UI_DIST.exists():
    app.mount("/", StaticFiles(directory=UI_DIST, html=True), name="ui")
