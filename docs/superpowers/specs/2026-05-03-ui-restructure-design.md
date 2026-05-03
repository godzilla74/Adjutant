# UI Restructure Design

**Date:** 2026-05-03
**Status:** Approved

## Problem

The current UI has grown organically as features were added and now feels crowded and hard to navigate. Specific pain points:

- The Chief Adjutant interface is buried in a drawer panel, not discoverable as a first-class feature
- Settings is a flat list of 18 tabs with no grouping — hard to find anything
- Workstreams live in Settings even though they are operational (not configuration), and show too little information to be actionable
- The overall layout feels dense; too much competing for attention at once

## Design Goals

1. Make navigation obvious — every major section reachable in one click
2. Elevate the Chief Adjutant to a first-class destination
3. Move workstreams out of Settings and into the live workspace
4. Collapse 18 flat settings tabs into 5 alphabetically-ordered groups
5. Carry forward the preferred visual style: dark background, purple accent, compact font size and spacing from the initial brainstorm mockup

---

## Architecture: Left Nav App Shell

A persistent left navigation rail is the top-level structure. It contains four items:

```
[A]          ← logo / wordmark

⊞ Overview   ← default landing
◎ Products   ← product workspaces
✦ Chief      ← Chief Adjutant (badge when reviews pending)

⚙ Settings   ← pinned to bottom of rail
```

Each item is an icon + small label. The active item is highlighted with the purple accent. The Chief item shows an amber dot badge when there are pending reviews, making the review queue impossible to miss without hunting.

---

## Section 1: Overview (Default Landing)

The page the user sees on open. Purpose: state of the entire business at a glance.

**Layout:**
- Page header: title + date + active product count
- Stats row: four cards — Workstreams (count, running), Reviews (count, pending), Signals (count, today), Chief (schedule status)
- Product list: one card per product showing name, an "Open workspace →" link, and all of that product's workstreams inline

**Workstreams on Overview:**
Each workstream chip shows: name, status indicator (running / paused / warn), and time since last run. Pause/resume is available inline — no detour to Settings required. This replaces the Settings → Workstreams tab entirely.

---

## Section 2: Product Workspace

The per-product view, reached via "Open workspace →" from Overview or via the Products nav item. Clicking the Products nav item opens a product picker: a list of all products with name, workstream count, and last-active time. Selecting a product enters its workspace. A "+ New product" button at the top of the picker triggers the Product Wizard modal.

**Layout — three columns:**
1. **Left nav rail** (same across all sections)
2. **Sessions sidebar** (190px): product name + session count at top; session list with name, timestamp, activity count; "+ New session" at bottom; live agents pinned to the bottom of the sidebar with name and elapsed time
3. **Main area**: session header (name, activity count, Notes and History as small buttons), activity feed, directive bar at the bottom

**Activity cards:**
Review items (email drafts, social posts, new product recommendations) show Approve / Edit / Dismiss actions inline on the card. No separate panel or drawer required.

**Directive bar:**
Single text input + Send button. A ⚡ icon next to Send expands directive templates as a panel that slides up above the directive bar — collapsed by default so they don't compete for space.

**Removed from this view:**
- Status strip (workstream + review counts move to Overview stats row and Chief badge)
- Directive templates always-visible row (collapsed to ⚡ icon)

---

## Section 3: Chief Adjutant

A full dedicated page — not a drawer. Reached via the ✦ nav item.

**Layout — two columns:**

**Left column — Review queue:**
All pending reviews across every product. Each card shows:
- Action type (LinkedIn post, Send email, New product, etc.) — color-coded by type
- Product tag (which product it came from)
- Content preview
- Approve / Edit / Dismiss actions inline
- Timestamp

**Right column — Briefing + Run history:**
- Latest briefing: bullet-point summary from the most recent Chief run
- Run history: list of past runs (run number + timestamp) with a ↗ link to the full report
- Page header contains: "Last ran X ago · next run in Y", a "▶ Run now" button, and a "⚙ Configure" link into Settings → System → Chief Adjutant

---

## Section 4: Settings

A full page with a two-panel layout: grouped sidebar on the left, content on the right.

### Sidebar structure (alphabetical groups, alphabetical items within each group)

**Connections**
- All connections
- Google
- Slack / Discord
- Social
- Telegram

**General**
- API Keys
- Token Usage
- Workspace

**Models**
- Agent default
- Image generation
- Per-product

**Products**
- Autonomy
- MCP servers
- Objectives

**System**
- Chief Adjutant
- Global MCP
- Orchestrator
- Signals
- Tags

### Migration from 18 flat tabs

| Old tab | New location |
|---|---|
| Overview | General → Workspace |
| Agent Models | Models → Agent default |
| Product Models | Models → Per-product |
| Autonomy | Products → Autonomy |
| Workstreams | Removed — lives on Overview |
| Objectives | Products → Objectives |
| Tags | System → Tags |
| Signals | System → Signals |
| Orchestrator | System → Orchestrator |
| HCA | System → Chief Adjutant |
| Google OAuth | Connections → Google |
| Social | Connections → Social |
| Integrations (Slack/Discord) | Connections → Slack / Discord |
| Connections list | Connections → All connections |
| Global MCP | System → Global MCP |
| Product MCP | Products → MCP servers |
| Image Generation | Models → Image generation |
| Token Usage | General → Token Usage |
| *(new)* | General → API Keys (consolidates Anthropic + OpenAI key entry) |
| Telegram | Connections → Telegram |

---

## Visual Style

Carry forward the style established in the brainstorm mockups:
- Background: `#0a0a14` (page), `#0e0e1a` (rail), `#0c0c18` (sidebar)
- Cards / panels: `#12121e` with `#1e1e2e` borders
- Primary accent: `#7c3aed` (purple), hover/active tint `#a78bfa`
- Status colors: green `#4ade80` (running/ok), amber `#f59e0b` (warn/pending), red `#f87171` (error/urgent), blue `#60a5fa` (info)
- Font: system-ui / Inter, 12px base, 11px secondary, 10px labels
- Border radius: 8px cards, 6px inner elements

---

## What This Does Not Change

- Backend API surface — all existing endpoints remain; this is a pure frontend restructure
- Data model — sessions, workstreams, objectives, signals, tags, reviews are unchanged
- Auth / password gate — unchanged
- WebSocket protocol — unchanged
- Product Wizard modal — unchanged, triggered from the "+ New product" button in the Products picker view
