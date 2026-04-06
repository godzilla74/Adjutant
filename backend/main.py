"""Hannah Mission Control — FastAPI backend."""

import json
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

load_dotenv()

app = FastAPI()

UI_DIST = Path(__file__).parent.parent / "ui" / "dist"

HANNAH_PASSWORD = os.environ.get("HANNAH_PASSWORD", "")


def _ts() -> str:
    return datetime.now().isoformat(timespec="seconds")


async def _send(ws: WebSocket, event: dict) -> None:
    await ws.send_text(json.dumps(event))


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

    # Stub message loop — replaced in a later task
    try:
        while True:
            msg = await ws.receive_json()
            if msg.get("type") == "message":
                await _send(ws, {"type": "hannah_token", "content": "Hello (stub)"})
                await _send(ws, {"type": "hannah_done", "ts": _ts()})
    except WebSocketDisconnect:
        pass


if UI_DIST.exists():
    app.mount("/", StaticFiles(directory=UI_DIST, html=True), name="ui")
