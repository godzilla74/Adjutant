"""Tool definitions and executor for Hannah."""

import importlib
import json
import pkgutil
import sys
from datetime import datetime
from pathlib import Path

from agents.runner import run_email_agent, run_general_agent, run_research_agent

# ── Extension auto-loader ─────────────────────────────────────────────────────

_EXTENSIONS_DIR = Path(__file__).parent.parent / "extensions"
_EXTENSION_EXECUTORS: dict = {}

def _load_extensions() -> list[dict]:
    """Discover and load all tool extensions from the extensions/ directory."""
    definitions = []
    if not _EXTENSIONS_DIR.exists():
        return definitions
    for finder, name, _ in pkgutil.iter_modules([str(_EXTENSIONS_DIR)]):
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
                    "description": "Background context for the sub-agent AND rationale shown to Justin in the activity feed. Write this as a human-readable explanation of why this task is being done.",
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
                    "description": "Background context for the email agent AND rationale shown to Justin in the activity feed. Write this as a human-readable explanation of why this email task is being done.",
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
        "name": "create_objective",
        "description": "Create a new objective for a product. Use when Justin asks to add a new goal or target.",
        "input_schema": {
            "type": "object",
            "properties": {
                "product_id": {"type": "string", "description": "The product this objective belongs to"},
                "text": {"type": "string", "description": "The objective description, e.g. '500 Instagram followers by June 1'"},
                "progress_current": {"type": "integer", "description": "Starting progress value (default 0)"},
                "progress_target": {"type": "integer", "description": "Target value, e.g. 500. Omit if open-ended."},
            },
            "required": ["product_id", "text"],
        },
    },
    {
        "name": "update_objective",
        "description": (
            "Update the progress on one of Justin's active objectives for the current product. "
            "Use this after completing work that advances a measurable goal — e.g. after publishing "
            "an SEO post, increment the SEO post counter. Match the objective by a short text fragment."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "product_id": {
                    "type": "string",
                    "description": "The product this objective belongs to",
                },
                "text_fragment": {
                    "type": "string",
                    "description": "A few words from the objective text to identify it, e.g. 'SEO posts' or 'trial signups'",
                },
                "progress_current": {
                    "type": "integer",
                    "description": "The new current progress value",
                },
                "progress_target": {
                    "type": "integer",
                    "description": "Optional: update the target value too",
                },
            },
            "required": ["product_id", "text_fragment", "progress_current"],
        },
    },
    {
        "name": "create_product",
        "description": "Create a new product in Adjutant. Use when Justin wants to add a new business or product to track.",
        "input_schema": {
            "type": "object",
            "properties": {
                "id":         {"type": "string", "description": "Unique slug, e.g. 'my-product' (lowercase, hyphens ok)"},
                "name":       {"type": "string", "description": "Display name, e.g. 'My Product'"},
                "icon_label": {"type": "string", "description": "2-3 character label shown in the product rail, e.g. 'MP'"},
                "color":      {"type": "string", "description": "Hex color for the product, e.g. '#2563eb'"},
            },
            "required": ["id", "name", "icon_label", "color"],
        },
    },
    {
        "name": "update_product",
        "description": "Update a product's display info or brand configuration (brand voice, tone, writing style, target audience, social handles, hashtags, notes).",
        "input_schema": {
            "type": "object",
            "properties": {
                "product_id":      {"type": "string", "description": "The product's id slug"},
                "name":            {"type": "string", "description": "Display name"},
                "icon_label":      {"type": "string", "description": "2-3 char label"},
                "color":           {"type": "string", "description": "Hex color"},
                "brand_voice":     {"type": "string", "description": "Brand voice description, e.g. 'authoritative and warm'"},
                "tone":            {"type": "string", "description": "Tone guidelines, e.g. 'professional but approachable, never salesy'"},
                "writing_style":   {"type": "string", "description": "Writing style notes, e.g. 'short sentences, active voice, no jargon'"},
                "target_audience": {"type": "string", "description": "Who the product is for"},
                "social_handles":  {"type": "string", "description": "JSON string of platform handles, e.g. {\"instagram\": \"@handle\", \"linkedin\": \"url\"}"},
                "hashtags":        {"type": "string", "description": "Comma-separated hashtags to use for this product"},
                "brand_notes":     {"type": "string", "description": "Any other brand guidance or context"},
            },
            "required": ["product_id"],
        },
    },
    {
        "name": "delete_product",
        "description": "Permanently delete a product and all its data (workstreams, objectives, events, messages). Use with caution — irreversible.",
        "input_schema": {
            "type": "object",
            "properties": {
                "product_id": {"type": "string", "description": "The product's id slug"},
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
                "name_fragment": {"type": "string", "description": "Part of the workstream name to match"},
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
                "name_fragment": {"type": "string", "description": "Part of the workstream name to match"},
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
                "text_fragment": {"type": "string", "description": "Part of the objective text to match"},
            },
            "required": ["product_id", "text_fragment"],
        },
    },
    {
        "name": "draft_social_post",
        "description": (
            "Draft a social media post for a product. Saves the draft and automatically adds it to Justin's "
            "approval queue before anything is posted. Use the product's brand voice and tone when writing content."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "product_id":         {"type": "string"},
                "platform":           {"type": "string", "description": "e.g. 'instagram', 'linkedin', 'twitter', 'facebook'"},
                "content":            {"type": "string", "description": "The post text, ready to publish"},
                "image_description":  {"type": "string", "description": "Description of the image/visual to pair with this post (optional)"},
                "image_url":          {"type": "string", "description": "Public URL of an image to attach (required for Instagram, optional for others)"},
            },
            "required": ["product_id", "platform", "content"],
        },
    },
    {
        "name": "find_skill",
        "description": (
            "Search the skills.sh ecosystem for agent skills that can add a new capability. "
            "Use this when you identify a capability gap — e.g. posting to Instagram, generating images, "
            "sending SMS. Returns a list of matching skills with install counts."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Keywords to search for, e.g. 'instagram posting' or 'image generation'"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "install_skill",
        "description": "Install a skill from skills.sh so it becomes available to sub-agents. Run find_skill first to identify the right package.",
        "input_schema": {
            "type": "object",
            "properties": {
                "package": {"type": "string", "description": "The package to install, e.g. 'inferen-sh/skills@ai-social-media-content'"},
            },
            "required": ["package"],
        },
    },
    {
        "name": "add_agent_tool",
        "description": (
            "Create a new tool by writing an extension file. The tool will spawn a sub-agent with your specified "
            "instructions. After calling this, call restart_server to activate it."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tool_name": {"type": "string", "description": "Snake_case name for the tool, e.g. 'instagram_post'"},
                "description": {"type": "string", "description": "What this tool does (shown in your tool list)"},
                "agent_instructions": {"type": "string", "description": "Full system prompt / instructions for the sub-agent that will execute this tool"},
            },
            "required": ["tool_name", "description", "agent_instructions"],
        },
    },
    {
        "name": "restart_server",
        "description": (
            "Restart the Adjutant server to pick up new extensions or code changes. "
            "The client will reconnect automatically within a few seconds. "
            "Call this after add_agent_tool or any code modification."
        ),
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
]

# Load extensions and append their definitions
TOOLS_DEFINITIONS.extend(_load_extensions())

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
    if name == "create_objective":
        return _create_objective(**inputs)
    if name == "update_objective":
        return _update_objective(**inputs)
    if name == "get_datetime":
        return _get_datetime()
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
        return _add_agent_tool(**inputs)
    if name == "restart_server":
        return _restart_server()
    if name in _EXTENSION_EXECUTORS:
        return await _EXTENSION_EXECUTORS[name](inputs)
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


def _add_agent_tool(tool_name: str, description: str, agent_instructions: str) -> str:
    import re
    if not re.match(r"^[a-z][a-z0-9_]*$", tool_name):
        return f"Invalid tool_name '{tool_name}': must be lowercase snake_case."

    ext_dir = _EXTENSIONS_DIR
    ext_dir.mkdir(exist_ok=True)

    # Escape for embedding in a Python string literal
    safe_instructions = agent_instructions.replace('\\', '\\\\').replace('"""', '\\"\\"\\"')
    safe_description = description.replace('"', '\\"')

    code = f'''# extensions/{tool_name}.py
# Auto-generated by Hannah on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

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
    from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage
    task = inputs.get("task", "")
    context = inputs.get("context", "")
    full_task = f"{{task}}\\n\\nContext: {{context}}" if context else task

    result = "Agent completed with no output."
    async for message in query(
        prompt=full_task,
        options=ClaudeAgentOptions(
            max_turns=20,
            permission_mode="bypassPermissions",
            system_prompt=_INSTRUCTIONS,
        ),
    ):
        if isinstance(message, ResultMessage):
            result = message.result
    return result
'''
    (ext_dir / f"{tool_name}.py").write_text(code)
    return f"Created extension: extensions/{tool_name}.py — call restart_server to activate."


def _restart_server() -> str:
    import subprocess
    subprocess.Popen(
        "sleep 3 && systemctl --user restart adjutant",
        shell=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return "Server restart scheduled in 3 seconds. The connection will drop and reconnect automatically."


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

async def _draft_social_post(product_id: str, platform: str, content: str, image_description: str = "", image_url: str = "") -> str:
    from backend.db import save_social_draft, save_review_item
    # Create review item first
    risk = f"Social post · {platform} · public-facing · irreversible once posted"
    description = f"**Platform:** {platform}\n\n**Content:**\n{content}"
    if image_description:
        description += f"\n\n**Image:** {image_description}"
    if image_url:
        description += f"\n\n**Image URL:** {image_url}"
    review_id = save_review_item(
        product_id=product_id,
        title=f"Post to {platform.capitalize()}",
        description=description,
        risk_label=risk,
    )
    # Save the draft linked to the review item
    draft_id = save_social_draft(
        product_id=product_id,
        platform=platform,
        content=content,
        image_description=image_description,
        image_url=image_url,
        review_item_id=review_id,
    )
    return json.dumps({
        "draft_id": draft_id,
        "review_item_id": review_id,
        "platform": platform,
        "status": "pending_review",
    })


def _create_review_item(title: str, description: str, risk_label: str, product_id: str) -> str:
    from backend.db import save_review_item
    item_id = save_review_item(
        product_id=product_id,
        title=title,
        description=description,
        risk_label=risk_label,
    )
    return json.dumps({"id": item_id, "title": title, "status": "pending"})
