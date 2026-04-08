# backend/api.py
"""REST API for Adjutant settings — product config, workstreams, objectives."""
import os

import httpx
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel

router = APIRouter(prefix="/api")


def _auth(x_agent_password: str | None = Header(None, alias="X-Agent-Password")) -> None:
    password = os.environ.get("AGENT_PASSWORD", "")
    if not password or x_agent_password != password:
        raise HTTPException(status_code=401, detail="Unauthorized")


# ── Pydantic models ───────────────────────────────────────────────────────────

class ProductConfigUpdate(BaseModel):
    name:            str | None = None
    icon_label:      str | None = None
    color:           str | None = None
    brand_voice:     str | None = None
    tone:            str | None = None
    writing_style:   str | None = None
    target_audience: str | None = None
    social_handles:  str | None = None
    hashtags:        str | None = None
    brand_notes:     str | None = None


class WorkstreamCreate(BaseModel):
    name:   str
    status: str = "paused"


class WorkstreamUpdate(BaseModel):
    name:     str | None = None
    status:   str | None = None
    mission:  str | None = None
    schedule: str | None = None


class ObjectiveCreate(BaseModel):
    text:             str
    progress_current: int       = 0
    progress_target:  int | None = None


class ObjectiveUpdate(BaseModel):
    text:             str | None = None
    progress_current: int | None = None
    progress_target:  int | None = None


# ── Product config ────────────────────────────────────────────────────────────

@router.get("/products/{product_id}/config")
def get_config(product_id: str, _=Depends(_auth)):
    from backend.db import get_product_config
    config = get_product_config(product_id)
    if not config:
        raise HTTPException(status_code=404, detail="Product not found")
    return config


@router.put("/products/{product_id}/config")
def update_config(product_id: str, body: ProductConfigUpdate, _=Depends(_auth)):
    from backend.db import update_product, get_product_config
    updates = body.model_dump(exclude_none=True)
    if updates:
        update_product(product_id, **updates)
    return get_product_config(product_id)


# ── Workstreams ───────────────────────────────────────────────────────────────

@router.post("/products/{product_id}/workstreams", status_code=201)
def create_workstream_api(product_id: str, body: WorkstreamCreate, _=Depends(_auth)):
    from backend.db import create_workstream, get_workstreams
    if body.status not in ("running", "warn", "paused"):
        raise HTTPException(status_code=422, detail="Invalid status")
    create_workstream(product_id, body.name, body.status)
    rows = get_workstreams(product_id)
    return rows[-1]  # return the newly created workstream


@router.patch("/workstreams/{ws_id}")
def update_workstream_api(ws_id: int, body: WorkstreamUpdate, _=Depends(_auth)):
    from backend.db import update_workstream_fields
    from backend.scheduler import calc_next_run
    from datetime import datetime

    fields: dict = {}
    if body.name     is not None: fields["name"]    = body.name
    if body.status   is not None: fields["status"]  = body.status
    if body.mission  is not None: fields["mission"] = body.mission
    if body.schedule is not None:
        fields["schedule"] = body.schedule
        nxt = calc_next_run(body.schedule)
        fields["next_run_at"] = nxt.isoformat(timespec="seconds") if nxt else None

    try:
        update_workstream_fields(ws_id, **fields)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {"id": ws_id}


@router.post("/workstreams/{ws_id}/run", status_code=202)
async def run_workstream_now(ws_id: int, _=Depends(_auth)):
    """Trigger an immediate workstream agent run."""
    from backend.scheduler import trigger_workstream
    await trigger_workstream(ws_id)
    return {"queued": True}


@router.delete("/workstreams/{ws_id}", status_code=204)
def delete_workstream_api(ws_id: int, _=Depends(_auth)):
    from backend.db import delete_workstream_by_id
    delete_workstream_by_id(ws_id)


# ── Objectives ────────────────────────────────────────────────────────────────

@router.post("/products/{product_id}/objectives", status_code=201)
def create_objective_api(product_id: str, body: ObjectiveCreate, _=Depends(_auth)):
    from backend.db import create_objective, get_objectives
    create_objective(product_id, body.text, body.progress_current, body.progress_target)
    rows = get_objectives(product_id)
    return rows[-1]


@router.patch("/objectives/{obj_id}")
def update_objective_api(obj_id: int, body: ObjectiveUpdate, _=Depends(_auth)):
    from backend.db import update_objective_by_id
    update_objective_by_id(
        obj_id,
        text=body.text,
        progress_current=body.progress_current,
        progress_target=body.progress_target,
    )
    return {"id": obj_id}


@router.delete("/objectives/{obj_id}", status_code=204)
def delete_objective_api(obj_id: int, _=Depends(_auth)):
    from backend.db import delete_objective_by_id
    delete_objective_by_id(obj_id)


# ── Directive templates ───────────────────────────────────────────────────────

class TemplateCreate(BaseModel):
    label:   str
    content: str


class TemplateUpdate(BaseModel):
    label:   str
    content: str


@router.get("/products/{product_id}/templates")
def list_templates(product_id: str, _=Depends(_auth)):
    from backend.db import get_directive_templates
    return get_directive_templates(product_id)


@router.post("/products/{product_id}/templates", status_code=201)
def create_template(product_id: str, body: TemplateCreate, _=Depends(_auth)):
    from backend.db import create_directive_template
    return create_directive_template(product_id, body.label, body.content)


@router.put("/templates/{template_id}")
def update_template(template_id: int, body: TemplateUpdate, _=Depends(_auth)):
    from backend.db import update_directive_template
    update_directive_template(template_id, body.label, body.content)
    return {"id": template_id}


@router.delete("/templates/{template_id}", status_code=204)
def delete_template(template_id: int, _=Depends(_auth)):
    from backend.db import delete_directive_template
    delete_directive_template(template_id)


# ── Agent config ──────────────────────────────────────────────────────────────

class AgentConfigUpdate(BaseModel):
    agent_model:    str | None = None
    subagent_model: str | None = None
    agent_name:     str | None = None


@router.get("/agent-config")
def get_agent_config_api(_=Depends(_auth)):
    from backend.db import get_agent_config
    return get_agent_config()


@router.put("/agent-config")
def update_agent_config_api(body: AgentConfigUpdate, _=Depends(_auth)):
    from backend.db import set_agent_config, get_agent_config
    import agents.runner as runner
    import backend.main as main_module

    if body.agent_model is not None:
        set_agent_config("agent_model", body.agent_model)
        main_module.AGENT_MODEL = body.agent_model

    if body.subagent_model is not None:
        set_agent_config("subagent_model", body.subagent_model)
        runner.SUBAGENT_MODEL = body.subagent_model

    if body.agent_name is not None:
        set_agent_config("agent_name", body.agent_name)

    return get_agent_config()


# ── Notes ─────────────────────────────────────────────────────────────────────

class NotesUpdate(BaseModel):
    content: str


@router.get("/products/{product_id}/notes")
def get_notes_api(product_id: str, _=Depends(_auth)):
    from backend.db import get_notes
    return get_notes(product_id)


@router.put("/products/{product_id}/notes")
def update_notes_api(product_id: str, body: NotesUpdate, _=Depends(_auth)):
    from backend.db import set_notes
    return set_notes(product_id, body.content)


# ── Directive history ─────────────────────────────────────────────────────────

@router.get("/products/{product_id}/directive-history")
def get_directive_history_api(product_id: str, _=Depends(_auth)):
    from backend.db import get_directive_history
    return get_directive_history(product_id, limit=30)


# ── Overview ──────────────────────────────────────────────────────────────────

@router.get("/overview")
def get_overview_api(_=Depends(_auth)):
    from backend.db import get_overview
    return get_overview()


# ── Email digest ──────────────────────────────────────────────────────────────

def _compile_digest_task(data: dict) -> str:
    lines = [
        f"Adjutant Digest — {data['generated_at']}",
        "",
        "Use gmail_get_profile to find the user's email address, then compose and",
        "send a clean summary email to that address.",
        f"Subject: Adjutant Digest — {data['generated_at']}",
        "Keep it concise and action-oriented. Here is the data:",
        "",
    ]
    for p in data["products"]:
        lines.append(f"## {p['product_name']}")
        ws_parts = [f"{w['name']} ({w['status']})" for w in p["workstreams"]]
        lines.append("Workstreams: " + (", ".join(ws_parts) if ws_parts else "none"))
        if p["recent_events"]:
            lines.append("Recent activity (last 24h):")
            for ev in p["recent_events"]:
                lines.append(f"  - {ev['headline']} [{ev['status']}]")
                if ev.get("summary"):
                    lines.append(f"    {ev['summary'][:200]}")
        else:
            lines.append("Recent activity: none")
        if p["pending_reviews"]:
            lines.append(f"Pending reviews ({len(p['pending_reviews'])}):")
            for r in p["pending_reviews"]:
                lines.append(f"  - {r['title']} ({r['risk_label']})")
        lines.append("")
    return "\n".join(lines)


@router.post("/digest", status_code=202)
async def send_digest_api(_=Depends(_auth)):
    import asyncio
    from backend.db import get_digest_data
    from agents.runner import run_email_agent
    data = get_digest_data()
    task_text = _compile_digest_task(data)
    asyncio.create_task(run_email_agent(task_text))
    return {"queued": True}


# ── Telegram ──────────────────────────────────────────────────────────────────

@router.get("/telegram/status")
async def get_telegram_status(_=Depends(_auth)):
    """Return Telegram configuration and connectivity status."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        return {"configured": False, "connected": False, "bot_username": None}
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"https://api.telegram.org/bot{token}/getMe")
            data = resp.json()
            if data.get("ok"):
                return {
                    "configured": True,
                    "connected": True,
                    "bot_username": data["result"].get("username"),
                }
    except Exception:
        pass
    return {"configured": True, "connected": False, "bot_username": None}
