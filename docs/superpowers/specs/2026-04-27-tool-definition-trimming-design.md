# Tool Definition Trimming Design

**Date:** 2026-04-27
**Goal:** Reduce per-call input tokens by trimming verbose tool descriptions and consolidating four identical social posting tools into one.

---

## Background

Tool definitions are sent to the Anthropic API on every call. The current set of ~44 tools carries two sources of unnecessary token cost:

1. **Verbose descriptions** — top-level descriptions and per-parameter descriptions include implementation details, fallback explanations, and "use for X, Y, Z" guidance that the model doesn't need to route correctly.
2. **Redundant social tools** — `twitter_post`, `linkedin_post`, `facebook_post`, `instagram_post` have near-identical schemas (same three parameters, same autonomy-tier behavior) with only the platform name differing. They add three extra full schema definitions for no functional benefit.

---

## Approach: Text Trimming + Social Consolidation

### Part 1: Social Tool Consolidation

Replace the four platform-specific posting tools with a single `post_to_social` tool.

**New tool definition:**

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
}
```

**Execute dispatch:** `execute_tool()` maps `post_to_social` to the existing `_twitter_post`, `_linkedin_post`, `_facebook_post`, `_instagram_post` helpers based on `inputs["platform"]`. Instagram receives `caption=inputs["text"]` and `image_url=inputs["image_url"]`. If `platform == "instagram"` and `image_url` is missing, return an error string immediately.

**TOOL_GROUPS update:** `TOOL_GROUPS["social"]` replaces the four old names with `post_to_social`:

```python
"social": {
    "draft_social_post", "post_to_social", "generate_image", "search_stock_photo",
},
```

The underlying `_twitter_post`, `_linkedin_post`, `_facebook_post`, `_instagram_post` functions are **not changed** — only the routing layer changes.

---

### Part 2: Description Trimming

**Rule:** Every tool description becomes one sentence stating what the tool does. Nothing else.

**What gets removed:**
- Fallback/implementation details ("uses the API if configured; otherwise falls back to browser automation")
- Autonomy-tier reminders on non-posting tools (kept only on tools that post or take irreversible external action)
- "Use for X, Y, Z" guidance lists
- Conditional behavior explanations that belong in the system prompt

**Parameter descriptions** trimmed to ≤8 words. Parameter names already convey most of the meaning.

**Autonomy-tier note** ("Respects autonomy tier — creates a review item if set to 'approve'") is retained only on tools that post externally or take irreversible action: `post_to_social`, `draft_social_post`, `gmail_send`, `calendar_create_event`.

---

## Files Changed

| File | Change |
|------|--------|
| `core/tools.py` | Remove 4 social tool dicts; add `post_to_social`; update `execute_tool()` dispatcher; update `TOOL_GROUPS["social"]`; trim descriptions throughout |
| `tests/test_token_optimization.py` | Update `test_tool_groups_social_tools` to expect `post_to_social` instead of the four old names |

---

## Testing

- **Unit:** `test_tool_groups_social_tools` updated — asserts `post_to_social` in social group, old names absent.
- **Unit:** New test `test_post_to_social_dispatches_correctly` — mock the four `_platform_post` helpers; verify `post_to_social` calls the right one for each platform value; verify Instagram missing `image_url` returns an error.
- **Unit:** New test `test_post_to_social_instagram_requires_image_url` — call with `platform="instagram"` and no `image_url`, assert error returned.
- **Regression:** Full test suite passes with no new failures.

---

## Non-Goals

- Changing the underlying `_twitter_post`, `_linkedin_post`, `_facebook_post`, `_instagram_post` helper functions
- Removing parameter descriptions entirely (they still need to be meaningful)
- Trimming `manage_mcp_server` or other system-level tools with complex schemas (risk of breaking agent behavior)
- Schema simplification (removing parameters) — deferred due to regression risk
