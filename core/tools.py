"""Tool definitions and executor for Hannah."""

import json
from datetime import datetime
from pathlib import Path

from agents.runner import run_email_agent, run_general_agent, run_research_agent

# ── Tool schemas (Anthropic API format) ──────────────────────────────────────

TOOLS_DEFINITIONS = [
    {
        "name": "delegate_task",
        "description": (
            "Delegate a task to a specialized sub-agent for autonomous execution. "
            "Use for research, competitive analysis, document drafting, or any task "
            "that requires focused independent work. The sub-agent runs and returns results."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "Clear, detailed task description for the sub-agent",
                },
                "agent_type": {
                    "type": "string",
                    "enum": ["research", "general"],
                    "description": (
                        "'research' for web research tasks; "
                        "'general' for broader tasks including file access"
                    ),
                },
                "context": {
                    "type": "string",
                    "description": "Optional background context to help the sub-agent",
                },
            },
            "required": ["task", "agent_type"],
        },
    },
    {
        "name": "save_note",
        "description": "Save an important note, decision, action item, or piece of context for later retrieval.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Short descriptive title for the note",
                },
                "content": {
                    "type": "string",
                    "description": "The content to save",
                },
            },
            "required": ["title", "content"],
        },
    },
    {
        "name": "read_notes",
        "description": "Read previously saved notes. Optionally filter by a search term.",
        "input_schema": {
            "type": "object",
            "properties": {
                "search": {
                    "type": "string",
                    "description": "Optional keyword to filter notes by title or content",
                }
            },
            "required": [],
        },
    },
    {
        "name": "email_task",
        "description": (
            "Perform an email task using Justin's Gmail account. Use for reading, "
            "searching, drafting, or sending emails. Be specific about what you need — "
            "e.g. 'search for emails from john@example.com this week', "
            "'draft a reply to the last email from Acme Corp', "
            "'send the draft with subject X'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "Detailed description of the email task to perform",
                },
                "context": {
                    "type": "string",
                    "description": "Optional context — e.g. what the email is about, tone to use, etc.",
                },
            },
            "required": ["task"],
        },
    },
    {
        "name": "create_review_item",
        "description": (
            "Add an item to Justin's approval queue. Use this before taking any consequential, "
            "irreversible, or public-facing action: sending emails to clients, posting to social "
            "media, making purchases, or anything that goes out under Justin's name. "
            "Do NOT use for internal research or drafting."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Short title for the item, e.g. 'LinkedIn post: launch announcement'",
                },
                "description": {
                    "type": "string",
                    "description": "What will happen when approved: who receives it, what it says, timing",
                },
                "risk_label": {
                    "type": "string",
                    "description": "One short phrase describing the risk, e.g. 'Public-facing · irreversible' or 'Sends from your email · 12 recipients'",
                },
                "product_id": {
                    "type": "string",
                    "description": "The product this action belongs to",
                },
            },
            "required": ["title", "description", "risk_label", "product_id"],
        },
    },
    {
        "name": "get_datetime",
        "description": "Get the current date and time.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]

# ── Storage ───────────────────────────────────────────────────────────────────

NOTES_DIR = Path.home() / ".hannah" / "notes"
NOTES_DIR.mkdir(parents=True, exist_ok=True)


# ── Executor ──────────────────────────────────────────────────────────────────

async def execute_tool(name: str, inputs: dict) -> str:
    """Dispatch a tool call by name."""
    if name == "delegate_task":
        return await _delegate_task(**inputs)
    if name == "save_note":
        return _save_note(**inputs)
    if name == "read_notes":
        return _read_notes(**inputs)
    if name == "email_task":
        return await _email_task(**inputs)
    if name == "create_review_item":
        return _create_review_item(**inputs)
    if name == "get_datetime":
        return _get_datetime()
    return f"Unknown tool: {name}"


# ── Implementations ───────────────────────────────────────────────────────────

async def _email_task(task: str, context: str = "") -> str:
    full_task = f"{task}\n\nContext: {context}" if context else task
    return await run_email_agent(full_task)


async def _delegate_task(task: str, agent_type: str = "general", context: str = "") -> str:
    full_task = f"{task}\n\nContext: {context}" if context else task
    if agent_type == "research":
        return await run_research_agent(full_task)
    return await run_general_agent(full_task)


def _save_note(title: str, content: str) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_title = "".join(c if c.isalnum() or c in " _-" else "_" for c in title)
    filename = f"{timestamp}_{safe_title[:40].strip().replace(' ', '_')}.md"
    note_path = NOTES_DIR / filename
    note_path.write_text(
        f"# {title}\n\n**Saved:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n{content}\n"
    )
    return f"Saved: {filename}"


def _read_notes(search: str = "") -> str:
    notes = sorted(NOTES_DIR.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not notes:
        return "No notes saved yet."

    matches = []
    for note_path in notes:
        content = note_path.read_text()
        if not search or search.lower() in content.lower():
            matches.append(f"---\n**{note_path.name}**\n{content}")

    if not matches:
        return f"No notes found matching '{search}'."

    return "\n\n".join(matches[:10])


def _get_datetime() -> str:
    return datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")


def _create_review_item(title: str, description: str, risk_label: str, product_id: str) -> str:
    from backend.db import save_review_item
    item_id = save_review_item(
        product_id=product_id,
        title=title,
        description=description,
        risk_label=risk_label,
    )
    return json.dumps({"id": item_id, "title": title, "status": "pending"})
