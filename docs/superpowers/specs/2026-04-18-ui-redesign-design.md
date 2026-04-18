# UI Redesign — Design Spec

**Date:** 2026-04-18
**Status:** Approved for implementation

## Overview

Adjutant has grown significantly in features and now feels cluttered for non-technical users. This redesign simplifies the layout, cleans up navigation, and introduces a smarter product creation flow — without changing how the core agent and workstream systems work.

**Design philosophy:** Chat is the hero. Status is always visible but never in the way. Settings are accessible but not cluttering the workspace.

---

## 1. Overall Layout

### Before

Seven panels competing for space simultaneously:
- ProductRail (w-14 icon strip, left edge)
- SessionsPanel + WorkstreamsPanel (left sidebar, stacked)
- ActivityFeed + DirectiveBar (center)
- ReviewQueue + ObjectivesPanel (right sidebar, stacked)
- SettingsSidebar drawer (overlays right side)

### After — Two-column workspace

```
[Header: Logo | Product Dropdown | Notes | History | Settings]
[Status Strip: ● workstreams | ⟳ agents | ⚠ reviews | ◎ objectives — expand ▾]
[Sessions Panel (slim) | Activity Feed + Directive Bar (full width)]
```

**Removed entirely:**
- `ProductRail` — replaced by product dropdown in header
- `WorkstreamsPanel` — managed in Settings page
- `ReviewQueue` — surfaced via status strip popover
- `ObjectivesPanel` — surfaced via status strip popover
- `SettingsSidebar` drawer — replaced by full-page Settings view

**Kept (simplified):**
- `SessionsPanel` — slimmer, left side only
- `ActivityFeed` with Chat/Activity tabs
- `DirectiveBar` + `DirectiveTemplates`
- `LiveAgents` bar
- `NotesDrawer` and `DirectiveHistoryDrawer`

---

## 2. Header

```
[⬡ logo] [divider] [Product Dropdown ▾] [spacer →] [✎ Notes] [⟲ History] [⚙ Settings]
```

- **Logo** — static, left edge
- **Product Dropdown** — shows current product name + color icon; click opens product switcher (see Section 5)
- **Notes, History** — icon buttons, open existing drawers unchanged
- **Settings** — icon button, navigates to full Settings page (not a drawer)
- **No badges in header** — count badges (review count, agent count) moved to status strip

---

## 3. Status Strip

A compact bar between the header and the main workspace. Always visible. Replaces the ReviewQueue and ObjectivesPanel right panels entirely.

### Collapsed (default)

```
● 3 workstreams  |  ⟳ 1 agent active  |  ⚠ 2 reviews pending  |  ◎ 4 objectives  [expand ▾]
```

Each segment is a clickable pill. Zero counts are dimmed but still present.

**Attention states:**
- Review pending: amber pill pulses to draw attention
- Agent active: blue spinner animates
- Workstream warning: amber dot instead of green

### Expanded — popovers (one open at a time)

**Workstreams popover:**
- List of workstreams with status dot (running/warn/paused), name, schedule
- "Manage workstreams →" link deep-links to Settings → Workstreams tab

**Reviews popover:**
- Full review cards with title, risk label, Approve / Skip buttons inline
- No navigation required — reviews can be actioned from the popover

**Active Agents popover:**
- Running agents with type, elapsed time, current task description
- Cancel button per agent
- Queue count shown at bottom

**Objectives popover:**
- Objective list with progress (current/target)
- "Manage objectives →" link deep-links to Settings → Objectives tab

---

## 4. Settings Page

Replaces `SettingsSidebar` drawer. Accessed via the ⚙ icon in the header. Full-page view with a left navigation sidebar.

### Navigation structure

```
[Product Dropdown — "Editing settings for: Acme Corp ▾"]

PRODUCT  (scoped to selected product)
  Overview       ← name, icon, color, brand voice, tone, audience, social handles
  Workstreams    ← full CRUD, mission editor, schedule selector
  Objectives     ← full CRUD, progress editing, autonomous toggle
  Autonomy       ← master tier + per-action approval thresholds

INTEGRATIONS  (scoped to selected product)
  Connections    ← OAuth connections: Gmail, Calendar, Twitter, LinkedIn, Facebook, Instagram
  Social         ← stored social credentials (Twitter, LinkedIn, Meta)

GLOBAL  (affects all products)
  Agent Model    ← Opus/Sonnet/Haiku selection for main + sub-agent
  Google OAuth   ← global client ID/secret for Gmail/Calendar
  Remote Access  ← Telegram bot setup
  MCP Servers    ← global + per-product server management
```

### Scope labeling

Every section group is labeled with a badge: `this product` (blue) or `all products` (purple). Users always know what they're changing.

### Product switcher in settings

The product dropdown at the top of the settings nav lets users switch which product's settings they're editing. Switching products reloads all product-scoped sections; Global sections stay unchanged.

Opening settings automatically lands on the currently active product in the workspace.

**Workstreams and Objectives are managed exclusively here.** They no longer appear as panels in the main workspace.

---

## 5. Product Dropdown

Shared component used in both the header and the settings page nav. Consistent behavior everywhere.

### Contents

```
YOUR PRODUCTS
  ● Acme Corp       ✓  (currently active)
  ● Side Project
  ● Client: TechCo
  ● Personal Brand
  ─────────────────
  + New Product
```

- Color dot = product color for quick visual identification
- Clicking a product switches the full workspace (header, sessions, feed, settings)
- "New Product" always last — obvious for new users, never hidden

### Single-product users

Dropdown opens with one product listed + "New Product". Simple, no confusion.

---

## 6. New Product Creation Wizard

Replaces `LaunchFormModal`. A 4-step wizard that uses the user's stated intent to auto-generate workstreams and objectives.

### Step 1 — Your Vision

Free-text question:
> "What do you want Adjutant to do for this product?"

Large textarea with placeholder example. "See examples →" helper link for users who are unsure. Button label: **"Build My Plan →"**

Adjutant sends this intent to the AI to derive a suggested plan (workstreams, objectives, required integrations).

### Step 2 — Basics

- Product name (text input)
- Icon (emoji picker)
- Product color (color swatches)

Product name may be pre-suggested based on the intent text.

### Step 3 — Review Plan

Shows AI-derived suggestions split into two groups: **Workstreams** and **Objectives**.

**Each suggestion item:**
- Checkbox (checked by default) — uncheck to exclude
- Name
- Metadata (schedule for workstreams, target for objectives)
- `AI` badge (green) — distinguishes Adjutant suggestions from user additions

**User additions:**
- Each group has an **"+ Add workstream"** / **"+ Add objective"** button (top right of group)
- Clicking expands an inline add form directly in the list:
  - Workstream: plain-language description input + schedule input + Add button
  - Objective: description input + target input + Add button
- User-added items show a `YOU` badge (amber) and an × remove button
- AI suggestions are removed by unchecking (not deleted — still available if user rechecks)

### Step 4 — Connect Apps

Shows only the integrations required by the selected workstreams. If the user selected "Daily Social Posts," this step shows Twitter and LinkedIn OAuth. Skippable — connections can be added later from Settings → Connections.

### Completion

Product is created with all checked workstreams and objectives pre-configured. User lands in the new product's workspace, ready to chat.

---

## 7. Visual Theme

Update the app's color palette to match the mockup scheme. Tailwind config changes cascade to all components.

| Token | Value | Usage |
|---|---|---|
| `bg-base` | `#0f0f1a` | Page background |
| `bg-panel` | `#111120` | Sidebar, nav panels |
| `bg-surface` | `#1a1a2e` | Cards, inputs, header |
| `bg-elevated` | `#1e1e30` | Hover states, dropdowns |
| `border-subtle` | `#2a2a3a` | All borders |
| `accent` | `#6366f1` | Primary indigo — buttons, active states, links |
| `accent-dark` | `#4338ca` | Active nav items, user chat bubbles |
| `text-primary` | `#e2e8f0` | Main text |
| `text-secondary` | `#94a3b8` | Supporting text |
| `text-muted` | `#64748b` | Labels, placeholders |
| `text-faint` | `#374151` | Disabled, inactive |
| `green` | `#4ade80` | Running/healthy status |
| `amber` | `#f59e0b` | Warning, review pending |
| `red` | `#ef4444` | High risk, errors |
| `blue` | `#60a5fa` | Agent active, info |
| `purple` | `#a78bfa` | Global scope badge |

---

## 8. Component Changes Summary

| Component | Action | Notes |
|---|---|---|
| `ProductRail` | **Delete** | Replaced by header product dropdown |
| `WorkstreamsPanel` | **Delete** | Moved to Settings → Workstreams |
| `ReviewQueue` | **Delete** | Moved to status strip popover |
| `ObjectivesPanel` | **Delete** | Moved to status strip popover |
| `SettingsSidebar` | **Delete** | Replaced by Settings page |
| `LaunchFormModal` | **Delete** | Replaced by 4-step wizard |
| `App.tsx` | **Major refactor** | Remove panel state, add status strip state, add settings page routing |
| `SessionsPanel` | **Simplify** | Remove product-switching logic (now in dropdown) |
| `ActivityFeed` | **Widen** | Benefits from removed right panel space |
| `StatusStrip` | **New component** | Compact bar with 4 clickable pills + 4 popovers |
| `ProductDropdown` | **New component** | Shared — used in header and settings nav |
| `SettingsPage` | **New component** | Full-page view with left nav, replaces drawer |
| `ProductWizard` | **New component** | 4-step creation wizard with AI intent parsing |
| `LaunchWizardPanel` | **Delete** | Agent-driven setup checklist superseded by ProductWizard Step 3 (Review Plan) |
| `tailwind.config` | **Update** | New color tokens per Section 7 |

---

## Out of Scope

- Mobile/responsive layout — not addressed in this redesign
- Changes to agent tools, workstream execution, or backend APIs
- Changes to `NotesDrawer` or `DirectiveHistoryDrawer` internals
- Changes to `ActivityCard`, `ReviewCard`, or `MarkdownContent`
