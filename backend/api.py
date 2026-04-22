# backend/api.py
"""REST API for Adjutant settings — product config, workstreams, objectives."""
import mimetypes
import os

import httpx
from fastapi import APIRouter, Depends, HTTPException, Header, UploadFile, File
from pydantic import BaseModel

from backend.uploads import save_uploaded_file

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
    autonomous:       int | None = None


class GoogleOAuthSettings(BaseModel):
    google_oauth_client_id:     str | None = None
    google_oauth_client_secret: str | None = None


class SocialAccountSettings(BaseModel):
    twitter_client_id:      str | None = None
    twitter_client_secret:  str | None = None
    linkedin_client_id:     str | None = None
    linkedin_client_secret: str | None = None
    meta_app_id:            str | None = None
    meta_app_secret:        str | None = None


class McpServerCreate(BaseModel):
    name: str
    type: str
    url: str | None = None
    command: str | None = None
    args: list[str] | None = None
    env: dict | None = None
    scope: str
    product_id: str | None = None

class McpServerUpdate(BaseModel):
    enabled: bool | None = None
    name: str | None = None
    url: str | None = None
    command: str | None = None
    args: list[str] | None = None
    env: dict | None = None


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
        autonomous=body.autonomous,
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


class ActionOverride(BaseModel):
    action_type: str
    tier: str
    window_minutes: int | None = None

class AutonomySettingsUpdate(BaseModel):
    master_tier: str | None = None
    master_window_minutes: int | None = None
    action_overrides: list[ActionOverride] = []


@router.get("/products/{product_id}/notes")
def get_notes_api(product_id: str, _=Depends(_auth)):
    from backend.db import get_notes
    return get_notes(product_id)


@router.put("/products/{product_id}/notes")
def update_notes_api(product_id: str, body: NotesUpdate, _=Depends(_auth)):
    from backend.db import set_notes
    return set_notes(product_id, body.content)


# ── Autonomy ──────────────────────────────────────────────────────────────────

@router.get("/products/{product_id}/autonomy")
def get_autonomy_api(product_id: str, _=Depends(_auth)):
    from backend.db import get_product_autonomy_settings
    return get_product_autonomy_settings(product_id)


@router.put("/products/{product_id}/autonomy")
def update_autonomy_api(product_id: str, body: AutonomySettingsUpdate, _=Depends(_auth)):
    from backend.db import (
        set_master_autonomy, set_action_autonomy,
        get_product_autonomy_settings, clear_product_autonomy,
    )
    clear_product_autonomy(product_id)
    set_master_autonomy(product_id, body.master_tier, body.master_window_minutes)
    for override in body.action_overrides:
        set_action_autonomy(product_id, override.action_type, override.tier, override.window_minutes)
    return get_product_autonomy_settings(product_id)


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
        "Use gmail_send to send a clean summary email to the owner. "
        "The owner's email is available in the system context or oauth connection info.",
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
    from agents.runner import run_general_agent
    data = get_digest_data()
    task_text = _compile_digest_task(data)
    asyncio.create_task(run_general_agent(task_text))
    return {"queued": True}


# ── Telegram ──────────────────────────────────────────────────────────────────

class TelegramTokenRequest(BaseModel):
    token: str


def _get_telegram_creds() -> tuple[str, str]:
    """Return (token, chat_id) — env vars take precedence over DB."""
    from backend.db import get_agent_config
    cfg = get_agent_config()
    token   = os.environ.get("TELEGRAM_BOT_TOKEN") or cfg.get("telegram_bot_token") or ""
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")   or cfg.get("telegram_chat_id")   or ""
    return token, chat_id


@router.get("/telegram/status")
async def get_telegram_status(_=Depends(_auth)):
    """Return Telegram configuration and connectivity status."""
    token, chat_id = _get_telegram_creds()
    if not token:
        return {"configured": False, "connected": False, "bot_username": None}
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"https://api.telegram.org/bot{token}/getMe")
            data = resp.json()
            if data.get("ok"):
                return {
                    "configured": True,
                    "connected": bool(chat_id),
                    "bot_username": data["result"].get("username"),
                }
    except Exception:
        pass
    return {"configured": True, "connected": False, "bot_username": None}


@router.put("/telegram/token")
async def save_telegram_token(body: TelegramTokenRequest, _=Depends(_auth)):
    """Validate and save a Telegram bot token, then hot-reload the bot."""
    from backend.db import set_agent_config
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"https://api.telegram.org/bot{body.token}/getMe")
            data = resp.json()
    except Exception:
        raise HTTPException(400, detail="Could not reach Telegram API")
    if not data.get("ok"):
        raise HTTPException(400, detail="Invalid bot token")
    set_agent_config("telegram_bot_token", body.token)
    bot_username = data["result"].get("username")
    _, chat_id = _get_telegram_creds()
    from backend import telegram_state
    await telegram_state.restart(body.token, chat_id)
    return {"bot_username": bot_username}


@router.get("/telegram/discover-chat")
async def discover_telegram_chat(_=Depends(_auth)):
    """Poll getUpdates to find the user's chat_id after they message the bot."""
    from backend.db import set_agent_config
    token, _ = _get_telegram_creds()
    if not token:
        raise HTTPException(400, detail="No bot token configured")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"https://api.telegram.org/bot{token}/getUpdates",
                params={"limit": 20},
            )
            data = resp.json()
    except Exception:
        raise HTTPException(502, detail="Could not reach Telegram API")
    if data.get("ok"):
        for update in reversed(data.get("result", [])):
            msg = update.get("message") or {}
            chat_id = str(msg.get("from", {}).get("id", ""))
            if chat_id:
                set_agent_config("telegram_chat_id", chat_id)
                from backend import telegram_state
                await telegram_state.restart(token, chat_id)
                return {"chat_id": chat_id}
    return {"chat_id": None}


# ── MCP Servers ───────────────────────────────────────────────────────────────

@router.get("/mcp-servers")
def list_mcp_servers_api(product_id: str | None = None, _=Depends(_auth)):
    from backend.db import list_mcp_servers, list_all_mcp_servers
    servers = list_mcp_servers(product_id) if product_id else list_all_mcp_servers()
    # Never return credentials
    return [{k: v for k, v in s.items() if k != "env"} for s in servers]


@router.post("/mcp-servers", status_code=201)
async def create_mcp_server_api(body: McpServerCreate, _=Depends(_auth)):
    import json as _json
    from backend.db import add_mcp_server, get_mcp_server
    if body.type not in ("remote", "stdio"):
        raise HTTPException(status_code=422, detail="type must be 'remote' or 'stdio'")
    if body.scope not in ("global", "product"):
        raise HTTPException(status_code=422, detail="scope must be 'global' or 'product'")
    if body.type == "remote" and not body.url:
        raise HTTPException(status_code=422, detail="url required for remote type")
    if body.type == "stdio" and not body.command:
        raise HTTPException(status_code=422, detail="command required for stdio type")

    env_json = _json.dumps(body.env) if body.env else None
    args_json = _json.dumps(body.args) if body.args else None

    sid = add_mcp_server(
        name=body.name, type=body.type, url=body.url,
        command=body.command, args=args_json, env=env_json,
        scope=body.scope, product_id=body.product_id,
    )

    if body.type == "stdio":
        import backend.main as _main
        if _main._mcp_manager is not None:
            config = get_mcp_server(sid)
            await _main._mcp_manager.add_server(config)

    config = get_mcp_server(sid)
    return {k: v for k, v in config.items() if k != "env"}


@router.get("/mcp-servers/{server_id}")
def get_mcp_server_api(server_id: int, _=Depends(_auth)):
    from backend.db import get_mcp_server
    server = get_mcp_server(server_id)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    return server  # includes env for the edit form


@router.patch("/mcp-servers/{server_id}")
async def update_mcp_server_api(server_id: int, body: McpServerUpdate, _=Depends(_auth)):
    import json as _json
    from backend.db import get_mcp_server, update_mcp_server
    server = get_mcp_server(server_id)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    env_json = _json.dumps(body.env) if body.env is not None else None
    args_json = _json.dumps(body.args) if body.args is not None else None

    update_mcp_server(
        server_id,
        enabled=body.enabled,
        name=body.name,
        url=body.url,
        command=body.command,
        args=args_json,
        env=env_json,
    )

    updated = get_mcp_server(server_id)
    new_enabled = updated["enabled"]
    if server["type"] == "stdio":
        import backend.main as _main
        if _main._mcp_manager is not None:
            if new_enabled:
                await _main._mcp_manager.remove_server(server_id)
                await _main._mcp_manager.add_server(updated)
            else:
                await _main._mcp_manager.remove_server(server_id)
    return {k: v for k, v in updated.items() if k != "env"}


@router.delete("/mcp-servers/{server_id}", status_code=204)
async def delete_mcp_server_api(server_id: int, _=Depends(_auth)):
    from backend.db import get_mcp_server, delete_mcp_server
    server = get_mcp_server(server_id)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    if server["type"] == "stdio":
        import backend.main as _main
        if _main._mcp_manager is not None:
            await _main._mcp_manager.remove_server(server_id)
    delete_mcp_server(server_id)


# ── Extensions (custom agent tools) ──────────────────────────────────────────

class ExtensionUpdate(BaseModel):
    enabled: bool | None = None
    description: str | None = None
    instructions: str | None = None


def _list_extensions_raw() -> list[dict]:
    """Return metadata for every extension file, including disabled ones."""
    import pkgutil, importlib
    from pathlib import Path
    from core.tools import _EXTENSIONS_DIR, _get_disabled_extensions
    disabled = _get_disabled_extensions()
    results = []
    if not _EXTENSIONS_DIR.exists():
        return results
    for finder, name, _ in pkgutil.iter_modules([str(_EXTENSIONS_DIR)]):
        try:
            mod = importlib.import_module(f"extensions.{name}")
            if not (hasattr(mod, "TOOL_DEFINITION") and hasattr(mod, "execute")):
                continue
            td = mod.TOOL_DEFINITION
            instructions = getattr(mod, "_INSTRUCTIONS", None)
            results.append({
                "name": name,
                "tool_name": td.get("name", name),
                "description": td.get("description", ""),
                "instructions": instructions,
                "auto_generated": instructions is not None,
                "enabled": name not in disabled,
            })
        except Exception:
            pass
    return results


@router.get("/extensions")
def list_extensions(_=Depends(_auth)):
    return _list_extensions_raw()


@router.patch("/extensions/{name}")
def update_extension(name: str, body: ExtensionUpdate, _=Depends(_auth)):
    from pathlib import Path
    from core.tools import _EXTENSIONS_DIR, _get_disabled_extensions, _set_disabled_extensions
    ext_file = _EXTENSIONS_DIR / f"{name}.py"
    if not ext_file.exists():
        raise HTTPException(status_code=404, detail="Extension not found")

    # Toggle enabled/disabled
    if body.enabled is not None:
        disabled = _get_disabled_extensions()
        if body.enabled:
            disabled.discard(name)
        else:
            disabled.add(name)
        _set_disabled_extensions(disabled)

    # Update description and/or instructions (only for auto-generated extensions)
    if body.description is not None or body.instructions is not None:
        import re
        from datetime import datetime
        source = ext_file.read_text()
        # Only allow editing auto-generated files (they have _INSTRUCTIONS)
        if "_INSTRUCTIONS" not in source:
            raise HTTPException(status_code=400, detail="Only auto-generated extensions can be edited")
        if body.description is not None:
            safe_desc = body.description.replace('"', '\\"')
            source = re.sub(r'"description":\s*"[^"]*"', f'"description": "{safe_desc}"', source, count=1)
        if body.instructions is not None:
            safe_instr = body.instructions.replace('\\', '\\\\').replace('"""', '\\"\\"\\"')
            source = re.sub(r'_INSTRUCTIONS = """.*?"""', f'_INSTRUCTIONS = """{safe_instr}"""', source, flags=re.DOTALL, count=1)
        ext_file.write_text(source)

    return {"ok": True}


@router.delete("/extensions/{name}", status_code=204)
def delete_extension(name: str, _=Depends(_auth)):
    from core.tools import _EXTENSIONS_DIR, _get_disabled_extensions, _set_disabled_extensions
    ext_file = _EXTENSIONS_DIR / f"{name}.py"
    if not ext_file.exists():
        raise HTTPException(status_code=404, detail="Extension not found")
    ext_file.unlink()
    # Remove from disabled list too if present
    disabled = _get_disabled_extensions()
    disabled.discard(name)
    _set_disabled_extensions(disabled)


# ── Wizard plan ──────────────────────────────────────────────────────────────

class WizardPlanRequest(BaseModel):
    intent: str


@router.post("/wizard-plan")
async def generate_wizard_plan(body: WizardPlanRequest, _=Depends(_auth)):
    """Use Claude to derive workstream/objective suggestions from user intent."""
    import anthropic
    import json as _json
    intent = body.intent.strip()
    if not intent:
        raise HTTPException(status_code=422, detail="intent is required")

    client = anthropic.Anthropic()
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system="""You are helping set up an AI agent system. Given a user's description of what they want the system to do, suggest workstreams, objectives, and required integrations.

Respond with ONLY valid JSON in this exact format, no explanation:
{
  "workstreams": [
    {"name": "string", "mission": "string describing what the AI does", "schedule": "daily|weekly|monthly|none"}
  ],
  "objectives": [
    {"text": "string describing the goal", "progress_target": number_or_null}
  ],
  "required_integrations": ["gmail", "twitter"]
}

The required_integrations list must only contain values from: gmail, google_calendar, twitter, linkedin, facebook, instagram.""",
        messages=[{
            "role": "user",
            "content": intent,
        }],
    )

    try:
        raw = message.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        ALLOWED_INTEGRATIONS = {"gmail", "google_calendar", "twitter", "linkedin", "facebook", "instagram"}
        result = _json.loads(raw)
        if isinstance(result.get("required_integrations"), list):
            result["required_integrations"] = [
                i for i in result["required_integrations"]
                if i in ALLOWED_INTEGRATIONS
            ]
        return result
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to parse AI response")


# ── File upload ───────────────────────────────────────────────────────────────

_IMAGE_PDF_LIMIT = 20 * 1024 * 1024   # 20 MB
_VIDEO_LIMIT     = 200 * 1024 * 1024  # 200 MB


@router.post("/upload")
async def upload_file(file: UploadFile = File(...), _=Depends(_auth)):
    data = await file.read()
    mime = file.content_type or mimetypes.guess_type(file.filename or "")[0] or "application/octet-stream"

    if mime.startswith("video/"):
        limit = _VIDEO_LIMIT
    else:
        limit = _IMAGE_PDF_LIMIT

    if len(data) > limit:
        raise HTTPException(status_code=413, detail=f"File too large (max {limit // (1024*1024)} MB for this type)")

    path = save_uploaded_file(file.filename or "upload", data)
    return {"path": str(path), "mime_type": mime, "name": file.filename, "size": len(data)}


# ── Google OAuth global settings ──────────────────────────────────────────────

@router.get("/settings/google-oauth")
def get_google_oauth_settings(_=Depends(_auth)):
    from backend.db import get_agent_config
    config = get_agent_config()
    return {
        "google_oauth_client_id": config.get("google_oauth_client_id", ""),
        "google_oauth_client_secret": "",  # never expose the secret
    }


@router.put("/settings/google-oauth")
def update_google_oauth_settings(body: GoogleOAuthSettings, _=Depends(_auth)):
    from backend.db import set_agent_config
    if body.google_oauth_client_id is not None:
        set_agent_config("google_oauth_client_id", body.google_oauth_client_id)
    if body.google_oauth_client_secret is not None:
        set_agent_config("google_oauth_client_secret", body.google_oauth_client_secret)
    return {"ok": True}


# ── Social Account global settings ────────────────────────────────────────────

@router.get("/settings/social-accounts")
def get_social_settings(_=Depends(_auth)):
    from backend.db import get_agent_config
    config = get_agent_config()
    return {
        "twitter_client_id":      config.get("twitter_client_id", ""),
        "twitter_client_secret":  "",
        "linkedin_client_id":     config.get("linkedin_client_id", ""),
        "linkedin_client_secret": "",
        "meta_app_id":            config.get("meta_app_id", ""),
        "meta_app_secret":        "",
    }


@router.put("/settings/social-accounts")
def update_social_settings(body: SocialAccountSettings, _=Depends(_auth)):
    from backend.db import set_agent_config
    for key in (
        "twitter_client_id", "twitter_client_secret",
        "linkedin_client_id", "linkedin_client_secret",
        "meta_app_id", "meta_app_secret",
    ):
        val = getattr(body, key)
        if val is not None:
            set_agent_config(key, val)
    return {"ok": True}


# ── OAuth flow ─────────────────────────────────────────────────────────────────

@router.get("/products/{product_id}/oauth/start/{service}")
async def start_oauth_flow(product_id: str, service: str, _=Depends(_auth)):
    from backend.db import get_agent_config
    GOOGLE_SERVICES = ("gmail", "google_calendar")
    SOCIAL_SERVICES = ("twitter", "linkedin", "meta")
    if service not in GOOGLE_SERVICES + SOCIAL_SERVICES:
        raise HTTPException(status_code=422, detail=f"Unknown service: {service}")
    config = get_agent_config()
    if service in GOOGLE_SERVICES:
        from backend.google_oauth import build_authorization_url
        client_id = config.get("google_oauth_client_id", "")
        if not client_id:
            raise HTTPException(
                status_code=400,
                detail="Google OAuth not configured. Add Client ID in Settings → Google OAuth.",
            )
        auth_url = build_authorization_url(product_id, service, client_id)
    else:
        from backend.social_oauth import build_authorization_url as social_build_url
        client_id_key = {"twitter": "twitter_client_id", "linkedin": "linkedin_client_id", "meta": "meta_app_id"}[service]
        platform_label = {"twitter": "Twitter", "linkedin": "LinkedIn", "meta": "Meta"}[service]
        client_id = config.get(client_id_key, "")
        if not client_id:
            raise HTTPException(
                status_code=400,
                detail=f"{platform_label} credentials not configured. Add them in Settings → Social Accounts.",
            )
        auth_url = social_build_url(product_id, service, client_id)
    return {"auth_url": auth_url}


@router.get("/oauth/callback")
async def oauth_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
):
    import base64 as _b64
    import json as _json
    from datetime import datetime, timezone, timedelta
    from fastapi.responses import HTMLResponse
    from backend.db import get_agent_config, save_oauth_connection
    def _error_page(msg: str) -> HTMLResponse:
        safe = msg.replace("'", "\\'")
        return HTMLResponse(
            f"<html><body style='font-family:sans-serif;padding:24px;background:#0f1117;color:#f87171'>"
            f"<p><strong>OAuth Error</strong></p><p>{msg}</p>"
            f"<script>window.opener&&window.opener.postMessage({{type:'oauth_error',message:'{safe}'}},'*');setTimeout(()=>window.close(),4000)</script>"
            f"</body></html>"
        )
    if error:
        return _error_page(error_description or error)
    if not code or not state:
        return _error_page("OAuth callback missing required parameters.")
    try:
        padded = state + "==" * ((4 - len(state) % 4) % 4)
        state_data = _json.loads(_b64.urlsafe_b64decode(padded).decode())
        product_id = state_data["product_id"]
        service = state_data["service"]
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid state parameter")
    GOOGLE_SERVICES = ("gmail", "google_calendar")
    SOCIAL_SERVICES = ("twitter", "linkedin", "meta")
    if service not in GOOGLE_SERVICES + SOCIAL_SERVICES:
        raise HTTPException(status_code=400, detail="Invalid state parameter")
    config = get_agent_config()
    if service in GOOGLE_SERVICES:
        from backend.google_oauth import exchange_code_for_tokens, get_user_email
        client_id = config.get("google_oauth_client_id", "")
        client_secret = config.get("google_oauth_client_secret", "")
        token_data = await exchange_code_for_tokens(code, client_id, client_secret)
        access_token = token_data["access_token"]
        refresh_token = token_data.get("refresh_token", "")
        expiry = (datetime.now(timezone.utc) + timedelta(seconds=token_data.get("expires_in", 3600))).isoformat()
        email = await get_user_email(access_token)
        save_oauth_connection(
            product_id=product_id, service=service, email=email,
            access_token=access_token, refresh_token=refresh_token,
            token_expiry=expiry, scopes=token_data.get("scope", ""),
        )
    elif service == "twitter":
        from backend.social_oauth import exchange_code_for_tokens, get_twitter_username
        client_id = config.get("twitter_client_id", "")
        client_secret = config.get("twitter_client_secret", "")
        token_data = await exchange_code_for_tokens(code, "twitter", client_id, client_secret, state=state)
        access_token = token_data["access_token"]
        refresh_token = token_data.get("refresh_token", "")
        expiry = (datetime.now(timezone.utc) + timedelta(seconds=token_data.get("expires_in", 7200))).isoformat()
        username = await get_twitter_username(access_token)
        save_oauth_connection(
            product_id=product_id, service="twitter", email=username,
            access_token=access_token, refresh_token=refresh_token,
            token_expiry=expiry, scopes=token_data.get("scope", ""),
        )
    elif service == "linkedin":
        from backend.social_oauth import exchange_code_for_tokens, get_linkedin_urn
        client_id = config.get("linkedin_client_id", "")
        client_secret = config.get("linkedin_client_secret", "")
        token_data = await exchange_code_for_tokens(code, "linkedin", client_id, client_secret)
        access_token = token_data["access_token"]
        expires_in = token_data.get("expires_in", 5184000)
        expiry = (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).isoformat()
        urn = await get_linkedin_urn(access_token)
        save_oauth_connection(
            product_id=product_id, service="linkedin", email=urn,
            access_token=access_token, refresh_token="",
            token_expiry=expiry, scopes=token_data.get("scope", ""),
        )
    elif service == "meta":
        from backend.social_oauth import exchange_code_for_tokens, get_meta_assets
        client_id = config.get("meta_app_id", "")
        client_secret = config.get("meta_app_secret", "")
        token_data = await exchange_code_for_tokens(code, "meta", client_id, client_secret)
        access_token = token_data.get("access_token", "")
        assets, debug_info = await get_meta_assets(access_token)
        if not assets:
            return _error_page(f"No Facebook Pages found. Debug: {debug_info}")
        expiry = (datetime.now(timezone.utc) + timedelta(days=60)).isoformat()
        for asset in assets:
            save_oauth_connection(
                product_id=product_id, service=asset["service"], email=asset["name"],
                access_token=asset["access_token"], refresh_token="",
                token_expiry=expiry, scopes="pages_manage_posts",
            )
    return HTMLResponse(
        "<html><body style='font-family:sans-serif;padding:24px;background:#0f1117;color:#86efac'>"
        "<p>Connected successfully! This window will close.</p>"
        "<script>window.opener&&window.opener.postMessage({type:'oauth_success'},'*');window.close()</script>"
        "</body></html>"
    )


@router.get("/products/{product_id}/oauth/connections")
def list_oauth_connections_api(product_id: str, _=Depends(_auth)):
    from backend.db import list_oauth_connections
    return list_oauth_connections(product_id)


@router.delete("/products/{product_id}/oauth/{service}", status_code=204)
async def delete_oauth_connection_api(product_id: str, service: str, _=Depends(_auth)):
    from backend.db import get_oauth_connection, delete_oauth_connection
    conn_row = get_oauth_connection(product_id, service)
    if conn_row:
        GOOGLE_SERVICES = ("gmail", "google_calendar")
        if service in GOOGLE_SERVICES:
            from backend.google_oauth import revoke_token
            await revoke_token(conn_row["access_token"])
        else:
            from backend.social_oauth import revoke_social_token
            await revoke_social_token(conn_row["access_token"], service)
    delete_oauth_connection(product_id, service)


@router.get("/products/{product_id}/browser-credentials")
def list_browser_credentials_api(product_id: str, _=Depends(_auth)):
    from backend.db import list_browser_credentials
    creds = list_browser_credentials(product_id)
    # Convert active from int to bool (SQLite stores booleans as 0/1)
    return [
        {**cred, "active": bool(cred["active"])}
        for cred in creds
    ]


class BrowserCredentialBody(BaseModel):
    username: str
    password: str
    handle: str = ""
    active: bool


_BROWSER_CRED_SERVICES = {"twitter", "linkedin", "facebook", "instagram"}


@router.put("/products/{product_id}/browser-credentials/{service}")
def save_browser_credential_api(
    product_id: str, service: str, body: BrowserCredentialBody, _=Depends(_auth)
):
    if service not in _BROWSER_CRED_SERVICES:
        raise HTTPException(status_code=422, detail=f"Unsupported service: {service}")
    from backend.db import save_browser_credential, get_browser_credential
    password = body.password
    if not password:
        existing = get_browser_credential(product_id, service)
        if existing:
            password = existing["password"]
    save_browser_credential(product_id, service, body.username, password, body.active, body.handle)
    return {"ok": True}


@router.delete("/products/{product_id}/browser-credentials/{service}", status_code=204)
def delete_browser_credential_api(product_id: str, service: str, _=Depends(_auth)):
    if service not in _BROWSER_CRED_SERVICES:
        raise HTTPException(status_code=422, detail=f"Unsupported service: {service}")
    from backend.db import delete_browser_credential
    delete_browser_credential(product_id, service)


# --- OpenAI / Codex OAuth ---

@router.get("/openai-oauth/start")
async def openai_oauth_start(_=Depends(_auth)):
    from backend.openai_oauth import build_auth_url
    return {"auth_url": build_auth_url()}


@router.get("/openai-oauth/callback")
async def openai_oauth_callback(code: str | None = None, error: str | None = None):
    import httpx
    from fastapi.responses import HTMLResponse
    from backend.openai_oauth import CLIENT_ID, REDIRECT_URI, TOKEN_URL, pop_verifier

    def _err(msg: str) -> HTMLResponse:
        safe = msg.replace("'", "").replace('"', "")[:200]
        return HTMLResponse(
            "<html><body><script>"
            f"window.opener&&window.opener.postMessage({{type:'oauth_error',message:'{safe}'}},'*');"
            "setTimeout(()=>window.close(),4000)"
            "</script></body></html>"
        )

    if error:
        return _err(error)
    if not code:
        return _err("Missing authorization code")
    verifier = pop_verifier()
    if not verifier:
        return _err("OAuth session expired — please try again")

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(TOKEN_URL, data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": REDIRECT_URI,
                "client_id": CLIENT_ID,
                "code_verifier": verifier,
            })
            if resp.status_code != 200:
                return _err(f"Token exchange failed ({resp.status_code})")
            tokens = resp.json()
            id_token = tokens.get("id_token")
            refresh_token = tokens.get("refresh_token", "")
            if not id_token:
                return _err("No id_token in token response")

            resp2 = await client.post(TOKEN_URL, data={
                "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
                "client_id": CLIENT_ID,
                "requested_token": "openai-api-key",
                "subject_token": id_token,
                "subject_token_type": "urn:ietf:params:oauth:token-type:id_token",
            })
            if resp2.status_code != 200:
                return _err(f"API key exchange failed ({resp2.status_code})")
            api_key = resp2.json().get("access_token")
            if not api_key:
                return _err("No API key in exchange response")
    except Exception as exc:
        return _err(f"Network error: {exc}")

    from backend.db import set_agent_config
    set_agent_config("openai_access_token", api_key)
    if refresh_token:
        set_agent_config("openai_refresh_token", refresh_token)

    return HTMLResponse(
        "<html><body><script>"
        "window.opener&&window.opener.postMessage({type:'oauth_success'},'*');window.close()"
        "</script></body></html>"
    )


@router.get("/openai-oauth/status")
async def openai_oauth_status(_=Depends(_auth)):
    from backend.db import get_agent_config
    cfg = get_agent_config()
    return {"connected": bool(cfg.get("openai_access_token"))}


@router.delete("/openai-oauth/disconnect")
async def openai_oauth_disconnect(_=Depends(_auth)):
    from backend.db import set_agent_config
    set_agent_config("openai_access_token", "")
    set_agent_config("openai_refresh_token", "")
    return {"ok": True}


# --- Image Generation settings ---

@router.get("/settings/image-generation")
async def get_image_generation_settings(_=Depends(_auth)):
    from backend.db import get_agent_config
    cfg = get_agent_config()
    return {
        "pexels_configured": bool(cfg.get("pexels_api_key")),
        "openai_connected": bool(cfg.get("openai_access_token")),
    }


@router.put("/settings/image-generation")
async def update_image_generation_settings(body: dict, _=Depends(_auth)):
    from backend.db import set_agent_config
    if "pexels_api_key" in body:
        set_agent_config("pexels_api_key", body["pexels_api_key"])
    return {"ok": True}
