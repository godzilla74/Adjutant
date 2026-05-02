import json
import logging
from datetime import datetime

log = logging.getLogger(__name__)

PA_SYSTEM_PROMPT = (
    "You are the Product Adjutant for {product_name} — an autonomous Chief of Staff responsible "
    "for keeping all workstreams aligned with the product's goals. You have full context of recent "
    "agent outputs, signals, and your own prior decisions.\n\n"
    "Your job each run:\n"
    "1. Review all unconsumed signals — decide what to do with each (route to a workstream, "
    "consume as noise, or flag a capability gap).\n"
    "2. Review recent workstream outputs — identify patterns, drift from mission, schedule "
    "mismatches, or underperformance.\n"
    "3. Make adjustments: update missions, schedules, subscriptions, create objectives as needed.\n"
    "4. For decisions above your autonomy level, create an approval request with clear reasoning.\n"
    "5. Write a brief summarizing your observations and decisions for the Holding Company Adjutant.\n\n"
    "Your autonomy settings are provided in the context. Only apply actions marked 'autonomous' "
    "directly. Actions marked 'approval_required' must be included in decisions — they will be "
    "queued for user approval.\n\n"
    "Respond ONLY with valid JSON:\n"
    "{{\"decisions\": [...], \"brief\": \"prose summary for HCA\"}}"
)


def build_context(product_id: str) -> dict:
    from backend.db import (
        _conn, get_workstreams, get_orchestrator_config,
        list_orchestrator_runs, get_signals,
    )
    with _conn() as conn:
        product_row = conn.execute(
            "SELECT id, name, brand_voice, tone, target_audience FROM products WHERE id = ?",
            (product_id,),
        ).fetchone()
        report_rows = conn.execute(
            """SELECT workstream_id, workstream_name, run_at, full_output FROM (
                 SELECT rr.workstream_id, w.name as workstream_name,
                        rr.created_at as run_at, rr.full_output,
                        ROW_NUMBER() OVER (PARTITION BY rr.workstream_id ORDER BY rr.created_at DESC) as rn
                 FROM run_reports rr
                 JOIN workstreams w ON w.id = rr.workstream_id
                 WHERE rr.product_id = ?
               ) WHERE rn <= 5""",
            (product_id,),
        ).fetchall()

    config = get_orchestrator_config(product_id)
    workstreams = get_workstreams(product_id)
    signals = get_signals(product_id)
    recent_runs = list_orchestrator_runs(product_id, limit=3)

    reports_by_ws: dict[int, list] = {}
    for r in report_rows:
        ws_id = r["workstream_id"]
        if ws_id not in reports_by_ws:
            reports_by_ws[ws_id] = []
        if len(reports_by_ws[ws_id]) < 5:
            reports_by_ws[ws_id].append({
                "workstream_name": r["workstream_name"],
                "run_at": r["run_at"],
                "full_output": r["full_output"],
            })

    return {
        "product": dict(product_row) if product_row else {"id": product_id, "name": product_id},
        "workstreams": workstreams,
        "recent_reports": [r for rs in reports_by_ws.values() for r in rs],
        "unconsumed_signals": signals,
        "recent_orchestrator_runs": [
            {"run_at": r["run_at"], "triggered_by": r["triggered_by"],
             "brief": r["brief"], "decisions": r["decisions"]}
            for r in recent_runs
        ],
        "autonomy_settings": config["autonomy_settings"],
        "current_datetime": datetime.now().isoformat(),
    }


def _execute_decision(
    product_id: str,
    d: dict,
    valid_ws: set,
    valid_signals: set,
) -> str:
    from backend.db import (
        _conn, update_workstream_fields, consume_signal,
        route_signal, save_review_item,
    )
    from backend.scheduler import calc_next_run

    action = d["action"]

    if action == "route_signal":
        sig_id = d["signal_id"]
        ws_id = d["workstream_id"]
        if sig_id not in valid_signals:
            raise ValueError(f"signal_id {sig_id} not found or already consumed")
        if ws_id not in valid_ws:
            raise ValueError(f"workstream_id {ws_id} not found")
        route_signal(sig_id, ws_id)
        return f"signal {sig_id} routed to workstream {ws_id}"

    if action == "update_mission":
        ws_id = d["workstream_id"]
        if ws_id not in valid_ws:
            raise ValueError(f"workstream_id {ws_id} not found")
        update_workstream_fields(ws_id, mission=d["new_mission"])
        return f"workstream {ws_id} mission updated"

    if action == "update_schedule":
        ws_id = d["workstream_id"]
        if ws_id not in valid_ws:
            raise ValueError(f"workstream_id {ws_id} not found")
        next_dt = calc_next_run(d["new_schedule"])
        update_workstream_fields(
            ws_id,
            schedule=d["new_schedule"],
            next_run_at=next_dt.isoformat() if next_dt else None,
        )
        return f"workstream {ws_id} schedule → '{d['new_schedule']}'"

    if action == "update_subscriptions":
        ws_id = d["workstream_id"]
        if ws_id not in valid_ws:
            raise ValueError(f"workstream_id {ws_id} not found")
        with _conn() as conn:
            row = conn.execute(
                "SELECT tag_subscriptions FROM workstreams WHERE id = ?", (ws_id,)
            ).fetchone()
        current = json.loads(row["tag_subscriptions"] or "[]")
        updated = list(set(current + d.get("add", [])) - set(d.get("remove", [])))
        update_workstream_fields(ws_id, tag_subscriptions=json.dumps(updated))
        return f"workstream {ws_id} subscriptions updated"

    if action == "create_objective":
        with _conn() as conn:
            max_order = conn.execute(
                "SELECT COALESCE(MAX(display_order), 0) FROM objectives WHERE product_id = ?",
                (product_id,),
            ).fetchone()[0]
            conn.execute(
                """INSERT INTO objectives (product_id, text, display_order, progress_current)
                   VALUES (?, ?, ?, 0)""",
                (product_id, d["text"], max_order + 1),
            )
        return "objective created"

    if action == "consume_signal":
        sig_id = d["signal_id"]
        if sig_id not in valid_signals:
            raise ValueError(f"signal_id {sig_id} not found or already consumed")
        consume_signal(sig_id, product_id)
        return f"signal {sig_id} consumed"

    if action == "capability_gap":
        save_review_item(
            product_id=product_id,
            title=f"Capability gap: {d.get('tag', 'unknown')}",
            description=d.get("description", ""),
            risk_label="Opportunity · no action taken",
            action_type="capability_gap",
            payload=json.dumps(d),
        )
        return f"capability gap escalated: {d.get('tag', '')}"

    raise ValueError(f"unhandled action: {action}")


def apply_decisions(
    product_id: str,
    decisions: list,
    autonomy_settings: dict,
    run_id: int,
) -> list:
    from backend.db import _conn, save_review_item

    with _conn() as conn:
        valid_ws = {
            r["id"] for r in conn.execute(
                "SELECT id FROM workstreams WHERE product_id = ?", (product_id,)
            ).fetchall()
        }
        valid_signals = {
            r["id"] for r in conn.execute(
                "SELECT id FROM signals WHERE product_id = ? AND consumed_at IS NULL",
                (product_id,),
            ).fetchall()
        }

    annotated = []
    for d in decisions:
        action = d.get("action", "")
        level = autonomy_settings.get(action)

        if level is None:
            log.warning("orchestrator: unknown action '%s', skipping", action)
            annotated.append({**d, "_status": "skipped", "_reason": "unknown action"})
            continue

        if level == "approval_required":
            item_id = save_review_item(
                product_id=product_id,
                title=action,
                description=f"[orchestrator_run:{run_id}] {d.get('reason', '')}",
                risk_label="medium",
                action_type=f"orchestrator_{action}",
                payload=json.dumps(d),
            )
            annotated.append({**d, "_status": "queued", "_review_item_id": item_id})
            continue

        try:
            note = _execute_decision(product_id, d, valid_ws, valid_signals)
            annotated.append({**d, "_status": "applied", "_note": note})
        except Exception as exc:
            log.warning("orchestrator: decision failed: %s — %s", d, exc, exc_info=True)
            annotated.append({**d, "_status": "error", "_error": str(exc)})

    return annotated
