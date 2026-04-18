# UI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the cluttered 7-panel layout with a clean 2-column workspace: compact status strip, full-page settings, and a 4-step intent-driven product creation wizard.

**Architecture:** New shared components (ProductDropdown, StatusStrip, SettingsPage, ProductWizard) are built first, then App.tsx is refactored to wire them in and remove the 5 deleted panels and 2 deleted modals. A new backend endpoint parses user intent to seed workstream/objective suggestions.

**Tech Stack:** React, TypeScript, Tailwind CSS v3, Vitest + React Testing Library, FastAPI (backend)

---

## File Map

### New files
- `ui/src/components/ProductDropdown.tsx` — shared product switcher used in header and settings nav
- `ui/src/components/StatusStrip.tsx` — compact status bar with 4 expandable popovers
- `ui/src/components/SettingsPage.tsx` — full-page settings with left nav + tab routing
- `ui/src/components/settings/OverviewSettings.tsx` — product name/icon/color/brand tab
- `ui/src/components/settings/WorkstreamsSettings.tsx` — workstream CRUD tab
- `ui/src/components/settings/ObjectivesSettings.tsx` — objectives CRUD tab
- `ui/src/components/settings/AutonomySettings.tsx` — autonomy tier/thresholds tab
- `ui/src/components/settings/ConnectionsSettings.tsx` — OAuth connections tab
- `ui/src/components/settings/SocialSettings.tsx` — social credentials tab
- `ui/src/components/settings/AgentModelSettings.tsx` — global agent model tab
- `ui/src/components/settings/GoogleOAuthSettings.tsx` — global Google OAuth tab
- `ui/src/components/settings/RemoteAccessSettings.tsx` — Telegram tab
- `ui/src/components/settings/MCPSettings.tsx` — MCP servers tab
- `ui/src/components/ProductWizard.tsx` — 4-step creation wizard
- `ui/src/__tests__/ProductDropdown.test.tsx`
- `ui/src/__tests__/StatusStrip.test.tsx`
- `ui/src/__tests__/ProductWizard.test.tsx`

### Modified files
- `ui/tailwind.config.js` — add adjutant color palette
- `ui/src/App.tsx` — major refactor: remove panel state, add StatusStrip + SettingsPage + ProductWizard
- `ui/src/api.ts` — add `getWizardPlan` endpoint
- `ui/src/components/SessionsPanel.tsx` — remove product-switching logic, apply new colors
- `ui/src/components/ActivityFeed.tsx` — apply new colors
- `ui/src/components/DirectiveBar.tsx` — apply new colors
- `ui/src/components/LiveAgents.tsx` — apply new colors
- `backend/api.py` — add `POST /api/wizard-plan` endpoint

### Deleted files
- `ui/src/components/ProductRail.tsx`
- `ui/src/components/WorkstreamsPanel.tsx`
- `ui/src/components/ReviewQueue.tsx`
- `ui/src/components/ObjectivesPanel.tsx`
- `ui/src/components/SettingsSidebar.tsx`
- `ui/src/components/LaunchFormModal.tsx`
- `ui/src/components/LaunchWizardPanel.tsx`
- `ui/src/__tests__/ProductRail.test.tsx`
- `ui/src/__tests__/WorkstreamsPanel.test.tsx`

---

## Task 1: Tailwind Color Palette

**Files:**
- Modify: `ui/tailwind.config.js`

- [ ] **Step 1: Add adjutant color tokens**

Replace the entire contents of `ui/tailwind.config.js`:

```js
/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        adj: {
          base:     '#0f0f1a',
          panel:    '#111120',
          surface:  '#1a1a2e',
          elevated: '#1e1e30',
          border:   '#2a2a3a',
          accent:   '#6366f1',
          'accent-dark': '#4338ca',
          'text-primary':   '#e2e8f0',
          'text-secondary': '#94a3b8',
          'text-muted':     '#64748b',
          'text-faint':     '#374151',
        },
      },
    },
  },
  plugins: [require('@tailwindcss/typography')],
}
```

- [ ] **Step 2: Verify dev server picks up the config**

```bash
cd ui && npm run dev
```

Open the browser. Confirm no compile errors. Color classes like `bg-adj-base` are now available.

- [ ] **Step 3: Commit**

```bash
git add ui/tailwind.config.js
git commit -m "feat: add adjutant color palette to tailwind config"
```

---

## Task 2: ProductDropdown Component

Shared dropdown used in both the header and the settings nav. Renders the product list, marks the active one, and exposes a "New Product" action.

**Files:**
- Create: `ui/src/components/ProductDropdown.tsx`
- Create: `ui/src/__tests__/ProductDropdown.test.tsx`

- [ ] **Step 1: Write failing tests**

Create `ui/src/__tests__/ProductDropdown.test.tsx`:

```tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import '@testing-library/jest-dom'
import ProductDropdown from '../components/ProductDropdown'
import { Product } from '../types'

const PRODUCTS: Product[] = [
  { id: 'p1', name: 'Acme Corp',  icon_label: '🏢', color: '#6366f1' },
  { id: 'p2', name: 'Side Project', icon_label: '🚀', color: '#ec4899' },
]

describe('ProductDropdown', () => {
  it('renders current product name as trigger', () => {
    render(
      <ProductDropdown
        products={PRODUCTS}
        activeProductId="p1"
        onSelect={vi.fn()}
        onNewProduct={vi.fn()}
      />
    )
    expect(screen.getByText('Acme Corp')).toBeInTheDocument()
  })

  it('opens dropdown on click and shows all products', () => {
    render(
      <ProductDropdown
        products={PRODUCTS}
        activeProductId="p1"
        onSelect={vi.fn()}
        onNewProduct={vi.fn()}
      />
    )
    fireEvent.click(screen.getByText('Acme Corp'))
    expect(screen.getByText('Side Project')).toBeInTheDocument()
    expect(screen.getByText('New Product')).toBeInTheDocument()
  })

  it('calls onSelect with product id when a product is clicked', () => {
    const onSelect = vi.fn()
    render(
      <ProductDropdown
        products={PRODUCTS}
        activeProductId="p1"
        onSelect={onSelect}
        onNewProduct={vi.fn()}
      />
    )
    fireEvent.click(screen.getByText('Acme Corp'))
    fireEvent.click(screen.getByText('Side Project'))
    expect(onSelect).toHaveBeenCalledWith('p2')
  })

  it('calls onNewProduct when New Product is clicked', () => {
    const onNew = vi.fn()
    render(
      <ProductDropdown
        products={PRODUCTS}
        activeProductId="p1"
        onSelect={vi.fn()}
        onNewProduct={onNew}
      />
    )
    fireEvent.click(screen.getByText('Acme Corp'))
    fireEvent.click(screen.getByText('New Product'))
    expect(onNew).toHaveBeenCalled()
  })

  it('shows checkmark on active product', () => {
    render(
      <ProductDropdown
        products={PRODUCTS}
        activeProductId="p1"
        onSelect={vi.fn()}
        onNewProduct={vi.fn()}
      />
    )
    fireEvent.click(screen.getByText('Acme Corp'))
    const p1Item = screen.getByTestId('product-item-p1')
    expect(p1Item).toHaveTextContent('✓')
  })

  it('closes on Escape key', () => {
    render(
      <ProductDropdown
        products={PRODUCTS}
        activeProductId="p1"
        onSelect={vi.fn()}
        onNewProduct={vi.fn()}
      />
    )
    fireEvent.click(screen.getByText('Acme Corp'))
    expect(screen.getByText('Side Project')).toBeInTheDocument()
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.queryByText('Side Project')).not.toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd ui && npm test -- --reporter=verbose ProductDropdown
```

Expected: FAIL — `ProductDropdown` not found.

- [ ] **Step 3: Implement ProductDropdown**

Create `ui/src/components/ProductDropdown.tsx`:

```tsx
import { useEffect, useRef, useState } from 'react'
import { Product } from '../types'

interface Props {
  products: Product[]
  activeProductId: string
  onSelect: (id: string) => void
  onNewProduct: () => void
}

export default function ProductDropdown({ products, activeProductId, onSelect, onNewProduct }: Props) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  const active = products.find(p => p.id === activeProductId)

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false) }
    const onClickOutside = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('keydown', onKey)
    document.addEventListener('mousedown', onClickOutside)
    return () => {
      document.removeEventListener('keydown', onKey)
      document.removeEventListener('mousedown', onClickOutside)
    }
  }, [open])

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen(o => !o)}
        className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-adj-panel border border-adj-border text-adj-text-primary text-sm font-medium hover:border-adj-accent transition-colors"
      >
        {active && (
          <span className="w-3 h-3 rounded-full flex-shrink-0" style={{ background: active.color }} />
        )}
        <span>{active?.name ?? 'Select product'}</span>
        <span className="text-adj-text-faint text-xs ml-1">▾</span>
      </button>

      {open && (
        <div className="absolute top-full left-0 mt-1 w-52 bg-adj-surface border border-adj-border rounded-lg shadow-xl z-50 overflow-hidden">
          <div className="px-3 py-2 text-[9px] font-bold uppercase tracking-widest text-adj-text-faint">
            Your Products
          </div>
          {products.map(p => (
            <button
              key={p.id}
              data-testid={`product-item-${p.id}`}
              onClick={() => { onSelect(p.id); setOpen(false) }}
              className="w-full flex items-center gap-3 px-3 py-2 text-sm text-left hover:bg-adj-elevated transition-colors"
            >
              <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: p.color }} />
              <span className={p.id === activeProductId ? 'text-adj-text-primary font-medium' : 'text-adj-text-secondary'}>
                {p.name}
              </span>
              {p.id === activeProductId && (
                <span className="ml-auto text-adj-accent text-xs">✓</span>
              )}
            </button>
          ))}
          <div className="border-t border-adj-border" />
          <button
            onClick={() => { onNewProduct(); setOpen(false) }}
            className="w-full flex items-center gap-3 px-3 py-2.5 text-sm text-adj-accent font-semibold hover:bg-adj-elevated transition-colors"
          >
            <span className="w-4 h-4 rounded border border-dashed border-adj-accent flex items-center justify-center text-base leading-none">+</span>
            New Product
          </button>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd ui && npm test -- --reporter=verbose ProductDropdown
```

Expected: All 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add ui/src/components/ProductDropdown.tsx ui/src/__tests__/ProductDropdown.test.tsx
git commit -m "feat: add ProductDropdown shared component"
```

---

## Task 3: StatusStrip Component

Compact bar with 4 clickable pills. Each pill opens a popover. Reviews popover has inline approve/skip. Replaces ReviewQueue and ObjectivesPanel entirely.

**Files:**
- Create: `ui/src/components/StatusStrip.tsx`
- Create: `ui/src/__tests__/StatusStrip.test.tsx`

- [ ] **Step 1: Write failing tests**

Create `ui/src/__tests__/StatusStrip.test.tsx`:

```tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import '@testing-library/jest-dom'
import StatusStrip from '../components/StatusStrip'
import { Workstream, ReviewItem, ActivityEvent, Objective } from '../types'

const WS: Workstream[] = [
  { id: 1, name: 'Social Posts', status: 'running', display_order: 0, schedule: 'daily' },
  { id: 2, name: 'Newsletter',   status: 'paused',  display_order: 1 },
]
const REVIEW: ReviewItem = {
  id: 10, title: 'Publish blog', description: 'Ready to go', risk_label: 'high',
  status: 'pending', created_at: '2026-01-01',
}
const EVENT: ActivityEvent = {
  id: 5, agent_type: 'research', headline: 'Analyzing data', rationale: '',
  status: 'running', created_at: '2026-01-01',
}
const OBJ: Objective = {
  id: 1, text: 'Grow followers', progress_current: 200, progress_target: 1000, display_order: 0,
}

const DEFAULT_PROPS = {
  workstreams: WS,
  reviewItems: [REVIEW],
  events: [EVENT],
  objectives: [OBJ],
  onResolveReview: vi.fn(),
  onCancelAgent: vi.fn(),
  onOpenSettings: vi.fn(),
}

describe('StatusStrip', () => {
  it('shows counts for each category', () => {
    render(<StatusStrip {...DEFAULT_PROPS} />)
    expect(screen.getByText('2')).toBeInTheDocument() // workstreams
    expect(screen.getByText('1 review')).toBeInTheDocument()
    expect(screen.getByText('1 active')).toBeInTheDocument()
  })

  it('opens workstreams popover on pill click', () => {
    render(<StatusStrip {...DEFAULT_PROPS} />)
    fireEvent.click(screen.getByTestId('pill-workstreams'))
    expect(screen.getByText('Social Posts')).toBeInTheDocument()
    expect(screen.getByText('Newsletter')).toBeInTheDocument()
  })

  it('opens reviews popover showing review title', () => {
    render(<StatusStrip {...DEFAULT_PROPS} />)
    fireEvent.click(screen.getByTestId('pill-reviews'))
    expect(screen.getByText('Publish blog')).toBeInTheDocument()
    expect(screen.getByText('Approve')).toBeInTheDocument()
    expect(screen.getByText('Skip')).toBeInTheDocument()
  })

  it('calls onResolveReview(id, approved) when Approve clicked', () => {
    const onResolve = vi.fn()
    render(<StatusStrip {...DEFAULT_PROPS} onResolveReview={onResolve} />)
    fireEvent.click(screen.getByTestId('pill-reviews'))
    fireEvent.click(screen.getByText('Approve'))
    expect(onResolve).toHaveBeenCalledWith(10, 'approved')
  })

  it('calls onResolveReview(id, skipped) when Skip clicked', () => {
    const onResolve = vi.fn()
    render(<StatusStrip {...DEFAULT_PROPS} onResolveReview={onResolve} />)
    fireEvent.click(screen.getByTestId('pill-reviews'))
    fireEvent.click(screen.getByText('Skip'))
    expect(onResolve).toHaveBeenCalledWith(10, 'skipped')
  })

  it('closes open popover when same pill clicked again', () => {
    render(<StatusStrip {...DEFAULT_PROPS} />)
    fireEvent.click(screen.getByTestId('pill-workstreams'))
    expect(screen.getByText('Social Posts')).toBeInTheDocument()
    fireEvent.click(screen.getByTestId('pill-workstreams'))
    expect(screen.queryByText('Social Posts')).not.toBeInTheDocument()
  })

  it('switches to different popover when another pill clicked', () => {
    render(<StatusStrip {...DEFAULT_PROPS} />)
    fireEvent.click(screen.getByTestId('pill-workstreams'))
    expect(screen.getByText('Social Posts')).toBeInTheDocument()
    fireEvent.click(screen.getByTestId('pill-reviews'))
    expect(screen.queryByText('Social Posts')).not.toBeInTheDocument()
    expect(screen.getByText('Publish blog')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd ui && npm test -- --reporter=verbose StatusStrip
```

Expected: FAIL — `StatusStrip` not found.

- [ ] **Step 3: Implement StatusStrip**

Create `ui/src/components/StatusStrip.tsx`:

```tsx
import { useEffect, useRef, useState } from 'react'
import { ActivityEvent, Objective, ReviewItem, Workstream } from '../types'

type PopoverKey = 'workstreams' | 'agents' | 'reviews' | 'objectives' | null

interface Props {
  workstreams: Workstream[]
  reviewItems: ReviewItem[]
  events: ActivityEvent[]
  objectives: Objective[]
  onResolveReview: (id: number, action: 'approved' | 'skipped') => void
  onCancelAgent: (directiveId: string) => void
  onOpenSettings: (tab: string) => void
}

export default function StatusStrip({
  workstreams, reviewItems, events, objectives,
  onResolveReview, onCancelAgent, onOpenSettings,
}: Props) {
  const [open, setOpen] = useState<PopoverKey>(null)
  const ref = useRef<HTMLDivElement>(null)

  const pendingReviews = reviewItems.filter(r => r.status === 'pending')
  const runningAgents  = events.filter(e => e.status === 'running')
  const runningWs      = workstreams.filter(w => w.status === 'running').length
  const warnWs         = workstreams.filter(w => w.status === 'warn').length

  useEffect(() => {
    if (!open) return
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(null)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  const toggle = (key: PopoverKey) => setOpen(prev => prev === key ? null : key)

  return (
    <div ref={ref} className="relative flex items-center gap-1 px-4 h-8 bg-adj-panel border-b border-adj-border flex-shrink-0 text-xs">

      {/* Workstreams pill */}
      <button
        data-testid="pill-workstreams"
        onClick={() => toggle('workstreams')}
        className={`flex items-center gap-1.5 px-2.5 py-0.5 rounded-full border transition-colors ${open === 'workstreams' ? 'border-adj-accent bg-adj-elevated' : 'border-transparent hover:bg-adj-elevated'}`}
      >
        <span className={`w-1.5 h-1.5 rounded-full ${warnWs > 0 ? 'bg-amber-400' : 'bg-green-400'}`} />
        <span className="font-semibold text-adj-text-primary">{workstreams.length}</span>
        <span className="text-adj-text-muted">workstreams</span>
      </button>

      <span className="w-px h-3 bg-adj-border" />

      {/* Agents pill */}
      <button
        data-testid="pill-agents"
        onClick={() => toggle('agents')}
        className={`flex items-center gap-1.5 px-2.5 py-0.5 rounded-full border transition-colors ${open === 'agents' ? 'border-adj-accent bg-adj-elevated' : 'border-transparent hover:bg-adj-elevated'}`}
      >
        <span className={`w-1.5 h-1.5 rounded-full ${runningAgents.length > 0 ? 'bg-blue-400 animate-pulse' : 'bg-adj-text-faint'}`} />
        <span className="font-semibold text-adj-text-primary">{runningAgents.length} active</span>
      </button>

      <span className="w-px h-3 bg-adj-border" />

      {/* Reviews pill */}
      <button
        data-testid="pill-reviews"
        onClick={() => toggle('reviews')}
        className={`flex items-center gap-1.5 px-2.5 py-0.5 rounded-full border transition-colors ${
          pendingReviews.length > 0
            ? open === 'reviews' ? 'border-amber-500 bg-adj-elevated' : 'border-transparent hover:bg-adj-elevated'
            : 'border-transparent hover:bg-adj-elevated'
        }`}
      >
        <span className={`w-1.5 h-1.5 rounded-full ${pendingReviews.length > 0 ? 'bg-amber-400' : 'bg-adj-text-faint'}`} />
        <span className={`font-semibold ${pendingReviews.length > 0 ? 'text-amber-400' : 'text-adj-text-primary'}`}>
          {pendingReviews.length} review{pendingReviews.length !== 1 ? 's' : ''}
        </span>
      </button>

      <span className="w-px h-3 bg-adj-border" />

      {/* Objectives pill */}
      <button
        data-testid="pill-objectives"
        onClick={() => toggle('objectives')}
        className={`flex items-center gap-1.5 px-2.5 py-0.5 rounded-full border transition-colors ${open === 'objectives' ? 'border-adj-accent bg-adj-elevated' : 'border-transparent hover:bg-adj-elevated'}`}
      >
        <span className="text-adj-text-muted">◎</span>
        <span className="font-semibold text-adj-text-primary">{objectives.length}</span>
        <span className="text-adj-text-muted">objectives</span>
      </button>

      {/* Popovers */}
      {open === 'workstreams' && (
        <Popover title="Workstreams" onManage={() => { onOpenSettings('workstreams'); setOpen(null) }}>
          {workstreams.map(ws => (
            <div key={ws.id} className="flex items-center gap-2.5 px-3 py-2 bg-adj-base rounded-md">
              <span className={`w-2 h-2 rounded-full flex-shrink-0 ${ws.status === 'running' ? 'bg-green-400' : ws.status === 'warn' ? 'bg-amber-400' : 'bg-adj-text-faint'}`} />
              <span className="text-adj-text-primary text-xs flex-1">{ws.name}</span>
              {ws.schedule && <span className="text-adj-text-muted text-[10px]">{ws.schedule}</span>}
            </div>
          ))}
        </Popover>
      )}

      {open === 'agents' && (
        <Popover title="Active Agents">
          {runningAgents.length === 0 && (
            <p className="text-adj-text-muted text-xs px-3 py-2">No agents running</p>
          )}
          {runningAgents.map(ev => (
            <div key={ev.id} className="flex items-center gap-2.5 px-3 py-2 bg-adj-base rounded-md">
              <span className="w-2 h-2 rounded-full bg-blue-400 animate-pulse flex-shrink-0" />
              <div className="flex-1 min-w-0">
                <div className="text-[10px] text-adj-text-muted capitalize">{ev.agent_type} agent</div>
                <div className="text-xs text-adj-text-primary truncate">{ev.headline}</div>
              </div>
            </div>
          ))}
        </Popover>
      )}

      {open === 'reviews' && (
        <Popover title="Pending Reviews">
          {pendingReviews.length === 0 && (
            <p className="text-adj-text-muted text-xs px-3 py-2">No pending reviews</p>
          )}
          {pendingReviews.map(r => (
            <div key={r.id} className={`px-3 py-2 bg-adj-base rounded-md border-l-2 ${r.risk_label === 'high' ? 'border-red-500' : r.risk_label === 'medium' ? 'border-amber-500' : 'border-adj-border'}`}>
              <div className={`text-[9px] font-bold uppercase mb-1 ${r.risk_label === 'high' ? 'text-red-400' : 'text-amber-400'}`}>{r.risk_label} risk</div>
              <div className="text-xs text-adj-text-primary mb-2">{r.title}</div>
              <div className="flex gap-2">
                <button onClick={() => onResolveReview(r.id, 'approved')} className="text-[10px] px-2 py-0.5 rounded bg-green-900 text-green-400 font-semibold hover:bg-green-800 transition-colors">Approve</button>
                <button onClick={() => onResolveReview(r.id, 'skipped')}  className="text-[10px] px-2 py-0.5 rounded bg-adj-elevated text-adj-text-muted font-semibold hover:bg-adj-border transition-colors">Skip</button>
              </div>
            </div>
          ))}
        </Popover>
      )}

      {open === 'objectives' && (
        <Popover title="Objectives" onManage={() => { onOpenSettings('objectives'); setOpen(null) }}>
          {objectives.map(obj => (
            <div key={obj.id} className="px-3 py-2 bg-adj-base rounded-md">
              <div className="text-xs text-adj-text-primary mb-1">{obj.text}</div>
              {obj.progress_target != null && (
                <div className="text-[10px] text-adj-text-muted">{obj.progress_current} / {obj.progress_target}</div>
              )}
            </div>
          ))}
        </Popover>
      )}
    </div>
  )
}

function Popover({ title, children, onManage }: { title: string; children: React.ReactNode; onManage?: () => void }) {
  return (
    <div className="absolute top-full left-4 mt-1 w-72 bg-adj-surface border border-adj-border rounded-xl shadow-2xl z-50 overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-adj-border">
        <span className="text-xs font-semibold text-adj-text-primary">{title}</span>
        {onManage && (
          <button onClick={onManage} className="text-[10px] text-adj-accent hover:underline">Manage →</button>
        )}
      </div>
      <div className="p-2 flex flex-col gap-1.5 max-h-72 overflow-y-auto">{children}</div>
    </div>
  )
}
```

- [ ] **Step 4: Run tests**

```bash
cd ui && npm test -- --reporter=verbose StatusStrip
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add ui/src/components/StatusStrip.tsx ui/src/__tests__/StatusStrip.test.tsx
git commit -m "feat: add StatusStrip with workstream/review/agent/objective popovers"
```

---

## Task 4: SettingsPage Shell + Navigation

Full-page settings view with left nav. Tabs route to section components built in Tasks 5–6. This task builds the shell only — tab content is stubbed.

**Files:**
- Create: `ui/src/components/SettingsPage.tsx`
- Create: `ui/src/components/settings/OverviewSettings.tsx` (stub)
- Create: `ui/src/components/settings/WorkstreamsSettings.tsx` (stub)
- Create: `ui/src/components/settings/ObjectivesSettings.tsx` (stub)
- Create: `ui/src/components/settings/AutonomySettings.tsx` (stub)
- Create: `ui/src/components/settings/ConnectionsSettings.tsx` (stub)
- Create: `ui/src/components/settings/SocialSettings.tsx` (stub)
- Create: `ui/src/components/settings/AgentModelSettings.tsx` (stub)
- Create: `ui/src/components/settings/GoogleOAuthSettings.tsx` (stub)
- Create: `ui/src/components/settings/RemoteAccessSettings.tsx` (stub)
- Create: `ui/src/components/settings/MCPSettings.tsx` (stub)

- [ ] **Step 1: Create stub tab components**

Each stub is a simple placeholder. Create all of these identical files, changing only the displayed name:

`ui/src/components/settings/OverviewSettings.tsx`:
```tsx
export default function OverviewSettings() {
  return <div className="text-adj-text-muted text-sm p-6">Overview settings — coming in next task</div>
}
```

Repeat for: `WorkstreamsSettings.tsx`, `ObjectivesSettings.tsx`, `AutonomySettings.tsx`, `ConnectionsSettings.tsx`, `SocialSettings.tsx`, `AgentModelSettings.tsx`, `GoogleOAuthSettings.tsx`, `RemoteAccessSettings.tsx`, `MCPSettings.tsx` — same stub pattern, different label text.

- [ ] **Step 2: Create SettingsPage shell**

Create `ui/src/components/SettingsPage.tsx`:

```tsx
import { useState } from 'react'
import { Product, ProductState, Workstream, Objective } from '../types'
import ProductDropdown from './ProductDropdown'
import OverviewSettings from './settings/OverviewSettings'
import WorkstreamsSettings from './settings/WorkstreamsSettings'
import ObjectivesSettings from './settings/ObjectivesSettings'
import AutonomySettings from './settings/AutonomySettings'
import ConnectionsSettings from './settings/ConnectionsSettings'
import SocialSettings from './settings/SocialSettings'
import AgentModelSettings from './settings/AgentModelSettings'
import GoogleOAuthSettings from './settings/GoogleOAuthSettings'
import RemoteAccessSettings from './settings/RemoteAccessSettings'
import MCPSettings from './settings/MCPSettings'

type Tab =
  | 'overview' | 'workstreams' | 'objectives' | 'autonomy'
  | 'connections' | 'social'
  | 'agent-model' | 'google-oauth' | 'remote-access' | 'mcp'

interface Props {
  products: Product[]
  activeProductId: string
  productStates: Record<string, ProductState>
  password: string
  initialTab?: Tab
  onClose: () => void
  onSwitchProduct: (id: string) => void
  onNewProduct: () => void
  onRefreshData: (productId: string) => void
  onWorkstreamUpdated: (wsId: number, patch: Partial<Workstream>) => void
  onObjectiveUpdated: (objId: number, patch: Partial<Objective>) => void
}

const PRODUCT_TABS: { key: Tab; label: string; icon: string }[] = [
  { key: 'overview',     label: 'Overview',     icon: '◻' },
  { key: 'workstreams',  label: 'Workstreams',  icon: '⟳' },
  { key: 'objectives',   label: 'Objectives',   icon: '◎' },
  { key: 'autonomy',     label: 'Autonomy',     icon: '🛡' },
]
const INTEGRATION_TABS: { key: Tab; label: string; icon: string }[] = [
  { key: 'connections',  label: 'Connections',  icon: '🔗' },
  { key: 'social',       label: 'Social',       icon: '📱' },
]
const GLOBAL_TABS: { key: Tab; label: string; icon: string }[] = [
  { key: 'agent-model',    label: 'Agent Model',    icon: '🤖' },
  { key: 'google-oauth',   label: 'Google OAuth',   icon: '🔑' },
  { key: 'remote-access',  label: 'Remote Access',  icon: '📡' },
  { key: 'mcp',            label: 'MCP Servers',    icon: '⚡' },
]

export default function SettingsPage({
  products, activeProductId, productStates, password,
  initialTab = 'overview',
  onClose, onSwitchProduct, onNewProduct, onRefreshData,
  onWorkstreamUpdated, onObjectiveUpdated,
}: Props) {
  const [tab, setTab] = useState<Tab>(initialTab)
  const [settingsProductId, setSettingsProductId] = useState(activeProductId)

  const activeProduct = products.find(p => p.id === settingsProductId)
  const activeState = productStates[settingsProductId]

  const handleSwitchProduct = (id: string) => {
    setSettingsProductId(id)
    onSwitchProduct(id)
  }

  const navItem = (key: Tab, label: string, icon: string) => (
    <button
      key={key}
      onClick={() => setTab(key)}
      className={`w-full flex items-center gap-2 px-3 py-1.5 text-xs rounded-sm text-left transition-colors ${
        tab === key
          ? 'text-adj-accent bg-adj-elevated border-r-2 border-adj-accent'
          : 'text-adj-text-muted hover:text-adj-text-secondary hover:bg-adj-elevated'
      }`}
    >
      <span className="w-4 text-center">{icon}</span>
      {label}
    </button>
  )

  const renderContent = () => {
    switch (tab) {
      case 'overview':    return <OverviewSettings product={activeProduct} password={password} onRefresh={() => onRefreshData(settingsProductId)} />
      case 'workstreams': return <WorkstreamsSettings productId={settingsProductId} workstreams={activeState?.workstreams ?? []} password={password} onWorkstreamUpdated={onWorkstreamUpdated} />
      case 'objectives':  return <ObjectivesSettings productId={settingsProductId} objectives={activeState?.objectives ?? []} password={password} onObjectiveUpdated={onObjectiveUpdated} />
      case 'autonomy':    return <AutonomySettings productId={settingsProductId} password={password} />
      case 'connections': return <ConnectionsSettings productId={settingsProductId} password={password} />
      case 'social':      return <SocialSettings password={password} />
      case 'agent-model': return <AgentModelSettings password={password} />
      case 'google-oauth':   return <GoogleOAuthSettings password={password} />
      case 'remote-access':  return <RemoteAccessSettings password={password} />
      case 'mcp':            return <MCPSettings productId={settingsProductId} password={password} />
    }
  }

  return (
    <div className="flex flex-col h-full bg-adj-base text-adj-text-primary overflow-hidden">
      {/* Header */}
      <header className="flex items-center gap-3 px-5 h-12 border-b border-adj-border flex-shrink-0 bg-adj-surface">
        <span className="text-sm font-bold text-adj-text-primary">Settings</span>
        <span className="w-px h-4 bg-adj-border" />
        <span className="text-xs text-adj-text-muted">Changes save automatically</span>
        <div className="ml-auto flex items-center gap-2">
          <button onClick={onClose} className="text-xs text-adj-text-muted hover:text-adj-text-secondary px-3 py-1.5 rounded hover:bg-adj-elevated transition-colors">
            ← Back to workspace
          </button>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        {/* Left nav */}
        <nav className="w-48 bg-adj-panel border-r border-adj-border flex flex-col flex-shrink-0 py-2">
          {/* Product switcher */}
          <div className="px-3 py-2 border-b border-adj-border mb-2">
            <div className="text-[9px] font-bold uppercase tracking-widest text-adj-text-faint mb-2">Editing settings for</div>
            <ProductDropdown
              products={products}
              activeProductId={settingsProductId}
              onSelect={handleSwitchProduct}
              onNewProduct={onNewProduct}
            />
          </div>

          {/* Product tabs */}
          <div className="px-2 mb-1">
            <div className="flex items-center gap-1.5 px-1 py-1 text-[9px] font-bold uppercase tracking-widest text-adj-text-faint">
              Product
              <span className="px-1 py-0.5 rounded text-[7px] bg-blue-900 text-blue-300 font-bold">this product</span>
            </div>
            {PRODUCT_TABS.map(t => navItem(t.key, t.label, t.icon))}
          </div>

          {/* Integration tabs */}
          <div className="px-2 mb-1 border-t border-adj-border pt-2">
            <div className="flex items-center gap-1.5 px-1 py-1 text-[9px] font-bold uppercase tracking-widest text-adj-text-faint">
              Integrations
              <span className="px-1 py-0.5 rounded text-[7px] bg-blue-900 text-blue-300 font-bold">this product</span>
            </div>
            {INTEGRATION_TABS.map(t => navItem(t.key, t.label, t.icon))}
          </div>

          {/* Global tabs */}
          <div className="px-2 mt-auto border-t border-adj-border pt-2">
            <div className="flex items-center gap-1.5 px-1 py-1 text-[9px] font-bold uppercase tracking-widest text-adj-text-faint">
              Global
              <span className="px-1 py-0.5 rounded text-[7px] bg-purple-900 text-purple-300 font-bold">all products</span>
            </div>
            {GLOBAL_TABS.map(t => navItem(t.key, t.label, t.icon))}
          </div>
        </nav>

        {/* Content area */}
        <main className="flex-1 overflow-y-auto p-6">
          {renderContent()}
        </main>
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Verify it compiles**

```bash
cd ui && npm run build 2>&1 | head -30
```

Expected: No TypeScript errors.

- [ ] **Step 4: Commit**

```bash
git add ui/src/components/SettingsPage.tsx ui/src/components/settings/
git commit -m "feat: add SettingsPage shell with left nav and stub tabs"
```

---

## Task 5: Settings Tab — Product Sections

Replace the stubs with real implementations for Overview, Workstreams, Objectives, and Autonomy tabs. Logic is extracted from `SettingsSidebar.tsx`.

**Files:**
- Modify: `ui/src/components/settings/OverviewSettings.tsx`
- Modify: `ui/src/components/settings/WorkstreamsSettings.tsx`
- Modify: `ui/src/components/settings/ObjectivesSettings.tsx`
- Modify: `ui/src/components/settings/AutonomySettings.tsx`
- Reference: `ui/src/components/SettingsSidebar.tsx` (read for existing logic)

- [ ] **Step 1: Read SettingsSidebar to understand existing logic**

Read `ui/src/components/SettingsSidebar.tsx` and identify:
- The brand config fields (voice, tone, writing_style, target_audience, social_handles, hashtags, brand_notes) 
- How `api.getProductConfig` / `api.updateProductConfig` are called
- Workstream CRUD logic (create, update, delete via `api.*Workstream`)
- Objective CRUD logic  
- Autonomy settings via `api.getAutonomySettings` / `api.updateAutonomySettings`

- [ ] **Step 2: Implement OverviewSettings**

Replace the stub in `ui/src/components/settings/OverviewSettings.tsx`:

```tsx
import { useEffect, useState } from 'react'
import { Product, ProductConfig } from '../../types'
import { api } from '../../api'

interface Props {
  product: Product | undefined
  password: string
  onRefresh: () => void
}

const COLORS = ['#6366f1','#ec4899','#f59e0b','#10b981','#3b82f6','#ef4444','#8b5cf6','#06b6d4']

export default function OverviewSettings({ product, password, onRefresh }: Props) {
  const [config, setConfig] = useState<Partial<ProductConfig>>({})
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    if (!product) return
    api.getProductConfig(password, product.id).then(setConfig).catch(() => {})
  }, [product?.id, password])

  if (!product) return <p className="text-adj-text-muted text-sm">No product selected.</p>

  const save = async () => {
    setSaving(true)
    try {
      await api.updateProductConfig(password, product.id, config)
      onRefresh()
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } finally {
      setSaving(false)
    }
  }

  const field = (label: string, key: keyof ProductConfig, placeholder = '') => (
    <div className="mb-4">
      <label className="block text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-1.5">{label}</label>
      <input
        className="w-full bg-adj-panel border border-adj-border rounded-md px-3 py-2 text-sm text-adj-text-primary placeholder:text-adj-text-faint focus:outline-none focus:border-adj-accent transition-colors"
        value={(config[key] as string) ?? ''}
        onChange={e => setConfig(c => ({ ...c, [key]: e.target.value }))}
        placeholder={placeholder}
      />
    </div>
  )

  return (
    <div className="max-w-lg">
      <h2 className="text-base font-bold text-adj-text-primary mb-1">Product Overview</h2>
      <p className="text-xs text-adj-text-muted mb-6">Identity and brand voice for {product.name}</p>

      <div className="flex gap-3 mb-4">
        <div className="flex-1">
          <label className="block text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-1.5">Product Name</label>
          <input
            className="w-full bg-adj-panel border border-adj-border rounded-md px-3 py-2 text-sm text-adj-text-primary focus:outline-none focus:border-adj-accent transition-colors"
            value={config.name ?? product.name}
            onChange={e => setConfig(c => ({ ...c, name: e.target.value }))}
          />
        </div>
        <div className="w-20">
          <label className="block text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-1.5">Icon</label>
          <input
            className="w-full bg-adj-panel border border-adj-border rounded-md px-3 py-2 text-sm text-center text-adj-text-primary focus:outline-none focus:border-adj-accent"
            value={config.icon_label ?? product.icon_label}
            onChange={e => setConfig(c => ({ ...c, icon_label: e.target.value }))}
          />
        </div>
      </div>

      <div className="mb-4">
        <label className="block text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-1.5">Color</label>
        <div className="flex gap-2">
          {COLORS.map(c => (
            <button
              key={c}
              onClick={() => setConfig(prev => ({ ...prev, color: c }))}
              className="w-6 h-6 rounded-full transition-transform hover:scale-110"
              style={{
                background: c,
                outline: (config.color ?? product.color) === c ? '2px solid white' : 'none',
                outlineOffset: '2px',
              }}
            />
          ))}
        </div>
      </div>

      {field('Brand Voice', 'brand_voice', 'e.g. Professional but approachable')}
      {field('Tone', 'tone', 'e.g. Confident, friendly')}
      {field('Writing Style', 'writing_style', 'e.g. Conversational, data-driven')}
      {field('Target Audience', 'target_audience', 'e.g. Small business owners')}
      {field('Social Handles', 'social_handles', '@handle')}
      {field('Hashtags', 'hashtags', '#brand #product')}

      <div className="mb-4">
        <label className="block text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-1.5">Brand Notes</label>
        <textarea
          className="w-full bg-adj-panel border border-adj-border rounded-md px-3 py-2 text-sm text-adj-text-primary placeholder:text-adj-text-faint focus:outline-none focus:border-adj-accent transition-colors h-24 resize-none"
          value={config.brand_notes ?? ''}
          onChange={e => setConfig(c => ({ ...c, brand_notes: e.target.value }))}
          placeholder="Any additional brand context..."
        />
      </div>

      <button
        onClick={save}
        disabled={saving}
        className="px-5 py-2 bg-adj-accent text-white rounded-md text-sm font-semibold hover:bg-adj-accent-dark transition-colors disabled:opacity-50"
      >
        {saved ? '✓ Saved' : saving ? 'Saving…' : 'Save Changes'}
      </button>
    </div>
  )
}
```

- [ ] **Step 3: Implement WorkstreamsSettings**

Replace the stub in `ui/src/components/settings/WorkstreamsSettings.tsx`:

```tsx
import { useState } from 'react'
import { Workstream } from '../../types'
import { api } from '../../api'

interface Props {
  productId: string
  workstreams: Workstream[]
  password: string
  onWorkstreamUpdated: (wsId: number, patch: Partial<Workstream>) => void
}

const SCHEDULES = ['none','daily','weekly','monthly'] as const

export default function WorkstreamsSettings({ productId, workstreams, password, onWorkstreamUpdated }: Props) {
  const [editId, setEditId] = useState<number | null>(null)
  const [form, setForm] = useState<{ name: string; mission: string; schedule: string }>({ name: '', mission: '', schedule: 'none' })
  const [adding, setAdding] = useState(false)
  const [newName, setNewName] = useState('')

  const openEdit = (ws: Workstream) => {
    setEditId(ws.id)
    setForm({ name: ws.name, mission: ws.mission ?? '', schedule: ws.schedule ?? 'none' })
  }

  const save = async () => {
    if (!editId) return
    await api.updateWorkstream(password, editId, { name: form.name, mission: form.mission, schedule: form.schedule === 'none' ? '' : form.schedule })
    onWorkstreamUpdated(editId, { name: form.name, mission: form.mission, schedule: form.schedule === 'none' ? '' : form.schedule })
    setEditId(null)
  }

  const del = async (ws: Workstream) => {
    if (!confirm(`Delete "${ws.name}"?`)) return
    await api.deleteWorkstream(password, ws.id)
    onWorkstreamUpdated(ws.id, { status: 'paused' }) // parent will re-fetch
  }

  const create = async () => {
    if (!newName.trim()) return
    await api.createWorkstream(password, productId, newName.trim())
    setNewName('')
    setAdding(false)
  }

  return (
    <div className="max-w-lg">
      <h2 className="text-base font-bold text-adj-text-primary mb-1">Workstreams</h2>
      <p className="text-xs text-adj-text-muted mb-6">Automated recurring tasks for this product</p>

      <div className="flex flex-col gap-2 mb-4">
        {workstreams.map(ws => (
          <div key={ws.id} className="bg-adj-panel border border-adj-border rounded-lg overflow-hidden">
            <div className="flex items-center gap-3 px-4 py-3">
              <span className={`w-2 h-2 rounded-full flex-shrink-0 ${ws.status === 'running' ? 'bg-green-400' : ws.status === 'warn' ? 'bg-amber-400' : 'bg-adj-text-faint'}`} />
              <span className="text-sm text-adj-text-primary flex-1">{ws.name}</span>
              {ws.schedule && <span className="text-xs text-adj-text-muted">{ws.schedule}</span>}
              <button onClick={() => openEdit(ws)} className="text-xs text-adj-accent hover:underline">Edit</button>
              <button onClick={() => del(ws)} className="text-xs text-red-400 hover:underline ml-2">Delete</button>
            </div>
            {editId === ws.id && (
              <div className="px-4 pb-4 border-t border-adj-border bg-adj-surface">
                <div className="mt-3 mb-2">
                  <label className="block text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-1">Name</label>
                  <input className="w-full bg-adj-panel border border-adj-border rounded px-3 py-1.5 text-sm text-adj-text-primary focus:outline-none focus:border-adj-accent" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} />
                </div>
                <div className="mb-2">
                  <label className="block text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-1">Mission</label>
                  <textarea className="w-full bg-adj-panel border border-adj-border rounded px-3 py-1.5 text-sm text-adj-text-primary focus:outline-none focus:border-adj-accent h-16 resize-none" value={form.mission} onChange={e => setForm(f => ({ ...f, mission: e.target.value }))} placeholder="What should this workstream do?" />
                </div>
                <div className="mb-3">
                  <label className="block text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-1">Schedule</label>
                  <select className="bg-adj-panel border border-adj-border rounded px-3 py-1.5 text-sm text-adj-text-primary focus:outline-none focus:border-adj-accent" value={form.schedule} onChange={e => setForm(f => ({ ...f, schedule: e.target.value }))}>
                    {SCHEDULES.map(s => <option key={s} value={s}>{s === 'none' ? 'No schedule' : s}</option>)}
                  </select>
                </div>
                <div className="flex gap-2">
                  <button onClick={save} className="px-4 py-1.5 bg-adj-accent text-white rounded text-xs font-semibold hover:bg-adj-accent-dark transition-colors">Save</button>
                  <button onClick={() => setEditId(null)} className="px-4 py-1.5 text-adj-text-muted hover:text-adj-text-secondary text-xs transition-colors">Cancel</button>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>

      {adding ? (
        <div className="flex gap-2">
          <input autoFocus className="flex-1 bg-adj-panel border border-adj-border rounded-md px-3 py-2 text-sm text-adj-text-primary focus:outline-none focus:border-adj-accent" placeholder="Workstream name" value={newName} onChange={e => setNewName(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') create(); if (e.key === 'Escape') setAdding(false) }} />
          <button onClick={create} className="px-4 py-2 bg-adj-accent text-white rounded-md text-sm font-semibold">Add</button>
          <button onClick={() => setAdding(false)} className="px-3 py-2 text-adj-text-muted hover:text-adj-text-secondary text-sm">✕</button>
        </div>
      ) : (
        <button onClick={() => setAdding(true)} className="w-full border border-dashed border-adj-text-faint rounded-lg py-2.5 text-sm text-adj-text-faint hover:border-adj-accent hover:text-adj-accent transition-colors">
          + Add Workstream
        </button>
      )}
    </div>
  )
}
```

- [ ] **Step 4: Implement ObjectivesSettings**

Replace the stub in `ui/src/components/settings/ObjectivesSettings.tsx`:

```tsx
import { useState } from 'react'
import { Objective } from '../../types'
import { api } from '../../api'

interface Props {
  productId: string
  objectives: Objective[]
  password: string
  onObjectiveUpdated: (objId: number, patch: Partial<Objective>) => void
}

export default function ObjectivesSettings({ productId, objectives, password, onObjectiveUpdated }: Props) {
  const [editId, setEditId] = useState<number | null>(null)
  const [form, setForm] = useState<{ text: string; progress_current: number; progress_target: number | null }>({ text: '', progress_current: 0, progress_target: null })
  const [adding, setAdding] = useState(false)
  const [newText, setNewText] = useState('')

  const openEdit = (obj: Objective) => {
    setEditId(obj.id)
    setForm({ text: obj.text, progress_current: obj.progress_current, progress_target: obj.progress_target ?? null })
  }

  const save = async () => {
    if (!editId) return
    await api.updateObjective(password, editId, form)
    onObjectiveUpdated(editId, form)
    setEditId(null)
  }

  const del = async (obj: Objective) => {
    if (!confirm(`Delete "${obj.text}"?`)) return
    await api.deleteObjective(password, obj.id)
    onObjectiveUpdated(obj.id, { text: '' }) // signals deletion to parent
  }

  const create = async () => {
    if (!newText.trim()) return
    await api.createObjective(password, productId, newText.trim())
    setNewText('')
    setAdding(false)
  }

  return (
    <div className="max-w-lg">
      <h2 className="text-base font-bold text-adj-text-primary mb-1">Objectives</h2>
      <p className="text-xs text-adj-text-muted mb-6">Goals to track progress toward</p>

      <div className="flex flex-col gap-2 mb-4">
        {objectives.map(obj => (
          <div key={obj.id} className="bg-adj-panel border border-adj-border rounded-lg overflow-hidden">
            <div className="flex items-center gap-3 px-4 py-3">
              <span className="text-adj-text-muted text-sm">◎</span>
              <span className="text-sm text-adj-text-primary flex-1">{obj.text}</span>
              {obj.progress_target != null && (
                <span className="text-xs text-adj-text-muted">{obj.progress_current}/{obj.progress_target}</span>
              )}
              <button onClick={() => openEdit(obj)} className="text-xs text-adj-accent hover:underline">Edit</button>
              <button onClick={() => del(obj)} className="text-xs text-red-400 hover:underline ml-2">Delete</button>
            </div>
            {editId === obj.id && (
              <div className="px-4 pb-4 border-t border-adj-border bg-adj-surface">
                <div className="mt-3 mb-2">
                  <label className="block text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-1">Objective</label>
                  <input className="w-full bg-adj-panel border border-adj-border rounded px-3 py-1.5 text-sm text-adj-text-primary focus:outline-none focus:border-adj-accent" value={form.text} onChange={e => setForm(f => ({ ...f, text: e.target.value }))} />
                </div>
                <div className="flex gap-3 mb-3">
                  <div className="flex-1">
                    <label className="block text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-1">Current</label>
                    <input type="number" className="w-full bg-adj-panel border border-adj-border rounded px-3 py-1.5 text-sm text-adj-text-primary focus:outline-none focus:border-adj-accent" value={form.progress_current} onChange={e => setForm(f => ({ ...f, progress_current: Number(e.target.value) }))} />
                  </div>
                  <div className="flex-1">
                    <label className="block text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-1">Target</label>
                    <input type="number" className="w-full bg-adj-panel border border-adj-border rounded px-3 py-1.5 text-sm text-adj-text-primary focus:outline-none focus:border-adj-accent" value={form.progress_target ?? ''} onChange={e => setForm(f => ({ ...f, progress_target: e.target.value ? Number(e.target.value) : null }))} placeholder="optional" />
                  </div>
                </div>
                <div className="flex gap-2">
                  <button onClick={save} className="px-4 py-1.5 bg-adj-accent text-white rounded text-xs font-semibold hover:bg-adj-accent-dark transition-colors">Save</button>
                  <button onClick={() => setEditId(null)} className="px-4 py-1.5 text-adj-text-muted hover:text-adj-text-secondary text-xs transition-colors">Cancel</button>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>

      {adding ? (
        <div className="flex gap-2">
          <input autoFocus className="flex-1 bg-adj-panel border border-adj-border rounded-md px-3 py-2 text-sm text-adj-text-primary focus:outline-none focus:border-adj-accent" placeholder="Describe the objective" value={newText} onChange={e => setNewText(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') create(); if (e.key === 'Escape') setAdding(false) }} />
          <button onClick={create} className="px-4 py-2 bg-adj-accent text-white rounded-md text-sm font-semibold">Add</button>
          <button onClick={() => setAdding(false)} className="px-3 py-2 text-adj-text-muted text-sm">✕</button>
        </div>
      ) : (
        <button onClick={() => setAdding(true)} className="w-full border border-dashed border-adj-text-faint rounded-lg py-2.5 text-sm text-adj-text-faint hover:border-adj-accent hover:text-adj-accent transition-colors">
          + Add Objective
        </button>
      )}
    </div>
  )
}
```

- [ ] **Step 5: Port AutonomySettings from SettingsSidebar**

Read the autonomy section of `ui/src/components/SettingsSidebar.tsx`. Copy the autonomy UI logic into `ui/src/components/settings/AutonomySettings.tsx`, updating props signature to:

```tsx
interface Props {
  productId: string
  password: string
}
```

Remove all references to sidebar-specific state (`sectionOpen`, etc.). Keep the autonomy fetch and save logic identical.

- [ ] **Step 6: Verify TypeScript build**

```bash
cd ui && npm run build 2>&1 | head -40
```

Expected: No errors.

- [ ] **Step 7: Commit**

```bash
git add ui/src/components/settings/
git commit -m "feat: implement Overview, Workstreams, Objectives, Autonomy settings tabs"
```

---

## Task 6: Settings Tab — Integrations + Global Sections

Port remaining tabs from SettingsSidebar: Connections, Social, AgentModel, GoogleOAuth, RemoteAccess, MCP.

**Files:**
- Modify: `ui/src/components/settings/ConnectionsSettings.tsx`
- Modify: `ui/src/components/settings/SocialSettings.tsx`
- Modify: `ui/src/components/settings/AgentModelSettings.tsx`
- Modify: `ui/src/components/settings/GoogleOAuthSettings.tsx`
- Modify: `ui/src/components/settings/RemoteAccessSettings.tsx`
- Modify: `ui/src/components/settings/MCPSettings.tsx`
- Reference: `ui/src/components/SettingsSidebar.tsx`

- [ ] **Step 1: Port ConnectionsSettings**

Read the "Connections" section of `SettingsSidebar.tsx`. Move all OAuth connection UI (Gmail, Calendar, Twitter, LinkedIn, Facebook, Instagram connect/disconnect buttons) into `ConnectionsSettings.tsx` with this props interface:

```tsx
interface Props {
  productId: string
  password: string
}
```

Keep all existing API calls identical (`api.getOAuthStatus`, `api.initiateOAuth`, `api.revokeOAuth`, etc.).

- [ ] **Step 2: Port SocialSettings**

Read the "Social Accounts" section of `SettingsSidebar.tsx`. Move credential inputs (Twitter API key/secret, LinkedIn, Meta) into `SocialSettings.tsx`:

```tsx
interface Props {
  password: string
}
```

- [ ] **Step 3: Port AgentModelSettings**

Read the "Agent" section of `SettingsSidebar.tsx`. Move model dropdowns (Opus/Sonnet/Haiku for main + sub-agent) into `AgentModelSettings.tsx`:

```tsx
interface Props {
  password: string
}
```

- [ ] **Step 4: Port GoogleOAuthSettings**

Read the "Google OAuth" section of `SettingsSidebar.tsx`. Move client ID/secret inputs into `GoogleOAuthSettings.tsx`:

```tsx
interface Props {
  password: string
}
```

- [ ] **Step 5: Port RemoteAccessSettings**

Read the "Remote Access" section of `SettingsSidebar.tsx`. Move Telegram bot status display into `RemoteAccessSettings.tsx`:

```tsx
interface Props {
  password: string
}
```

- [ ] **Step 6: Port MCPSettings**

Read the "MCP Servers" section of `SettingsSidebar.tsx`. Move MCP server management UI into `MCPSettings.tsx`:

```tsx
interface Props {
  productId: string
  password: string
}
```

- [ ] **Step 7: Verify TypeScript build**

```bash
cd ui && npm run build 2>&1 | head -40
```

Expected: No errors.

- [ ] **Step 8: Commit**

```bash
git add ui/src/components/settings/
git commit -m "feat: implement Connections, Social, Agent, OAuth, Remote, MCP settings tabs"
```

---

## Task 7: Backend — Wizard Plan Endpoint

New endpoint that takes a user's intent text and returns AI-generated workstream and objective suggestions.

**Files:**
- Modify: `backend/api.py`
- Modify: `ui/src/api.ts`

- [ ] **Step 1: Add the endpoint to backend/api.py**

Open `backend/api.py`. Find where other POST routes are defined. Add:

```python
@router.post("/wizard-plan")
async def generate_wizard_plan(body: dict, password: str = Depends(verify_password)):
    """Use Claude to derive workstream and objective suggestions from user intent text."""
    import anthropic
    intent = body.get("intent", "").strip()
    if not intent:
        raise HTTPException(status_code=422, detail="intent is required")

    client = anthropic.Anthropic()
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": f"""You are helping set up an AI agent system. A user described what they want the system to do:

<intent>
{intent}
</intent>

Based on this, suggest:
1. 2-5 workstreams (automated recurring tasks the AI should run on a schedule)
2. 1-3 objectives (measurable goals to track progress toward)
3. Required integrations from this list only: gmail, google_calendar, twitter, linkedin, facebook, instagram

Respond with ONLY valid JSON in this exact format, no explanation:
{{
  "workstreams": [
    {{"name": "string", "mission": "string describing what the AI does", "schedule": "daily|weekly|monthly|none"}}
  ],
  "objectives": [
    {{"text": "string describing the goal", "progress_target": number_or_null}}
  ],
  "required_integrations": ["gmail", "twitter"]
}}"""
        }],
    )

    import json
    try:
        raw = message.content[0].text.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw)
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to parse AI response")
```

- [ ] **Step 2: Add getWizardPlan to ui/src/api.ts**

Open `ui/src/api.ts`. Add at the end of the `api` object:

```ts
  getWizardPlan: (pw: string, intent: string) =>
    apiFetch<{
      workstreams: Array<{ name: string; mission: string; schedule: string }>
      objectives: Array<{ text: string; progress_target: number | null }>
      required_integrations: string[]
    }>('/api/wizard-plan', pw, {
      method: 'POST',
      body: JSON.stringify({ intent }),
    }),
```

- [ ] **Step 3: Test the endpoint manually**

Start the dev server. Run:

```bash
curl -s -X POST http://localhost:8000/api/wizard-plan \
  -H "Content-Type: application/json" \
  -H "X-Agent-Password: $(cat .env | grep AGENT_PASSWORD | cut -d= -f2)" \
  -d '{"intent":"I want to post daily on LinkedIn and Twitter, send a weekly newsletter, and track competitor blogs"}' | python3 -m json.tool
```

Expected: JSON with `workstreams`, `objectives`, and `required_integrations` arrays.

- [ ] **Step 4: Commit**

```bash
git add backend/api.py ui/src/api.ts
git commit -m "feat: add /api/wizard-plan endpoint for AI-derived product setup suggestions"
```

---

## Task 8: ProductWizard Component

4-step wizard: Vision → Basics → Review Plan → Connect Apps.

**Files:**
- Create: `ui/src/components/ProductWizard.tsx`
- Create: `ui/src/__tests__/ProductWizard.test.tsx`

- [ ] **Step 1: Write failing tests**

Create `ui/src/__tests__/ProductWizard.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import '@testing-library/jest-dom'
import ProductWizard from '../components/ProductWizard'
import { api } from '../api'

vi.mock('../api', () => ({
  api: {
    getWizardPlan: vi.fn().mockResolvedValue({
      workstreams: [{ name: 'Daily Posts', mission: 'Post on social', schedule: 'daily' }],
      objectives:  [{ text: 'Grow followers', progress_target: 1000 }],
      required_integrations: ['twitter'],
    }),
  },
}))

const DEFAULT_PROPS = {
  password: 'pw',
  onComplete: vi.fn(),
  onClose: vi.fn(),
}

beforeEach(() => vi.clearAllMocks())

describe('ProductWizard', () => {
  it('renders step 1 with intent textarea', () => {
    render(<ProductWizard {...DEFAULT_PROPS} />)
    expect(screen.getByText(/What do you want Adjutant to do/i)).toBeInTheDocument()
    expect(screen.getByRole('textbox')).toBeInTheDocument()
  })

  it('disables "Build My Plan" when intent is empty', () => {
    render(<ProductWizard {...DEFAULT_PROPS} />)
    expect(screen.getByText('Build My Plan →')).toBeDisabled()
  })

  it('enables "Build My Plan" when intent has text', () => {
    render(<ProductWizard {...DEFAULT_PROPS} />)
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'I want to post on social media' } })
    expect(screen.getByText('Build My Plan →')).not.toBeDisabled()
  })

  it('advances to step 2 (Basics) on Continue', async () => {
    render(<ProductWizard {...DEFAULT_PROPS} />)
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Manage my social' } })
    fireEvent.click(screen.getByText('Build My Plan →'))
    await waitFor(() => {
      expect(screen.getByLabelText(/Product Name/i)).toBeInTheDocument()
    })
  })

  it('shows AI suggestions on step 3 after getWizardPlan resolves', async () => {
    render(<ProductWizard {...DEFAULT_PROPS} />)
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Manage my social' } })
    fireEvent.click(screen.getByText('Build My Plan →'))
    // advance past step 2
    await waitFor(() => screen.getByLabelText(/Product Name/i))
    fireEvent.change(screen.getByLabelText(/Product Name/i), { target: { value: 'My Brand' } })
    fireEvent.click(screen.getByText('Continue →'))
    await waitFor(() => {
      expect(screen.getByText('Daily Posts')).toBeInTheDocument()
      expect(screen.getByText('Grow followers')).toBeInTheDocument()
    })
  })

  it('allows adding a custom workstream on step 3', async () => {
    render(<ProductWizard {...DEFAULT_PROPS} />)
    // navigate to step 3
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Test' } })
    fireEvent.click(screen.getByText('Build My Plan →'))
    await waitFor(() => screen.getByLabelText(/Product Name/i))
    fireEvent.change(screen.getByLabelText(/Product Name/i), { target: { value: 'X' } })
    fireEvent.click(screen.getByText('Continue →'))
    await waitFor(() => screen.getByText('+ Add workstream'))
    fireEvent.click(screen.getByText('+ Add workstream'))
    expect(screen.getByPlaceholderText(/What should Adjutant do/i)).toBeInTheDocument()
  })

  it('calls onClose when × is clicked', () => {
    const onClose = vi.fn()
    render(<ProductWizard {...DEFAULT_PROPS} onClose={onClose} />)
    fireEvent.click(screen.getByTitle('Close'))
    expect(onClose).toHaveBeenCalled()
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd ui && npm test -- --reporter=verbose ProductWizard
```

Expected: FAIL.

- [ ] **Step 3: Implement ProductWizard**

Create `ui/src/components/ProductWizard.tsx`:

```tsx
import { useState } from 'react'
import { api } from '../api'

type Step = 1 | 2 | 3 | 4

interface WsSuggestion {
  name: string
  mission: string
  schedule: string
  checked: boolean
  source: 'ai' | 'user'
}
interface ObjSuggestion {
  text: string
  progress_target: number | null
  checked: boolean
  source: 'ai' | 'user'
}

interface Props {
  password: string
  onComplete: (productData: { name: string; icon: string; color: string; intent: string; workstreams: WsSuggestion[]; objectives: ObjSuggestion[] }) => void
  onClose: () => void
}

const COLORS = ['#6366f1','#ec4899','#f59e0b','#10b981','#3b82f6','#ef4444']
const STEPS = ['Your Vision', 'Basics', 'Review Plan', 'Connect Apps']

export default function ProductWizard({ password, onComplete, onClose }: Props) {
  const [step, setStep]     = useState<Step>(1)
  const [intent, setIntent] = useState('')
  const [name, setName]     = useState('')
  const [icon, setIcon]     = useState('🚀')
  const [color, setColor]   = useState(COLORS[0])
  const [loading, setLoading] = useState(false)
  const [workstreams, setWorkstreams] = useState<WsSuggestion[]>([])
  const [objectives,  setObjectives]  = useState<ObjSuggestion[]>([])
  const [addingWs,  setAddingWs]  = useState(false)
  const [addingObj, setAddingObj] = useState(false)
  const [newWsName, setNewWsName] = useState('')
  const [newWsSched, setNewWsSched] = useState('daily')
  const [newObjText, setNewObjText] = useState('')

  const advanceFromStep1 = () => setStep(2)

  const advanceFromStep2 = async () => {
    setLoading(true)
    try {
      const plan = await api.getWizardPlan(password, intent)
      setWorkstreams(plan.workstreams.map(w => ({ ...w, checked: true, source: 'ai' as const })))
      setObjectives(plan.objectives.map(o => ({ ...o, checked: true, source: 'ai' as const })))
    } catch {
      setWorkstreams([])
      setObjectives([])
    } finally {
      setLoading(false)
    }
    setStep(3)
  }

  const addUserWs = () => {
    if (!newWsName.trim()) return
    setWorkstreams(ws => [...ws, { name: newWsName.trim(), mission: '', schedule: newWsSched, checked: true, source: 'user' }])
    setNewWsName('')
    setNewWsSched('daily')
    setAddingWs(false)
  }

  const addUserObj = () => {
    if (!newObjText.trim()) return
    setObjectives(os => [...os, { text: newObjText.trim(), progress_target: null, checked: true, source: 'user' }])
    setNewObjText('')
    setAddingObj(false)
  }

  const finish = () => {
    onComplete({ name, icon, color, intent, workstreams: workstreams.filter(w => w.checked), objectives: objectives.filter(o => o.checked) })
  }

  const stepNum = (n: number) => (
    <div className={`flex items-center gap-2 ${n < step ? 'text-green-400' : n === step ? 'text-adj-text-primary' : 'text-adj-text-faint'}`}>
      <span className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold flex-shrink-0 ${n < step ? 'bg-green-800 text-green-400' : n === step ? 'bg-adj-accent text-white' : 'bg-adj-elevated text-adj-text-faint'}`}>
        {n < step ? '✓' : n}
      </span>
      <span className="text-xs">{STEPS[n - 1]}</span>
    </div>
  )

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
      <div className="bg-adj-base border border-adj-border rounded-2xl shadow-2xl w-full max-w-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 bg-adj-surface border-b border-adj-border">
          <span className="text-sm font-bold text-adj-text-primary">Create New Product</span>
          <div className="flex items-center gap-3">
            <span className="text-xs text-adj-text-muted">Step {step} of 4</span>
            <button title="Close" onClick={onClose} className="text-adj-text-muted hover:text-adj-text-primary transition-colors text-lg leading-none">×</button>
          </div>
        </div>

        <div className="flex">
          {/* Step nav */}
          <div className="w-36 bg-adj-panel border-r border-adj-border p-4 flex flex-col gap-3">
            {[1,2,3,4].map(n => <div key={n}>{stepNum(n)}</div>)}
          </div>

          {/* Content */}
          <div className="flex-1 p-6">

            {step === 1 && (
              <div>
                <p className="text-[10px] font-bold uppercase tracking-wider text-adj-accent mb-1">Let's get started</p>
                <h3 className="text-base font-bold text-adj-text-primary mb-2">What do you want Adjutant to do?</h3>
                <p className="text-xs text-adj-text-muted mb-4">Describe it in plain language — Adjutant will build a plan from your answer.</p>
                <textarea
                  className="w-full bg-adj-panel border border-adj-border rounded-lg px-4 py-3 text-sm text-adj-text-primary placeholder:text-adj-text-faint focus:outline-none focus:border-adj-accent resize-none h-32 transition-colors"
                  placeholder="e.g. I run a small brand. I want Adjutant to manage our Instagram and LinkedIn posts, send a weekly email newsletter, and alert me before anything gets published."
                  value={intent}
                  onChange={e => setIntent(e.target.value)}
                />
                <div className="flex justify-end mt-4">
                  <button
                    onClick={advanceFromStep1}
                    disabled={!intent.trim()}
                    className="px-5 py-2 bg-adj-accent text-white rounded-lg text-sm font-semibold hover:bg-adj-accent-dark transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    Build My Plan →
                  </button>
                </div>
              </div>
            )}

            {step === 2 && (
              <div>
                <h3 className="text-base font-bold text-adj-text-primary mb-5">Name your product</h3>
                <div className="flex gap-3 mb-4">
                  <div className="flex-1">
                    <label aria-label="Product Name" className="block text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-1.5">Product Name</label>
                    <input
                      className="w-full bg-adj-panel border border-adj-border rounded-md px-3 py-2 text-sm text-adj-text-primary focus:outline-none focus:border-adj-accent transition-colors"
                      value={name}
                      onChange={e => setName(e.target.value)}
                      placeholder="My Brand"
                      autoFocus
                    />
                  </div>
                  <div className="w-20">
                    <label className="block text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-1.5">Icon</label>
                    <input className="w-full bg-adj-panel border border-adj-border rounded-md px-3 py-2 text-sm text-center text-adj-text-primary focus:outline-none focus:border-adj-accent" value={icon} onChange={e => setIcon(e.target.value)} />
                  </div>
                </div>
                <div className="mb-6">
                  <label className="block text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-1.5">Color</label>
                  <div className="flex gap-2">
                    {COLORS.map(c => (
                      <button key={c} onClick={() => setColor(c)} className="w-6 h-6 rounded-full transition-transform hover:scale-110" style={{ background: c, outline: color === c ? '2px solid white' : 'none', outlineOffset: '2px' }} />
                    ))}
                  </div>
                </div>
                <div className="flex justify-between">
                  <button onClick={() => setStep(1)} className="text-sm text-adj-text-muted hover:text-adj-text-secondary transition-colors">← Back</button>
                  <button
                    onClick={advanceFromStep2}
                    disabled={!name.trim() || loading}
                    className="px-5 py-2 bg-adj-accent text-white rounded-lg text-sm font-semibold hover:bg-adj-accent-dark transition-colors disabled:opacity-40"
                  >
                    {loading ? 'Building plan…' : 'Continue →'}
                  </button>
                </div>
              </div>
            )}

            {step === 3 && (
              <div>
                <p className="text-[10px] font-bold uppercase tracking-wider text-adj-accent mb-1">Adjutant built this from your vision</p>
                <h3 className="text-base font-bold text-adj-text-primary mb-1">Review and customize your plan</h3>
                <p className="text-xs text-adj-text-muted mb-4">Uncheck anything you don't want. Add your own below each group.</p>

                {/* Workstreams */}
                <div className="mb-4">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-adj-text-faint">⟳ Workstreams</span>
                    <button onClick={() => setAddingWs(true)} className="text-[10px] text-adj-accent border border-dashed border-adj-accent px-2 py-0.5 rounded hover:bg-adj-elevated transition-colors">+ Add workstream</button>
                  </div>
                  {workstreams.map((ws, i) => (
                    <div key={i} className={`flex items-center gap-2.5 px-3 py-2 rounded-md mb-1.5 border ${ws.checked ? 'bg-adj-panel border-adj-accent-dark' : 'bg-adj-panel border-adj-border opacity-50'}`}>
                      <input type="checkbox" checked={ws.checked} onChange={e => setWorkstreams(wss => wss.map((w, j) => j === i ? { ...w, checked: e.target.checked } : w))} className="accent-adj-accent" />
                      <span className="text-xs text-adj-text-primary flex-1">{ws.name}</span>
                      <span className="text-[9px] text-adj-text-muted">{ws.schedule}</span>
                      <span className={`text-[8px] px-1.5 py-0.5 rounded font-bold ${ws.source === 'ai' ? 'bg-green-900 text-green-400' : 'bg-amber-900 text-amber-400'}`}>{ws.source === 'ai' ? 'AI' : 'YOU'}</span>
                      {ws.source === 'user' && <button onClick={() => setWorkstreams(wss => wss.filter((_, j) => j !== i))} className="text-adj-text-faint hover:text-red-400 text-sm transition-colors">×</button>}
                    </div>
                  ))}
                  {addingWs && (
                    <div className="flex gap-2 mt-1">
                      <input autoFocus className="flex-1 bg-adj-panel border border-adj-border rounded px-2 py-1 text-xs text-adj-text-primary focus:outline-none focus:border-adj-accent" placeholder="What should Adjutant do?" value={newWsName} onChange={e => setNewWsName(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') addUserWs(); if (e.key === 'Escape') setAddingWs(false) }} />
                      <select className="bg-adj-panel border border-adj-border rounded px-2 py-1 text-xs text-adj-text-primary" value={newWsSched} onChange={e => setNewWsSched(e.target.value)}>
                        <option value="daily">daily</option>
                        <option value="weekly">weekly</option>
                        <option value="monthly">monthly</option>
                        <option value="none">no schedule</option>
                      </select>
                      <button onClick={addUserWs} className="px-3 py-1 bg-adj-accent text-white rounded text-xs font-semibold">Add</button>
                      <button onClick={() => setAddingWs(false)} className="text-adj-text-muted text-sm">✕</button>
                    </div>
                  )}
                </div>

                {/* Objectives */}
                <div className="mb-4">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-adj-text-faint">◎ Objectives</span>
                    <button onClick={() => setAddingObj(true)} className="text-[10px] text-adj-accent border border-dashed border-adj-accent px-2 py-0.5 rounded hover:bg-adj-elevated transition-colors">+ Add objective</button>
                  </div>
                  {objectives.map((obj, i) => (
                    <div key={i} className={`flex items-center gap-2.5 px-3 py-2 rounded-md mb-1.5 border ${obj.checked ? 'bg-adj-panel border-adj-accent-dark' : 'bg-adj-panel border-adj-border opacity-50'}`}>
                      <input type="checkbox" checked={obj.checked} onChange={e => setObjectives(os => os.map((o, j) => j === i ? { ...o, checked: e.target.checked } : o))} className="accent-adj-accent" />
                      <span className="text-xs text-adj-text-primary flex-1">{obj.text}</span>
                      {obj.progress_target != null && <span className="text-[9px] text-adj-text-muted">target: {obj.progress_target}</span>}
                      <span className={`text-[8px] px-1.5 py-0.5 rounded font-bold ${obj.source === 'ai' ? 'bg-green-900 text-green-400' : 'bg-amber-900 text-amber-400'}`}>{obj.source === 'ai' ? 'AI' : 'YOU'}</span>
                      {obj.source === 'user' && <button onClick={() => setObjectives(os => os.filter((_, j) => j !== i))} className="text-adj-text-faint hover:text-red-400 text-sm transition-colors">×</button>}
                    </div>
                  ))}
                  {addingObj && (
                    <div className="flex gap-2 mt-1">
                      <input autoFocus className="flex-1 bg-adj-panel border border-adj-border rounded px-2 py-1 text-xs text-adj-text-primary focus:outline-none focus:border-adj-accent" placeholder="Describe the objective" value={newObjText} onChange={e => setNewObjText(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') addUserObj(); if (e.key === 'Escape') setAddingObj(false) }} />
                      <button onClick={addUserObj} className="px-3 py-1 bg-adj-accent text-white rounded text-xs font-semibold">Add</button>
                      <button onClick={() => setAddingObj(false)} className="text-adj-text-muted text-sm">✕</button>
                    </div>
                  )}
                </div>

                <div className="flex justify-between">
                  <button onClick={() => setStep(2)} className="text-sm text-adj-text-muted hover:text-adj-text-secondary transition-colors">← Back</button>
                  <button onClick={() => setStep(4)} className="px-5 py-2 bg-adj-accent text-white rounded-lg text-sm font-semibold hover:bg-adj-accent-dark transition-colors">Looks good, continue →</button>
                </div>
              </div>
            )}

            {step === 4 && (
              <div>
                <h3 className="text-base font-bold text-adj-text-primary mb-2">Connect apps</h3>
                <p className="text-xs text-adj-text-muted mb-6">You can connect these later in Settings → Connections. Skip to finish and connect whenever you're ready.</p>
                <p className="text-sm text-adj-text-secondary mb-6">Your workstreams may need integrations to function fully. Connect them in Settings after your product is created.</p>
                <div className="flex justify-between">
                  <button onClick={() => setStep(3)} className="text-sm text-adj-text-muted hover:text-adj-text-secondary transition-colors">← Back</button>
                  <button onClick={finish} className="px-5 py-2 bg-adj-accent text-white rounded-lg text-sm font-semibold hover:bg-adj-accent-dark transition-colors">
                    Create Product 🚀
                  </button>
                </div>
              </div>
            )}

          </div>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Run tests**

```bash
cd ui && npm test -- --reporter=verbose ProductWizard
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add ui/src/components/ProductWizard.tsx ui/src/__tests__/ProductWizard.test.tsx
git commit -m "feat: add 4-step ProductWizard with AI-derived plan suggestions"
```

---

## Task 9: App.tsx — Full Layout Refactor

Wire all new components in. Remove 5 old panel components, 2 old modals. Refactor header. The existing WebSocket logic, callbacks, and state management stay untouched.

**Files:**
- Modify: `ui/src/App.tsx`

- [ ] **Step 1: Update imports**

In `ui/src/App.tsx`, replace all the old imports at the top:

```tsx
// REMOVE these imports:
import ProductRail from './components/ProductRail'
import WorkstreamsPanel from './components/WorkstreamsPanel'
import ObjectivesPanel from './components/ObjectivesPanel'
import ReviewQueue from './components/ReviewQueue'
import SettingsSidebar from './components/SettingsSidebar'
import LaunchWizardPanel from './components/LaunchWizardPanel'
import LaunchFormModal from './components/LaunchFormModal'

// ADD these imports:
import ProductDropdown from './components/ProductDropdown'
import StatusStrip from './components/StatusStrip'
import SettingsPage from './components/SettingsPage'
import ProductWizard from './components/ProductWizard'
```

Keep all other imports unchanged.

- [ ] **Step 2: Replace settingsOpen state and add settingsTab state**

Find this line in App.tsx:
```tsx
const [settingsOpen,    setSettingsOpen]    = useState(false)
```

Replace with:
```tsx
const [settingsOpen,    setSettingsOpen]    = useState(false)
const [settingsTab,     setSettingsTab]     = useState<string>('overview')
const [wizardOpen,      setWizardOpen]      = useState(false)
```

- [ ] **Step 3: Add openSettings helper**

After the existing callbacks (after `deleteSession`), add:

```tsx
const openSettings = useCallback((tab = 'overview') => {
  setSettingsTab(tab)
  setSettingsOpen(true)
}, [])
```

- [ ] **Step 4: Replace the header JSX**

Find the `<header>` block in the return statement (lines ~485–548 in the original). Replace it entirely with:

```tsx
<header className="flex items-center gap-3 px-5 h-12 border-b border-adj-border flex-shrink-0 bg-adj-surface">
  {/* Logo */}
  <span className="w-7 h-7 rounded-lg bg-adj-accent text-white text-xs font-bold flex items-center justify-center flex-shrink-0">
    {agentName[0]?.toUpperCase() ?? 'A'}
  </span>
  <span className="w-px h-4 bg-adj-border flex-shrink-0" />

  {/* Product dropdown */}
  {!showOverview && (
    <ProductDropdown
      products={products}
      activeProductId={activeProductId}
      onSelect={switchProduct}
      onNewProduct={() => setWizardOpen(true)}
    />
  )}
  {showOverview && (
    <button onClick={switchToGlobal} className="text-sm font-semibold text-adj-text-secondary hover:text-adj-text-primary transition-colors">
      Overview
    </button>
  )}

  <div className="ml-auto flex items-center gap-2">
    {/* Connection status */}
    <span className={`flex items-center gap-1.5 text-xs ${connState === 'ready' ? 'text-green-500' : 'text-adj-text-faint'}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${connState === 'ready' ? 'bg-green-500' : 'bg-adj-text-faint'}`} />
      {connState === 'ready' ? 'connected' : 'disconnected'}
    </span>

    {/* Notes */}
    <button
      onClick={() => { setNotesOpen(o => !o); setHistoryOpen(false) }}
      title="Product notes"
      className={`w-7 h-7 flex items-center justify-center rounded transition-colors ${notesOpen ? 'text-adj-text-primary bg-adj-elevated' : 'text-adj-text-muted hover:text-adj-text-secondary hover:bg-adj-elevated'}`}
    >
      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
      </svg>
    </button>

    {/* History */}
    <button
      onClick={() => { setHistoryOpen(o => !o); setNotesOpen(false) }}
      title="Directive history"
      className={`w-7 h-7 flex items-center justify-center rounded transition-colors ${historyOpen ? 'text-adj-text-primary bg-adj-elevated' : 'text-adj-text-muted hover:text-adj-text-secondary hover:bg-adj-elevated'}`}
    >
      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    </button>

    {/* Settings */}
    <button
      onClick={() => openSettings()}
      title="Settings"
      className="w-7 h-7 flex items-center justify-center rounded bg-adj-elevated border border-adj-accent text-adj-accent hover:bg-adj-accent hover:text-white transition-colors"
    >
      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
        <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
      </svg>
    </button>
  </div>
</header>
```

- [ ] **Step 5: Add StatusStrip below the header**

Directly after the `</header>` tag and before the `<div className="flex flex-1 overflow-hidden">` body div, add:

```tsx
{/* Status strip — shown only in product workspace, not overview or settings */}
{!showOverview && !settingsOpen && (
  <StatusStrip
    workstreams={activeState.workstreams}
    reviewItems={activeState.review_items}
    events={activeState.events}
    objectives={activeState.objectives}
    onResolveReview={resolveReview}
    onCancelAgent={cancelDirective}
    onOpenSettings={openSettings}
  />
)}
```

- [ ] **Step 6: Replace the product workspace body**

Find the body section that starts with `{/* Body */}` and has `<ProductRail ...>`. Replace the full workspace render (product view branch only — the `<>` block starting at line ~640 in the original) with:

```tsx
{/* Settings page — full-width overlay */}
{settingsOpen ? (
  <SettingsPage
    products={products}
    activeProductId={activeProductId}
    productStates={productStates}
    password={pw}
    initialTab={settingsTab as any}
    onClose={() => setSettingsOpen(false)}
    onSwitchProduct={switchProduct}
    onNewProduct={() => { setSettingsOpen(false); setWizardOpen(true) }}
    onRefreshData={pid => wsRef.current?.send(JSON.stringify({ type: 'switch_product', product_id: pid }))}
    onWorkstreamUpdated={(wsId, patch) =>
      setProductState(activeProductId, prev => ({
        ...prev,
        workstreams: prev.workstreams.map(ws => ws.id === wsId ? { ...ws, ...patch } : ws),
      }))
    }
    onObjectiveUpdated={(objId, patch) =>
      setProductState(activeProductId, prev => ({
        ...prev,
        objectives: patch.text === ''
          ? prev.objectives.filter(o => o.id !== objId)
          : prev.objectives.map(o => o.id === objId ? { ...o, ...patch } : o),
      }))
    }
  />
) : showOverview ? (
  <div className="flex flex-1 overflow-hidden">
    {/* --- OVERVIEW mode: keep existing overview JSX unchanged --- */}
    {/* Copy the existing showOverview block here verbatim */}
  </div>
) : (
  /* Product workspace — two column */
  <div className="flex flex-1 overflow-hidden">
    {/* Left: sessions only */}
    <div className="flex flex-col border-r border-adj-border w-52 flex-shrink-0 bg-adj-panel">
      <SessionsPanel
        sessions={activeState.sessions}
        activeSessionId={activeState.activeSessionId}
        onCreate={createSession}
        onSwitch={switchSession}
        onRename={renameSession}
        onDelete={deleteSession}
      />
    </div>

    {/* Center: full-width activity feed */}
    <div className="flex-1 flex flex-col overflow-hidden bg-adj-base">
      {activeState.activeSessionId && (
        <div className="flex items-center px-4 py-1 border-b border-adj-border">
          <span className="text-[10px] text-adj-text-faint ml-auto">
            {activeState.sessions.find(s => s.id === activeState.activeSessionId)?.name ?? ''} session
          </span>
        </div>
      )}
      <LiveAgents
        events={activeState.events}
        currentDirective={queueByProduct[activeProductId]?.current ?? null}
        onCancelDirective={cancelDirective}
        agentName={agentName}
      />
      <ActivityFeed
        events={activeState.events}
        directives={directives[activeProductId] ?? []}
        agentMessages={agentMessages[activeProductId] ?? []}
        agentDraft={agentDraftByProduct[activeProductId] ?? ''}
        agentName={agentName}
      />
      <DirectiveTemplates
        productId={activeProductId}
        password={pw}
        onSelect={content => setDirectivePrefill(content)}
      />
      <DirectiveBar
        onSend={sendDirective}
        disabled={connState !== 'ready'}
        productName={activeProduct?.name ?? 'this product'}
        agentName={agentName}
        prefill={directivePrefill}
        onPrefillConsumed={() => setDirectivePrefill('')}
        password={pw}
      />
    </div>
  </div>
)}
```

**Note:** Copy the existing `showOverview` JSX block verbatim into the overview branch. Do not rewrite it.

- [ ] **Step 7: Add ProductWizard and remove old modals**

At the bottom of the return statement, remove:
```tsx
{settingsOpen && <SettingsSidebar ... />}
{launchFormOpen && <LaunchFormModal ... />}
```

Add `ProductWizard` instead (keep `NotesDrawer` and `DirectiveHistoryDrawer` as-is):

```tsx
{wizardOpen && (
  <ProductWizard
    password={pw}
    onComplete={({ name, icon, color, intent, workstreams, objectives }) => {
      setWizardOpen(false)
      launchProduct(name, intent, intent)  // sends launch_product WS message
    }}
    onClose={() => setWizardOpen(false)}
  />
)}
```

Also remove the `launchFormOpen` state line since it's no longer needed.

- [ ] **Step 8: Update App background color**

Find `className="flex flex-col h-full bg-zinc-950 text-zinc-100 overflow-hidden"` on the root div. Change to:

```tsx
className="flex flex-col h-full bg-adj-base text-adj-text-primary overflow-hidden"
```

- [ ] **Step 9: TypeScript check**

```bash
cd ui && npm run build 2>&1 | head -50
```

Fix any type errors. Common ones:
- `openSettings` called with string arg — ensure `settingsTab` state accepts `string`
- `wizardOpen` used before declaration — check state declaration order

- [ ] **Step 10: Run all tests**

```bash
cd ui && npm test
```

Expected: All tests pass. Tests for deleted components (ProductRail, WorkstreamsPanel) will now fail — that's expected, they get deleted in Task 10.

- [ ] **Step 11: Commit**

```bash
git add ui/src/App.tsx
git commit -m "feat: refactor App.tsx — status strip, settings page, product wizard, 2-col layout"
```

---

## Task 10: Delete Removed Components + Update Tests

**Files:**
- Delete: `ui/src/components/ProductRail.tsx`
- Delete: `ui/src/components/WorkstreamsPanel.tsx`
- Delete: `ui/src/components/ReviewQueue.tsx`
- Delete: `ui/src/components/ObjectivesPanel.tsx`
- Delete: `ui/src/components/SettingsSidebar.tsx`
- Delete: `ui/src/components/LaunchFormModal.tsx`
- Delete: `ui/src/components/LaunchWizardPanel.tsx`
- Delete: `ui/src/__tests__/ProductRail.test.tsx`
- Delete: `ui/src/__tests__/WorkstreamsPanel.test.tsx`

- [ ] **Step 1: Delete removed component files**

```bash
rm ui/src/components/ProductRail.tsx
rm ui/src/components/WorkstreamsPanel.tsx
rm ui/src/components/ReviewQueue.tsx
rm ui/src/components/ObjectivesPanel.tsx
rm ui/src/components/SettingsSidebar.tsx
rm ui/src/components/LaunchFormModal.tsx
rm ui/src/components/LaunchWizardPanel.tsx
```

- [ ] **Step 2: Delete obsolete test files**

```bash
rm ui/src/__tests__/ProductRail.test.tsx
rm ui/src/__tests__/WorkstreamsPanel.test.tsx
```

- [ ] **Step 3: Run full test suite**

```bash
cd ui && npm test
```

Expected: All tests PASS. If any test imports a deleted component, fix the import.

- [ ] **Step 4: Final build check**

```bash
cd ui && npm run build
```

Expected: Clean build, zero errors.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: delete replaced UI components — ProductRail, SettingsSidebar, ReviewQueue, ObjectivesPanel, WorkstreamsPanel, LaunchFormModal, LaunchWizardPanel"
```

---

## Task 11: Apply New Colors to Kept Components

Update SessionsPanel, ActivityFeed, DirectiveBar, and LiveAgents to use `adj-*` color classes instead of `zinc-*`.

**Files:**
- Modify: `ui/src/components/SessionsPanel.tsx`
- Modify: `ui/src/components/ActivityFeed.tsx`
- Modify: `ui/src/components/DirectiveBar.tsx`
- Modify: `ui/src/components/LiveAgents.tsx`

- [ ] **Step 1: Update SessionsPanel colors**

In `SessionsPanel.tsx`, replace all Tailwind color classes:

| Old class | New class |
|---|---|
| `bg-zinc-950` | `bg-adj-base` |
| `bg-zinc-900` | `bg-adj-panel` |
| `bg-zinc-800` | `bg-adj-surface` |
| `border-zinc-800` | `border-adj-border` |
| `border-zinc-800/60` | `border-adj-border` |
| `text-zinc-100` | `text-adj-text-primary` |
| `text-zinc-400` | `text-adj-text-secondary` |
| `text-zinc-500` | `text-adj-text-muted` |
| `text-zinc-600` | `text-adj-text-faint` |
| `bg-blue-600` | `bg-adj-accent` |
| `text-blue-400` | `text-adj-accent` |
| `hover:bg-zinc-800` | `hover:bg-adj-elevated` |

- [ ] **Step 2: Update ActivityFeed, DirectiveBar, LiveAgents**

Apply the same color substitution table to each file. These are mechanical find-and-replace operations — work through each file top-to-bottom.

- [ ] **Step 3: Run tests**

```bash
cd ui && npm test
```

Expected: All tests PASS (color changes don't affect behavior).

- [ ] **Step 4: Verify visually**

Start the dev server and confirm the app loads with the new deep navy/indigo palette:

```bash
cd ui && npm run dev
```

Open `http://localhost:5173`. Check:
- Background is `#0f0f1a` (very dark navy)
- Accent elements are `#6366f1` (indigo)
- Status strip shows workstreams, agents, reviews, objectives
- Settings opens full-page (not a drawer)
- Product dropdown works in header
- "New Product" opens wizard

- [ ] **Step 5: Commit**

```bash
git add ui/src/components/SessionsPanel.tsx ui/src/components/ActivityFeed.tsx ui/src/components/DirectiveBar.tsx ui/src/components/LiveAgents.tsx
git commit -m "feat: apply adjutant color palette to kept components"
```

---

## Self-Review Notes

**Spec coverage check:**
- ✅ Section 1 (layout) — Tasks 9, 10
- ✅ Section 2 (header) — Task 9, Step 4
- ✅ Section 3 (status strip) — Task 3
- ✅ Section 4 (settings page) — Tasks 4, 5, 6
- ✅ Section 5 (product dropdown) — Task 2
- ✅ Section 6 (wizard) — Tasks 7, 8
- ✅ Section 7 (visual theme) — Tasks 1, 11
- ✅ Section 8 (component changes table) — Tasks 9, 10

**Type consistency:**
- `openSettings(tab: string)` — used in StatusStrip (`onOpenSettings`) and App.tsx (`openSettings`)
- `onWorkstreamUpdated(wsId: number, patch: Partial<Workstream>)` — consistent across SettingsPage, WorkstreamsSettings, App.tsx
- `onObjectiveUpdated(objId: number, patch: Partial<Objective>)` — consistent across SettingsPage, ObjectivesSettings, App.tsx; empty `text` patch signals deletion
- `resolveReview(id: number, action: 'approved' | 'skipped')` — used in StatusStrip; matches existing App.tsx callback signature
