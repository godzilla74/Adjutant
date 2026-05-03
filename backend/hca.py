# backend/hca.py
import json
import logging
import re
from datetime import datetime

from backend.provider import make_provider

log = logging.getLogger(__name__)

HCA_SYSTEM_PROMPT = (
    "You are the Holding Company Adjutant — the owner's autonomous proxy across all products.\n"
    "You have full context of what every Product Adjutant has done since your last run.\n\n"
    "Your job each run:\n"
    "1. Read all PA briefs — identify cross-product patterns, opportunities, and misalignment.\n"
    "2. Issue strategic directives to products that need guidance or reorientation.\n"
    "3. Execute direct PA-level actions on any product when immediate intervention is warranted.\n"
    "4. Identify new product opportunities emerging from the portfolio and propose them for owner approval.\n"
    "5. Flag portfolio-level capability gaps.\n"
    "6. Write a brief summarizing your observations and decisions.\n\n"
    "You act as the owner. You are fully autonomous. The only action requiring owner approval is\n"
    "proposing a new product — everything else you execute directly.\n\n"
    "Respond ONLY with valid JSON:\n"
    '{\"decisions\": [...], \"brief\": \"prose summary\"}'
)


def build_hca_context() -> dict:
    from backend.db import _conn, get_products, list_hca_runs, list_hca_directives

    products = get_products()
    recent_hca_runs = list_hca_runs(limit=3)
    cfg = _get_hca_config_raw()
    last_run_at = cfg.get("last_run_at")

    product_entries = []
    for p in products:
        pid = p["id"]
        # PA runs since last HCA run (or all runs if never run before), capped at 10
        with _conn() as conn:
            if last_run_at:
                pa_rows = conn.execute(
                    """SELECT id, triggered_by, run_at, brief,
                              json_array_length(decisions) as decision_count
                       FROM orchestrator_runs
                       WHERE product_id = ? AND run_at > ?
                       ORDER BY run_at DESC LIMIT 10""",
                    (pid, last_run_at),
                ).fetchall()
            else:
                pa_rows = conn.execute(
                    """SELECT id, triggered_by, run_at, brief,
                              json_array_length(decisions) as decision_count
                       FROM orchestrator_runs
                       WHERE product_id = ?
                       ORDER BY run_at DESC LIMIT 10""",
                    (pid,),
                ).fetchall()
            ws_count = conn.execute(
                "SELECT COUNT(*) FROM workstreams WHERE product_id = ?", (pid,)
            ).fetchone()[0]
            obj_count = conn.execute(
                "SELECT COUNT(*) FROM objectives WHERE product_id = ?", (pid,)
            ).fetchone()[0]
            oc = conn.execute(
                "SELECT enabled FROM orchestrator_config WHERE product_id = ?", (pid,)
            ).fetchone()

        directives = list_hca_directives(product_id=pid)

        product_entries.append({
            "id": pid,
            "name": p["name"],
            "pa_enabled": bool(oc and oc["enabled"]),
            "recent_pa_runs": [
                {
                    "run_at": r["run_at"],
                    "triggered_by": r["triggered_by"],
                    "brief": r["brief"],
                    "decision_count": r["decision_count"] or 0,
                }
                for r in pa_rows
            ],
            "active_directives": [
                {"id": d["id"], "content": d["content"], "created_at": d["created_at"]}
                for d in directives
            ],
            "workstream_count": ws_count,
            "objective_count": obj_count,
        })

    return {
        "products": product_entries,
        "recent_hca_runs": [
            {
                "run_at": r["run_at"],
                "triggered_by": r["triggered_by"],
                "brief": r["brief"],
                "decision_count": len(r.get("decisions") or []),
            }
            for r in recent_hca_runs
        ],
        "current_datetime": datetime.now().isoformat(timespec="seconds"),
    }


def _get_hca_config_raw() -> dict:
    from backend.db import _conn
    with _conn() as conn:
        row = conn.execute("SELECT * FROM hca_config WHERE id = 1").fetchone()
    if row is None:
        return {"last_run_at": None, "next_run_at": None, "schedule": "weekly on mondays at 8am"}
    return dict(row)


def apply_hca_decisions(decisions: list, run_id: int) -> list:
    from backend.db import (
        _conn, create_hca_directive, supersede_hca_directive,
        save_review_item, get_products,
    )
    from backend.orchestrator import _execute_decision

    valid_products = {p["id"] for p in get_products()}
    annotated = []

    for d in decisions:
        action = d.get("action", "")
        try:
            if action == "issue_directive":
                pid = d.get("product_id")  # None = global
                create_hca_directive(pid, d["content"], run_id)
                annotated.append({**d, "_status": "applied"})

            elif action == "supersede_directive":
                new_id = supersede_hca_directive(
                    d["directive_id"], d["replacement"], run_id
                )
                annotated.append({**d, "_status": "applied", "_new_directive_id": new_id})

            elif action == "pa_action":
                pid = d.get("product_id", "")
                if pid not in valid_products:
                    log.warning("hca: pa_action references unknown product '%s', skipping", pid)
                    annotated.append({**d, "_status": "skipped", "_reason": "unknown product"})
                    continue
                pa_dec = d.get("pa_decision", {})
                # Pre-load valid workstream and signal sets for target product
                with _conn() as conn:
                    valid_ws = {
                        r["id"] for r in conn.execute(
                            "SELECT id FROM workstreams WHERE product_id = ?", (pid,)
                        ).fetchall()
                    }
                    valid_signals = {
                        r["id"] for r in conn.execute(
                            "SELECT id FROM signals WHERE product_id = ? AND consumed_at IS NULL",
                            (pid,),
                        ).fetchall()
                    }
                note = _execute_decision(pid, pa_dec, valid_ws, valid_signals)
                annotated.append({**d, "_status": "applied", "_note": note})

            elif action == "propose_new_product":
                payload = {
                    "name": d.get("name", ""),
                    "description": d.get("description", ""),
                    "goals": d.get("goals", ""),
                    "icon_label": d.get("icon_label", "🏢"),
                    "color": d.get("color", "#6366f1"),
                    "suggested_workstreams": d.get("suggested_workstreams", []),
                }
                item_id = save_review_item(
                    product_id=None,
                    title=f"New product: {d.get('name', 'Unnamed')}",
                    description=d.get("reason", ""),
                    risk_label="High · owner approval required",
                    action_type="hca_new_product",
                    payload=json.dumps(payload),
                )
                annotated.append({**d, "_status": "queued", "_review_item_id": item_id})

            elif action == "portfolio_gap":
                save_review_item(
                    product_id=None,
                    title=d.get("description", "Portfolio gap"),
                    description=d.get("reason", ""),
                    risk_label="Opportunity · no action taken",
                    action_type="portfolio_gap",
                    payload=json.dumps(d),
                )
                annotated.append({**d, "_status": "applied"})

            else:
                log.warning("hca: unknown action '%s', skipping", action)
                annotated.append({**d, "_status": "skipped", "_reason": "unknown action"})

        except Exception as exc:
            log.warning("hca: decision failed: %s — %s", d, exc, exc_info=True)
            annotated.append({**d, "_status": "error", "_error": str(exc)})

    return annotated


def _slugify(name: str) -> str:
    slug = name.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
    return slug or "product"


async def launch_product_from_hca(payload: dict, broadcast) -> None:
    from backend.db import (
        create_product, update_orchestrator_config, create_workstream_for_launch,
    )
    from backend.scheduler import calc_next_run

    name = payload.get("name", "New Product")
    product_id = _slugify(name)
    icon_label = payload.get("icon_label", "🏢")
    color = payload.get("color", "#6366f1")

    create_product(id=product_id, name=name, icon_label=icon_label, color=color)

    for ws in payload.get("suggested_workstreams", []):
        schedule = ws.get("schedule", "")
        next_dt = calc_next_run(schedule)
        create_workstream_for_launch(
            product_id=product_id,
            name=ws.get("name", "Workstream"),
            mission=ws.get("mission", ""),
            schedule=schedule,
            tag_subscriptions=json.dumps(ws.get("tag_subscriptions", [])),
            next_run_at=next_dt.isoformat(timespec="seconds") if next_dt else None,
        )

    update_orchestrator_config(product_id, enabled=1, schedule="daily at 8am")

    await broadcast({
        "type": "product_launched",
        "product_id": product_id,
        "product_name": name,
        "source": "hca",
    })


async def run_hca(triggered_by: str, broadcast) -> None:
    from backend.db import (
        get_hca_config, update_hca_config,
        save_hca_run, update_hca_run_decisions,
        get_agent_config,
    )
    from backend.scheduler import calc_next_run

    cfg = get_hca_config()
    context = build_hca_context()

    user_msg = (
        "Here is the current state of the portfolio. "
        "Review everything and return your decisions.\n\n"
        + json.dumps(context, indent=2, default=str)
    )

    agent_cfg = get_agent_config()
    model = agent_cfg.get("agent_model", "claude-opus-4-7")

    run_id: int | None = None
    pending = 0
    brief = ""

    try:
        provider = make_provider(model)
        response = await provider.create(
            model=model,
            system=HCA_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
            max_tokens=4096,
        )
        raw = response.content[0].text

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
            if m:
                parsed = json.loads(m.group(1))
            else:
                raise

        decisions_raw = parsed.get("decisions", [])
        brief = parsed.get("brief", "")

        run_id = save_hca_run(
            triggered_by=triggered_by,
            status="complete",
            decisions=[],
            brief=brief,
        )

        annotated = apply_hca_decisions(decisions_raw, run_id)
        update_hca_run_decisions(run_id, annotated)
        pending = sum(1 for d in annotated if d.get("_status") == "queued")

    except Exception as exc:
        log.error("hca run failed: %s", exc, exc_info=True)
        if run_id is None:
            run_id = save_hca_run(
                triggered_by=triggered_by,
                status="error",
                decisions=[],
                brief="",
                error=str(exc),
            )
        else:
            update_hca_run_decisions(run_id, [], status="error", error=str(exc))

    from datetime import timedelta as _timedelta
    now_str = datetime.now().isoformat(timespec="seconds")
    next_dt = calc_next_run(cfg["schedule"])
    if next_dt is None:
        next_dt = datetime.now() + _timedelta(days=7)
    update_hca_config(
        next_run_at=next_dt.isoformat(timespec="seconds"),
        last_run_at=now_str,
    )

    await broadcast({
        "type": "hca_run_complete",
        "run_id": run_id,
        "brief_preview": brief[:300],
        "pending_proposal_count": pending,
    })
