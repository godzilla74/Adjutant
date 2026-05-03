# backend/scheduler.py
"""Autonomous workstream scheduler.

Runs as a background asyncio task started from main.py lifespan.
Each workstream with a mission + schedule fires its own agent on time.
"""

import asyncio
import logging
import re
from datetime import datetime, timedelta
from typing import Awaitable, Callable

log = logging.getLogger(__name__)

# Per-workstream in-flight guard (asyncio is single-threaded — no lock needed)
_running: dict[int, bool] = {}

# Per-objective in-flight guard
_running_objectives: dict[int, bool] = {}

# Per-product launch wizard in-flight guard
_running_wizards: dict[str, bool] = {}

# Per-product orchestrator (Product Adjutant) in-flight guard
_running_orchestrators: set[str] = set()

# HCA (Head of Chief Adjutant) in-flight guard
_running_hca: bool = False

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
    s = (schedule or "").strip().lower()

    if not s or s == "manual":
        return None

    def at_hour(dt: datetime, hour: int, minute: int = 0) -> datetime:
        return dt.replace(hour=hour, minute=minute, second=0, microsecond=0)

    def at_nine(dt: datetime) -> datetime:
        return at_hour(dt, 9)

    # ── Keyword shortcuts ─────────────────────────────────────────────────────
    if s == "hourly":
        return (now + timedelta(hours=1)).replace(second=0, microsecond=0)

    if s == "daily":
        candidate = at_nine(now)
        if candidate <= now:
            candidate += timedelta(days=1)
        return candidate

    if s == "weekdays":
        candidate = at_nine(now)
        if candidate <= now:
            candidate += timedelta(days=1)
        while candidate.weekday() >= 5:
            candidate += timedelta(days=1)
        return candidate

    if s == "weekly":
        days_ahead = (0 - now.weekday()) % 7
        candidate = at_nine(now + timedelta(days=days_ahead))
        if candidate <= now:
            candidate += timedelta(days=7)
        return candidate

    # ── Natural language ──────────────────────────────────────────────────────

    # "every N minutes" / "every N mins"
    m = re.match(r"every\s+(\d+)\s+min(?:utes?|s)?$", s)
    if m:
        return (now + timedelta(minutes=int(m.group(1)))).replace(second=0, microsecond=0)

    # "every N hours" / "every hour"
    m = re.match(r"every\s+(\d+)\s+hours?$", s)
    if m:
        return (now + timedelta(hours=int(m.group(1)))).replace(second=0, microsecond=0)
    if re.match(r"every\s+hour$", s):
        return (now + timedelta(hours=1)).replace(second=0, microsecond=0)

    # "every N days"
    m = re.match(r"every\s+(\d+)\s+days?$", s)
    if m:
        candidate = at_nine(now + timedelta(days=int(m.group(1))))
        return candidate

    # "twice daily"
    if re.match(r"twice\s+daily$", s):
        return (now + timedelta(hours=12)).replace(second=0, microsecond=0)

    # "every day at Xam/pm" / "daily at X:30pm"
    m = re.match(r"(?:every\s+day|daily)\s+at\s+(\d+)(?::(\d+))?\s*(am|pm)?$", s)
    if m:
        hour, minute = int(m.group(1)), int(m.group(2) or 0)
        ampm = (m.group(3) or "").lower()
        if ampm == "pm" and hour != 12:
            hour += 12
        elif ampm == "am" and hour == 12:
            hour = 0
        candidate = at_hour(now, hour, minute)
        if candidate <= now:
            candidate += timedelta(days=1)
        return candidate

    # "every weekday at X" / "weekdays at X"
    m = re.match(r"(?:every\s+)?weekdays?\s+at\s+(\d+)(?::(\d+))?\s*(am|pm)?$", s)
    if m:
        hour, minute = int(m.group(1)), int(m.group(2) or 0)
        ampm = (m.group(3) or "").lower()
        if ampm == "pm" and hour != 12:
            hour += 12
        elif ampm == "am" and hour == 12:
            hour = 0
        candidate = at_hour(now, hour, minute)
        if candidate <= now:
            candidate += timedelta(days=1)
        while candidate.weekday() >= 5:
            candidate += timedelta(days=1)
        return candidate

    # "every [day of week]" / "every monday at X"
    DAYS = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
            "friday": 4, "saturday": 5, "sunday": 6}
    m = re.match(r"every\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
                 r"(?:\s+at\s+(\d+)(?::(\d+))?\s*(am|pm)?)?$", s)
    if m:
        target_day = DAYS[m.group(1)]
        hour = int(m.group(2) or 9)
        minute = int(m.group(3) or 0)
        ampm = (m.group(4) or "").lower()
        if ampm == "pm" and hour != 12:
            hour += 12
        elif ampm == "am" and hour == 12:
            hour = 0
        days_ahead = (target_day - now.weekday()) % 7
        candidate = at_hour(now + timedelta(days=days_ahead), hour, minute)
        if candidate <= now:
            candidate += timedelta(days=7)
        return candidate

    return None


# ── Agent execution ───────────────────────────────────────────────────────────

def _build_routed_signal_prefix(workstream_id: int) -> str:
    """Return a context block of routed signals to prepend to the agent mission, or '' if none."""
    from backend.db import get_routed_signals_for_workstream
    signals = get_routed_signals_for_workstream(workstream_id)
    if not signals:
        return ""
    lines = ["=== ROUTED SIGNALS ==="]
    for s in signals:
        lines.append(
            f"[{s['tag_name']}] {s['content_type']} #{s['content_id']} "
            f"({s['created_at']}): \"{s['note']}\""
        )
    lines.append("======================\n")
    return "\n".join(lines) + "\n"


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

After your summary, if you identified any opportunities for other workstreams to act on, \
add a SIGNALS block using this exact format (omit the block entirely if there are no signals):

SIGNALS:
- tag:name :: One-sentence note for the receiving agent explaining the opportunity
- tag:name :: Another opportunity
END_SIGNALS

Use namespaced tags: social:linkedin, social:twitter, social:instagram, social:facebook, \
email:newsletter, email:customers, email:prospects, feature:request, feature:improvement, \
research:competitive, research:market. Create a new tag:name if none fit.

End your response with exactly one of these lines (no extra text on the line):
STATUS:OK
STATUS:WARN

Use STATUS:WARN if you found problems, blockers, anomalies, or anything Justin should \
review urgently. Otherwise use STATUS:OK."""


def _parse_warn(result: str) -> bool:
    return "STATUS:WARN" in result


def _parse_signals(output: str) -> list[tuple[str, str]]:
    """Extract (tag_name, note) pairs from a SIGNALS: ... END_SIGNALS block."""
    signals = []
    in_block = False
    for line in output.splitlines():
        if line.strip() == "SIGNALS:":
            in_block = True
            continue
        if line.strip() == "END_SIGNALS":
            in_block = False
            continue
        if in_block and line.strip().startswith("- "):
            content = line.strip()[2:]
            if " :: " in content:
                tag, note = content.split(" :: ", 1)
                signals.append((tag.strip(), note.strip()))
    return signals


def _strip_signals_block(output: str) -> str:
    """Remove the SIGNALS: ... END_SIGNALS block from output text."""
    lines, in_block = [], False
    for line in output.splitlines():
        if line.strip() == "SIGNALS:":
            in_block = True
            continue
        if line.strip() == "END_SIGNALS":
            in_block = False
            continue
        if not in_block:
            lines.append(line)
    return "\n".join(lines).strip()


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
            create_run_report, create_signal, get_or_create_tag,
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

        # Build task with any routed signal context prepended
        signal_prefix = _build_routed_signal_prefix(ws_id)
        task_text = signal_prefix + _build_task(ws, config)

        # Run the agent
        from agents.runner import run_research_agent
        result = await run_research_agent(task_text)

        is_warn = _parse_warn(result)
        raw_signals = _parse_signals(result)
        # Strip STATUS and SIGNALS blocks from the saved summary
        clean = _strip_signals_block(result)
        summary_text = clean.replace("STATUS:OK", "").replace("STATUS:WARN", "").strip()
        summary = summary_text[:300].rstrip() + ("…" if len(summary_text) > 300 else "")

        # Save the full output as a report (best-effort)
        report_id: int | None = None
        try:
            report_id = create_run_report(
                product_id=product_id,
                workstream_id=ws_id,
                workstream_name=ws["name"],
                full_output=summary_text,
            )
        except Exception as report_exc:
            log.error("Failed to save run report for workstream %s: %s", ws_id, report_exc)

        # Create signals from the SIGNALS block (best-effort)
        if report_id and raw_signals:
            for tag_name, note in raw_signals:
                try:
                    tag_id = get_or_create_tag(tag_name)
                    create_signal(
                        tag_id=tag_id,
                        content_type="run_report",
                        content_id=report_id,
                        product_id=product_id,
                        tagged_by="agent",
                        note=note,
                    )
                except Exception as sig_exc:
                    log.error("Failed to create signal '%s' for report %s: %s", tag_name, report_id, sig_exc)

        # Consume routed signals now that this run completed successfully
        from backend.db import consume_routed_signals
        consume_routed_signals(ws_id)

        update_activity_event(event_id, status="done", summary=summary, report_id=report_id)

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
            "report_id": report_id,
            "workstream_name": ws["name"],
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


async def _run_product_adjutant_task(
    product_id: str,
    triggered_by: str,
    broadcast: BroadcastFn,
) -> None:
    try:
        from backend.orchestrator import run_product_adjutant
        await run_product_adjutant(product_id, triggered_by, broadcast)
    except Exception as exc:
        log.error("orchestrator task error for %s: %s", product_id, exc, exc_info=True)
    finally:
        _running_orchestrators.discard(product_id)


async def _run_hca_task(triggered_by: str, broadcast: BroadcastFn) -> None:
    global _running_hca
    if _running_hca:
        return
    _running_hca = True
    try:
        from backend.hca import run_hca
        await run_hca(triggered_by, broadcast)
    except Exception as exc:
        log.error("hca task error: %s", exc, exc_info=True)
    finally:
        _running_hca = False


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


async def _run_approved_review_task(product_id: str, review: dict) -> None:
    """Spawn an agent loop to execute a user-approved review item."""
    event_id = None

    try:
        from backend.db import (
            save_activity_event, update_activity_event,
            get_workstreams, get_objectives,
            load_activity_events, load_review_items,
        )
        from backend.main import _agent_loop

        event_id = save_activity_event(
            product_id=product_id,
            agent_type="general",
            headline=f"[Approved] {review['title'][:60]}",
            rationale=review.get("description", ""),
            status="running",
        )
        now_ts = datetime.now().isoformat(timespec="seconds")
        if _broadcast_fn:
            await _broadcast_fn({
                "type": "activity_started",
                "product_id": product_id,
                "id": event_id,
                "agent_type": "general",
                "headline": f"[Approved] {review['title'][:60]}",
                "rationale": review.get("description", ""),
                "ts": now_ts,
            })

        messages = [{
            "role": "user",
            "content": (
                f"The following was reviewed and approved by the user:\n\n"
                f"**{review['title']}**\n\n"
                f"{review.get('description', '')}\n\n"
                "Please execute this now using your available tools. "
                "IMPORTANT: This action has already been approved — do NOT call "
                "create_review_item or queue anything for further approval. "
                "Execute directly and report what you did."
            ),
        }]

        await _agent_loop(_broadcast_fn, product_id, messages, session_id=None)
        summary = f"Completed: {review['title']}"
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
        log.error("Approved review task %r (%s) failed: %s", review.get("title"), product_id, exc)
        if event_id is not None:
            update_activity_event(event_id, status="done", summary=f"Error: {exc}")
        if _broadcast_fn and event_id is not None:
            await _broadcast_fn({
                "type": "activity_done",
                "product_id": product_id,
                "id": event_id,
                "summary": f"Error: {exc}",
                "ts": datetime.now().isoformat(timespec="seconds"),
            })


async def _run_launch_wizard(
    product_id: str, session_id: str, description: str, primary_goal: str
) -> None:
    """Run the launch wizard agent loop for a new product."""
    if _running_wizards.get(product_id):
        return

    _running_wizards[product_id] = True
    event_id = None

    try:
        from backend.db import (
            get_product_config, set_launch_wizard_active,
            get_workstreams, get_objectives, load_activity_events, load_review_items,
            save_activity_event, update_activity_event,
        )
        from backend.main import _build_context, _agent_loop

        config = get_product_config(product_id)
        product_name = config.get("name", product_id) if config else product_id

        event_id = save_activity_event(
            product_id=product_id,
            agent_type="general",
            headline=f"[Wizard] Setting up {product_name}",
            rationale="Launch wizard — configuring brand, objectives, and autonomous mode",
            status="running",
        )
        now_ts = datetime.now().isoformat(timespec="seconds")
        if _broadcast_fn:
            await _broadcast_fn({
                "type": "activity_started",
                "product_id": product_id,
                "id": event_id,
                "agent_type": "general",
                "headline": f"[Wizard] Setting up {product_name}",
                "rationale": "Launch wizard — configuring brand, objectives, and autonomous mode",
                "ts": now_ts,
            })

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

        update_activity_event(event_id, status="done", summary="Launch wizard complete.")
        done_ts = datetime.now().isoformat(timespec="seconds")
        if _broadcast_fn:
            await _broadcast_fn({
                "type": "activity_done",
                "product_id": product_id,
                "id": event_id,
                "summary": "Launch wizard complete.",
                "ts": done_ts,
            })

    except Exception as exc:
        log.error("Launch wizard for %s failed: %s", product_id, exc)
        if event_id is not None:
            try:
                update_activity_event(event_id, status="done", summary=f"Error: {exc}")
            except Exception:
                pass
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


async def _publish_scheduled_drafts() -> None:
    """Fetch all social drafts past their scheduled_for time and publish them."""
    from backend.db import get_due_scheduled_drafts
    due = get_due_scheduled_drafts()
    for draft in due:
        try:
            from backend.main import _do_publish_draft
            await _do_publish_draft(draft)
        except Exception as exc:
            log.error("Failed to publish scheduled draft %s: %s", draft.get("id"), exc)


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
    _auto_resolve_counter = 0
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
            # Orchestrator triggers
            from backend.db import get_due_orchestrator_products
            due_orch = get_due_orchestrator_products()
            for item in due_orch:
                pid = item["product_id"]
                if pid not in _running_orchestrators:
                    _running_orchestrators.add(pid)
                    asyncio.create_task(_run_product_adjutant_task(pid, item["trigger_type"], broadcast))
            # HCA triggers
            from backend.db import get_due_hca
            due_hca = get_due_hca()
            if due_hca and not _running_hca:
                asyncio.create_task(_run_hca_task(due_hca["trigger_type"], broadcast))
            # Auto-resolve expired window reviews (every ~30s regardless of main interval)
            _auto_resolve_counter += 1
            if _auto_resolve_counter >= max(1, 30 // interval_seconds):
                _auto_resolve_counter = 0
                from backend.db import auto_resolve_expired_reviews
                resolved = auto_resolve_expired_reviews()
                for r in resolved:
                    await broadcast({
                        "type": "review_resolved",
                        "review_item_id": r["id"],
                        "action": "auto_approved",
                    })
            # Publish scheduled social posts that are now due
            await _publish_scheduled_drafts()
        except Exception as exc:
            log.error("Scheduler poll error: %s", exc)
        await asyncio.sleep(interval_seconds)
