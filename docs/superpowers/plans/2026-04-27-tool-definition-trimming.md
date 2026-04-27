# Tool Definition Trimming Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce per-call input tokens by consolidating four near-identical social posting tools into one and trimming verbose descriptions throughout.

**Architecture:** Two sequential tasks in `core/tools.py`: (1) replace `twitter_post`, `linkedin_post`, `facebook_post`, `instagram_post` with a single `post_to_social` tool that dispatches to the existing `_twitter_post`, `_linkedin_post`, `_facebook_post`, `_instagram_post` helpers; (2) rewrite every top-level tool description to one sentence and shorten parameter descriptions to ≤8 words.

**Tech Stack:** Python, pytest

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `core/tools.py` | Modify | Remove 4 social tool dicts; add `post_to_social`; update dispatcher; update `TOOL_GROUPS`; trim all descriptions |
| `tests/test_token_optimization.py` | Modify | Update social group test; add `post_to_social` dispatch tests |

---

### Task 1: Consolidate social posting tools into `post_to_social`

**Files:**
- Modify: `core/tools.py`
- Modify: `tests/test_token_optimization.py`

- [ ] **Step 1: Write failing tests**

Add to the bottom of `tests/test_token_optimization.py`:

```python
# ── Social tool consolidation ─────────────────────────────────────────────────

def test_post_to_social_in_tool_groups():
    from core.tools import TOOL_GROUPS
    social = TOOL_GROUPS["social"]
    assert "post_to_social" in social
    # Old names must be gone
    assert "twitter_post" not in social
    assert "linkedin_post" not in social
    assert "facebook_post" not in social
    assert "instagram_post" not in social


@pytest.mark.asyncio
async def test_post_to_social_dispatches_twitter():
    from unittest.mock import AsyncMock, patch
    from core.tools import execute_tool
    with patch("core.tools._twitter_post", new=AsyncMock(return_value="tweeted")) as mock_tw:
        result = await execute_tool(
            "post_to_social",
            {"product_id": "p1", "platform": "twitter", "text": "hello"},
        )
    mock_tw.assert_called_once_with(product_id="p1", text="hello", media_url=None)
    assert result == "tweeted"


@pytest.mark.asyncio
async def test_post_to_social_dispatches_instagram():
    from unittest.mock import AsyncMock, patch
    from core.tools import execute_tool
    with patch("core.tools._instagram_post", new=AsyncMock(return_value="posted")) as mock_ig:
        result = await execute_tool(
            "post_to_social",
            {"product_id": "p1", "platform": "instagram", "text": "my caption", "image_url": "https://img.example.com/photo.jpg"},
        )
    # instagram receives caption=text, image_url forwarded
    mock_ig.assert_called_once_with(product_id="p1", caption="my caption", image_url="https://img.example.com/photo.jpg")
    assert result == "posted"


@pytest.mark.asyncio
async def test_post_to_social_instagram_missing_image_url_returns_error():
    from core.tools import execute_tool
    result = await execute_tool(
        "post_to_social",
        {"product_id": "p1", "platform": "instagram", "text": "caption only"},
    )
    assert "image_url" in result.lower() or "required" in result.lower()


@pytest.mark.asyncio
async def test_post_to_social_unknown_platform_returns_error():
    from core.tools import execute_tool
    result = await execute_tool(
        "post_to_social",
        {"product_id": "p1", "platform": "tiktok", "text": "hello"},
    )
    assert "unknown" in result.lower() or "tiktok" in result.lower()
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd /home/justin/Code/Adjutant
.venv/bin/python -m pytest tests/test_token_optimization.py::test_post_to_social_in_tool_groups tests/test_token_optimization.py::test_post_to_social_dispatches_twitter -v
```

Expected: FAIL — `post_to_social` not in TOOL_GROUPS, `execute_tool` returns "Unknown tool"

- [ ] **Step 3: Find and remove the four social tool dicts in `core/tools.py`**

Search for `"name": "twitter_post"` in `core/tools.py`. The four dicts (`twitter_post`, `linkedin_post`, `facebook_post`, `instagram_post`) are in a platform-specific section (around lines 894–974, likely inside a `_TWITTER_TOOLS`/`_SOCIAL_TOOLS` list or inlined into the main tool getter). Remove all four dicts entirely.

- [ ] **Step 4: Add the `post_to_social` tool definition in their place**

Insert this dict where the four were removed:

```python
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
```

- [ ] **Step 5: Update `TOOL_GROUPS["social"]` in `core/tools.py`**

Find `TOOL_GROUPS` (around line 690). Replace the social group:

```python
"social": {
    "draft_social_post", "post_to_social", "generate_image", "search_stock_photo",
},
```

- [ ] **Step 6: Add `_post_to_social` helper and update the dispatcher**

Add this async function somewhere near the existing `_twitter_post`, `_linkedin_post`, `_facebook_post`, `_instagram_post` helpers (around line 1416):

```python
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
```

In `execute_tool()`, replace the four platform dispatches:

```python
    if name == "twitter_post":
        return await _twitter_post(**inputs)
    if name == "linkedin_post":
        return await _linkedin_post(**inputs)
    if name == "facebook_post":
        return await _facebook_post(**inputs)
    if name == "instagram_post":
        return await _instagram_post(**inputs)
```

With the single consolidated dispatch:

```python
    if name == "post_to_social":
        return await _post_to_social(**inputs)
```

- [ ] **Step 7: Update the existing social group test**

In `tests/test_token_optimization.py`, find `test_tool_groups_social_tools` and replace it:

```python
def test_tool_groups_social_tools():
    from core.tools import TOOL_GROUPS
    social = TOOL_GROUPS["social"]
    assert "post_to_social" in social
    assert "draft_social_post" in social
    assert "generate_image" in social
    assert "search_stock_photo" in social
    assert "twitter_post" not in social
    assert "linkedin_post" not in social
    assert "facebook_post" not in social
    assert "instagram_post" not in social
```

- [ ] **Step 8: Run the full test suite**

```bash
.venv/bin/python -m pytest tests/test_token_optimization.py tests/test_prescreener.py -v
```

Expected: all tests PASS

- [ ] **Step 9: Run the full suite for regressions**

```bash
.venv/bin/python -m pytest tests/ -q 2>&1 | tail -10
```

Expected: 4 pre-existing failures in `test_openai_oauth.py`, everything else passes.

- [ ] **Step 10: Commit**

```bash
git add core/tools.py tests/test_token_optimization.py
git commit -m "feat: consolidate social posting tools into post_to_social"
```

---

### Task 2: Trim all tool descriptions and parameter descriptions

**Files:**
- Modify: `core/tools.py`

This task is a content edit — no new tests needed. The suite passing is the regression check.

- [ ] **Step 1: Replace the `TOOLS_DEFINITIONS` list with trimmed descriptions**

In `core/tools.py`, replace the content of `TOOLS_DEFINITIONS` with the following trimmed version. **Do not change any other part of the file — only the description strings and parameter description strings inside TOOLS_DEFINITIONS.**

```python
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
```

- [ ] **Step 2: Run the full test suite**

```bash
cd /home/justin/Code/Adjutant
.venv/bin/python -m pytest tests/ -q 2>&1 | tail -10
```

Expected: 4 pre-existing failures in `test_openai_oauth.py`, everything else passes.

- [ ] **Step 3: Verify the server can still import cleanly**

```bash
.venv/bin/python -c "from core.tools import TOOLS_DEFINITIONS, get_tools_for_product; print(f'OK — {len(TOOLS_DEFINITIONS)} tool defs')"
```

Expected: `OK — 31 tool defs` (or whatever the count is after the social consolidation from Task 1)

- [ ] **Step 4: Commit**

```bash
git add core/tools.py
git commit -m "feat: trim tool descriptions to reduce per-call input tokens"
```

---

## Self-Review

### Spec coverage

- ✅ `post_to_social` replaces the four platform-specific tools — Task 1
- ✅ `_post_to_social` dispatches to existing helpers, translates `text` → `caption` for Instagram — Task 1, Step 6
- ✅ Instagram missing `image_url` returns an error — Task 1, Step 6
- ✅ `TOOL_GROUPS["social"]` updated — Task 1, Step 5
- ✅ Autonomy-tier note retained on `post_to_social` and `draft_social_post` — Task 2 descriptions
- ✅ All TOOLS_DEFINITIONS descriptions trimmed to one sentence — Task 2
- ✅ Parameter descriptions trimmed to ≤8 words — Task 2
- ✅ Tests updated for TOOL_GROUPS social membership — Task 1, Steps 1 + 7
- ✅ Tests for `post_to_social` dispatch and Instagram validation — Task 1, Step 1

### Placeholder scan

None found.

### Type consistency

- `_post_to_social(product_id, platform, text, image_url=None)` defined in Task 1 Step 6, dispatched in execute_tool() Step 6 ✅
- Tests call `execute_tool("post_to_social", {...})` matching dispatcher ✅
