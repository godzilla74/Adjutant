# Gmail & Calendar Tool Description Trimming Design

**Date:** 2026-04-27
**Goal:** Reduce per-call input tokens by trimming verbose descriptions in `_GMAIL_TOOLS` and `_CALENDAR_TOOLS` in `core/tools.py`.

---

## Background

`TOOLS_DEFINITIONS` was trimmed in a previous task. Two remaining tool lists were deferred:

- `_GMAIL_TOOLS` (4 tools): `gmail_search` has a 3-sentence description with example queries; `gmail_send` has a 3-sentence description with an autonomy-tier note and a usage tip; `gmail_draft` has a 2-sentence description. Parameter descriptions include verbose phrasing like "The product whose Gmail account to search".
- `_CALENDAR_TOOLS` (3 tools): `calendar_create_event` has a 3-sentence description with an autonomy-tier note and an ISO format reminder. Parameter descriptions include long format examples like `"Start datetime in ISO 8601 format with timezone, e.g. '2026-04-18T00:00:00Z'"`.

`_SOCIAL_TOOLS` was trimmed in the social consolidation task and requires no changes.

---

## Approach

Same rules as the previous trimming pass:

- **Top-level description:** one sentence stating what the tool does. Autonomy-tier note ("Respects autonomy tier — creates a review item if set to 'approve'") retained only on tools that send externally or take irreversible action: `gmail_send`, `calendar_create_event`.
- **Parameter descriptions:** ≤8 words. Drop verbose examples and "The product whose X" phrasing in favour of shorter equivalents.

---

## Trimmed Content

### `_GMAIL_TOOLS`

```python
_GMAIL_TOOLS = [
    {
        "name": "gmail_search",
        "description": "Search the product's Gmail inbox and return matching message IDs.",
        "input_schema": {
            "type": "object",
            "properties": {
                "product_id": {"type": "string", "description": "Product's Gmail to search"},
                "query": {"type": "string", "description": "Gmail search query"},
                "max_results": {"type": "integer", "description": "Max messages to return (default 10)"},
            },
            "required": ["product_id", "query"],
        },
    },
    {
        "name": "gmail_read",
        "description": "Read a Gmail message by ID and return its content.",
        "input_schema": {
            "type": "object",
            "properties": {
                "product_id": {"type": "string", "description": "Product's Gmail account"},
                "message_id": {"type": "string", "description": "Message ID from gmail_search"},
            },
            "required": ["product_id", "message_id"],
        },
    },
    {
        "name": "gmail_send",
        "description": "Send an email from the product's Gmail. Respects autonomy tier — creates a review item if set to 'approve'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "product_id": {"type": "string", "description": "Product's Gmail account"},
                "to": {"type": "string", "description": "Recipient email address"},
                "subject": {"type": "string", "description": "Email subject line"},
                "body": {"type": "string", "description": "Plain text email body"},
                "thread_id": {"type": "string", "description": "Thread ID to reply within (optional)"},
            },
            "required": ["product_id", "to", "subject", "body"],
        },
    },
    {
        "name": "gmail_draft",
        "description": "Create a Gmail draft without sending it.",
        "input_schema": {
            "type": "object",
            "properties": {
                "product_id": {"type": "string", "description": "Product's Gmail account"},
                "to": {"type": "string", "description": "Recipient email address"},
                "subject": {"type": "string", "description": "Email subject line"},
                "body": {"type": "string", "description": "Plain text email body"},
            },
            "required": ["product_id", "to", "subject", "body"],
        },
    },
]
```

### `_CALENDAR_TOOLS`

```python
_CALENDAR_TOOLS = [
    {
        "name": "calendar_list_events",
        "description": "List Google Calendar events between two datetimes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "product_id": {"type": "string", "description": "Product's Google Calendar"},
                "start": {"type": "string", "description": "Start datetime, ISO 8601 with timezone"},
                "end": {"type": "string", "description": "End datetime, ISO 8601 with timezone"},
            },
            "required": ["product_id", "start", "end"],
        },
    },
    {
        "name": "calendar_create_event",
        "description": "Create a Google Calendar event. Respects autonomy tier — creates a review item if set to 'approve'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "product_id": {"type": "string", "description": "Product's Google Calendar"},
                "title": {"type": "string", "description": "Event title"},
                "start": {"type": "string", "description": "Start datetime, ISO 8601 with timezone"},
                "end": {"type": "string", "description": "End datetime, ISO 8601 with timezone"},
                "attendees": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Attendee email addresses (optional)",
                },
                "description": {"type": "string", "description": "Event description or agenda (optional)"},
            },
            "required": ["product_id", "title", "start", "end"],
        },
    },
    {
        "name": "calendar_find_free_time",
        "description": "Find free time slots on a date long enough for a meeting.",
        "input_schema": {
            "type": "object",
            "properties": {
                "product_id": {"type": "string", "description": "Product's Google Calendar"},
                "date": {"type": "string", "description": "Date to check, YYYY-MM-DD"},
                "duration_minutes": {"type": "integer", "description": "Required meeting duration in minutes"},
            },
            "required": ["product_id", "date", "duration_minutes"],
        },
    },
]
```

---

## Files Changed

| File | Change |
|------|--------|
| `core/tools.py` | Replace `_GMAIL_TOOLS` and `_CALENDAR_TOOLS` list content with trimmed versions |

---

## Testing

No new tests. Full test suite passes as regression check.

---

## Non-Goals

- Trimming `_SOCIAL_TOOLS` (already done)
- Trimming `TOOLS_DEFINITIONS` (already done)
- Removing parameter descriptions entirely
