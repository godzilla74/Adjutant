# backend/main.py
"""Hannah Mission Control — FastAPI backend (multi-product)."""

import json
import os
from datetime import datetime
from pathlib import Path

import anthropic
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

from backend.db import (
    get_products,
    get_workstreams,
    get_objectives,
    init_db,
    load_activity_events,
    load_messages,
    load_review_items,
    resolve_review_item,
    save_activity_event,
    save_message,
    update_activity_event,
)
from core.config import get_system_prompt
from core.tools import TOOLS_DEFINITIONS, execute_tool

load_dotenv()
init_db()

app = FastAPI()

UI_DIST = Path(__file__).parent.parent / "ui" / "dist"

HANNAH_PASSWORD = os.environ.get("HANNAH_PASSWORD", "")
client = anthropic.AsyncAnthropic()


def _ts() -> str:
    return datetime.now().isoformat(timespec="seconds")


async def _send(ws: WebSocket, event: dict) -> None:
    await ws.send_text(json.dumps(event))


def _product_data_payload(product_id: str) -> dict:
    return {
        "type": "product_data",
        "product_id": product_id,
        "workstreams": get_workstreams(product_id),
        "objectives": get_objectives(product_id),
        "events": load_activity_events(product_id),
        "review_items": load_review_items(product_id),
    }


# ── Hannah agentic loop ────────────────────────────────────────────────────────

async def _hannah_loop(ws: WebSocket, product_id: str, messages: list) -> tuple[list, list]:
    """Run Hannah's agentic loop. Returns (updated messages, new review items)."""
    system = get_system_prompt(product_id)
    new_review_items: list[dict] = []

    while True:
        accumulated_text = ""

        async with client.messages.stream(
            model="claude-opus-4-6",
            max_tokens=8096,
            system=system,
            tools=TOOLS_DEFINITIONS,
            messages=messages,
            thinking={"type": "adaptive"},
        ) as stream:
            async for event in stream:
                if (
                    event.type == "content_block_delta"
                    and event.delta.type == "text_delta"
                ):
                    await _send(ws, {"type": "hannah_token", "product_id": product_id, "content": event.delta.text})
                    accumulated_text += event.delta.text

            final = await stream.get_final_message()

        if accumulated_text:
            ts = _ts()
            await _send(ws, {
                "type": "hannah_done",
                "product_id": product_id,
                "content": accumulated_text,
                "ts": ts,
            })

        _BLOCK_KEYS = {
            "thinking": {"type", "thinking", "signature"},
            "text":     {"type", "text"},
            "tool_use": {"type", "id", "name", "input"},
        }
        content_serializable = []
        for b in final.content:
            if hasattr(b, "model_dump"):
                d = b.model_dump()
                allowed = _BLOCK_KEYS.get(d.get("type", ""), set(d.keys()))
                content_serializable.append({k: v for k, v in d.items() if k in allowed})
            else:
                content_serializable.append(b)
        messages.append({"role": "assistant", "content": content_serializable})
        save_message(product_id, "assistant", content_serializable)

        if final.stop_reason != "tool_use":
            break

        tool_results = []
        event_id = None
        for block in final.content:
            if block.type != "tool_use":
                continue

            is_agent_task = block.name in ("delegate_task", "email_task")
            is_review = block.name == "create_review_item"

            if is_agent_task:
                headline = block.input.get("task", block.name)
                rationale = block.input.get("context", "")
                agent_type = block.input.get(
                    "agent_type", "email" if block.name == "email_task" else "general"
                )
                event_id = save_activity_event(
                    product_id=product_id,
                    agent_type=agent_type,
                    headline=headline,
                    rationale=rationale,
                    status="running",
                )
                await _send(ws, {
                    "type": "activity_started",
                    "product_id": product_id,
                    "id": event_id,
                    "agent_type": agent_type,
                    "headline": headline,
                    "rationale": rationale,
                    "ts": _ts(),
                })

            try:
                result = await execute_tool(block.name, block.input)
                output = result if isinstance(result, str) else json.dumps(result)
            except Exception as exc:
                output = f"Error in {block.name}: {exc}"

            if is_agent_task and event_id is not None:
                summary = output[:300].rstrip() + ("…" if len(output) > 300 else "")
                update_activity_event(event_id, status="done", summary=summary)
                await _send(ws, {
                    "type": "activity_done",
                    "product_id": product_id,
                    "id": event_id,
                    "summary": summary,
                    "ts": _ts(),
                })

            if is_review:
                try:
                    parsed = json.loads(output)
                    item_id = parsed["id"]
                    item = {
                        "id": item_id,
                        "title": block.input.get("title", ""),
                        "description": block.input.get("description", ""),
                        "risk_label": block.input.get("risk_label", ""),
                        "status": "pending",
                        "created_at": _ts(),
                    }
                    await _send(ws, {
                        "type": "review_item_added",
                        "product_id": product_id,
                        "item": item,
                    })
                    new_review_items.append(item)
                except (json.JSONDecodeError, KeyError):
                    pass

            if block.name in ("create_objective", "update_objective"):
                await _send(ws, _product_data_payload(block.input.get("product_id", product_id)))

            # Product changes — push updated product list to refresh the rail
            if block.name in ("create_product", "update_product", "delete_product"):
                await _send(ws, {"type": "init", "products": get_products()})

            # Workstream / objective changes — push product_data refresh
            if block.name in ("create_workstream", "update_workstream_status", "delete_workstream",
                              "delete_objective"):
                await _send(ws, _product_data_payload(block.input.get("product_id", product_id)))

            # Social draft — push review_item_added + product_data refresh
            if block.name == "draft_social_post":
                try:
                    parsed = json.loads(output)
                    review_id = parsed.get("review_item_id")
                    pid = block.input.get("product_id", product_id)
                    if review_id:
                        item = {
                            "id": review_id,
                            "title": f"Post to {block.input.get('platform', '').capitalize()}",
                            "description": block.input.get("content", "")[:200],
                            "risk_label": f"Social post · {block.input.get('platform', '')} · public-facing",
                            "status": "pending",
                            "created_at": _ts(),
                        }
                        await _send(ws, {"type": "review_item_added", "product_id": pid, "item": item})
                except (json.JSONDecodeError, KeyError):
                    pass

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": output,
            })

        if tool_results:
            messages.append({"role": "user", "content": tool_results})
            save_message(product_id, "user", tool_results)

    return messages, new_review_items


# ── WebSocket endpoint ─────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()

    if not HANNAH_PASSWORD:
        await _send(ws, {"type": "auth_fail", "reason": "HANNAH_PASSWORD not set"})
        await ws.close()
        return

    try:
        msg = await ws.receive_json()
    except Exception:
        await ws.close()
        return

    if msg.get("type") != "auth" or msg.get("password") != HANNAH_PASSWORD:
        await _send(ws, {"type": "auth_fail", "reason": "Invalid password"})
        await ws.close()
        return

    await _send(ws, {"type": "auth_ok"})
    await _send(ws, {"type": "init", "products": get_products()})

    # Per-product in-memory message history (loaded from DB on first access)
    messages_by_product: dict[str, list] = {}
    active_product_id = "retainerops"

    try:
        while True:
            msg = await ws.receive_json()
            msg_type = msg.get("type")

            if msg_type == "switch_product":
                product_id = msg.get("product_id", "retainerops")
                active_product_id = product_id
                if product_id not in messages_by_product:
                    messages_by_product[product_id] = load_messages(product_id)
                await _send(ws, _product_data_payload(product_id))

            elif msg_type == "directive":
                product_id = msg.get("product_id", active_product_id)
                known_ids = {p["id"] for p in get_products()}
                if product_id not in known_ids:
                    await _send(ws, {"type": "error", "message": f"Unknown product: {product_id}"})
                    continue
                active_product_id = product_id
                content = msg.get("content", "").strip()
                if not content:
                    continue

                ts = _ts()
                await _send(ws, {
                    "type": "directive_echo",
                    "product_id": product_id,
                    "content": content,
                    "ts": ts,
                })

                if product_id not in messages_by_product:
                    messages_by_product[product_id] = load_messages(product_id)

                messages_by_product[product_id].append({"role": "user", "content": content})
                save_message(product_id, "user", content)
                try:
                    messages_by_product[product_id], _ = await _hannah_loop(
                        ws, product_id, messages_by_product[product_id]
                    )
                except Exception as exc:
                    import traceback; traceback.print_exc()
                    await _send(ws, {"type": "error", "message": f"Agent error: {exc}"})

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

    except WebSocketDisconnect:
        pass


# ── Static UI ──────────────────────────────────────────────────────────────────

if UI_DIST.exists():
    app.mount("/", StaticFiles(directory=UI_DIST, html=True), name="ui")
