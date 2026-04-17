"""Direct REST API calls to Gmail and Google Calendar."""

import base64
import json
from email.mime.text import MIMEText

import httpx

import backend.google_oauth as google_oauth
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
        try:
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"Gmail API error: {e.response.status_code}") from e
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
        try:
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"Gmail API error: {e.response.status_code}") from e
        data = resp.json()
    hdrs = {h["name"]: h["value"] for h in data.get("payload", {}).get("headers", []) if "name" in h and "value" in h}
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
        try:
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"Gmail API error: {e.response.status_code}") from e
        data = resp.json()
    return json.dumps({"message_id": data.get("id"), **({"thread_id": data["threadId"]} if data.get("threadId") else {}), "sent": True})


async def gmail_draft(product_id: str, to: str, subject: str, body: str) -> str:
    token = await get_valid_access_token(product_id, "gmail")
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{_GMAIL_BASE}/drafts",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"message": {"raw": _build_raw_email(to, subject, body)}},
        )
        try:
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"Gmail API error: {e.response.status_code}") from e
        data = resp.json()
    return json.dumps({"draft_id": data.get("id"), "created": True})


# ── Calendar ──────────────────────────────────────────────────────────────────

async def calendar_list_events(product_id: str, start: str, end: str) -> str:
    token = await google_oauth.get_valid_access_token(product_id, "google_calendar")
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{_CALENDAR_BASE}/calendars/primary/events",
            headers={"Authorization": f"Bearer {token}"},
            params={"timeMin": start, "timeMax": end, "singleEvents": "true", "orderBy": "startTime"},
        )
        try:
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"Calendar API error: {e.response.status_code}") from e
        data = resp.json()
    events = [
        {
            "id": e["id"],
            "summary": e.get("summary", ""),
            "start": e.get("start", {}).get("dateTime", e.get("start", {}).get("date", "")),
            "end": e.get("end", {}).get("dateTime", e.get("end", {}).get("date", "")),
            "attendees": [a["email"] for a in e.get("attendees", [])],
        }
        for e in data.get("items", [])
    ]
    return json.dumps({"events": events, "count": len(events)})


async def calendar_create_event(
    product_id: str,
    title: str,
    start: str,
    end: str,
    attendees: list | None = None,
    description: str | None = None,
) -> str:
    token = await google_oauth.get_valid_access_token(product_id, "google_calendar")
    event: dict = {"summary": title, "start": {"dateTime": start}, "end": {"dateTime": end}}
    if attendees:
        event["attendees"] = [{"email": e} for e in attendees]
    if description:
        event["description"] = description
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{_CALENDAR_BASE}/calendars/primary/events",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=event,
        )
        try:
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"Calendar API error: {e.response.status_code}") from e
        data = resp.json()
    return json.dumps({"event_id": data.get("id"), "html_link": data.get("htmlLink"), "created": True})


async def calendar_find_free_time(product_id: str, date: str, duration_minutes: int) -> str:
    from datetime import datetime, timedelta, timezone
    token = await google_oauth.get_valid_access_token(product_id, "google_calendar")
    day_start = f"{date}T00:00:00Z"
    day_end = f"{date}T23:59:59Z"
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{_CALENDAR_BASE}/freeBusy",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"timeMin": day_start, "timeMax": day_end, "items": [{"id": "primary"}]},
        )
        try:
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"Calendar API error: {e.response.status_code}") from e
        data = resp.json()
    busy = data.get("calendars", {}).get("primary", {}).get("busy", [])
    cursor = datetime.fromisoformat(day_start.replace("Z", "+00:00"))
    end_of_day = datetime.fromisoformat(day_end.replace("Z", "+00:00"))
    slots = []
    for period in busy:
        busy_start = datetime.fromisoformat(period["start"].replace("Z", "+00:00"))
        if (busy_start - cursor).total_seconds() >= duration_minutes * 60:
            slots.append({"start": cursor.isoformat(), "end": busy_start.isoformat()})
        cursor = datetime.fromisoformat(period["end"].replace("Z", "+00:00"))
    if (end_of_day - cursor).total_seconds() >= duration_minutes * 60:
        slots.append({"start": cursor.isoformat(), "end": end_of_day.isoformat()})
    return json.dumps({"free_slots": slots[:5], "date": date, "duration_minutes": duration_minutes})
