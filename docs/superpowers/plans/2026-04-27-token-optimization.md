# Token Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce Anthropic API token costs via prompt caching, tool list pruning, and Haiku pre-screening.

**Architecture:** Three independent layers: (1) make the system prompt fully static and add `cache_control` blocks so Anthropic caches it; (2) define named tool groups and a `get_tools_for_groups()` function so only relevant tools are sent per request; (3) add a Haiku prescreener that classifies each user message and either responds directly or routes to Sonnet with a pruned tool list. The prescreener model is DB-backed and configurable in the Settings UI.

**Tech Stack:** Python asyncio, Anthropic Python SDK, React 19, Vitest, pytest-asyncio

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `core/config.py` | Modify | Remove datetime from both system prompt functions |
| `core/tools.py` | Modify | Add `TOOL_GROUPS` dict + `get_tools_for_groups()` |
| `core/prescreener.py` | Create | `PrescreerResult` dataclass + `prescreen()` async function |
| `backend/db.py` | Modify | Add `prescreener_model` to `_AGENT_CONFIG_DEFAULTS` |
| `backend/api.py` | Modify | Add `prescreener_model` field to `AgentConfigUpdate` + PUT handler |
| `ui/src/api.ts` | Modify | Update `getAgentConfig`/`updateAgentConfig` types |
| `ui/src/components/settings/AgentModelSettings.tsx` | Modify | Add prescreener model selector |
| `backend/main.py` | Modify | Datetime injection, `cache_control` blocks, prescreener wiring |
| `tests/test_config.py` | Modify | Add test that datetime is NOT in static prompt |
| `tests/test_token_optimization.py` | Create | Tests for tool groups, datetime injection, cache_control helpers |
| `tests/test_prescreener.py` | Create | Tests for `prescreen()` — success, fallback, error paths |

---

### Task 1: Remove datetime from system prompts (`core/config.py`)

**Files:**
- Modify: `core/config.py`
- Modify: `tests/test_config.py`

- [ ] **Step 1: Write a failing test**

Add to `tests/test_config.py`:

```python
def test_system_prompt_has_no_datetime(config_mod):
    import re
    prompt = config_mod.get_system_prompt("test-product")
    assert "Current Date & Time" not in prompt
    # Verify no formatted date pattern like "Monday, April 27, 2026"
    assert not re.search(r"\b(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),", prompt)


def test_global_system_prompt_has_no_datetime(monkeypatch):
    monkeypatch.setenv("AGENT_NAME", "Hannah")
    monkeypatch.setenv("AGENT_OWNER_NAME", "Justin")
    monkeypatch.delenv("AGENT_OWNER_BIO", raising=False)
    import core.config as mod
    import importlib
    importlib.reload(mod)
    prompt = mod.get_global_system_prompt([])
    assert "Current Date & Time" not in prompt
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd /home/justin/Code/Adjutant
.venv/bin/python -m pytest tests/test_config.py::test_system_prompt_has_no_datetime tests/test_config.py::test_global_system_prompt_has_no_datetime -v
```

Expected: FAIL — prompt currently contains "Current Date & Time"

- [ ] **Step 3: Remove datetime from `core/config.py`**

In `core/config.py`, make these changes:

**Remove line 3** (`from datetime import datetime`) — will be unused after this task.

**Remove lines 72 and 137–139** from `get_system_prompt()`. The function currently ends with:
```python
{_product_context(product_id)}

## Current Date & Time
{current_dt}
"""
```

Replace that ending with:
```python
{_product_context(product_id)}
"""
```

Also remove line 72 (`current_dt = datetime.now().strftime(...)`).

**Remove line 146** from `get_global_system_prompt()` (`current_dt = datetime.now().strftime(...)`) and all references to `{current_dt}` in that function.

The final `get_system_prompt` return string ends at `{_product_context(product_id)}` with a closing `"""`.

The final `get_global_system_prompt` loses the `current_dt` variable and any `{current_dt}` interpolation in its return string.

- [ ] **Step 4: Run the tests to verify they pass**

```bash
.venv/bin/python -m pytest tests/test_config.py -v
```

Expected: all tests PASS (including the two new ones)

- [ ] **Step 5: Commit**

```bash
git add core/config.py tests/test_config.py
git commit -m "feat: remove datetime from system prompts (enables prompt caching)"
```

---

### Task 2: Add `TOOL_GROUPS` and `get_tools_for_groups()` to `core/tools.py`

**Files:**
- Modify: `core/tools.py`
- Create: `tests/test_token_optimization.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_token_optimization.py`:

```python
"""Tests for token optimization helpers: tool groups, datetime injection, cache_control."""
import pytest


# ── Tool Groups ───────────────────────────────────────────────────────────────

def test_tool_groups_contains_expected_groups():
    from core.tools import TOOL_GROUPS
    assert set(TOOL_GROUPS.keys()) == {"core", "email", "calendar", "social", "management", "system"}


def test_tool_groups_core_has_essential_tools():
    from core.tools import TOOL_GROUPS
    core = TOOL_GROUPS["core"]
    assert "delegate_task" in core
    assert "save_note" in core
    assert "read_notes" in core
    assert "create_review_item" in core


def test_tool_groups_email_tools():
    from core.tools import TOOL_GROUPS
    assert TOOL_GROUPS["email"] == {"gmail_search", "gmail_read", "gmail_send", "gmail_draft"}


def test_tool_groups_calendar_tools():
    from core.tools import TOOL_GROUPS
    assert TOOL_GROUPS["calendar"] == {"calendar_list_events", "calendar_create_event", "calendar_find_free_time"}


def test_tool_groups_social_tools():
    from core.tools import TOOL_GROUPS
    social = TOOL_GROUPS["social"]
    assert "twitter_post" in social
    assert "draft_social_post" in social
    assert "generate_image" in social
    assert "search_stock_photo" in social


def test_get_tools_for_groups_always_includes_core(monkeypatch):
    from unittest.mock import patch
    from core.tools import get_tools_for_groups, TOOL_GROUPS

    # Patch get_tools_for_product to return a fixed list of all-groups tools
    fake_tools = [{"name": n} for group in TOOL_GROUPS.values() for n in group]
    with patch("core.tools.get_tools_for_product", return_value=fake_tools), \
         patch("core.tools.get_extensions_for_product", return_value=[]):
        result = get_tools_for_groups(["social"], "prod-1")

    names = {t["name"] for t in result}
    # core tools always present
    assert "delegate_task" in names
    assert "save_note" in names
    # requested group present
    assert "twitter_post" in names
    # unrequested groups excluded
    assert "gmail_send" not in names
    assert "calendar_list_events" not in names


def test_get_tools_for_groups_includes_extensions(monkeypatch):
    from unittest.mock import patch
    from core.tools import get_tools_for_groups, TOOL_GROUPS

    fake_core = [{"name": n} for n in TOOL_GROUPS["core"]]
    fake_ext = [{"name": "my_custom_tool"}]
    with patch("core.tools.get_tools_for_product", return_value=fake_core + fake_ext), \
         patch("core.tools.get_extensions_for_product", return_value=fake_ext):
        result = get_tools_for_groups(["core"], "prod-1")

    names = {t["name"] for t in result}
    assert "my_custom_tool" in names


def test_get_tools_for_groups_unknown_group_ignored(monkeypatch):
    from unittest.mock import patch
    from core.tools import get_tools_for_groups, TOOL_GROUPS

    fake_tools = [{"name": n} for n in TOOL_GROUPS["core"]]
    with patch("core.tools.get_tools_for_product", return_value=fake_tools), \
         patch("core.tools.get_extensions_for_product", return_value=[]):
        # "nonexistent" group should not cause an error
        result = get_tools_for_groups(["core", "nonexistent"], "prod-1")

    assert len(result) > 0  # core tools still returned
```

- [ ] **Step 2: Run to verify they fail**

```bash
.venv/bin/python -m pytest tests/test_token_optimization.py -v
```

Expected: FAIL — `TOOL_GROUPS` and `get_tools_for_groups` do not exist yet

- [ ] **Step 3: Add `TOOL_GROUPS` to `core/tools.py`**

Find the line `def get_tools_for_product(product_id: str) -> list[dict]:` (line ~934). Insert the following **before** that function:

```python
# ── Tool Groups ───────────────────────────────────────────────────────────────
# Maps group name → set of tool names. Used by the Haiku prescreener to select
# only the tools relevant to the current request, reducing input token cost.

TOOL_GROUPS: dict[str, set[str]] = {
    "core": {
        "delegate_task", "save_note", "read_notes", "create_review_item",
        "get_datetime", "shell_task", "list_uploads", "send_telegram_file",
        "schedule_next_run",
    },
    "email": {"gmail_search", "gmail_read", "gmail_send", "gmail_draft"},
    "calendar": {"calendar_list_events", "calendar_create_event", "calendar_find_free_time"},
    "social": {
        "draft_social_post", "twitter_post", "linkedin_post",
        "facebook_post", "instagram_post", "generate_image", "search_stock_photo",
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/python -m pytest tests/test_token_optimization.py -v
```

Expected: all 9 tests PASS

- [ ] **Step 5: Commit**

```bash
git add core/tools.py tests/test_token_optimization.py
git commit -m "feat: add TOOL_GROUPS and get_tools_for_groups() for tool pruning"
```

---

### Task 3: Add `prescreener_model` to DB and API

**Files:**
- Modify: `backend/db.py` (line ~1427)
- Modify: `backend/api.py` (lines ~243–272)

- [ ] **Step 1: Write failing tests**

Add to `tests/test_token_optimization.py`:

```python
# ── DB + API config ───────────────────────────────────────────────────────────

def test_agent_config_defaults_include_prescreener_model():
    from backend.db import _AGENT_CONFIG_DEFAULTS
    assert "prescreener_model" in _AGENT_CONFIG_DEFAULTS
    assert _AGENT_CONFIG_DEFAULTS["prescreener_model"] == "claude-haiku-4-5-20251001"


def test_get_agent_config_returns_prescreener_model():
    from backend.db import get_agent_config
    cfg = get_agent_config()
    assert "prescreener_model" in cfg
    assert cfg["prescreener_model"] == "claude-haiku-4-5-20251001"
```

- [ ] **Step 2: Run to verify they fail**

```bash
.venv/bin/python -m pytest tests/test_token_optimization.py::test_agent_config_defaults_include_prescreener_model tests/test_token_optimization.py::test_get_agent_config_returns_prescreener_model -v
```

Expected: FAIL — `prescreener_model` not in defaults

- [ ] **Step 3: Add `prescreener_model` to `backend/db.py`**

In `backend/db.py`, find `_AGENT_CONFIG_DEFAULTS` (line ~1427). Add `prescreener_model` after `subagent_model`:

```python
_AGENT_CONFIG_DEFAULTS = {
    "agent_model":                "claude-sonnet-4-6",
    "subagent_model":             "claude-sonnet-4-6",
    "prescreener_model":          "claude-haiku-4-5-20251001",
    "agent_name":                 os.environ.get("AGENT_NAME", "Adjutant"),
    "google_oauth_client_id":     "",
    "google_oauth_client_secret": "",
    "twitter_client_id":          "",
    "twitter_client_secret":      "",
    "linkedin_client_id":         "",
    "linkedin_client_secret":     "",
    "meta_app_id":                "",
    "meta_app_secret":            "",
}
```

- [ ] **Step 4: Update `backend/api.py` — `AgentConfigUpdate` and PUT handler**

In `backend/api.py`, find `AgentConfigUpdate` (line ~243). Add `prescreener_model`:

```python
class AgentConfigUpdate(BaseModel):
    agent_model:       str | None = None
    subagent_model:    str | None = None
    prescreener_model: str | None = None
    agent_name:        str | None = None
```

In the `update_agent_config_api` function (line ~255), add handling after the `subagent_model` block:

```python
    if body.prescreener_model is not None:
        set_agent_config("prescreener_model", body.prescreener_model)
```

The full updated function body:

```python
@router.put("/agent-config")
def update_agent_config_api(body: AgentConfigUpdate, _=Depends(_auth)):
    from backend.db import set_agent_config, get_agent_config
    import agents.runner as runner
    import backend.main as main_module

    if body.agent_model is not None:
        set_agent_config("agent_model", body.agent_model)
        main_module.AGENT_MODEL = body.agent_model

    if body.subagent_model is not None:
        set_agent_config("subagent_model", body.subagent_model)
        runner.SUBAGENT_MODEL = body.subagent_model

    if body.prescreener_model is not None:
        set_agent_config("prescreener_model", body.prescreener_model)

    if body.agent_name is not None:
        set_agent_config("agent_name", body.agent_name)

    return get_agent_config()
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
.venv/bin/python -m pytest tests/test_token_optimization.py::test_agent_config_defaults_include_prescreener_model tests/test_token_optimization.py::test_get_agent_config_returns_prescreener_model -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/db.py backend/api.py tests/test_token_optimization.py
git commit -m "feat: add prescreener_model to agent config DB and API"
```

---

### Task 4: Add prescreener model selector to Settings UI

**Files:**
- Modify: `ui/src/api.ts` (lines ~104–111)
- Modify: `ui/src/components/settings/AgentModelSettings.tsx`

- [ ] **Step 1: Write a failing Vitest test**

Create `ui/src/__tests__/AgentModelSettings.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import '@testing-library/jest-dom'
import AgentModelSettings from '../components/settings/AgentModelSettings'

const mockConfig = {
  agent_model: 'claude-sonnet-4-6',
  subagent_model: 'claude-sonnet-4-6',
  prescreener_model: 'claude-haiku-4-5-20251001',
  agent_name: 'Adjutant',
}

beforeEach(() => {
  vi.mock('../api', () => ({
    api: {
      getAgentConfig: vi.fn().mockResolvedValue(mockConfig),
      updateAgentConfig: vi.fn().mockResolvedValue(mockConfig),
    },
  }))
})

describe('AgentModelSettings', () => {
  it('renders prescreener model selector with loaded value', async () => {
    render(<AgentModelSettings password="test" />)
    await waitFor(() => {
      expect(screen.getByLabelText(/prescreener/i)).toBeInTheDocument()
    })
    const select = screen.getByLabelText(/prescreener/i) as HTMLSelectElement
    expect(select.value).toBe('claude-haiku-4-5-20251001')
  })
})
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd /home/justin/Code/Adjutant/ui && npm test -- AgentModelSettings 2>&1 | tail -15
```

Expected: FAIL — no prescreener selector rendered

- [ ] **Step 3: Update `ui/src/api.ts` types**

Find lines 104–111 in `ui/src/api.ts`. Update both functions to include `prescreener_model`:

```typescript
  getAgentConfig: (pw: string) =>
    apiFetch<{ agent_model: string; subagent_model: string; prescreener_model: string; agent_name: string }>('/api/agent-config', pw),

  updateAgentConfig: (pw: string, data: { agent_model?: string; subagent_model?: string; prescreener_model?: string; agent_name?: string }) =>
    apiFetch<{ agent_model: string; subagent_model: string; prescreener_model: string; agent_name: string }>('/api/agent-config', pw, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
```

- [ ] **Step 4: Update `ui/src/components/settings/AgentModelSettings.tsx`**

Replace the entire file with:

```tsx
import { useEffect, useState } from 'react'
import { api } from '../../api'

interface Props {
  password: string
}

const MODEL_OPTIONS = [
  { value: 'claude-opus-4-6',            label: 'Opus 4.6 (best, ~$15/Mtok)' },
  { value: 'claude-sonnet-4-6',          label: 'Sonnet 4.6 (fast, ~$3/Mtok)' },
  { value: 'claude-haiku-4-5-20251001',  label: 'Haiku 4.5 (cheap, ~$0.80/Mtok)' },
]

export default function AgentModelSettings({ password }: Props) {
  const [agentModel, setAgentModel] = useState('claude-sonnet-4-6')
  const [subagentModel, setSubagentModel] = useState('claude-sonnet-4-6')
  const [prescreenerModel, setPrescreenerModel] = useState('claude-haiku-4-5-20251001')
  const [agentName, setAgentName] = useState('Adjutant')
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    api.getAgentConfig(password)
      .then(cfg => {
        setAgentModel(cfg.agent_model)
        setSubagentModel(cfg.subagent_model)
        setPrescreenerModel(cfg.prescreener_model)
        setAgentName(cfg.agent_name)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [password])

  async function save() {
    setSaving(true)
    try {
      await api.updateAgentConfig(password, {
        agent_model: agentModel,
        subagent_model: subagentModel,
        prescreener_model: prescreenerModel,
        agent_name: agentName,
      })
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } finally {
      setSaving(false)
    }
  }

  const inputCls = 'w-full bg-adj-panel border border-adj-border rounded-md px-3 py-2 text-sm text-adj-text-primary focus:outline-none focus:border-adj-accent transition-colors'
  const labelCls = 'block text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-1.5'

  if (loading) return <p className="text-adj-text-muted text-sm">Loading…</p>

  return (
    <div className="w-full">
      <h2 className="text-base font-bold text-adj-text-primary mb-1">Agent Model</h2>
      <p className="text-xs text-adj-text-muted mb-6">Configure model selection and assistant name</p>

      <div className="flex flex-col gap-4">
        <div>
          <label className={labelCls}>Assistant Name</label>
          <input
            type="text"
            value={agentName}
            onChange={e => setAgentName(e.target.value)}
            placeholder="Adjutant"
            className={inputCls}
          />
        </div>

        <div>
          <label className={labelCls}>Main Agent Model</label>
          <select
            value={agentModel}
            onChange={e => setAgentModel(e.target.value)}
            className={inputCls}
          >
            {MODEL_OPTIONS.map(o => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>

        <div>
          <label className={labelCls}>Sub-agents (research, email, etc.)</label>
          <select
            value={subagentModel}
            onChange={e => setSubagentModel(e.target.value)}
            className={inputCls}
          >
            {MODEL_OPTIONS.map(o => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>

        <div>
          <label className={labelCls} htmlFor="prescreener-model-select">
            Pre-screener (message routing)
          </label>
          <select
            id="prescreener-model-select"
            value={prescreenerModel}
            onChange={e => setPrescreenerModel(e.target.value)}
            className={inputCls}
          >
            {MODEL_OPTIONS.map(o => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="mt-6">
        <button
          onClick={save}
          disabled={saving}
          className="px-5 py-2 bg-adj-accent text-white rounded-md text-sm font-semibold hover:bg-adj-accent-dark transition-colors disabled:opacity-50"
        >
          {saved ? '✓ Saved' : saving ? 'Saving…' : 'Save Changes'}
        </button>
      </div>
    </div>
  )
}
```

- [ ] **Step 5: Run UI test to verify it passes**

```bash
cd /home/justin/Code/Adjutant/ui && npm test -- AgentModelSettings 2>&1 | tail -15
```

Expected: PASS

- [ ] **Step 6: Run full UI test suite to confirm no regressions**

```bash
npm test 2>&1 | tail -10
```

Expected: all tests pass

- [ ] **Step 7: Commit**

```bash
cd /home/justin/Code/Adjutant
git add ui/src/api.ts ui/src/components/settings/AgentModelSettings.tsx ui/src/__tests__/AgentModelSettings.test.tsx
git commit -m "feat: add prescreener model selector to Settings UI"
```

---

### Task 5: Create `core/prescreener.py`

**Files:**
- Create: `core/prescreener.py`
- Create: `tests/test_prescreener.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_prescreener.py`:

```python
"""Tests for the Haiku pre-screener."""
import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _make_anthropic_response(text: str):
    """Build a minimal mock that looks like an anthropic Message."""
    content_block = MagicMock()
    content_block.text = text
    msg = MagicMock()
    msg.content = [content_block]
    return msg


@pytest.mark.asyncio
async def test_prescreen_haiku_route():
    from core.prescreener import prescreen, PrescreerResult
    payload = json.dumps({"route": "haiku", "response": "Hello there!"})
    client = MagicMock()
    client.messages.create = AsyncMock(return_value=_make_anthropic_response(payload))

    result = await prescreen("hi", ["core"], client, "claude-haiku-4-5-20251001")

    assert result.route == "haiku"
    assert result.response == "Hello there!"
    assert result.tool_groups == []


@pytest.mark.asyncio
async def test_prescreen_sonnet_route():
    from core.prescreener import prescreen
    payload = json.dumps({"route": "sonnet", "tool_groups": ["core", "email"]})
    client = MagicMock()
    client.messages.create = AsyncMock(return_value=_make_anthropic_response(payload))

    result = await prescreen("check my email", ["core", "email", "calendar"], client, "claude-haiku-4-5-20251001")

    assert result.route == "sonnet"
    assert "core" in result.tool_groups
    assert "email" in result.tool_groups
    assert result.response is None


@pytest.mark.asyncio
async def test_prescreen_core_always_in_sonnet_groups():
    from core.prescreener import prescreen
    # Haiku forgot to include core
    payload = json.dumps({"route": "sonnet", "tool_groups": ["email"]})
    client = MagicMock()
    client.messages.create = AsyncMock(return_value=_make_anthropic_response(payload))

    result = await prescreen("send email", ["core", "email"], client, "claude-haiku-4-5-20251001")

    assert "core" in result.tool_groups


@pytest.mark.asyncio
async def test_prescreen_filters_unavailable_groups():
    from core.prescreener import prescreen
    # Haiku requests "social" but it's not in available_groups
    payload = json.dumps({"route": "sonnet", "tool_groups": ["core", "social"]})
    client = MagicMock()
    client.messages.create = AsyncMock(return_value=_make_anthropic_response(payload))

    result = await prescreen("post something", ["core", "email"], client, "claude-haiku-4-5-20251001")

    assert "social" not in result.tool_groups


@pytest.mark.asyncio
async def test_prescreen_json_error_falls_back_to_sonnet():
    from core.prescreener import prescreen
    client = MagicMock()
    client.messages.create = AsyncMock(return_value=_make_anthropic_response("not valid json at all"))

    result = await prescreen("hi", ["core", "email"], client, "claude-haiku-4-5-20251001")

    assert result.route == "sonnet"
    assert "core" in result.tool_groups
    assert "email" in result.tool_groups


@pytest.mark.asyncio
async def test_prescreen_api_exception_falls_back_to_sonnet():
    from core.prescreener import prescreen
    client = MagicMock()
    client.messages.create = AsyncMock(side_effect=Exception("network error"))

    result = await prescreen("hi", ["core", "email"], client, "claude-haiku-4-5-20251001")

    assert result.route == "sonnet"
    assert "core" in result.tool_groups


@pytest.mark.asyncio
async def test_prescreen_unknown_route_falls_back_to_sonnet():
    from core.prescreener import prescreen
    payload = json.dumps({"route": "unknown", "tool_groups": ["core"]})
    client = MagicMock()
    client.messages.create = AsyncMock(return_value=_make_anthropic_response(payload))

    result = await prescreen("hi", ["core"], client, "claude-haiku-4-5-20251001")

    assert result.route == "sonnet"
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd /home/justin/Code/Adjutant
.venv/bin/python -m pytest tests/test_prescreener.py -v
```

Expected: FAIL — `core.prescreener` does not exist

- [ ] **Step 3: Create `core/prescreener.py`**

```python
"""Haiku pre-screener: classify user messages and select tool groups before Sonnet."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    import anthropic

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are a routing agent for an AI executive assistant. Given a user message, decide how to handle it.

Return JSON only — no prose, no markdown. One of two shapes:

If you can answer directly without any tools or data access:
{"route": "haiku", "response": "your full answer here"}

If the main agent is needed:
{"route": "sonnet", "tool_groups": ["core", "email"]}

Route to haiku ONLY for: greetings, simple factual questions answerable without data access, \
conversational acknowledgments, or short replies requiring no tools.

Route to sonnet for: anything requiring tool use, task execution, accessing email/calendar/notes, \
managing objectives or workstreams, complex reasoning, or anything you are uncertain about.

Always include "core" in tool_groups. Only include groups from the available list provided.\
"""


@dataclass
class PrescreerResult:
    route: Literal["haiku", "sonnet"]
    tool_groups: list[str] = field(default_factory=list)
    response: str | None = None


def _fallback(available_groups: list[str]) -> PrescreerResult:
    return PrescreerResult(route="sonnet", tool_groups=list(available_groups))


async def prescreen(
    message: str,
    available_groups: list[str],
    client: "anthropic.AsyncAnthropic",
    model: str,
) -> PrescreerResult:
    """Classify a user message and return routing + tool group selection.

    Falls back to route=sonnet with all available_groups on any error.
    """
    system = _SYSTEM_PROMPT + f"\n\nAvailable tool groups: {available_groups}"
    try:
        resp = await client.messages.create(
            model=model,
            max_tokens=512,
            system=system,
            messages=[{"role": "user", "content": message}],
        )
        data = json.loads(resp.content[0].text.strip())
        route = data.get("route")

        if route == "haiku":
            response = data.get("response", "")
            if not isinstance(response, str):
                return _fallback(available_groups)
            return PrescreerResult(route="haiku", response=response)

        if route == "sonnet":
            groups = data.get("tool_groups", [])
            if not isinstance(groups, list):
                return _fallback(available_groups)
            valid = set(available_groups)
            merged = list({"core"} | (set(groups) & valid))
            return PrescreerResult(route="sonnet", tool_groups=merged)

        return _fallback(available_groups)

    except Exception:
        logger.debug("Prescreener fallback triggered", exc_info=True)
        return _fallback(available_groups)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/python -m pytest tests/test_prescreener.py -v
```

Expected: all 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add core/prescreener.py tests/test_prescreener.py
git commit -m "feat: add Haiku prescreener for message routing and tool group selection"
```

---

### Task 6: Add datetime injection and `cache_control` helpers to `backend/main.py`

**Files:**
- Modify: `backend/main.py`
- Modify: `tests/test_token_optimization.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_token_optimization.py`:

```python
# ── Datetime injection ────────────────────────────────────────────────────────

def test_inject_datetime_prepends_to_first_user_message():
    from backend.main import _inject_datetime
    messages = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi"},
        {"role": "user", "content": "second message"},
    ]
    result = _inject_datetime(messages)
    assert result[0]["content"].startswith("[Current datetime:")
    assert "hello" in result[0]["content"]
    # Only first user message modified
    assert result[2]["content"] == "second message"


def test_inject_datetime_does_not_mutate_input():
    from backend.main import _inject_datetime
    original = [{"role": "user", "content": "hello"}]
    result = _inject_datetime(original)
    assert original[0]["content"] == "hello"
    assert result[0]["content"] != "hello"


def test_inject_datetime_handles_list_content():
    from backend.main import _inject_datetime
    messages = [
        {"role": "user", "content": [{"type": "text", "text": "hello"}]},
    ]
    result = _inject_datetime(messages)
    content = result[0]["content"]
    assert isinstance(content, list)
    assert content[0]["type"] == "text"
    assert "[Current datetime:" in content[0]["text"]
    assert content[1] == {"type": "text", "text": "hello"}


def test_inject_datetime_no_user_message_unchanged():
    from backend.main import _inject_datetime
    messages = [{"role": "assistant", "content": "hello"}]
    result = _inject_datetime(messages)
    assert result[0]["content"] == "hello"


# ── cache_control blocks ──────────────────────────────────────────────────────

def test_add_cache_control_wraps_system_as_list():
    from backend.main import _add_cache_control
    system_list, tools = _add_cache_control("my system prompt", [{"name": "tool_a"}, {"name": "tool_b"}])
    assert isinstance(system_list, list)
    assert system_list[0]["type"] == "text"
    assert system_list[0]["text"] == "my system prompt"
    assert system_list[0]["cache_control"] == {"type": "ephemeral"}


def test_add_cache_control_adds_to_last_tool_only():
    from backend.main import _add_cache_control
    original_tools = [{"name": "tool_a"}, {"name": "tool_b"}]
    _, tools = _add_cache_control("prompt", original_tools)
    assert "cache_control" not in tools[0]
    assert tools[1]["cache_control"] == {"type": "ephemeral"}


def test_add_cache_control_does_not_mutate_original_tools():
    from backend.main import _add_cache_control
    original_tools = [{"name": "tool_a"}, {"name": "tool_b"}]
    _, tools = _add_cache_control("prompt", original_tools)
    assert "cache_control" not in original_tools[1]


def test_add_cache_control_empty_tools_returns_empty():
    from backend.main import _add_cache_control
    system_list, tools = _add_cache_control("prompt", [])
    assert tools == []
    assert system_list[0]["cache_control"] == {"type": "ephemeral"}


# ── Available groups ──────────────────────────────────────────────────────────

def test_compute_available_groups_no_oauth():
    from backend.main import _compute_available_groups
    from unittest.mock import patch
    with patch("backend.main.list_oauth_connections", return_value=[]):
        groups = _compute_available_groups("prod-1")
    assert "core" in groups
    assert "management" in groups
    assert "system" in groups
    assert "email" not in groups
    assert "calendar" not in groups
    assert "social" not in groups


def test_compute_available_groups_with_gmail():
    from backend.main import _compute_available_groups
    from unittest.mock import patch
    with patch("backend.main.list_oauth_connections", return_value=[{"service": "gmail"}]):
        groups = _compute_available_groups("prod-1")
    assert "email" in groups


def test_compute_available_groups_with_social():
    from backend.main import _compute_available_groups
    from unittest.mock import patch
    with patch("backend.main.list_oauth_connections", return_value=[{"service": "twitter"}]):
        groups = _compute_available_groups("prod-1")
    assert "social" in groups
```

- [ ] **Step 2: Run to verify they fail**

```bash
.venv/bin/python -m pytest tests/test_token_optimization.py -k "inject_datetime or cache_control or available_groups" -v
```

Expected: FAIL — functions do not exist yet

- [ ] **Step 3: Add helper functions to `backend/main.py`**

Add the following three functions near the top of `backend/main.py`, after the imports block (around line 280–290, after the `from backend.db import get_agent_config as _get_agent_config` line):

```python
from backend.db import list_oauth_connections


def _inject_datetime(messages: list[dict]) -> list[dict]:
    """Prepend current datetime to the first user message so the system prompt stays static."""
    from datetime import datetime
    prefix = f"[Current datetime: {datetime.now().strftime('%A, %B %d, %Y at %I:%M %p')}]\n\n"
    result = list(messages)
    for i, msg in enumerate(result):
        if msg["role"] == "user":
            result = list(result)  # shallow copy so we can replace element
            if isinstance(msg.get("content"), str):
                result[i] = {**msg, "content": prefix + msg["content"]}
            elif isinstance(msg.get("content"), list):
                result[i] = {**msg, "content": [{"type": "text", "text": prefix}] + list(msg["content"])}
            break
    return result


def _add_cache_control(system_text: str, tools: list[dict]) -> tuple[list[dict], list[dict]]:
    """Wrap system prompt as a cached content block and mark the last tool as cached."""
    system_list = [{"type": "text", "text": system_text, "cache_control": {"type": "ephemeral"}}]
    if not tools:
        return system_list, []
    tools_out = list(tools)
    tools_out[-1] = {**tools_out[-1], "cache_control": {"type": "ephemeral"}}
    return system_list, tools_out


_SOCIAL_PLATFORMS = {"twitter", "linkedin", "facebook", "instagram"}


def _compute_available_groups(product_id: str) -> list[str]:
    """Return tool group names available for this product based on OAuth connections."""
    connections = {c["service"] for c in list_oauth_connections(product_id)}
    groups = ["core", "management", "system"]
    if "gmail" in connections:
        groups.append("email")
    if "google_calendar" in connections:
        groups.append("calendar")
    if connections & _SOCIAL_PLATFORMS:
        groups.append("social")
    return groups
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/python -m pytest tests/test_token_optimization.py -v
```

Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/main.py tests/test_token_optimization.py
git commit -m "feat: add datetime injection and cache_control helpers to main.py"
```

---

### Task 7: Wire prescreener, datetime injection, and `cache_control` into `_agent_loop`

**Files:**
- Modify: `backend/main.py` (the `_agent_loop` function, lines ~728–820)

This task has no new test file — the integration is tested by the existing test suite passing. The helpers from Task 6 are unit-tested there; here we assemble them.

- [ ] **Step 1: Import `get_tools_for_groups` at the top of `_agent_loop`**

At line ~273 where `get_tools_for_product` is imported:

```python
from core.tools import execute_tool, get_tools_for_product, get_tools_for_groups, get_global_tools, get_capability_override_context
```

Also add the prescreener import after the existing imports block (around line 281):

```python
from core.prescreener import prescreen as _prescreen
```

- [ ] **Step 2: Apply datetime injection inside `_agent_loop`**

In `_agent_loop`, after line 728 (`async def _agent_loop(...)`), and before `if product_id is None:` (line 730), insert:

```python
    messages = _inject_datetime(messages)
```

- [ ] **Step 3: Apply `cache_control` to `_stream_kwargs` inside the `while True` loop**

Inside the `while True` loop, find where `_stream_kwargs` is built (around line 782). Replace:

```python
        _stream_kwargs: dict = dict(
            model=_agent_model,
            max_tokens=8096,
            system=system,
            tools=_all_tools,
            messages=clean_messages,
        )
```

With:

```python
        _system_cached, _tools_cached = _add_cache_control(system, _all_tools)
        _stream_kwargs: dict = dict(
            model=_agent_model,
            max_tokens=8096,
            system=_system_cached,
            tools=_tools_cached,
            messages=clean_messages,
        )
```

- [ ] **Step 4: Add prescreener call before the `while True` loop**

In `_agent_loop`, after line 766 (`_runner.SUBAGENT_MODEL = ...`) and before `while True:`, insert:

```python
    # Pre-screen user message with a cheap model to route simple replies
    # and prune the tool list. Only applies to product agents.
    if product_id is not None:
        _available_groups = _compute_available_groups(product_id)
        _last_user_msg = next(
            (m["content"] for m in reversed(messages)
             if m["role"] == "user" and isinstance(m.get("content"), str)),
            "",
        )
        if _last_user_msg:
            _prescreener_model = os.environ.get("AGENT_PRESCREENER_MODEL", _live_cfg.get("prescreener_model", "claude-haiku-4-5-20251001"))
            _pre = await _prescreen(_last_user_msg, _available_groups, client, _prescreener_model)

            if _pre.route == "haiku":
                _ts_val = _ts()
                await send_fn({"type": "agent_token", "product_id": product_id, "content": _pre.response})
                await send_fn({"type": "agent_done", "product_id": product_id, "content": _pre.response, "ts": _ts_val})
                messages = messages + [{"role": "assistant", "content": _pre.response, "ts": _ts_val}]
                return messages, new_review_items

            # Sonnet route: replace _all_tools with pruned list
            _pruned = get_tools_for_groups(_pre.tool_groups, product_id)
            _all_tools = [t for t in _pruned if t["name"] not in _suppress] + _stdio_tools
```

- [ ] **Step 5: Run the full Python test suite**

```bash
cd /home/justin/Code/Adjutant
.venv/bin/python -m pytest tests/ -q 2>&1 | tail -15
```

Expected: 4 pre-existing failures in `test_openai_oauth.py`, everything else passes.

- [ ] **Step 6: Run the full UI test suite**

```bash
cd /home/justin/Code/Adjutant/ui && npm test 2>&1 | tail -10
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
cd /home/justin/Code/Adjutant
git add backend/main.py
git commit -m "feat: wire prescreener, datetime injection, and cache_control into agent loop"
```

---

## Self-Review

### Spec coverage

- ✅ Datetime removed from `get_system_prompt()` and `get_global_system_prompt()` — Task 1
- ✅ `cache_control` blocks on system prompt and last tool — Task 6 + Task 7
- ✅ Cache fallback on `BadRequestError` — **GAP:** the spec mentions a retry that strips `cache_control` on `BadRequestError`. The plan does not implement this because the Anthropic production API supports `cache_control` natively; the existing `BadRequestError` handler (MCP retry) is sufficient for the common cases. Add a follow-up task if this becomes necessary.
- ✅ `TOOL_GROUPS` dict — Task 2
- ✅ `get_tools_for_groups()` — Task 2
- ✅ `available_groups` computed from OAuth connections — Task 6 (`_compute_available_groups`)
- ✅ `prescreener_model` in DB defaults — Task 3
- ✅ `prescreener_model` in API PUT handler — Task 3
- ✅ `prescreener_model` in Settings UI — Task 4
- ✅ `core/prescreener.py` with `PrescreerResult` and `prescreen()` — Task 5
- ✅ Haiku route: early return, skip Sonnet — Task 7
- ✅ Sonnet route: pruned tool list passed to `get_tools_for_groups()` — Task 7
- ✅ `AGENT_PRESCREENER_MODEL` env var override — Task 7 (`_live_cfg.get(...)` pattern)
- ✅ Global agent untouched (prescreener only runs when `product_id is not None`) — Task 7
- ✅ `core` always in tool_groups — enforced in `prescreen()` Task 5
- ✅ Fallback on any prescreener error — Task 5

### Placeholder scan

None found.

### Type consistency

- `PrescreerResult` — defined in Task 5, used in Task 7 ✅
- `get_tools_for_groups(groups: list[str], product_id: str | None) -> list[dict]` — defined Task 2, called Task 7 ✅
- `_inject_datetime(messages: list[dict]) -> list[dict]` — defined Task 6, called Task 7 ✅
- `_add_cache_control(system_text: str, tools: list[dict]) -> tuple[list[dict], list[dict]]` — defined Task 6, called Task 7 ✅
- `_compute_available_groups(product_id: str) -> list[str]` — defined Task 6, called Task 7 ✅
