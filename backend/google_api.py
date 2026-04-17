"""Direct REST API calls to Gmail and Google Calendar."""

import base64
import json
from email.mime.text import MIMEText

import httpx

from backend.google_oauth import get_valid_access_token

_GMAIL_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"
_CALENDAR_BASE = "https://www.googleapis.com/calendar/v3"


# ── Gmail ─────────────────────────────────────────────────────────────────────

async def gmail_search(product_id: str, query: str, max_results: int = 10) -> str:
    token = await get_valid_access_token(product_id, "gmail")
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{_GMAIL_BASE}/messages",
            headers={"Authorization": f"Bearer {token}"},
            params={"q": query, "maxResults": max_results},
        )
        resp.raise_for_status()
        data = resp.json()
    messages = data.get("messages", [])
    if not messages:
        return "No messages found."
    return json.dumps({"message_ids": [m["id"] for m in messages], "count": len(messages)})


def _extract_body(payload: dict) -> str:
    if payload.get("mimeType") == "text/plain":
        raw = payload.get("body", {}).get("data", "")
        return base64.urlsafe_b64decode(raw + "==").decode("utf-8", errors="replace") if raw else ""
    for part in payload.get("parts", []):
        text = _extract_body(part)
        if text:
            return text
    return ""


async def gmail_read(product_id: str, message_id: str) -> str:
    token = await get_valid_access_token(product_id, "gmail")
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{_GMAIL_BASE}/messages/{message_id}",
            headers={"Authorization": f"Bearer {token}"},
            params={"format": "full"},
        )
        resp.raise_for_status()
        data = resp.json()
    hdrs = {h["name"]: h["value"] for h in data.get("payload", {}).get("headers", [])}
    body = _extract_body(data.get("payload", {}))
    return json.dumps({
        "from": hdrs.get("From", ""),
        "to": hdrs.get("To", ""),
        "subject": hdrs.get("Subject", ""),
        "date": hdrs.get("Date", ""),
        "body": body[:3000],
    })


def _build_raw_email(to: str, subject: str, body: str) -> str:
    msg = MIMEText(body)
    msg["to"] = to
    msg["subject"] = subject
    return base64.urlsafe_b64encode(msg.as_bytes()).decode()


async def gmail_send(
    product_id: str, to: str, subject: str, body: str, thread_id: str | None = None,
) -> str:
    token = await get_valid_access_token(product_id, "gmail")
    payload: dict = {"raw": _build_raw_email(to, subject, body)}
    if thread_id:
        payload["threadId"] = thread_id
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{_GMAIL_BASE}/messages/send",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
    return json.dumps({"message_id": data.get("id"), "thread_id": data.get("threadId"), "sent": True})


async def gmail_draft(product_id: str, to: str, subject: str, body: str) -> str:
    token = await get_valid_access_token(product_id, "gmail")
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{_GMAIL_BASE}/drafts",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"message": {"raw": _build_raw_email(to, subject, body)}},
        )
        resp.raise_for_status()
        data = resp.json()
    return json.dumps({"draft_id": data.get("id"), "created": True})
