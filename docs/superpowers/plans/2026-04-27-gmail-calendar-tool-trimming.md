# Gmail & Calendar Tool Description Trimming Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Trim verbose descriptions in `_GMAIL_TOOLS` and `_CALENDAR_TOOLS` in `core/tools.py` to reduce per-call API token cost.

**Architecture:** Single-file content edit — replace the two list definitions in-place with pre-written trimmed versions. No functional logic changes. Regression suite is the verification.

**Tech Stack:** Python

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `core/tools.py` | Modify (lines 601–722) | Replace `_GMAIL_TOOLS` and `_CALENDAR_TOOLS` content with trimmed descriptions |

---

### Task 1: Replace `_GMAIL_TOOLS` and `_CALENDAR_TOOLS` with trimmed descriptions

**Files:**
- Modify: `core/tools.py` (lines 601–722)

- [ ] **Step 1: Replace `_GMAIL_TOOLS` (lines 601–667)**

Find the block starting with `_GMAIL_TOOLS = [` at line 601 and ending with the closing `]` at line 667. Replace it entirely with:

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

- [ ] **Step 2: Replace `_CALENDAR_TOOLS` (lines 671–722)**

Find the block starting with `_CALENDAR_TOOLS = [` at line 671 and ending with the closing `]` at line 722. Replace it entirely with:

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

- [ ] **Step 3: Verify import still works**

```bash
cd /home/justin/Code/Adjutant
.venv/bin/python -c "from core.tools import get_tools_for_product; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Run the full test suite**

```bash
.venv/bin/python -m pytest tests/ -q 2>&1 | tail -5
```

Expected: 4 pre-existing failures in `test_openai_oauth.py`, everything else passes.

- [ ] **Step 5: Commit**

```bash
git add core/tools.py
git commit -m "feat: trim gmail and calendar tool descriptions to reduce per-call tokens"
```

---

## Self-Review

### Spec coverage
- ✅ `_GMAIL_TOOLS` trimmed — all 4 tools, one-sentence descriptions, parameter descriptions ≤8 words
- ✅ `_CALENDAR_TOOLS` trimmed — all 3 tools, one-sentence descriptions, parameter descriptions ≤8 words
- ✅ Autonomy-tier note retained on `gmail_send` and `calendar_create_event`
- ✅ `_SOCIAL_TOOLS` not touched (already trimmed)

### Placeholder scan
None.

### Type consistency
N/A — content-only edit, no function signatures changed.
