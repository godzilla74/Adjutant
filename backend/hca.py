# backend/hca.py
import json
import logging
import re
from datetime import datetime

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
