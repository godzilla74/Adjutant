"""Tool definitions and executor for Adjutant."""

import importlib
import json
import pkgutil
import sys
from datetime import datetime
from pathlib import Path

from agents.runner import run_general_agent, run_research_agent

# ── Extension auto-loader ─────────────────────────────────────────────────────

_EXTENSIONS_DIR = Path(__file__).parent.parent / "extensions"
_EXTENSION_EXECUTORS: dict = {}
_EXT_CONFIG = _EXTENSIONS_DIR / "_config.json"


def _get_disabled_extensions() -> set:
    if not _EXT_CONFIG.exists():
        return set()
    import json
    try:
        return set(json.loads(_EXT_CONFIG.read_text()).get("disabled", []))
    except Exception:
        return set()


def _set_disabled_extensions(disabled: set) -> None:
    import json
    _EXTENSIONS_DIR.mkdir(exist_ok=True)
    _EXT_CONFIG.write_text(json.dumps({"disabled": sorted(disabled)}, indent=2))


def _load_extensions() -> list[dict]:
    """Discover and load all tool extensions from the extensions/ directory."""
    disabled = _get_disabled_extensions()
    definitions = []
    if not _EXTENSIONS_DIR.exists():
        return definitions
    for finder, name, _ in pkgutil.iter_modules([str(_EXTENSIONS_DIR)]):
        if name in disabled:
            continue
        try:
            mod = importlib.import_module(f"extensions.{name}")
            if hasattr(mod, "TOOL_DEFINITION") and hasattr(mod, "execute"):
                definitions.append(mod.TOOL_DEFINITION)
                _EXTENSION_EXECUTORS[mod.TOOL_DEFINITION["name"]] = mod.execute
        except Exception as e:
            print(f"[extensions] Failed to load {name}: {e}", file=sys.stderr)
    return definitions

# ── Tool schemas (Anthropic API format) ──────────────────────────────────────

TOOLS_DEFINITIONS = [
    {
        "name": "delegate_task",
        "description": "Delegate a task to a specialized sub-agent for autonomous execution.",
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
                    "description": "'research' for web research; 'general' for broader tasks including file access",
                },
                "context": {
                    "type": "string",
                    "description": "Background context and rationale shown to the user",
                },
            },
            "required": ["task", "agent_type"],
        },
    },
    {
        "name": "save_note",
        "description": "Save an important note, decision, or action item for later retrieval.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Short descriptive title"},
                "content": {"type": "string", "description": "Content to save"},
            },
            "required": ["title", "content"],
        },
    },
    {
        "name": "read_notes",
        "description": "Read previously saved notes, optionally filtered by keyword.",
        "input_schema": {
            "type": "object",
            "properties": {
                "search": {"type": "string", "description": "Keyword to filter notes by"},
            },
            "required": [],
        },
    },
    {
        "name": "create_review_item",
        "description": (
            "Add an item to the user's approval queue before taking any consequential, "
            "irreversible, or public-facing action."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Short title, e.g. 'LinkedIn post: launch announcement'",
                },
                "description": {
                    "type": "string",
                    "description": "2-3 sentence summary of what will happen when approved",
                },
                "risk_label": {
                    "type": "string",
                    "description": "Short risk phrase, e.g. 'Public-facing · irreversible'",
                },
                "product_id": {"type": "string", "description": "The product this action belongs to"},
                "action_type": {
                    "type": "string",
                    "enum": ["social_post", "email", "agent_review"],
                    "description": "Category: social_post, email, or agent_review",
                },
            },
            "required": ["title", "description", "risk_label", "product_id", "action_type"],
        },
    },
    {
        "name": "create_objective",
        "description": "Create a new objective (goal or target) for a product.",
        "input_schema": {
            "type": "object",
            "properties": {
                "product_id": {"type": "string", "description": "Product this objective belongs to"},
                "text": {"type": "string", "description": "Objective description, e.g. '500 Instagram followers by June 1'"},
                "progress_current": {"type": "integer", "description": "Starting progress value (default 0)"},
                "progress_target": {"type": "integer", "description": "Target value; omit if open-ended"},
            },
            "required": ["product_id", "text"],
        },
    },
    {
        "name": "update_objective",
        "description": "Update progress on an active objective after completing work that advances a measurable goal.",
        "input_schema": {
            "type": "object",
            "properties": {
                "product_id": {"type": "string", "description": "Product this objective belongs to"},
                "text_fragment": {"type": "string", "description": "Words from the objective text to identify it"},
                "progress_current": {"type": "integer", "description": "New current progress value"},
                "progress_target": {"type": "integer", "description": "Updated target value (optional)"},
            },
            "required": ["product_id", "text_fragment", "progress_current"],
        },
    },
    {
        "name": "create_product",
        "description": "Create a new product in Adjutant.",
        "input_schema": {
            "type": "object",
            "properties": {
                "id":         {"type": "string", "description": "Unique slug, e.g. 'my-product'"},
                "name":       {"type": "string", "description": "Display name"},
                "icon_label": {"type": "string", "description": "2-3 char label shown in product rail"},
                "color":      {"type": "string", "description": "Hex color, e.g. '#2563eb'"},
            },
            "required": ["id", "name", "icon_label", "color"],
        },
    },
    {
        "name": "update_product",
        "description": "Update a product's display info or brand configuration.",
        "input_schema": {
            "type": "object",
            "properties": {
                "product_id":      {"type": "string", "description": "Product id slug"},
                "name":            {"type": "string", "description": "Display name"},
                "icon_label":      {"type": "string", "description": "2-3 char label"},
                "color":           {"type": "string", "description": "Hex color"},
                "brand_voice":     {"type": "string", "description": "Brand voice description"},
                "tone":            {"type": "string", "description": "Tone guidelines"},
                "writing_style":   {"type": "string", "description": "Writing style notes"},
                "target_audience": {"type": "string", "description": "Who the product is for"},
                "social_handles":  {"type": "string", "description": "JSON string of platform handles"},
                "hashtags":        {"type": "string", "description": "Comma-separated hashtags"},
                "brand_notes":     {"type": "string", "description": "Additional brand guidance"},
            },
            "required": ["product_id"],
        },
    },
    {
        "name": "delete_product",
        "description": "Permanently delete a product and all its data. Irreversible.",
        "input_schema": {
            "type": "object",
            "properties": {
                "product_id": {"type": "string", "description": "Product id slug"},
            },
            "required": ["product_id"],
        },
    },
    {
        "name": "create_workstream",
        "description": "Add a new workstream (operational area) to a product.",
        "input_schema": {
            "type": "object",
            "properties": {
                "product_id": {"type": "string"},
                "name":       {"type": "string", "description": "Workstream name, e.g. 'Content'"},
                "status":     {"type": "string", "enum": ["running", "warn", "paused"], "description": "Initial status (default: paused)"},
            },
            "required": ["product_id", "name"],
        },
    },
    {
        "name": "update_workstream_status",
        "description": "Change the status of a workstream (running / warn / paused).",
        "input_schema": {
            "type": "object",
            "properties": {
                "product_id":    {"type": "string"},
                "name_fragment": {"type": "string", "description": "Part of workstream name to match"},
                "status":        {"type": "string", "enum": ["running", "warn", "paused"]},
            },
            "required": ["product_id", "name_fragment", "status"],
        },
    },
    {
        "name": "delete_workstream",
        "description": "Remove a workstream from a product.",
        "input_schema": {
            "type": "object",
            "properties": {
                "product_id":    {"type": "string"},
                "name_fragment": {"type": "string", "description": "Part of workstream name to match"},
            },
            "required": ["product_id", "name_fragment"],
        },
    },
    {
        "name": "delete_objective",
        "description": "Remove a completed or obsolete objective.",
        "input_schema": {
            "type": "object",
            "properties": {
                "product_id":    {"type": "string"},
                "text_fragment": {"type": "string", "description": "Part of objective text to match"},
            },
            "required": ["product_id", "text_fragment"],
        },
    },
    {
        "name": "draft_social_post",
        "description": (
            "Draft a social media post for a product and add it to the approval queue. "
            "Respects autonomy tier — publishes immediately if set to 'auto'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "product_id":        {"type": "string"},
                "platform":          {"type": "string", "description": "e.g. 'instagram', 'linkedin'"},
                "content":           {"type": "string", "description": "Post text, ready to publish"},
                "image_description": {"type": "string", "description": "Description of image to pair with post"},
                "image_url":         {"type": "string", "description": "Public image URL (required for Instagram)"},
                "scheduled_for":     {"type": "string", "description": "ISO-8601 datetime to auto-publish"},
            },
            "required": ["product_id", "platform", "content"],
        },
    },
    {
        "name": "find_skill",
        "description": "Search the skills.sh ecosystem for agent skills that add a new capability.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Keywords to search for"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "install_skill",
        "description": "Install a skill from skills.sh. Run find_skill first to identify the right package.",
        "input_schema": {
            "type": "object",
            "properties": {
                "package": {"type": "string", "description": "Package to install, e.g. 'org/skills@name'"},
            },
            "required": ["package"],
        },
    },
    {
        "name": "add_agent_tool",
        "description": "Create a new tool by writing an extension file that spawns a sub-agent. Call restart_server after.",
        "input_schema": {
            "type": "object",
            "properties": {
                "tool_name":          {"type": "string", "description": "Snake_case tool name"},
                "description":        {"type": "string", "description": "What this tool does"},
                "agent_instructions": {"type": "string", "description": "System prompt for the sub-agent"},
            },
            "required": ["tool_name", "description", "agent_instructions"],
        },
    },
    {
        "name": "restart_server",
        "description": "Restart the Adjutant server to pick up new extensions or code changes.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
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
    {
        "name": "shell_task",
        "description": "Run a shell command on the local host machine. Sources ~/.bashrc; returns exit code and combined output.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to run"},
                "timeout": {"type": "integer", "description": "Timeout in seconds (default 120)"},
                "cwd":     {"type": "string", "description": "Working directory (default: home)"},
            },
            "required": ["command"],
        },
    },
    {
        "name": "list_uploads",
        "description": "List all files that have been uploaded or stored locally.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "send_telegram_file",
        "description": "Send a locally stored file to the user via Telegram.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Absolute path to the file to send"},
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "manage_mcp_server",
        "description": "Add, remove, enable, disable, or list MCP servers. Confirm scope (global vs product) with the user before adding.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["add", "remove", "enable", "disable", "list"],
                    "description": "Action to perform",
                },
                "name":       {"type": "string", "description": "Display name (required for add)"},
                "type":       {"type": "string", "enum": ["remote", "stdio"], "description": "remote or stdio"},
                "url":        {"type": "string", "description": "SSE/HTTP endpoint URL (remote only)"},
                "command":    {"type": "string", "description": "Executable command (stdio only)"},
                "args":       {"type": "array", "items": {"type": "string"}, "description": "Command arguments (stdio only)"},
                "env":        {"type": "object", "description": "Auth headers (remote) or env vars (stdio)"},
                "scope":      {"type": "string", "enum": ["global", "product"], "description": "global or product-scoped"},
                "product_id": {"type": "string", "description": "Required when scope is 'product'"},
                "server_id":  {"type": "integer", "description": "Required for remove, enable, disable"},
            },
            "required": ["action"],
        },
    },
    {
        "name": "schedule_next_run",
        "description": "Schedule the next autonomous run for an objective. Call at the end of every autonomous cycle.",
        "input_schema": {
            "type": "object",
            "properties": {
                "objective_id": {"type": "integer", "description": "The objective's ID"},
                "hours":        {"type": "number", "description": "Hours until next run (min 0.25)"},
                "reason":       {"type": "string", "description": "Why this cadence makes sense"},
            },
            "required": ["objective_id", "hours", "reason"],
        },
    },
    {
        "name": "update_objective_progress",
        "description": "Update measurable progress toward an objective with a new concrete number.",
        "input_schema": {
            "type": "object",
            "properties": {
                "objective_id": {"type": "integer", "description": "The objective's ID"},
                "current":      {"type": "integer", "description": "New current progress value"},
                "notes":        {"type": "string", "description": "How this was measured or what changed"},
            },
            "required": ["objective_id", "current"],
        },
    },
    {
        "name": "set_objective_autonomous",
        "description": "Enable or disable autonomous mode for an objective.",
        "input_schema": {
            "type": "object",
            "properties": {
                "objective_id": {"type": "integer", "description": "The objective's ID"},
                "autonomous":   {"type": "boolean", "description": "true to enable, false to disable"},
            },
            "required": ["objective_id", "autonomous"],
        },
    },
    {
        "name": "report_wizard_progress",
        "description": "Report what you are currently doing during the launch wizard setup.",
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "Present-tense description, e.g. 'Configuring brand voice'"},
            },
            "required": ["message"],
        },
    },
    {
        "name": "complete_launch",
        "description": "End the launch wizard after the product is fully configured and all objectives are set to autonomous.",
        "input_schema": {
            "type": "object",
            "properties": {
                "product_id": {"type": "string", "description": "The product's ID"},
                "summary":    {"type": "string", "description": "2-3 sentence summary of what was set up"},
            },
            "required": ["product_id", "summary"],
        },
    },
    {
        "name": "search_stock_photo",
        "description": "Search Pexels for a stock photo. Returns a public CDN URL suitable for social posts.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Description of the photo needed"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "generate_image",
        "description": "Generate a custom image from a text prompt using DALL-E 3. Requires OpenAI connection.",
        "input_schema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "Detailed description of the image to generate"},
            },
            "required": ["prompt"],
        },
    },
    {
        "name": "manage_capability_slots",
        "description": "Manage capability slot definitions (list, create, or delete). System slots cannot be deleted.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["list", "create", "delete"],
                    "description": "Operation to perform",
                },
                "name":          {"type": "string", "description": "Slot name slug (required for create/delete)"},
                "label":         {"type": "string", "description": "Human-readable display name (required for create)"},
                "built_in_tools": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Built-in tool names this slot replaces",
                },
            },
            "required": ["action"],
        },
    },
]

# Load all extension modules at startup. Extensions are NOT added to TOOLS_DEFINITIONS —
# they are filtered per-product at runtime via get_extensions_for_product().
_EXTENSION_DEFS: dict[str, dict] = {}  # module_name → tool definition

def _load_all_extensions() -> None:
    if not _EXTENSIONS_DIR.exists():
        return
    for _, name, _ in pkgutil.iter_modules([str(_EXTENSIONS_DIR)]):
        try:
            mod = importlib.import_module(f"extensions.{name}")
            if hasattr(mod, "TOOL_DEFINITION") and hasattr(mod, "execute"):
                _EXTENSION_DEFS[name] = mod.TOOL_DEFINITION
                _EXTENSION_EXECUTORS[mod.TOOL_DEFINITION["name"]] = mod.execute
        except Exception as e:
            print(f"[extensions] Failed to load {name}: {e}", file=sys.stderr)

_load_all_extensions()


def get_extensions_for_product(product_id: str | None) -> list[dict]:
    """Return tool definitions for extensions enabled for this product."""
    if not product_id:
        return []
    from backend.db import get_product_extension_names
    enabled_names = get_product_extension_names(product_id)
    return [defn for name, defn in _EXTENSION_DEFS.items() if name in enabled_names]

# ── Tool Groups ───────────────────────────────────────────────────────────────

TOOL_GROUPS: dict[str, set[str]] = {
    "core": {
        "delegate_task", "save_note", "read_notes", "create_review_item",
        "get_datetime", "shell_task", "list_uploads", "send_telegram_file",
        "schedule_next_run",
    },
    "email": {"gmail_search", "gmail_read", "gmail_send", "gmail_draft"},
    "calendar": {"calendar_list_events", "calendar_create_event", "calendar_find_free_time"},
    "social": {
        "draft_social_post", "post_to_social", "generate_image", "search_stock_photo",
    },
    "management": {
        "create_product", "update_product", "delete_product",
        "create_workstream", "update_workstream_status", "delete_workstream",
        "create_objective", "update_objective", "update_objective_progress",
        "delete_objective", "set_objective_autonomous",
    },
    "system": {
        "add_agent_tool", "find_skill", "install_skill", "restart_server",
        "manage_mcp_server", "manage_capability_slots",
        "report_wizard_progress", "complete_launch",
    },
}


def get_tools_for_groups(groups: list[str], product_id: str | None) -> list[dict]:
    """Return only the tools belonging to the requested groups (core always included).

    Reuses get_tools_for_product() so OAuth/extension logic is not duplicated.
    Extensions are always included regardless of group selection.
    """
    all_tools = get_tools_for_product(product_id) if product_id else get_global_tools()
    ext_names = {t["name"] for t in get_extensions_for_product(product_id)} if product_id else set()

    allowed: set[str] = set(TOOL_GROUPS.get("core", set()))
    for g in groups:
        allowed |= TOOL_GROUPS.get(g, set())

    return [t for t in all_tools if t["name"] in allowed or t["name"] in ext_names]

_DISPATCH_TOOL = {
    "name": "dispatch_to_product",
    "description": (
        "Route a directive to a specific product agent for execution. "
        "Use when the message clearly targets one product. "
        "Acknowledge briefly before calling this tool (e.g. 'On it' or 'Forwarding to [Product]')."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "product_id": {
                "type": "string",
                "description": "The id of the target product (from the products list in your system prompt)",
            },
            "message": {
                "type": "string",
                "description": "The full directive to send to the product agent",
            },
        },
        "required": ["product_id", "message"],
    },
}

_GLOBAL_BASE_TOOL_NAMES = {
    "delegate_task", "save_note", "read_notes", "get_datetime", "shell_task",
    "create_product", "update_product", "delete_product",
    "create_workstream", "update_workstream_status", "delete_workstream",
    "create_objective", "update_objective", "delete_objective",
}


def get_global_tools() -> list[dict]:
    """Tools available to the global (product_id=None) agent."""
    base = [t for t in TOOLS_DEFINITIONS if t["name"] in _GLOBAL_BASE_TOOL_NAMES]
    return base + [_DISPATCH_TOOL]


# ── Gmail tools (injected per-product when OAuth connected) ───────────────────

_GMAIL_TOOLS = [
    {
        "name": "gmail_search",
        "description": (
            "Search the product's connected Gmail inbox. Returns message IDs matching the query. "
            "Follow up with gmail_read to read specific messages. "
            "Example queries: 'from:john@example.com', 'subject:invoice is:unread'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "product_id": {"type": "string", "description": "The product whose Gmail account to search"},
                "query": {"type": "string", "description": "Gmail search query"},
                "max_results": {"type": "integer", "description": "Maximum messages to return (default 10)"},
            },
            "required": ["product_id", "query"],
        },
    },
    {
        "name": "gmail_read",
        "description": "Read the full content of a Gmail message by its ID. Returns sender, subject, date, and body.",
        "input_schema": {
            "type": "object",
            "properties": {
                "product_id": {"type": "string", "description": "The product whose Gmail account to read from"},
                "message_id": {"type": "string", "description": "Gmail message ID (from gmail_search results)"},
            },
            "required": ["product_id", "message_id"],
        },
    },
    {
        "name": "gmail_send",
        "description": (
            "Send an email from the product's connected Gmail account. "
            "Respects the product's autonomy tier — if set to 'approve', creates a review item instead of sending immediately. "
            "Use thread_id to reply to an existing thread."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "product_id": {"type": "string", "description": "The product whose Gmail account to send from"},
                "to": {"type": "string", "description": "Recipient email address"},
                "subject": {"type": "string", "description": "Email subject line"},
                "body": {"type": "string", "description": "Plain text email body"},
                "thread_id": {"type": "string", "description": "Optional: Gmail thread ID to reply within"},
            },
            "required": ["product_id", "to", "subject", "body"],
        },
    },
    {
        "name": "gmail_draft",
        "description": (
            "Create a Gmail draft without sending it. Use when the user wants to compose but not send, "
            "or when you want to prepare content for review."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "product_id": {"type": "string", "description": "The product whose Gmail account to draft in"},
                "to": {"type": "string", "description": "Recipient email address"},
                "subject": {"type": "string", "description": "Email subject line"},
                "body": {"type": "string", "description": "Plain text email body"},
            },
            "required": ["product_id", "to", "subject", "body"],
        },
    },
]

# ── Calendar tools (injected per-product when OAuth connected) ────────────────

_CALENDAR_TOOLS = [
    {
        "name": "calendar_list_events",
        "description": "List events on the product's Google Calendar between two ISO 8601 datetimes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "product_id": {"type": "string", "description": "The product whose calendar to query"},
                "start": {"type": "string", "description": "Start datetime in ISO 8601 format with timezone, e.g. '2026-04-18T00:00:00Z'"},
                "end": {"type": "string", "description": "End datetime in ISO 8601 format with timezone"},
            },
            "required": ["product_id", "start", "end"],
        },
    },
    {
        "name": "calendar_create_event",
        "description": (
            "Create a Google Calendar event for the product. "
            "Respects the product's autonomy tier — if set to 'approve', creates a review item instead. "
            "Use ISO 8601 datetimes with timezone for start and end."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "product_id": {"type": "string", "description": "The product whose calendar to add the event to"},
                "title": {"type": "string", "description": "Event title"},
                "start": {"type": "string", "description": "Start datetime in ISO 8601 format, e.g. '2026-04-18T10:00:00Z'"},
                "end": {"type": "string", "description": "End datetime in ISO 8601 format"},
                "attendees": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of attendee email addresses",
                },
                "description": {"type": "string", "description": "Optional event description or agenda"},
            },
            "required": ["product_id", "title", "start", "end"],
        },
    },
    {
        "name": "calendar_find_free_time",
        "description": "Find free time slots on a specific date long enough for a meeting of the given duration.",
        "input_schema": {
            "type": "object",
            "properties": {
                "product_id": {"type": "string", "description": "The product whose calendar to check"},
                "date": {"type": "string", "description": "Date to check in YYYY-MM-DD format"},
                "duration_minutes": {"type": "integer", "description": "Required meeting duration in minutes"},
            },
            "required": ["product_id", "date", "duration_minutes"],
        },
    },
]


_SOCIAL_TOOLS = [
    {
        "name": "post_to_social",
        "description": (
            "Post to a social platform. Respects autonomy tier — creates a review item if set to 'approve'. "
            "Instagram requires image_url."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "product_id": {"type": "string", "description": "Product to post from"},
                "platform": {
                    "type": "string",
                    "enum": ["twitter", "linkedin", "facebook", "instagram"],
                    "description": "Target platform",
                },
                "text": {"type": "string", "description": "Post text (used as caption on Instagram)"},
                "image_url": {"type": "string", "description": "Image URL (required for Instagram)"},
            },
            "required": ["product_id", "platform", "text"],
        },
    },
]


def get_tools_for_product(product_id: str) -> list[dict]:
    from backend.db import list_oauth_connections
    tools = list(TOOLS_DEFINITIONS)
    tools.extend(get_extensions_for_product(product_id))
    connections = {c["service"] for c in list_oauth_connections(product_id)}
    if "gmail" in connections:
        tools.extend(_GMAIL_TOOLS)
    if "google_calendar" in connections:
        tools.extend(_CALENDAR_TOOLS)
    # _SOCIAL_TOOLS is always included regardless of OAuth connections — the
    # underlying helpers fall back to browser automation when no API connection
    # is configured, so all platforms remain available unconditionally.
    tools.extend(_SOCIAL_TOOLS)
    return tools


def get_capability_override_context(
    product_id: str,
    connected_mcp_servers: set[str],
) -> tuple[set[str], dict[str, str]]:
    """Return (tools_to_suppress, disconnected_overrides).

    tools_to_suppress: built-in tool names to remove from the tool list because
    their override MCP server is currently connected.

    disconnected_overrides: {tool_name: server_name} for built-in tools whose
    override server is configured but not connected — used by the pre-flight check.
    """
    from backend.db import list_capability_overrides, list_capability_slot_definitions
    slot_map = {s["name"]: s["built_in_tools"] for s in list_capability_slot_definitions()}
    overrides = list_capability_overrides(product_id)
    suppress: set[str] = set()
    disconnected: dict[str, str] = {}
    for row in overrides:
        slot = row["capability_slot"]
        server_name = row["mcp_server_name"]
        slot_tools = slot_map.get(slot, [])
        if server_name in connected_mcp_servers:
            suppress.update(slot_tools)
        else:
            for tool_name in slot_tools:
                disconnected[tool_name] = server_name
    return suppress, disconnected

# ── Storage ───────────────────────────────────────────────────────────────────

NOTES_DIR = Path.home() / ".hannah" / "notes"
NOTES_DIR.mkdir(parents=True, exist_ok=True)


# ── Executor functions ───────────────────────────────────────────────────────

def _report_wizard_progress(message: str) -> str:
    return message


def _complete_launch(product_id: str, summary: str) -> str:
    from backend.db import set_launch_wizard_active
    set_launch_wizard_active(product_id, False)
    return summary

# ── MCP server management ─────────────────────────────────────────────────────

async def _manage_mcp_server(
    action: str,
    name: str | None = None,
    type: str | None = None,
    url: str | None = None,
    command: str | None = None,
    args: list | None = None,
    env: dict | None = None,
    scope: str | None = None,
    product_id: str | None = None,
    server_id: int | None = None,
) -> str:
    import json as _json
    from backend.db import (
        add_mcp_server, list_mcp_servers, list_all_mcp_servers,
        get_mcp_server, update_mcp_server, delete_mcp_server,
    )

    if action == "list":
        servers = list_mcp_servers(product_id) if product_id else list_all_mcp_servers()
        if not servers:
            return "No MCP servers configured."
        lines = ["Configured MCP servers:"]
        for s in servers:
            status = "enabled" if s["enabled"] else "disabled"
            scope_str = "global" if s["scope"] == "global" else f"product:{s['product_id']}"
            lines.append(f"  [{s['id']}] {s['name']} ({s['type']}, {scope_str}, {status})")
        return "\n".join(lines)

    elif action == "add":
        if not name or not type or not scope:
            return "Error: name, type, and scope are required for add."
        if type == "remote" and not url:
            return "Error: url is required for remote type."
        if type == "stdio" and not command:
            return "Error: command is required for stdio type."
        if scope == "product" and not product_id:
            return "Error: product_id is required when scope is 'product'."

        env_json = _json.dumps(env) if env else None
        args_json = _json.dumps(args) if args else None

        sid = add_mcp_server(
            name=name, type=type, url=url, command=command,
            args=args_json, env=env_json, scope=scope, product_id=product_id,
        )

        if type == "stdio":
            import backend.main as _main
            if _main._mcp_manager is not None:
                config = get_mcp_server(sid)
                await _main._mcp_manager.add_server(config)

        mode = "active" if type == "remote" else "connecting"
        return f"MCP server '{name}' added (id: {sid}). It is now {mode}."

    elif action == "remove":
        if server_id is None:
            return "Error: server_id is required for remove."
        server = get_mcp_server(server_id)
        if not server:
            return f"Error: no server with id {server_id}."
        if server["type"] == "stdio":
            import backend.main as _main
            if _main._mcp_manager is not None:
                await _main._mcp_manager.remove_server(server_id)
        delete_mcp_server(server_id)
        return f"Removed MCP server '{server['name']}'."

    elif action == "enable":
        if server_id is None:
            return "Error: server_id is required for enable."
        server = get_mcp_server(server_id)
        if not server:
            return f"Error: no server with id {server_id}."
        update_mcp_server(server_id, enabled=True)
        if server["type"] == "stdio":
            import backend.main as _main
            if _main._mcp_manager is not None:
                config = get_mcp_server(server_id)
                await _main._mcp_manager.add_server(config)
        return f"Enabled MCP server '{server['name']}'."

    elif action == "disable":
        if server_id is None:
            return "Error: server_id is required for disable."
        server = get_mcp_server(server_id)
        if not server:
            return f"Error: no server with id {server_id}."
        update_mcp_server(server_id, enabled=False)
        if server["type"] == "stdio":
            import backend.main as _main
            if _main._mcp_manager is not None:
                await _main._mcp_manager.remove_server(server_id)
        return f"Disabled MCP server '{server['name']}'."

    return f"Unknown action: {action}"


async def _search_stock_photo(query: str) -> str:
    import httpx
    from backend.db import get_agent_config
    cfg = get_agent_config()
    api_key = cfg.get("pexels_api_key", "")
    if not api_key:
        return "Stock photo search not configured — add a Pexels API key in Global settings."
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://api.pexels.com/v1/search",
                params={"query": query, "per_page": 1},
                headers={"Authorization": api_key},
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as e:
        return f"Pexels API error: {e.response.status_code}"
    except Exception as e:
        return f"Stock photo search failed: {e}"
    photos = data.get("photos", [])
    if not photos:
        return f"No stock photos found for: {query}"
    return photos[0]["src"]["large2x"]


async def _generate_image(prompt: str) -> str:
    import os
    import httpx
    from backend.db import get_agent_config
    from backend.uploads import save_uploaded_file
    cfg = get_agent_config()
    token = cfg.get("openai_access_token", "")
    if not token:
        return "Image generation not configured — add an OpenAI access token in Global settings."
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://api.openai.com/v1/images/generations",
                headers={"Authorization": f"Bearer {token}"},
                json={"prompt": prompt, "model": "dall-e-3", "n": 1, "size": "1024x1024"},
            )
            resp.raise_for_status()
            image_url = resp.json()["data"][0]["url"]
            img_resp = await client.get(image_url)
            img_resp.raise_for_status()
            path = save_uploaded_file("generated.png", img_resp.content)
        port = os.environ.get("HANNAH_PORT", "8001")
        return f"http://localhost:{port}/uploads/{path.name}"
    except Exception as e:
        return f"Image generation failed: {e}"


# ── Capability slot management ────────────────────────────────────────────────

def _manage_capability_slots(
    action: str,
    name: str | None = None,
    label: str | None = None,
    built_in_tools: list[str] | None = None,
) -> str:
    from backend.db import list_capability_slot_definitions, create_capability_slot_definition, delete_capability_slot_definition

    if action == "list":
        slots = list_capability_slot_definitions()
        if not slots:
            return "No capability slots defined."
        lines = ["Capability slots:"]
        for s in slots:
            kind = "system" if s["is_system"] else "custom"
            tools_str = ", ".join(s["built_in_tools"]) if s["built_in_tools"] else "none"
            lines.append(f"  {s['name']} ({s['label']}, {kind}, built-ins: {tools_str})")
        return "\n".join(lines)

    elif action == "create":
        if not name or not label:
            return "Error: name and label are required for create."
        try:
            create_capability_slot_definition(name, label, built_in_tools or [])
            return f"Capability slot '{name}' ({label}) created."
        except Exception as e:
            if "UNIQUE" in str(e) or "unique" in str(e):
                return f"Error: capability slot '{name}' already exists."
            return f"Error: {e}"

    elif action == "delete":
        if not name:
            return "Error: name is required for delete."
        try:
            delete_capability_slot_definition(name)
            return f"Capability slot '{name}' deleted."
        except ValueError as e:
            return f"Error: {e}"
        except Exception as e:
            return f"Error: {e}"

    return f"Error: unknown action '{action}'."


# ── Executor ──────────────────────────────────────────────────────────────────

async def execute_tool(name: str, inputs: dict, product_id: str | None = None) -> str:
    """Dispatch a tool call by name."""
    if name == "delegate_task":
        return await _delegate_task(**inputs)
    if name == "save_note":
        return _save_note(**inputs)
    if name == "read_notes":
        return _read_notes(**inputs)
    if name == "create_review_item":
        return _create_review_item(**inputs)
    if name == "create_objective":
        return _create_objective(**inputs)
    if name == "update_objective":
        return _update_objective(**inputs)
    if name == "get_datetime":
        return _get_datetime()
    if name == "shell_task":
        return await _shell_task(**inputs)
    if name == "create_product":
        return _create_product(**inputs)
    if name == "update_product":
        return _update_product(**inputs)
    if name == "delete_product":
        return _delete_product(**inputs)
    if name == "create_workstream":
        return _create_workstream(**inputs)
    if name == "update_workstream_status":
        return _update_workstream_status(**inputs)
    if name == "delete_workstream":
        return _delete_workstream(**inputs)
    if name == "delete_objective":
        return _delete_objective(**inputs)
    if name == "draft_social_post":
        return await _draft_social_post(**inputs)
    if name == "find_skill":
        return await _find_skill(**inputs)
    if name == "install_skill":
        return await _install_skill(**inputs)
    if name == "add_agent_tool":
        return _add_agent_tool(**inputs, _product_id=product_id)
    if name == "restart_server":
        return _restart_server()
    if name == "manage_mcp_server":
        return await _manage_mcp_server(**inputs)
    if name == "manage_capability_slots":
        return _manage_capability_slots(**inputs)
    if name == "schedule_next_run":
        return _schedule_next_run(**inputs)
    if name == "update_objective_progress":
        return _update_objective_progress(**inputs)
    if name == "set_objective_autonomous":
        return _set_objective_autonomous_tool(**inputs)
    if name == "report_wizard_progress":
        return _report_wizard_progress(**inputs)
    if name == "complete_launch":
        return _complete_launch(**inputs)
    if name == "list_uploads":
        return _list_uploads()
    if name == "send_telegram_file":
        return await _send_telegram_file(**inputs)
    if name == "gmail_search":
        return await _gmail_search(**inputs)
    if name == "gmail_read":
        return await _gmail_read(**inputs)
    if name == "gmail_send":
        return await _gmail_send(**inputs)
    if name == "gmail_draft":
        return await _gmail_draft(**inputs)
    if name == "calendar_list_events":
        return await _calendar_list_events(**inputs)
    if name == "calendar_create_event":
        return await _calendar_create_event(**inputs)
    if name == "calendar_find_free_time":
        return await _calendar_find_free_time(**inputs)
    if name == "post_to_social":
        return await _post_to_social(**inputs)
    if name == "search_stock_photo":
        return await _search_stock_photo(**inputs)
    if name == "generate_image":
        return await _generate_image(**inputs)
    if name in _EXTENSION_EXECUTORS:
        return await _EXTENSION_EXECUTORS[name](inputs)
    return f"Unknown tool: {name}"


# ── Implementations ───────────────────────────────────────────────────────────

async def _delegate_task(task: str, agent_type: str = "general", context: str = "") -> str:
    full_task = f"{task}\n\nContext: {context}" if context else task
    if agent_type == "research":
        return await run_research_agent(full_task)
    return await run_general_agent(full_task)


# ── Gmail / Calendar implementations ─────────────────────────────────────────

def _get_effective_tier(product_id: str, action_type: str) -> str:
    from backend.db import get_autonomy_config
    tier, _ = get_autonomy_config(product_id, action_type)
    return tier


async def _gmail_search(product_id: str, query: str, max_results: int = 10) -> str:
    from backend.google_api import gmail_search
    return await gmail_search(product_id, query, max_results)


async def _gmail_read(product_id: str, message_id: str) -> str:
    from backend.google_api import gmail_read
    return await gmail_read(product_id, message_id)


async def _gmail_send(product_id: str, to: str, subject: str, body: str, thread_id: str | None = None) -> str:
    if _get_effective_tier(product_id, "email") == "approve":
        from backend.db import save_review_item
        item_id = save_review_item(
            product_id=product_id,
            title=f"Send email: {subject}",
            description=f"To: {to}\n\n{body[:300]}",
            risk_label="Sends email · irreversible",
            action_type="email",
        )
        return json.dumps({"queued_for_review": True, "review_item_id": item_id,
                           "message": "Email queued for approval."})
    from backend.google_api import gmail_send
    return await gmail_send(product_id, to, subject, body, thread_id)


async def _gmail_draft(product_id: str, to: str, subject: str, body: str) -> str:
    from backend.google_api import gmail_draft
    return await gmail_draft(product_id, to, subject, body)


async def _calendar_list_events(product_id: str, start: str, end: str) -> str:
    from backend.google_api import calendar_list_events
    return await calendar_list_events(product_id, start, end)


async def _calendar_create_event(
    product_id: str, title: str, start: str, end: str,
    attendees: list | None = None, description: str | None = None,
) -> str:
    if _get_effective_tier(product_id, "agent_review") == "approve":
        from backend.db import save_review_item
        desc_parts = [f"Title: {title}", f"Start: {start}", f"End: {end}"]
        if attendees:
            desc_parts.append(f"Attendees: {', '.join(attendees)}")
        item_id = save_review_item(
            product_id=product_id,
            title=f"Create calendar event: {title}",
            description="\n".join(desc_parts),
            risk_label="Creates calendar event · sends invites",
            action_type="agent_review",
        )
        return json.dumps({"queued_for_review": True, "review_item_id": item_id,
                           "message": "Calendar event queued for approval."})
    from backend.google_api import calendar_create_event
    return await calendar_create_event(product_id, title, start, end, attendees, description)


async def _calendar_find_free_time(product_id: str, date: str, duration_minutes: int) -> str:
    from backend.google_api import calendar_find_free_time
    return await calendar_find_free_time(product_id, date, duration_minutes)


async def _twitter_post(product_id: str, text: str, media_url: str | None = None) -> str:
    if _get_effective_tier(product_id, "social_post") == "approve":
        from backend.db import save_review_item, save_social_draft
        item_id = save_review_item(
            product_id=product_id,
            title=f"Tweet: {text[:60]}{'…' if len(text) > 60 else ''}",
            description=text,
            risk_label="Posts tweet · public · irreversible",
            action_type="social_post",
        )
        save_social_draft(product_id=product_id, platform="twitter", content=text,
                          image_url=media_url or "", review_item_id=item_id)
        return json.dumps({"queued_for_review": True, "review_item_id": item_id,
                           "message": "Tweet queued for approval."})
    from backend.db import get_oauth_connection
    has_api = get_oauth_connection(product_id, "twitter") is not None
    if has_api:
        from backend.social_api import twitter_post
        return await twitter_post(product_id, text, media_url)
    # No API credentials — post via browser automation
    task = f"Post the following tweet on X (twitter.com). Log in if needed. Tweet text: {text}"
    if media_url:
        task += f"\nAttach this media: {media_url}"
    task += "\nConfirm the tweet was posted and return the tweet URL if available."
    return await execute_tool("browser_task", {"task": task})


async def _linkedin_post(product_id: str, text: str, media_url: str | None = None) -> str:
    if _get_effective_tier(product_id, "social_post") == "approve":
        from backend.db import save_review_item, save_social_draft
        item_id = save_review_item(
            product_id=product_id,
            title=f"LinkedIn post: {text[:60]}{'…' if len(text) > 60 else ''}",
            description=text,
            risk_label="Posts to LinkedIn · public",
            action_type="social_post",
        )
        save_social_draft(product_id=product_id, platform="linkedin", content=text,
                          image_url=media_url or "", review_item_id=item_id)
        return json.dumps({"queued_for_review": True, "review_item_id": item_id,
                           "message": "LinkedIn post queued for approval."})
    from backend.db import get_oauth_connection
    if get_oauth_connection(product_id, "linkedin") is not None:
        from backend.social_api import linkedin_post
        return await linkedin_post(product_id, text, media_url)
    task = f"Post the following to LinkedIn (linkedin.com). Log in if needed.\n\nPost text:\n{text}"
    if media_url:
        task += f"\nAttach this image: {media_url}"
    task += "\nConfirm the post was published and return the post URL if available."
    return await execute_tool("browser_task", {"task": task})


async def _facebook_post(product_id: str, text: str, media_url: str | None = None) -> str:
    if _get_effective_tier(product_id, "social_post") == "approve":
        from backend.db import save_review_item, save_social_draft
        item_id = save_review_item(
            product_id=product_id,
            title=f"Facebook post: {text[:60]}{'…' if len(text) > 60 else ''}",
            description=text,
            risk_label="Posts to Facebook Page · public",
            action_type="social_post",
        )
        save_social_draft(product_id=product_id, platform="facebook", content=text,
                          image_url=media_url or "", review_item_id=item_id)
        return json.dumps({"queued_for_review": True, "review_item_id": item_id,
                           "message": "Facebook post queued for approval."})
    from backend.db import get_oauth_connection
    if get_oauth_connection(product_id, "facebook") is not None:
        from backend.social_api import facebook_post
        return await facebook_post(product_id, text, media_url)
    task = f"Post the following to Facebook (facebook.com). Log in if needed.\n\nPost text:\n{text}"
    if media_url:
        task += f"\nAttach this image: {media_url}"
    task += "\nConfirm the post was published and return the post URL if available."
    return await execute_tool("browser_task", {"task": task})


async def _instagram_post(product_id: str, caption: str, image_url: str) -> str:
    if _get_effective_tier(product_id, "social_post") == "approve":
        from backend.db import save_review_item, save_social_draft
        item_id = save_review_item(
            product_id=product_id,
            title=f"Instagram post: {caption[:60]}{'…' if len(caption) > 60 else ''}",
            description=f"{caption}\n\nImage: {image_url}",
            risk_label="Posts to Instagram · public · irreversible",
            action_type="social_post",
        )
        save_social_draft(product_id=product_id, platform="instagram", content=caption,
                          image_url=image_url, review_item_id=item_id)
        return json.dumps({"queued_for_review": True, "review_item_id": item_id,
                           "message": "Instagram post queued for approval."})
    from backend.db import get_oauth_connection
    if get_oauth_connection(product_id, "instagram") is not None:
        from backend.social_api import instagram_post
        return await instagram_post(product_id, caption, image_url)
    task = (
        f"Post the following to Instagram (instagram.com). Log in if needed.\n\n"
        f"Caption:\n{caption}\n\nImage URL: {image_url}\n\n"
        f"Download or use the image at that URL for the post. "
        f"Confirm the post was published."
    )
    return await execute_tool("browser_task", {"task": task})


async def _post_to_social(
    product_id: str,
    platform: str,
    text: str,
    image_url: str | None = None,
) -> str:
    if platform == "twitter":
        return await _twitter_post(product_id=product_id, text=text, media_url=image_url)
    if platform == "linkedin":
        return await _linkedin_post(product_id=product_id, text=text, media_url=image_url)
    if platform == "facebook":
        return await _facebook_post(product_id=product_id, text=text, media_url=image_url)
    if platform == "instagram":
        if not image_url:
            return "image_url is required for Instagram posts."
        return await _instagram_post(product_id=product_id, caption=text, image_url=image_url)
    return f"Unknown platform: {platform}"


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


async def _shell_task(command: str, timeout: int = 120, cwd: str | None = None) -> str:
    import asyncio
    import json as _json
    import os

    wrapped = f'source ~/.bashrc 2>/dev/null; {command}'
    work_dir = cwd or str(Path.home())

    proc = await asyncio.create_subprocess_shell(
        wrapped,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        cwd=work_dir,
        env={**os.environ},
    )
    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        output = stdout.decode("utf-8", errors="replace").strip()
        return _json.dumps({
            "exit_code": proc.returncode,
            "output": output or "(no output)",
        })
    except asyncio.TimeoutError:
        proc.kill()
        await proc.communicate()
        return _json.dumps({
            "exit_code": -1,
            "output": f"Command timed out after {timeout}s",
        })


def _list_uploads() -> str:
    """Return a summary of all uploaded files."""
    from backend.uploads import get_uploads_dir
    uploads_dir = get_uploads_dir()
    if not uploads_dir.exists():
        return "No uploaded files found."
    files = sorted((f for f in uploads_dir.iterdir() if f.is_file()), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return "No uploaded files found."
    lines = [f"Uploaded files ({len(files)} total):"]
    for f in files:
        stat = f.stat()
        size_kb = stat.st_size / 1024
        mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
        lines.append(f"  {f.name}  ({size_kb:.1f} KB)  {mtime}  path: {f}")
    return "\n".join(lines)


async def _send_telegram_file(file_path: str) -> str:
    """Send a file to the user via Telegram."""
    import mimetypes
    import backend.main as _main

    bot = _main._telegram_bot
    if bot is None:
        return "Telegram is not configured — cannot send file."

    from backend.uploads import get_uploads_dir
    p = Path(file_path)
    if not p.resolve().is_relative_to(get_uploads_dir().resolve()):
        return f"Access denied: {file_path} is outside the uploads directory."
    if not p.exists():
        return f"File not found: {file_path}"
    if not p.is_file():
        return f"Path is not a file: {file_path}"

    mime = mimetypes.guess_type(file_path)[0] or ""
    try:
        if mime.startswith("video/"):
            await bot.send_video(file_path)
        else:
            await bot.send_document(file_path)
        return f"Sent {p.name} via Telegram."
    except Exception as e:
        return f"Failed to send file: {e}"


# ── Meta-tools ────────────────────────────────────────────────────────────────

async def _find_skill(query: str) -> str:
    import subprocess
    result = subprocess.run(
        ["npx", "skills", "find", query],
        capture_output=True, text=True, timeout=30,
    )
    # Strip ANSI escape codes for clean LLM output
    import re
    clean = re.sub(r"\x1b\[[0-9;]*m", "", result.stdout)
    return clean.strip() or result.stderr.strip() or "No results found."


async def _install_skill(package: str) -> str:
    import subprocess
    result = subprocess.run(
        ["npx", "skills", "add", package, "-g", "-y"],
        capture_output=True, text=True, timeout=60,
    )
    import re
    clean = re.sub(r"\x1b\[[0-9;]*m", "", result.stdout + result.stderr)
    return clean.strip() or f"Installed {package}."


def _add_agent_tool(tool_name: str, description: str, agent_instructions: str, _product_id: str | None = None) -> str:
    import re
    if not re.match(r"^[a-z][a-z0-9_]*$", tool_name):
        return f"Invalid tool_name '{tool_name}': must be lowercase snake_case."

    ext_dir = _EXTENSIONS_DIR
    ext_dir.mkdir(exist_ok=True)

    # Escape for embedding in a Python string literal
    safe_instructions = agent_instructions.replace('\\', '\\\\').replace('"""', '\\"\\"\\"')
    safe_description = description.replace('"', '\\"')

    code = f'''# extensions/{tool_name}.py
# Auto-generated by Adjutant on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

TOOL_DEFINITION = {{
    "name": "{tool_name}",
    "description": "{safe_description}",
    "input_schema": {{
        "type": "object",
        "properties": {{
            "task": {{"type": "string", "description": "What to do"}},
            "context": {{"type": "string", "description": "Background context and rationale"}},
        }},
        "required": ["task"],
    }},
}}

_INSTRUCTIONS = """{safe_instructions}"""


async def execute(inputs: dict) -> str:
    import asyncio
    import json
    import os
    from pathlib import Path

    task = inputs.get("task", "")
    context = inputs.get("context", "")
    full_task = f"{{task}}\\n\\nContext: {{context}}" if context else task

    model = os.environ.get("AGENT_SUBAGENT_MODEL", "claude-sonnet-4-6")
    cmd = [
        "claude", "-p", full_task,
        "--output-format", "json",
        "--system-prompt", _INSTRUCTIONS,
        "--permission-mode", "bypassPermissions",
        "--no-session-persistence",
        "--model", model,
    ]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={{**os.environ}},
            cwd=str(Path.home()),
        )
    except FileNotFoundError:
        return "Sub-agent failed: 'claude' executable not found on PATH."

    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=900)
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except ProcessLookupError:
            pass
        try:
            await proc.communicate()
        except (asyncio.TimeoutError, OSError):
            pass
        return "Sub-agent timed out after 900s."

    raw = stdout.decode("utf-8", errors="replace").strip()
    if proc.returncode != 0:
        err = stderr.decode("utf-8", errors="replace").strip() if stderr else ""
        return f"Sub-agent process failed (exit {{proc.returncode}}): {{err or raw}}"

    try:
        data = json.loads(raw)
        return data.get("result", raw)
    except json.JSONDecodeError:
        return raw
'''
    (ext_dir / f"{tool_name}.py").write_text(code)
    from backend.db import add_extension_permission
    if _product_id:
        add_extension_permission(tool_name, "product", _product_id)
    else:
        add_extension_permission(tool_name, "global", "")
    return f"Created extension: extensions/{tool_name}.py — call restart_server to activate."


def _restart_server() -> str:
    import subprocess
    import sys
    if sys.platform == "darwin":
        cmd = "sleep 3 && launchctl kickstart -k gui/$(id -u)/ai.adjutantapp"
    elif sys.platform == "win32":
        cmd = "timeout 3 && schtasks /run /tn Adjutant"
    else:  # Linux
        cmd = "sleep 3 && systemctl --user restart adjutant"
    subprocess.Popen(
        cmd,
        shell=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return "Server restart initiated — client will reconnect in a few seconds."


def _create_objective(product_id: str, text: str, progress_current: int = 0, progress_target: int | None = None) -> str:
    from backend.db import create_objective
    return create_objective(product_id, text, progress_current, progress_target)


def _update_objective(product_id: str, text_fragment: str, progress_current: int, progress_target: int | None = None) -> str:
    from backend.db import update_objective
    return update_objective(product_id, text_fragment, progress_current, progress_target)


# ── Product / workstream / objective / social management ──────────────────────

def _create_product(id: str, name: str, icon_label: str, color: str) -> str:
    from backend.db import create_product
    return create_product(id, name, icon_label, color)

def _update_product(product_id: str, **kwargs) -> str:
    from backend.db import update_product
    return update_product(product_id, **kwargs)

def _delete_product(product_id: str) -> str:
    from backend.db import delete_product
    return delete_product(product_id)

def _create_workstream(product_id: str, name: str, status: str = "paused") -> str:
    from backend.db import create_workstream
    return create_workstream(product_id, name, status)

def _update_workstream_status(product_id: str, name_fragment: str, status: str) -> str:
    from backend.db import update_workstream_status
    return update_workstream_status(product_id, name_fragment, status)

def _delete_workstream(product_id: str, name_fragment: str) -> str:
    from backend.db import delete_workstream
    return delete_workstream(product_id, name_fragment)

def _delete_objective(product_id: str, text_fragment: str) -> str:
    from backend.db import delete_objective
    return delete_objective(product_id, text_fragment)

async def _draft_social_post(
    product_id: str,
    platform: str,
    content: str,
    image_description: str = "",
    image_url: str = "",
    scheduled_for: str | None = None,
) -> str:
    from backend.db import save_social_draft, save_review_item
    risk = f"Social post · {platform} · public-facing · irreversible once posted"
    description = f"**Platform:** {platform}\n\n**Content:**\n{content}"
    if scheduled_for:
        description += f"\n\n**Scheduled for:** {scheduled_for}"
    if image_description:
        description += f"\n\n**Image:** {image_description}"
    if image_url:
        description += f"\n\n**Image URL:** {image_url}"
    review_id = save_review_item(
        product_id=product_id,
        title=f"Post to {platform.capitalize()}",
        description=description,
        risk_label=risk,
        action_type="social_post",
    )
    draft_id = save_social_draft(
        product_id=product_id,
        platform=platform,
        content=content,
        image_description=image_description,
        image_url=image_url,
        review_item_id=review_id,
        scheduled_for=scheduled_for,
    )
    return json.dumps({
        "draft_id": draft_id,
        "review_item_id": review_id,
        "platform": platform,
        "status": "pending_review",
        "scheduled_for": scheduled_for,
    })


def _create_review_item(
    title: str, description: str, risk_label: str, product_id: str,
    action_type: str = "agent_review",
) -> str:
    from backend.db import save_review_item
    item_id = save_review_item(
        product_id=product_id,
        title=title,
        description=description,
        risk_label=risk_label,
        action_type=action_type,
    )
    return json.dumps({"id": item_id, "title": title, "status": "pending"})


def _schedule_next_run(objective_id: int, hours: float, reason: str) -> str:
    from backend.db import set_objective_next_run
    set_objective_next_run(objective_id, hours)
    return f"Scheduled next run in {hours}h. Reason: {reason}"


def _update_objective_progress(objective_id: int, current: int, notes: str = "") -> str:
    from backend.db import update_objective_by_id
    update_objective_by_id(objective_id, progress_current=current)
    msg = f"Progress updated to {current}"
    return f"{msg}. {notes}" if notes else msg


def _set_objective_autonomous_tool(objective_id: int, autonomous: bool) -> str:
    from backend.db import set_objective_autonomous
    set_objective_autonomous(objective_id, autonomous)
    state = "enabled" if autonomous else "disabled"
    return f"Objective {objective_id} autonomous mode {state}."
