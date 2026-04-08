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
            from backend.db import get_due_workstreams
            due = get_due_workstreams()
            for ws in due:
                if not _running.get(ws["id"]):
                    asyncio.create_task(_run_workstream(ws, broadcast))
        except Exception as exc:
            log.error("Scheduler poll error: %s", exc)
        await asyncio.sleep(interval_seconds)
