"""Hannah Mission Control — FastAPI backend."""

import json
import os
import uuid
from datetime import datetime
from pathlib import Path

import anthropic
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

from backend.db import init_db, load_events, load_messages, save_event, save_message
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


# ── Hannah agentic loop ────────────────────────────────────────────────────────

async def _hannah_loop(ws: WebSocket, messages: list) -> list:
    system = get_system_prompt()

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
                    await _send(ws, {"type": "hannah_token", "content": event.delta.text})
                    accumulated_text += event.delta.text

            final = await stream.get_final_message()

        if accumulated_text:
            ts = _ts()
            await _send(ws, {"type": "hannah_done", "ts": ts})
            # Persist the assembled message for history replay (not tokens)
            save_event({"type": "hannah_message", "content": accumulated_text, "ts": ts})

        # Convert Pydantic content blocks to dicts for JSON serialization
        content_serializable = [
            b.model_dump() if hasattr(b, "model_dump") else b
            for b in final.content
        ]
        messages.append({"role": "assistant", "content": final.content})
        save_message("assistant", content_serializable)

        if final.stop_reason != "tool_use":
            break

        tool_results = []
        for block in final.content:
            if block.type != "tool_use":
                continue

            task_id = str(uuid.uuid4())
            is_agent_task = block.name in ("delegate_task", "email_task")

            if is_agent_task:
                description = block.input.get("task", block.name)
                agent_type = block.input.get(
                    "agent_type", "email" if block.name == "email_task" else "general"
                )
                ev = {
                    "type": "task_started",
                    "id": task_id,
                    "agent_type": agent_type,
                    "description": description,
                    "ts": _ts(),
                }
                await _send(ws, ev)
                save_event(ev)

            try:
                result = await execute_tool(block.name, block.input)
                output = result if isinstance(result, str) else json.dumps(result)
            except Exception as exc:
                output = f"Error in {block.name}: {exc}"

            if is_agent_task:
                summary = output[:200].rstrip() + ("…" if len(output) > 200 else "")
                ev = {
                    "type": "task_done",
                    "id": task_id,
                    "summary": summary,
                    "ts": _ts(),
                }
                await _send(ws, ev)
                save_event(ev)

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": output,
            })

        if tool_results:
            messages.append({"role": "user", "content": tool_results})

    return messages


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

    # Send persisted event history so the feed is populated on load
    await _send(ws, {"type": "history", "events": load_events()})

    # Restore conversation history so Hannah has full context
    messages: list = load_messages()

    try:
        while True:
            msg = await ws.receive_json()
            if msg.get("type") != "message":
                continue
            content = msg.get("content", "").strip()
            if not content:
                continue
            ts = _ts()
            ev = {"type": "user_message", "content": content, "ts": ts}
            await _send(ws, ev)
            save_event(ev)
            messages.append({"role": "user", "content": content})
            save_message("user", content)
            messages = await _hannah_loop(ws, messages)
    except WebSocketDisconnect:
        pass


# ── Static UI ──────────────────────────────────────────────────────────────────

if UI_DIST.exists():
    app.mount("/", StaticFiles(directory=UI_DIST, html=True), name="ui")
