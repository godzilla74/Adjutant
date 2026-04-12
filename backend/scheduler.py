# backend/scheduler.py
"""Autonomous workstream scheduler.

Runs as a background asyncio task started from main.py lifespan.
Each workstream with a mission + schedule fires its own agent on time.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Awaitable, Callable

log = logging.getLogger(__name__)

# Per-workstream in-flight guard (asyncio is single-threaded — no lock needed)
_running: dict[int, bool] = {}

# Per-objective in-flight guard
_running_objectives: dict[int, bool] = {}

# Per-product launch wizard in-flight guard
_running_wizards: dict[str, bool] = {}

# Broadcast function registered by main.py
_broadcast_fn: Callable[[dict], Awaitable[None]] | None = None

BroadcastFn = Callable[[dict], Awaitable[None]]


def register_broadcast(fn: BroadcastFn) -> None:
    global _broadcast_fn
    _broadcast_fn = fn


# ── Schedule math ─────────────────────────────────────────────────────────────

def calc_next_run(schedule: str, from_dt: datetime | None = None) -> datetime | None:
    """Return the next datetime this schedule should fire, or None for 'manual'."""
    now = from_dt or datetime.now()

    if not schedule or schedule == "manual":
        return None

    def at_nine(dt: datetime) -> datetime:
        return dt.replace(hour=9, minute=0, second=0, microsecond=0)

    if schedule == "hourly":
        return (now + timedelta(hours=1)).replace(second=0, microsecond=0)

    if schedule == "daily":
        candidate = at_nine(now)
        if candidate <= now:
            candidate += timedelta(days=1)
        return candidate

    if schedule == "weekdays":
        candidate = at_nine(now)
        if candidate <= now:
            candidate += timedelta(days=1)
        while candidate.weekday() >= 5:   # 5=Sat, 6=Sun
            candidate += timedelta(days=1)
        return candidate

    if schedule == "weekly":
        # Next Monday at 9am
        days_ahead = (0 - now.weekday()) % 7   # 0 = Monday
        candidate = at_nine(now + timedelta(days=days_ahead))
        if candidate <= now:
            candidate += timedelta(days=7)
        return candidate

    return None


# ── Agent execution ───────────────────────────────────────────────────────────

def _build_task(ws: dict, product_config: dict) -> str:
    product_name = product_config.get("name", ws["product_id"]) if product_config else ws["product_id"]
    last_run = ws.get("last_run_at") or "never"
    brand_ctx = ""
    if product_config:
        if product_config.get("target_audience"):
            brand_ctx += f"\nTarget audience: {product_config['target_audience']}"
        if product_config.get("brand_voice"):
            brand_ctx += f"\nBrand voice: {product_config['brand_voice']}"

    return f"""You are the autonomous agent for the **{ws['name']}** workstream of {product_name}.
{brand_ctx}

MISSION:
{ws['mission']}

LAST RUN: {last_run}
NOW: {datetime.now().strftime('%A, %B %d, %Y at %I:%M %p')}

Execute the mission above fully. Be concrete and specific — summarise what you found, \
drafted, or changed. Keep the summary under 400 words.

End your response with exactly one of these lines (no extra text on the line):
STATUS:OK
STATUS:WARN

Use STATUS:WARN if you found problems, blockers, anomalies, or anything Justin should \
review urgently. Otherwise use STATUS:OK."""


def _parse_warn(result: str) -> bool:
    return "STATUS:WARN" in result


async def _run_workstream(ws: dict, broadcast: BroadcastFn) -> None:
    ws_id      = ws["id"]
    product_id = ws["product_id"]

    if _running.get(ws_id):
        return  # already in-flight

    _running[ws_id] = True
    event_id = None

    try:
        from backend.db import (
            save_activity_event, update_activity_event,
            update_workstream_fields, get_product_config,
            get_workstreams, get_objectives,
            load_activity_events, load_review_items,
        )

        config = get_product_config(product_id)

        # Activity feed entry
        event_id = save_activity_event(
            product_id=product_id,
            agent_type="general",
            headline=f"[Auto] {ws['name']}",
            rationale=f"Scheduled workstream run · {ws['schedule']}",
            status="running",
        )
        now_ts = datetime.now().isoformat(timespec="seconds")

        await broadcast({
            "type": "activity_started",
            "product_id": product_id,
            "id": event_id,
            "agent_type": "general",
            "headline": f"[Auto] {ws['name']}",
            "rationale": f"Scheduled workstream run · {ws['schedule']}",
            "ts": now_ts,
        })

        # Run the agent
        from agents.runner import run_research_agent
        result = await run_research_agent(_build_task(ws, config))

        is_warn = _parse_warn(result)
        # Strip the STATUS line from the summary shown to Justin
        summary_text = result.replace("STATUS:OK", "").replace("STATUS:WARN", "").strip()
        summary = summary_text[:300].rstrip() + ("…" if len(summary_text) > 300 else "")

        update_activity_event(event_id, status="done", summary=summary)

        now = datetime.now()
        next_run = calc_next_run(ws["schedule"], now)
        next_run_str = next_run.isoformat(timespec="seconds") if next_run else None

        updates: dict = {
            "last_run_at": now.isoformat(timespec="seconds"),
            "next_run_at": next_run_str,
        }
        if is_warn:
            updates["status"] = "warn"
        update_workstream_fields(ws_id, **updates)

        done_ts = datetime.now().isoformat(timespec="seconds")
        await broadcast({
            "type": "activity_done",
            "product_id": product_id,
            "id": event_id,
            "summary": summary,
            "ts": done_ts,
        })

        # Refresh product data so workstream last_run_at / status updates in UI
        await broadcast({
            "type": "product_data",
            "product_id": product_id,
            "workstreams":   get_workstreams(product_id),
            "objectives":    get_objectives(product_id),
            "events":        load_activity_events(product_id),
            "review_items":  load_review_items(product_id),
        })

    except Exception as exc:
        log.error("Workstream %s (%s) failed: %s", ws_id, ws.get("name"), exc)
        if event_id is not None:
            try:
                from backend.db import update_activity_event
                update_activity_event(event_id, status="done", summary=f"Error: {exc}")
            except Exception:
                pass
        await broadcast({
            "type": "activity_done",
            "product_id": product_id,
            "id": event_id,
            "summary": f"Workstream agent error: {exc}",
            "ts": datetime.now().isoformat(timespec="seconds"),
        })
    finally:
        _running.pop(ws_id, None)


async def _run_objective_loop(product_id: str, objective_id: int) -> None:
    """Run one autonomous cycle for an objective using the full agent loop."""
    if _running_objectives.get(objective_id):
        return

    _running_objectives[objective_id] = True
    event_id = None

    try:
        from backend.db import (
            get_objective_by_id, set_objective_autonomous, set_objective_session,
            set_objective_blocked, save_review_item,
            save_activity_event, update_activity_event,
            get_workstreams, get_objectives, load_activity_events, load_review_items,
            set_objective_next_run, create_session,
        )
        from backend.main import _build_context, _agent_loop

        obj = get_objective_by_id(objective_id)
        if not obj:
            return

        # Ensure dedicated session exists
        session_id = obj.get("session_id")
        if not session_id:
            session_id = create_session(f"Objective: {obj['text'][:40]}", product_id)
            set_objective_session(objective_id, session_id)

        # Activity feed entry
        event_id = save_activity_event(
            product_id=product_id,
            agent_type="general",
            headline=f"[Auto] {obj['text'][:60]}",
            rationale="Autonomous objective run",
            status="running",
        )
        now_ts = datetime.now().isoformat(timespec="seconds")
        if _broadcast_fn:
            await _broadcast_fn({
                "type": "activity_started",
                "product_id": product_id,
                "id": event_id,
                "agent_type": "general",
                "headline": f"[Auto] {obj['text'][:60]}",
                "rationale": "Autonomous objective run",
                "ts": now_ts,
            })

        # Build context: product system prompt + objective session history
        messages = _build_context(product_id, session_id=session_id)

        # Inject the cycle prompt
        progress_str = str(obj["progress_current"])
        if obj.get("progress_target") is not None:
            progress_str += f" of {obj['progress_target']}"
        last_run = obj.get("last_run_at") or "never"

        cycle_prompt = (
            f'You are autonomously working toward this objective: "{obj["text"]}"\n'
            f"Current progress: {progress_str}.\n"
            f"Last run: {last_run}.\n\n"
            "Use your available tools to take the best next action toward this goal.\n\n"
            "When you have taken action, call `update_objective_progress` to record measurable "
            "progress, then call `schedule_next_run` with how many hours until you should check "
            "back and why.\n\n"
            "If you are blocked and need human input before you can proceed, call "
            "`create_review_item` instead — do NOT call `schedule_next_run`.\n\n"
            "If you need a capability you don't currently have (e.g., posting to a social "
            "platform, reading analytics), use `find_skill` or `manage_mcp_server` to add it "
            "before proceeding — don't create a review item just because a tool is missing."
        )
        messages.append({"role": "user", "content": cycle_prompt})

        # Run the full agent loop
        _updated_messages, new_review_items = await _agent_loop(
            _broadcast_fn, product_id, messages, session_id=session_id
        )

        # Refresh objective from DB (agent may have updated progress via tools)
        refreshed = get_objective_by_id(objective_id)
        if not refreshed:
            return

        target = refreshed.get("progress_target")
        current = refreshed.get("progress_current", 0)

        # Priority 1: target reached → create "what's next?" review, go dormant
        if target is not None and current >= target:
            review_id = save_review_item(
                product_id=product_id,
                title=f"Goal reached: {obj['text'][:60]}",
                description=(
                    f"Objective reached its target of {target}. "
                    "Set a new target to continue, or disable autonomous mode."
                ),
                risk_label="Goal milestone — awaiting new direction",
                activity_event_id=event_id,
            )
            set_objective_autonomous(objective_id, False)
            if _broadcast_fn:
                review_item = {
                    "id": review_id,
                    "title": f"Goal reached: {obj['text'][:60]}",
                    "description": f"Objective reached its target of {target}. Set a new target to continue, or disable autonomous mode.",
                    "risk_label": "Goal milestone — awaiting new direction",
                    "status": "pending",
                    "created_at": now_ts,
                }
                await _broadcast_fn({"type": "review_item_added", "product_id": product_id, "item": review_item})

        # Priority 2: agent created blocking review → go dormant until resolved
        elif new_review_items:
            set_objective_blocked(objective_id, new_review_items[-1]["id"])

        # Priority 3: schedule_next_run was called → next_run_at already set by tool
        # If agent forgot to call schedule_next_run, default to 24h
        else:
            refreshed2 = get_objective_by_id(objective_id)
            if refreshed2 and not refreshed2.get("next_run_at"):
                set_objective_next_run(objective_id, 24.0)

        summary = "Autonomous cycle complete."
        update_activity_event(event_id, status="done", summary=summary)
        done_ts = datetime.now().isoformat(timespec="seconds")
        if _broadcast_fn:
            await _broadcast_fn({
                "type": "activity_done",
                "product_id": product_id,
                "id": event_id,
                "summary": summary,
                "ts": done_ts,
            })
            await _broadcast_fn({
                "type": "product_data",
                "product_id": product_id,
                "workstreams":  get_workstreams(product_id),
                "objectives":   get_objectives(product_id),
                "events":       load_activity_events(product_id),
                "review_items": load_review_items(product_id),
            })

    except Exception as exc:
        log.error("Objective %s (%s) loop failed: %s", objective_id, product_id, exc)
        if event_id is not None:
            try:
                from backend.db import update_activity_event
                update_activity_event(event_id, status="done", summary=f"Error: {exc}")
            except Exception:
                pass
        if _broadcast_fn:
            await _broadcast_fn({
                "type": "activity_done",
                "product_id": product_id,
                "id": event_id,
                "summary": f"Objective loop error: {exc}",
                "ts": datetime.now().isoformat(timespec="seconds"),
            })
        # Go dormant on error to avoid crash loop
        try:
            from backend.db import set_objective_autonomous
            set_objective_autonomous(objective_id, False)
        except Exception:
            pass
    finally:
        _running_objectives.pop(objective_id, None)


async def _run_launch_wizard(
    product_id: str, session_id: str, description: str, primary_goal: str
) -> None:
    """Run the launch wizard agent loop for a new product."""
    if _running_wizards.get(product_id):
        return

    _running_wizards[product_id] = True

    try:
        from backend.db import (
            get_product_config, set_launch_wizard_active,
            get_workstreams, get_objectives, load_activity_events, load_review_items,
        )
        from backend.main import _build_context, _agent_loop

        config = get_product_config(product_id)
        product_name = config.get("name", product_id) if config else product_id

        wizard_prompt = (
            f'You are setting up a new product launch for "{product_name}".\n'
            f"Description: {description}\n"
            f"Primary goal: {primary_goal}\n\n"
            "Your job during this setup session:\n"
            "1. Ask the user focused questions to understand their brand, audience, and competitive "
            "position — one question at a time, conversationally\n"
            "2. As you learn, call update_product to fill in brand_voice, tone, writing_style, "
            "target_audience, social_handles, hashtags, and brand_notes — fill in what you can "
            "infer without asking\n"
            "3. Before each action, call report_wizard_progress with a brief description of what "
            "you are doing\n"
            '4. Create specific, measurable objectives (e.g. "Grow Instagram to 5,000 followers '
            'in 90 days") and call set_objective_autonomous to enable each one immediately\n'
            "5. When all brand fields are configured and at least 2-3 autonomous objectives are "
            "created, call complete_launch with a summary\n\n"
            "Keep questions short and conversational. Never ask about something you can reasonably "
            "infer from the description and primary goal. Fill first, ask only when you genuinely "
            "need the user's input."
        )

        messages = _build_context(product_id, session_id=session_id)
        messages.append({"role": "user", "content": wizard_prompt})

        await _agent_loop(_broadcast_fn, product_id, messages, session_id=session_id)

        # Safety: if agent forgot to call complete_launch, clear the flag
        refreshed = get_product_config(product_id)
        if refreshed and refreshed.get("launch_wizard_active"):
            set_launch_wizard_active(product_id, False)
            if _broadcast_fn:
                await _broadcast_fn({
                    "type": "product_data",
                    "product_id": product_id,
                    "workstreams": get_workstreams(product_id),
                    "objectives": get_objectives(product_id),
                    "events": load_activity_events(product_id),
                    "review_items": load_review_items(product_id),
                    "launch_wizard_active": 0,
                })

    except Exception as exc:
        log.error("Launch wizard for %s failed: %s", product_id, exc)
        try:
            from backend.db import set_launch_wizard_active
            set_launch_wizard_active(product_id, False)
        except Exception:
            pass
        if _broadcast_fn:
            await _broadcast_fn({
                "type": "launch_complete",
                "product_id": product_id,
                "summary": f"Setup encountered an error: {exc}",
            })
    finally:
        _running_wizards.pop(product_id, None)


# ── Public API ────────────────────────────────────────────────────────────────

async def trigger_workstream(ws_id: int) -> None:
    """Manually trigger a workstream run. Called by the REST API."""
    from backend.db import get_workstream_by_id
    ws = get_workstream_by_id(ws_id)
    if not ws:
        return
    if not ws.get("mission", "").strip():
        return
    if _broadcast_fn is None:
        log.warning("trigger_workstream called before broadcast registered")
        return
    asyncio.create_task(_run_workstream(ws, _broadcast_fn))


async def scheduler_loop(broadcast: BroadcastFn, interval_seconds: int = 60) -> None:
    """Main loop — polls for due workstreams every `interval_seconds`."""
    log.info("Workstream scheduler started (interval=%ds)", interval_seconds)
    while True:
        try:
            from backend.db import get_due_workstreams, get_due_autonomous_objectives
            due = get_due_workstreams()
            for ws in due:
                if not _running.get(ws["id"]):
                    asyncio.create_task(_run_workstream(ws, broadcast))
            # Autonomous objectives check
            due_objs = get_due_autonomous_objectives()
            for obj in due_objs:
                if not _running_objectives.get(obj["id"]):
                    asyncio.create_task(_run_objective_loop(obj["product_id"], obj["id"]))
        except Exception as exc:
            log.error("Scheduler poll error: %s", exc)
        await asyncio.sleep(interval_seconds)
