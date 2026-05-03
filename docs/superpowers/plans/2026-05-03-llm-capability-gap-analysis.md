# LLM Capability Gap Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the mechanical scheduler-level capability gap check with PA-orchestrator-level LLM reasoning that prefers extending existing workstreams over recommending new ones.

**Architecture:** Delete `_check_capability_gap` from `scheduler.py` and its call site. Add a `capability_gap_hints` block to `build_context()` in `orchestrator.py` that precomputes unsubscribed tag namespaces and gives the PA a structured overview of each workstream. Update `PA_SYSTEM_PROMPT` with explicit 3-tier gap handling logic.

**Tech Stack:** Python, SQLite, pytest, Anthropic LLM via existing `run_product_adjutant` path.

---

## File Map

| File | Change |
|---|---|
| `backend/scheduler.py` | Delete `_check_capability_gap()` (lines 258–274) and call site (line 358) |
| `backend/orchestrator.py` | Add `capability_gap_hints` to `build_context()`; update `PA_SYSTEM_PROMPT` |
| `tests/test_orchestrator.py` | Add 3 new tests for `capability_gap_hints`; add 1 test confirming removal |
| `tests/test_scheduler_signals.py` | Add 1 test confirming `_check_capability_gap` is gone |

---

## Task 1: Remove `_check_capability_gap` from scheduler.py

**Files:**
- Modify: `backend/scheduler.py:258-274` (function body)
- Modify: `backend/scheduler.py:358` (call site)
- Test: `tests/test_scheduler_signals.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_scheduler_signals.py`:

```python
def test_check_capability_gap_removed():
    import importlib
    import backend.scheduler as sched_mod
    assert not hasattr(sched_mod, "_check_capability_gap"), (
        "_check_capability_gap should have been removed from scheduler"
    )
```

- [ ] **Step 2: Run to confirm it fails**

```
pytest tests/test_scheduler_signals.py::test_check_capability_gap_removed -v
```

Expected: FAIL — `_check_capability_gap` still exists in the module.

- [ ] **Step 3: Delete the function and call site**

In `backend/scheduler.py`, delete lines 258–274 (the entire `_check_capability_gap` function including its docstring):

```python
# DELETE this entire block (lines 258–274):
def _check_capability_gap(product_id: str, tag_name: str, note: str) -> None:
    """Create a review item if no workstream subscribes to this tag's namespace."""
    import json as _json
    from backend.db import get_workstreams, save_review_item
    workstreams = get_workstreams(product_id)
    namespace = tag_name.split(":")[0] + ":" if ":" in tag_name else tag_name
    for ws in workstreams:
        subs = _json.loads(ws.get("tag_subscriptions") or "[]")
        if namespace in subs:
            return  # a workstream covers this
    save_review_item(
        product_id=product_id,
        title=f"Capability gap: no workstream handles '{tag_name}'",
        description=f"An agent identified an opportunity tagged **{tag_name}** but no workstream is subscribed to this namespace.\n\n**Opportunity note:** {note}\n\nConsider creating a new workstream to handle `{namespace}*` signals.",
        risk_label="Opportunity · no action taken",
        action_type="capability_gap",
    )
```

Also delete the call site at line 358:

```python
# DELETE this line (in the for tag_name, note in raw_signals: loop):
                    _check_capability_gap(product_id, tag_name, note)
```

After the delete, the signal-creation loop should look like:

```python
        if report_id and raw_signals:
            for tag_name, note in raw_signals:
                try:
                    tag_id = get_or_create_tag(tag_name)
                    create_signal(
                        tag_id=tag_id,
                        content_type="run_report",
                        content_id=report_id,
                        product_id=product_id,
                        tagged_by="agent",
                        note=note,
                    )
                except Exception as sig_exc:
                    log.error("Failed to create signal '%s' for report %s: %s", tag_name, report_id, sig_exc)
```

- [ ] **Step 4: Run test to confirm it passes**

```
pytest tests/test_scheduler_signals.py::test_check_capability_gap_removed -v
```

Expected: PASS.

- [ ] **Step 5: Run full test suite to check for regressions**

```
pytest tests/test_scheduler_signals.py tests/test_orchestrator.py -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add backend/scheduler.py tests/test_scheduler_signals.py
git commit -m "refactor: remove mechanical _check_capability_gap from scheduler"
```

---

## Task 2: Add `capability_gap_hints` to `build_context()`

**Files:**
- Modify: `backend/orchestrator.py` — `build_context()` return dict
- Test: `tests/test_orchestrator.py`

- [ ] **Step 1: Write failing tests**

Add three tests to `tests/test_orchestrator.py` after `test_build_context_empty_product_no_error`:

```python
def test_build_context_includes_capability_gap_hints(populated_db):
    from backend.orchestrator import build_context
    db, ws_id, sig_id = populated_db
    ctx = build_context("p1")
    assert "capability_gap_hints" in ctx
    hints = ctx["capability_gap_hints"]
    assert "unsubscribed_namespaces" in hints
    assert "workstream_overview" in hints


def test_unsubscribed_namespaces_includes_uncovered_tags(populated_db):
    """Namespaces on signals with no subscribed workstream appear in unsubscribed_namespaces."""
    from backend.orchestrator import build_context
    db, ws_id, sig_id = populated_db
    # populated_db has tag "social:linkedin" but workstream has tag_subscriptions=[]
    ctx = build_context("p1")
    hints = ctx["capability_gap_hints"]
    assert "social:" in hints["unsubscribed_namespaces"]


def test_unsubscribed_namespaces_excludes_covered_tags(populated_db):
    """Namespaces covered by at least one workstream are excluded from unsubscribed_namespaces."""
    from backend.orchestrator import build_context
    import json
    db, ws_id, sig_id = populated_db
    # Subscribe the workstream to social:
    db.update_workstream_fields(ws_id, tag_subscriptions=json.dumps(["social:"]))
    ctx = build_context("p1")
    hints = ctx["capability_gap_hints"]
    assert "social:" not in hints["unsubscribed_namespaces"]
```

- [ ] **Step 2: Run to confirm they fail**

```
pytest tests/test_orchestrator.py::test_build_context_includes_capability_gap_hints tests/test_orchestrator.py::test_unsubscribed_namespaces_includes_uncovered_tags tests/test_orchestrator.py::test_unsubscribed_namespaces_excludes_covered_tags -v
```

Expected: FAIL — `capability_gap_hints` key not present.

- [ ] **Step 3: Add `capability_gap_hints` computation to `build_context()`**

In `backend/orchestrator.py`, inside `build_context()`, add the following block just before the `return` statement (after `signals = get_signals(product_id)`):

```python
    # Compute capability gap hints for the PA
    try:
        import json as _json
        signal_namespaces: set[str] = set()
        for sig in signals:
            tag = sig.get("tag_name", "")
            if not tag:
                continue
            ns = (tag.split(":")[0] + ":") if ":" in tag else tag
            signal_namespaces.add(ns)

        unsubscribed = [
            ns for ns in sorted(signal_namespaces)
            if not any(
                ns in _json.loads(ws.get("tag_subscriptions") or "[]")
                for ws in workstreams
            )
        ]

        capability_gap_hints: dict = {
            "unsubscribed_namespaces": unsubscribed,
            "workstream_overview": [
                {
                    "id": ws["id"],
                    "name": ws["name"],
                    "mission_excerpt": (ws.get("mission") or "")[:150],
                    "subscriptions": _json.loads(ws.get("tag_subscriptions") or "[]"),
                }
                for ws in workstreams
            ],
        }
    except Exception:
        log.warning("build_context: failed to compute capability_gap_hints", exc_info=True)
        capability_gap_hints = {}
```

Then add `"capability_gap_hints": capability_gap_hints,` to the returned dict. The full return statement becomes:

```python
    return {
        "product": dict(product_row) if product_row else {"id": product_id, "name": product_id},
        "workstreams": workstreams,
        "recent_reports": [r for rs in reports_by_ws.values() for r in rs],
        "unconsumed_signals": signals,
        "recent_orchestrator_runs": [
            {"run_at": r["run_at"], "triggered_by": r["triggered_by"],
             "brief": r["brief"], "decisions": r["decisions"]}
            for r in recent_runs
        ],
        "autonomy_settings": config["autonomy_settings"],
        "active_directives": list_hca_directives(product_id=product_id),
        "current_datetime": datetime.now().isoformat(),
        "capability_gap_hints": capability_gap_hints,
    }
```

- [ ] **Step 4: Run tests to confirm they pass**

```
pytest tests/test_orchestrator.py::test_build_context_includes_capability_gap_hints tests/test_orchestrator.py::test_unsubscribed_namespaces_includes_uncovered_tags tests/test_orchestrator.py::test_unsubscribed_namespaces_excludes_covered_tags -v
```

Expected: all PASS.

- [ ] **Step 5: Run full orchestrator test suite**

```
pytest tests/test_orchestrator.py -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add backend/orchestrator.py tests/test_orchestrator.py
git commit -m "feat: add capability_gap_hints to build_context for LLM gap analysis"
```

---

## Task 3: Update `PA_SYSTEM_PROMPT` with 3-tier gap guidance

**Files:**
- Modify: `backend/orchestrator.py` — `PA_SYSTEM_PROMPT` constant

There are no new DB operations or API changes here — this is a prompt update only. No new tests needed beyond running the existing suite.

- [ ] **Step 1: Replace the single-line gap mention in step 1 of the prompt**

Current step 1 in `PA_SYSTEM_PROMPT`:

```python
    "1. Review all unconsumed signals — decide what to do with each (route to a workstream, "
    "consume as noise, or flag a capability gap). For capability_gap decisions, always include "
    "the signal_id so the signal is consumed and does not re-trigger this run.\n"
```

Replace with:

```python
    "1. Review all unconsumed signals — decide what to do with each (route to a workstream, "
    "consume as noise, or handle a capability gap).\n"
    "   When a signal's tag namespace appears in capability_gap_hints.unsubscribed_namespaces, "
    "reason over capability_gap_hints.workstream_overview before deciding:\n"
    "   a. If an existing workstream's mission already covers or could naturally extend to this "
    "domain → use update_subscriptions to add the namespace and/or update_mission to broaden "
    "the mission. Prefer this — it is autonomous and requires no approval.\n"
    "   b. If no existing workstream is a reasonable fit → use capability_gap. Your description "
    "MUST name which workstreams you evaluated and briefly explain why each was not a match. "
    "Never flag a capability_gap without first explaining what you considered.\n"
    "   For capability_gap decisions, always include the signal_id so the signal is consumed "
    "and does not re-trigger this run.\n"
```

The full updated `PA_SYSTEM_PROMPT` constant becomes:

```python
PA_SYSTEM_PROMPT = (
    "You are the Product Adjutant for {product_name} — an autonomous Chief of Staff responsible "
    "for keeping all workstreams aligned with the product's goals. You have full context of recent "
    "agent outputs, signals, and your own prior decisions.\n\n"
    "Your job each run:\n"
    "1. Review all unconsumed signals — decide what to do with each (route to a workstream, "
    "consume as noise, or handle a capability gap).\n"
    "   When a signal's tag namespace appears in capability_gap_hints.unsubscribed_namespaces, "
    "reason over capability_gap_hints.workstream_overview before deciding:\n"
    "   a. If an existing workstream's mission already covers or could naturally extend to this "
    "domain → use update_subscriptions to add the namespace and/or update_mission to broaden "
    "the mission. Prefer this — it is autonomous and requires no approval.\n"
    "   b. If no existing workstream is a reasonable fit → use capability_gap. Your description "
    "MUST name which workstreams you evaluated and briefly explain why each was not a match. "
    "Never flag a capability_gap without first explaining what you considered.\n"
    "   For capability_gap decisions, always include the signal_id so the signal is consumed "
    "and does not re-trigger this run.\n"
    "2. Review recent workstream outputs — identify patterns, drift from mission, schedule "
    "mismatches, or underperformance.\n"
    "3. Make adjustments: update missions, schedules, subscriptions, create objectives as needed.\n"
    "4. For decisions above your autonomy level, create an approval request with clear reasoning.\n"
    "5. Write a brief summarizing your observations and decisions for the Chief Adjutant.\n\n"
    "Your autonomy settings are provided in the context. Only apply actions marked 'autonomous' "
    "directly. Actions marked 'approval_required' must be included in decisions — they will be "
    "queued for user approval.\n\n"
    "Respond ONLY with valid JSON:\n"
    "{{\"decisions\": [...], \"brief\": \"prose summary for HCA\"}}"
)
```

- [ ] **Step 2: Run full test suite to confirm no regressions**

```
pytest tests/test_orchestrator.py -v
```

Expected: all pass.

- [ ] **Step 3: Commit**

```bash
git add backend/orchestrator.py
git commit -m "feat: update PA_SYSTEM_PROMPT with 3-tier capability gap guidance"
```

---

## Self-Review

**Spec coverage:**
- ✅ Delete `_check_capability_gap` from `scheduler.py` → Task 1
- ✅ Delete call site in `_run_workstream` → Task 1
- ✅ Add `capability_gap_hints` block to `build_context()` → Task 2
- ✅ Update `PA_SYSTEM_PROMPT` with 3-tier guidance → Task 3
- ✅ `test_build_context_includes_capability_gap_hints` → Task 2
- ✅ `test_unsubscribed_namespaces_excludes_covered_tags` → Task 2
- ✅ `test_unsubscribed_namespaces_includes_uncovered_tags` → Task 2
- ✅ `test_check_capability_gap_removed` → Task 1
- ✅ Error handling: try/except around hints block with `log.warning` fallback → Task 2
- ✅ `signal_id` required in `capability_gap` decision description → Task 3 prompt

**Placeholder scan:** None found.

**Type consistency:** `capability_gap_hints` is typed as `dict` in build_context and referenced by that name in the prompt. All field names (`unsubscribed_namespaces`, `workstream_overview`, `mission_excerpt`, `subscriptions`) are consistent between Task 2 implementation and Task 3 prompt.
