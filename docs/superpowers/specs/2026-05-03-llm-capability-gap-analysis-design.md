# LLM-Assisted Capability Gap Analysis Design

**Goal:** Replace the mechanical scheduler-level capability gap check with PA-orchestrator-level LLM reasoning that prefers extending existing workstreams over recommending new ones.

**Architecture:** Remove `_check_capability_gap` from `scheduler.py`. Add a `capability_gap_hints` block to `build_context()` that precomputes which tag namespaces have no subscribed workstream and gives the PA a structured overview of each workstream's name, mission, and subscriptions. Update the PA system prompt with explicit 3-tier gap handling logic. The PA reasons over this structured context and chooses the right action: extend an existing workstream (autonomous), or flag a genuine gap (approval required).

**Tech Stack:** Python, SQLite, Anthropic LLM via existing `run_product_adjutant` path.

---

## What Changes

### `backend/scheduler.py`
- Delete `_check_capability_gap()` function (~17 lines)
- Delete its call site inside `_run_workstream()` (the loop over `raw_signals`)

Nothing else changes in the scheduler. Signals are still created by workstream agents as before — they just no longer trigger an immediate mechanical review item.

### `backend/orchestrator.py` — `build_context()`
Add a computed `capability_gap_hints` key to the returned context dict. This is derived entirely from `workstreams` and `unconsumed_signals` already fetched — no extra DB calls.

```python
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

context["capability_gap_hints"] = {
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
```

### `backend/orchestrator.py` — `PA_SYSTEM_PROMPT`
Replace the single-line gap mention in step 1 with explicit 3-tier guidance:

> When a signal's tag namespace has no subscribed workstream, check `capability_gap_hints.unsubscribed_namespaces` and reason over `capability_gap_hints.workstream_overview` before deciding:
>
> 1. If an existing workstream's mission already covers or could naturally extend to this domain → use `update_subscriptions` to add the namespace and/or `update_mission` to broaden the mission. Prefer this.
> 2. If no existing workstream is a reasonable fit → use `capability_gap`. Your description MUST name which workstreams you evaluated and briefly explain why each wasn't a match.
>
> Never flag a `capability_gap` without first explaining what you considered.

---

## Decision Schema

`capability_gap` decisions should now include:

```json
{
  "action": "capability_gap",
  "tag": "email:",
  "signal_id": 42,
  "description": "Evaluated: Organic Content Growth (content/social-focused, not email), Customer Success (support-focused). Neither covers email nurture sequences. A dedicated email workstream is needed.",
  "reason": "no existing workstream covers email marketing lifecycle"
}
```

`signal_id` is required so the signal is consumed and does not re-trigger threshold-based PA runs. (The `_execute_decision` handler already consumes the signal when `signal_id` is present — fixed in a prior commit.)

---

## Autonomy Mapping

| Gap resolution action | Autonomy level |
|---|---|
| `update_subscriptions` (extend existing) | `autonomous` (configurable) |
| `update_mission` (extend existing) | `autonomous` (configurable) |
| `capability_gap` (new workstream needed) | `approval_required` (always) |

No new action types needed. No autonomy settings changes needed.

---

## Error Handling

- If `tag_name` is empty or missing on a signal, skip it in namespace computation (don't crash).
- If `tag_subscriptions` is malformed JSON on a workstream, treat it as `[]` (already the existing pattern: `or "[]"`).
- `capability_gap_hints` is best-effort derived data — if it raises, catch and omit the key rather than failing the whole PA run.

---

## Testing

- `test_build_context_includes_capability_gap_hints` — returns key with correct structure
- `test_unsubscribed_namespaces_excludes_covered_tags` — namespaces covered by at least one workstream are excluded
- `test_unsubscribed_namespaces_includes_uncovered_tags` — namespaces with no subscribed workstream are included
- `test_check_capability_gap_removed` — `_check_capability_gap` no longer importable from `backend.scheduler`
- Existing `tests/test_orchestrator.py` suite passes without modification
