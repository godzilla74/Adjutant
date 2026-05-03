# UI Restructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current header-flag navigation with a persistent left nav rail, a new Overview landing page, a first-class Chief Adjutant page, and a grouped settings sidebar — reducing cognitive load and making every major section reachable in one click.

**Architecture:** A `navSection` state in `App.tsx` (`'overview' | 'products' | 'chief' | 'settings'`) replaces the current `showOverview`, `showHCA`, and `settingsOpen` boolean flags. A new `NavRail` component renders the persistent left rail. Five new/refactored page-level components (`OverviewPage`, `ProductPicker`, `ChiefPage`, and the restructured `SettingsPage`) render based on `navSection`. The product workspace (sessions + activity + directive bar) renders when `navSection === 'products'` and a product is selected.

**Tech Stack:** React 19, TypeScript, Tailwind CSS (`adj-*` custom classes), Vite, Vitest + @testing-library/react

---

## File Map

### New files
- `ui/src/components/NavRail.tsx` — persistent left nav (4 items, badge, active state)
- `ui/src/components/OverviewPage.tsx` — stats row + per-product workstream cards
- `ui/src/components/WorkstreamChip.tsx` — inline workstream chip with pause/resume
- `ui/src/components/ProductPicker.tsx` — product list with "New product" button
- `ui/src/components/ChiefPage.tsx` — Chief Adjutant: review queue (left) + briefing/runs (right)
- `ui/src/components/settings/ApiKeysSettings.tsx` — Anthropic + OpenAI key inputs (extracted from OverviewSettings)
- `ui/src/__tests__/NavRail.test.tsx`
- `ui/src/__tests__/WorkstreamChip.test.tsx`
- `ui/src/__tests__/OverviewPage.test.tsx`
- `ui/src/__tests__/ProductPicker.test.tsx`
- `ui/src/__tests__/ChiefPage.test.tsx`

### Modified files
- `ui/src/App.tsx` — replace flags with `navSection`, add `NavRail`, wire new pages
- `ui/src/components/SettingsPage.tsx` — grouped sidebar (5 categories, alphabetical)
- `ui/src/components/SessionsPanel.tsx` — add `productName` + `liveAgents` props; product header at top, live agents pinned at bottom
- `ui/src/components/DirectiveBar.tsx` — accept `templates` slot; render `⚡` toggle button that reveals a slide-up panel
- `ui/src/components/settings/OverviewSettings.tsx` — remove API key inputs (moved to ApiKeysSettings)

### Retired (deleted after Task 9 wires replacements)
- `ui/src/components/StatusStrip.tsx`
- `ui/src/components/OverviewPanel.tsx`
- `ui/src/components/HCABriefingPanel.tsx`
- `ui/src/components/ProductDropdown.tsx`

---

## Task 1: NavRail component

**Files:**
- Create: `ui/src/components/NavRail.tsx`
- Create: `ui/src/__tests__/NavRail.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// ui/src/__tests__/NavRail.test.tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import '@testing-library/jest-dom'
import NavRail from '../components/NavRail'

describe('NavRail', () => {
  const onNavigate = vi.fn()
  const defaultProps = {
    section: 'overview' as const,
    reviewBadgeCount: 0,
    agentInitial: 'A',
    onNavigate,
  }

  it('renders all four nav items', () => {
    render(<NavRail {...defaultProps} />)
    expect(screen.getByTitle('Overview')).toBeInTheDocument()
    expect(screen.getByTitle('Products')).toBeInTheDocument()
    expect(screen.getByTitle('Chief')).toBeInTheDocument()
    expect(screen.getByTitle('Settings')).toBeInTheDocument()
  })

  it('calls onNavigate with correct section on click', () => {
    render(<NavRail {...defaultProps} />)
    fireEvent.click(screen.getByTitle('Chief'))
    expect(onNavigate).toHaveBeenCalledWith('chief')
  })

  it('shows badge on Chief when reviewBadgeCount > 0', () => {
    render(<NavRail {...defaultProps} reviewBadgeCount={3} />)
    expect(screen.getByText('3')).toBeInTheDocument()
  })

  it('does not show badge when reviewBadgeCount is 0', () => {
    render(<NavRail {...defaultProps} reviewBadgeCount={0} />)
    expect(screen.queryByText('0')).not.toBeInTheDocument()
  })

  it('highlights the active section', () => {
    render(<NavRail {...defaultProps} section="chief" />)
    const chiefBtn = screen.getByTitle('Chief')
    expect(chiefBtn.closest('div')).toHaveClass('bg-adj-accent/20')
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd ui && npm test -- NavRail
```
Expected: FAIL — `NavRail` not found

- [ ] **Step 3: Implement NavRail**

```tsx
// ui/src/components/NavRail.tsx
type Section = 'overview' | 'products' | 'chief' | 'settings'

interface Props {
  section: Section
  reviewBadgeCount: number
  agentInitial: string
  onNavigate: (s: Section) => void
}

const NAV_ITEMS: { section: Section; title: string; icon: string }[] = [
  { section: 'overview',  title: 'Overview',  icon: '⊞' },
  { section: 'products',  title: 'Products',  icon: '◎' },
  { section: 'chief',     title: 'Chief',     icon: '✦' },
]

export default function NavRail({ section, reviewBadgeCount, agentInitial, onNavigate }: Props) {
  return (
    <div className="w-14 bg-adj-base border-r border-adj-border flex flex-col items-center py-3 gap-1 flex-shrink-0">
      {/* Logo */}
      <div className="w-8 h-8 rounded-lg bg-adj-accent text-white text-sm font-bold flex items-center justify-center mb-3 flex-shrink-0">
        {agentInitial}
      </div>

      {/* Main nav items */}
      {NAV_ITEMS.map(item => (
        <div key={item.section} className="flex flex-col items-center gap-0.5 w-full px-1 mb-1">
          <div
            title={item.title}
            onClick={() => onNavigate(item.section)}
            className={`w-10 h-10 rounded-lg flex items-center justify-center cursor-pointer text-base transition-colors relative ${
              section === item.section
                ? 'bg-adj-accent/20 border border-adj-accent/50 text-adj-accent'
                : 'text-adj-text-faint hover:text-adj-text-secondary hover:bg-adj-elevated'
            }`}
          >
            {item.icon}
            {item.section === 'chief' && reviewBadgeCount > 0 && (
              <span className="absolute top-1 right-1 bg-amber-500 text-white text-[8px] rounded-full w-3.5 h-3.5 flex items-center justify-center font-bold leading-none">
                {reviewBadgeCount > 9 ? '9+' : reviewBadgeCount}
              </span>
            )}
          </div>
          <span className="text-[8px] text-adj-text-faint uppercase tracking-wide">{item.title}</span>
        </div>
      ))}

      {/* Settings pinned to bottom */}
      <div className="flex flex-col items-center gap-0.5 w-full px-1 mt-auto">
        <div
          title="Settings"
          onClick={() => onNavigate('settings')}
          className={`w-10 h-10 rounded-lg flex items-center justify-center cursor-pointer text-base transition-colors ${
            section === 'settings'
              ? 'bg-adj-accent/20 border border-adj-accent/50 text-adj-accent'
              : 'text-adj-text-faint hover:text-adj-text-secondary hover:bg-adj-elevated'
          }`}
        >
          ⚙
        </div>
        <span className="text-[8px] text-adj-text-faint uppercase tracking-wide">Settings</span>
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd ui && npm test -- NavRail
```
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add ui/src/components/NavRail.tsx ui/src/__tests__/NavRail.test.tsx
git commit -m "feat: add NavRail component with badge support"
```

---

## Task 2: WorkstreamChip component

**Files:**
- Create: `ui/src/components/WorkstreamChip.tsx`
- Create: `ui/src/__tests__/WorkstreamChip.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// ui/src/__tests__/WorkstreamChip.test.tsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import '@testing-library/jest-dom'
import WorkstreamChip from '../components/WorkstreamChip'
import { Workstream } from '../types'
import { api } from '../api'

vi.mock('../api', () => ({
  api: { updateWorkstream: vi.fn().mockResolvedValue({}) },
}))

const WS: Workstream = {
  id: 1,
  name: 'Blog publisher',
  status: 'running',
  display_order: 0,
  last_run_at: '2026-05-03T10:00:00',
}

describe('WorkstreamChip', () => {
  beforeEach(() => vi.clearAllMocks())

  it('renders workstream name and running status', () => {
    render(<WorkstreamChip workstream={WS} password="pw" onStatusChange={vi.fn()} />)
    expect(screen.getByText('Blog publisher')).toBeInTheDocument()
    expect(screen.getByTitle('Pause')).toBeInTheDocument()
  })

  it('shows resume button when paused', () => {
    render(<WorkstreamChip workstream={{ ...WS, status: 'paused' }} password="pw" onStatusChange={vi.fn()} />)
    expect(screen.getByTitle('Resume')).toBeInTheDocument()
  })

  it('calls api.updateWorkstream and onStatusChange when pause clicked', async () => {
    const onStatusChange = vi.fn()
    render(<WorkstreamChip workstream={WS} password="pw" onStatusChange={onStatusChange} />)
    fireEvent.click(screen.getByTitle('Pause'))
    await waitFor(() => expect(api.updateWorkstream).toHaveBeenCalledWith('pw', 1, { status: 'paused' }))
    expect(onStatusChange).toHaveBeenCalledWith(1, 'paused')
  })

  it('shows warn indicator for warn status', () => {
    render(<WorkstreamChip workstream={{ ...WS, status: 'warn' }} password="pw" onStatusChange={vi.fn()} />)
    expect(screen.getByTitle('Pause')).toBeInTheDocument()
    // warn chips have amber color class
    expect(screen.getByText('Blog publisher').closest('div')).toHaveClass('border-amber-900/40')
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd ui && npm test -- WorkstreamChip
```
Expected: FAIL — `WorkstreamChip` not found

- [ ] **Step 3: Implement WorkstreamChip**

```tsx
// ui/src/components/WorkstreamChip.tsx
import { useState } from 'react'
import { Workstream } from '../types'
import { api } from '../api'

interface Props {
  workstream: Workstream
  password: string
  onStatusChange: (wsId: number, status: 'running' | 'paused') => void
}

function relTime(ts: string | null | undefined) {
  if (!ts) return null
  const diff = Date.now() - new Date(ts.replace(' ', 'T') + (ts.includes('Z') ? '' : 'Z')).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 60) return `${mins}m ago`
  return `${Math.floor(mins / 60)}h ago`
}

const STATUS_STYLES: Record<string, string> = {
  running: 'bg-green-950/40 border-green-900/40 text-green-400',
  warn:    'bg-amber-950/40 border-amber-900/40 text-amber-400',
  paused:  'bg-adj-elevated border-adj-border text-adj-text-faint',
}

export default function WorkstreamChip({ workstream, password, onStatusChange }: Props) {
  const [saving, setSaving] = useState(false)

  const toggle = async () => {
    const next = workstream.status === 'paused' ? 'running' : 'paused'
    setSaving(true)
    try {
      await api.updateWorkstream(password, workstream.id, { status: next })
      onStatusChange(workstream.id, next)
    } finally {
      setSaving(false)
    }
  }

  const lastRun = relTime(workstream.last_run_at)

  return (
    <div className={`flex items-center gap-1.5 border rounded-md px-2 py-1 text-[11px] ${STATUS_STYLES[workstream.status] ?? STATUS_STYLES.paused}`}>
      <span className="truncate max-w-[120px]">{workstream.name}</span>
      {lastRun && <span className="text-[10px] opacity-60 flex-shrink-0">{lastRun}</span>}
      <button
        title={workstream.status === 'paused' ? 'Resume' : 'Pause'}
        onClick={toggle}
        disabled={saving}
        className="flex-shrink-0 opacity-60 hover:opacity-100 transition-opacity ml-0.5 disabled:opacity-30"
      >
        {workstream.status === 'paused' ? '▶' : '⏸'}
      </button>
    </div>
  )
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd ui && npm test -- WorkstreamChip
```
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add ui/src/components/WorkstreamChip.tsx ui/src/__tests__/WorkstreamChip.test.tsx
git commit -m "feat: add WorkstreamChip with inline pause/resume"
```

---

## Task 3: OverviewPage component

**Files:**
- Create: `ui/src/components/OverviewPage.tsx`
- Create: `ui/src/__tests__/OverviewPage.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// ui/src/__tests__/OverviewPage.test.tsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import '@testing-library/jest-dom'
import OverviewPage from '../components/OverviewPage'
import { Product, ProductState } from '../types'
import { api } from '../api'

vi.mock('../api', () => ({
  api: {
    getOverview: vi.fn().mockResolvedValue([
      { id: 'p1', name: 'Content Co', icon_label: 'CC', color: '#7c3aed',
        running_ws: 2, warn_ws: 0, paused_ws: 1, pending_reviews: 1, running_agents: 0 },
    ]),
    updateWorkstream: vi.fn().mockResolvedValue({}),
  },
}))

const PRODUCTS: Product[] = [
  { id: 'p1', name: 'Content Co', icon_label: 'CC', color: '#7c3aed' },
]

const PRODUCT_STATES: Record<string, ProductState> = {
  p1: {
    workstreams: [
      { id: 1, name: 'Blog publisher', status: 'running', display_order: 0, last_run_at: '2026-05-03T10:00:00' },
      { id: 2, name: 'Email drip', status: 'paused', display_order: 1 },
    ],
    objectives: [], events: [], review_items: [], sessions: [], activeSessionId: null,
  },
}

describe('OverviewPage', () => {
  beforeEach(() => vi.clearAllMocks())

  it('renders product name', async () => {
    render(<OverviewPage products={PRODUCTS} productStates={PRODUCT_STATES} password="pw" onOpenProduct={vi.fn()} />)
    await waitFor(() => expect(screen.getByText('Content Co')).toBeInTheDocument())
  })

  it('renders workstream chips for the product', async () => {
    render(<OverviewPage products={PRODUCTS} productStates={PRODUCT_STATES} password="pw" onOpenProduct={vi.fn()} />)
    await waitFor(() => expect(screen.getByText('Blog publisher')).toBeInTheDocument())
    expect(screen.getByText('Email drip')).toBeInTheDocument()
  })

  it('shows stats from getOverview', async () => {
    render(<OverviewPage products={PRODUCTS} productStates={PRODUCT_STATES} password="pw" onOpenProduct={vi.fn()} />)
    await waitFor(() => expect(screen.getByText('2')).toBeInTheDocument()) // running_ws
  })

  it('calls onOpenProduct when Open workspace clicked', async () => {
    const onOpenProduct = vi.fn()
    render(<OverviewPage products={PRODUCTS} productStates={PRODUCT_STATES} password="pw" onOpenProduct={onOpenProduct} />)
    await waitFor(() => screen.getByText('Open workspace →'))
    screen.getByText('Open workspace →').click()
    expect(onOpenProduct).toHaveBeenCalledWith('p1')
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd ui && npm test -- OverviewPage
```
Expected: FAIL — `OverviewPage` not found

- [ ] **Step 3: Implement OverviewPage**

```tsx
// ui/src/components/OverviewPage.tsx
import { useEffect, useState } from 'react'
import { Product, ProductState, ProductOverview } from '../types'
import { api } from '../api'
import WorkstreamChip from './WorkstreamChip'

interface Props {
  products: Product[]
  productStates: Record<string, ProductState>
  password: string
  onOpenProduct: (productId: string) => void
}

export default function OverviewPage({ products, productStates, password, onOpenProduct }: Props) {
  const [overview, setOverview] = useState<ProductOverview[]>([])

  useEffect(() => {
    api.getOverview(password).then(setOverview).catch(() => {})
  }, [password])

  const totalRunning  = overview.reduce((n, p) => n + p.running_ws, 0)
  const totalReviews  = overview.reduce((n, p) => n + p.pending_reviews, 0)
  const totalAgents   = overview.reduce((n, p) => n + p.running_agents, 0)

  const handleStatusChange = (productId: string, wsId: number, status: 'running' | 'paused') => {
    // Optimistic update is handled by WorkstreamChip; parent re-sync happens via WebSocket
  }

  return (
    <div className="flex-1 overflow-y-auto bg-adj-base">
      <div className="max-w-4xl mx-auto px-6 py-5">

        {/* Page header */}
        <div className="mb-5">
          <h1 className="text-[15px] font-semibold text-adj-text-primary tracking-tight">Overview</h1>
          <p className="text-[11px] text-adj-text-faint mt-0.5">
            {new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })} · {products.length} product{products.length !== 1 ? 's' : ''}
          </p>
        </div>

        {/* Stats row */}
        <div className="grid grid-cols-3 gap-3 mb-6">
          {[
            { label: 'Workstreams', value: totalRunning, sub: 'running', color: 'text-green-400' },
            { label: 'Reviews', value: totalReviews, sub: 'pending', color: 'text-amber-400' },
            { label: 'Agents', value: totalAgents, sub: 'active', color: 'text-blue-400' },
          ].map(stat => (
            <div key={stat.label} className="bg-adj-panel border border-adj-border rounded-lg px-4 py-3">
              <div className="text-[10px] text-adj-text-faint uppercase tracking-widest mb-1">{stat.label}</div>
              <div className={`text-xl font-semibold ${stat.color}`}>{stat.value}</div>
              <div className="text-[10px] text-adj-text-faint mt-0.5">{stat.sub}</div>
            </div>
          ))}
        </div>

        {/* Product cards */}
        <div className="space-y-3">
          <div className="text-[10px] text-adj-text-faint uppercase tracking-widest mb-2">Products & Workstreams</div>
          {products.map(product => {
            const state = productStates[product.id]
            const workstreams = state?.workstreams ?? []
            return (
              <div key={product.id} className="bg-adj-panel border border-adj-border rounded-lg px-4 py-3">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-[13px] font-medium text-adj-text-primary">{product.name}</span>
                  <button
                    onClick={() => onOpenProduct(product.id)}
                    className="text-[10px] text-adj-text-faint bg-adj-elevated border border-adj-border rounded px-2 py-1 hover:text-adj-text-secondary transition-colors"
                  >
                    Open workspace →
                  </button>
                </div>
                {workstreams.length === 0 ? (
                  <p className="text-[11px] text-adj-text-faint">No workstreams</p>
                ) : (
                  <div className="flex flex-wrap gap-2">
                    {workstreams.map(ws => (
                      <WorkstreamChip
                        key={ws.id}
                        workstream={ws}
                        password={password}
                        onStatusChange={(wsId, status) => handleStatusChange(product.id, wsId, status)}
                      />
                    ))}
                  </div>
                )}
              </div>
            )
          })}
          {products.length === 0 && (
            <p className="text-[12px] text-adj-text-faint">No products yet.</p>
          )}
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd ui && npm test -- OverviewPage
```
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add ui/src/components/OverviewPage.tsx ui/src/__tests__/OverviewPage.test.tsx
git commit -m "feat: add OverviewPage with stats and workstream chips"
```

---

## Task 4: ProductPicker component

**Files:**
- Create: `ui/src/components/ProductPicker.tsx`
- Create: `ui/src/__tests__/ProductPicker.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// ui/src/__tests__/ProductPicker.test.tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import '@testing-library/jest-dom'
import ProductPicker from '../components/ProductPicker'
import { Product, ProductState } from '../types'

const PRODUCTS: Product[] = [
  { id: 'p1', name: 'Content Co', icon_label: 'CC', color: '#7c3aed' },
  { id: 'p2', name: 'Dev Studio', icon_label: 'DS', color: '#2563eb' },
]

const STATES: Record<string, ProductState> = {
  p1: { workstreams: [{ id: 1, name: 'Blog', status: 'running', display_order: 0 }], objectives: [], events: [], review_items: [], sessions: [], activeSessionId: null },
  p2: { workstreams: [], objectives: [], events: [], review_items: [], sessions: [], activeSessionId: null },
}

describe('ProductPicker', () => {
  it('renders all product names', () => {
    render(<ProductPicker products={PRODUCTS} productStates={STATES} onSelect={vi.fn()} onNewProduct={vi.fn()} />)
    expect(screen.getByText('Content Co')).toBeInTheDocument()
    expect(screen.getByText('Dev Studio')).toBeInTheDocument()
  })

  it('calls onSelect with product id when clicked', () => {
    const onSelect = vi.fn()
    render(<ProductPicker products={PRODUCTS} productStates={STATES} onSelect={onSelect} onNewProduct={vi.fn()} />)
    fireEvent.click(screen.getByText('Content Co').closest('div')!)
    expect(onSelect).toHaveBeenCalledWith('p1')
  })

  it('shows workstream count per product', () => {
    render(<ProductPicker products={PRODUCTS} productStates={STATES} onSelect={vi.fn()} onNewProduct={vi.fn()} />)
    expect(screen.getByText('1 workstream')).toBeInTheDocument()
    expect(screen.getByText('No workstreams')).toBeInTheDocument()
  })

  it('calls onNewProduct when + New product clicked', () => {
    const onNewProduct = vi.fn()
    render(<ProductPicker products={PRODUCTS} productStates={STATES} onSelect={vi.fn()} onNewProduct={onNewProduct} />)
    fireEvent.click(screen.getByText('+ New product'))
    expect(onNewProduct).toHaveBeenCalled()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd ui && npm test -- ProductPicker
```
Expected: FAIL — `ProductPicker` not found

- [ ] **Step 3: Implement ProductPicker**

```tsx
// ui/src/components/ProductPicker.tsx
import { Product, ProductState } from '../types'

interface Props {
  products: Product[]
  productStates: Record<string, ProductState>
  onSelect: (productId: string) => void
  onNewProduct: () => void
}

export default function ProductPicker({ products, productStates, onSelect, onNewProduct }: Props) {
  return (
    <div className="flex-1 overflow-y-auto bg-adj-base">
      <div className="max-w-2xl mx-auto px-6 py-5">

        <div className="flex items-center justify-between mb-5">
          <h1 className="text-[15px] font-semibold text-adj-text-primary tracking-tight">Products</h1>
          <button
            onClick={onNewProduct}
            className="text-[11px] text-adj-accent border border-adj-accent/40 bg-adj-accent/10 rounded-md px-3 py-1.5 hover:bg-adj-accent/20 transition-colors"
          >
            + New product
          </button>
        </div>

        <div className="space-y-2">
          {products.map(product => {
            const state = productStates[product.id]
            const wsCount = state?.workstreams.length ?? 0
            const runningCount = state?.workstreams.filter(w => w.status === 'running').length ?? 0
            return (
              <div
                key={product.id}
                onClick={() => onSelect(product.id)}
                className="bg-adj-panel border border-adj-border rounded-lg px-4 py-3 cursor-pointer hover:border-adj-accent/40 hover:bg-adj-elevated transition-colors flex items-center gap-4"
              >
                <div
                  className="w-9 h-9 rounded-lg flex items-center justify-center text-sm font-bold text-white flex-shrink-0"
                  style={{ backgroundColor: product.color }}
                >
                  {product.icon_label}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-[13px] font-medium text-adj-text-primary">{product.name}</div>
                  <div className="text-[11px] text-adj-text-faint mt-0.5">
                    {wsCount === 0 ? 'No workstreams' : `${wsCount} workstream${wsCount !== 1 ? 's' : ''}`}
                    {runningCount > 0 && <span className="ml-2 text-green-400">· {runningCount} running</span>}
                  </div>
                </div>
                <span className="text-adj-text-faint text-sm flex-shrink-0">›</span>
              </div>
            )
          })}
          {products.length === 0 && (
            <p className="text-[12px] text-adj-text-faint text-center py-8">No products yet. Create one to get started.</p>
          )}
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd ui && npm test -- ProductPicker
```
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add ui/src/components/ProductPicker.tsx ui/src/__tests__/ProductPicker.test.tsx
git commit -m "feat: add ProductPicker component"
```

---

## Task 5: ChiefPage component

**Files:**
- Create: `ui/src/components/ChiefPage.tsx`
- Create: `ui/src/__tests__/ChiefPage.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// ui/src/__tests__/ChiefPage.test.tsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import '@testing-library/jest-dom'
import ChiefPage from '../components/ChiefPage'
import { ReviewItem } from '../types'
import { api } from '../api'

vi.mock('../api', () => ({
  api: {
    getHCARuns: vi.fn().mockResolvedValue([
      { id: 47, triggered_by: 'schedule', run_at: '2026-05-03T09:52:00', status: 'complete',
        decisions: [], brief: '• Content Co on track\n• Dev Studio sprint review due Friday' },
    ]),
    getHCADirectives: vi.fn().mockResolvedValue([]),
    getHCAConfig: vi.fn().mockResolvedValue({ enabled: 1, schedule: 'every 1 hours', pa_run_threshold: 3, next_run_at: '2026-05-03T10:52:00', last_run_at: '2026-05-03T09:52:00', hca_slack_channel_id: '', hca_discord_channel_id: '', hca_telegram_chat_id: '' }),
    triggerHCA: vi.fn().mockResolvedValue({ queued: true }),
  },
}))

const REVIEWS: ReviewItem[] = [
  { id: 1, title: 'LinkedIn post', description: 'Q2 recap post draft', risk_label: 'Public', status: 'pending', created_at: '2026-05-03T09:00:00', action_type: 'social_post' },
]

describe('ChiefPage', () => {
  beforeEach(() => vi.clearAllMocks())

  it('renders the page heading', async () => {
    render(<ChiefPage password="pw" reviewItems={[]} onResolveReview={vi.fn()} onOpenSettings={vi.fn()} />)
    expect(screen.getByText('Chief Adjutant')).toBeInTheDocument()
  })

  it('renders pending review items', async () => {
    render(<ChiefPage password="pw" reviewItems={REVIEWS} onResolveReview={vi.fn()} onOpenSettings={vi.fn()} />)
    expect(screen.getByText('LinkedIn post')).toBeInTheDocument()
  })

  it('calls onResolveReview with approved when Approve clicked', async () => {
    const onResolveReview = vi.fn()
    render(<ChiefPage password="pw" reviewItems={REVIEWS} onResolveReview={onResolveReview} onOpenSettings={vi.fn()} />)
    fireEvent.click(screen.getByText('Approve'))
    expect(onResolveReview).toHaveBeenCalledWith(1, 'approved')
  })

  it('calls triggerHCA when Run now clicked', async () => {
    render(<ChiefPage password="pw" reviewItems={[]} onResolveReview={vi.fn()} onOpenSettings={vi.fn()} />)
    await waitFor(() => screen.getByText('Run now'))
    fireEvent.click(screen.getByText('Run now'))
    await waitFor(() => expect(api.triggerHCA).toHaveBeenCalledWith('pw'))
  })

  it('shows latest briefing after load', async () => {
    render(<ChiefPage password="pw" reviewItems={[]} onResolveReview={vi.fn()} onOpenSettings={vi.fn()} />)
    await waitFor(() => expect(screen.getByText(/Content Co on track/)).toBeInTheDocument())
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd ui && npm test -- ChiefPage
```
Expected: FAIL — `ChiefPage` not found

- [ ] **Step 3: Implement ChiefPage**

```tsx
// ui/src/components/ChiefPage.tsx
import { useEffect, useState } from 'react'
import { ReviewItem, HCARun, HCAConfig } from '../types'
import { api } from '../api'
import MarkdownContent from './MarkdownContent'

interface Props {
  password: string
  reviewItems: ReviewItem[]
  onResolveReview: (id: number, action: 'approved' | 'skipped') => void
  onOpenSettings: () => void
}

function relDate(ts: string) {
  const diff = Date.now() - new Date(ts.replace(' ', 'T') + (ts.includes('Z') ? '' : 'Z')).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
}

function relNext(ts: string | null) {
  if (!ts) return null
  const diff = new Date(ts.replace(' ', 'T') + (ts.includes('Z') ? '' : 'Z')).getTime() - Date.now()
  if (diff <= 0) return 'due now'
  const mins = Math.floor(diff / 60000)
  if (mins < 60) return `in ${mins}m`
  return `in ${Math.floor(mins / 60)}h`
}

const REVIEW_COLORS: Record<string, string> = {
  social_post:      'border-l-amber-500 bg-amber-950/10',
  hca_new_product:  'border-l-purple-500 bg-purple-950/10',
  send_email:       'border-l-red-400 bg-red-950/10',
}

export default function ChiefPage({ password, reviewItems, onResolveReview, onOpenSettings }: Props) {
  const [runs, setRuns]         = useState<HCARun[]>([])
  const [config, setConfig]     = useState<HCAConfig | null>(null)
  const [triggering, setTriggering] = useState(false)

  useEffect(() => {
    Promise.all([
      api.getHCARuns(password, 10),
      api.getHCAConfig(password),
    ]).then(([r, c]) => { setRuns(r); setConfig(c) }).catch(() => {})
  }, [password])

  const triggerRun = async () => {
    setTriggering(true)
    try { await api.triggerHCA(password) } finally { setTriggering(false) }
  }

  const latestRun  = runs[0] ?? null
  const pendingItems = reviewItems.filter(r => r.status === 'pending')

  return (
    <div className="flex-1 flex flex-col overflow-hidden bg-adj-base">

      {/* Page header */}
      <div className="flex items-center justify-between px-5 py-3.5 border-b border-adj-border flex-shrink-0">
        <div>
          <h1 className="text-[15px] font-semibold text-adj-text-primary tracking-tight">Chief Adjutant</h1>
          <p className="text-[11px] text-adj-text-faint mt-0.5">
            {config?.last_run_at ? `Last ran ${relDate(config.last_run_at)}` : 'Never run'}
            {config?.next_run_at ? ` · next ${relNext(config.next_run_at)}` : ''}
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={triggerRun}
            disabled={triggering}
            className="text-[11px] text-adj-accent border border-adj-accent/40 bg-adj-accent/10 rounded-md px-3 py-1.5 hover:bg-adj-accent/20 transition-colors disabled:opacity-50"
          >
            {triggering ? 'Queuing…' : 'Run now'}
          </button>
          <button
            onClick={onOpenSettings}
            className="text-[11px] text-adj-text-faint border border-adj-border bg-adj-elevated rounded-md px-3 py-1.5 hover:text-adj-text-secondary transition-colors"
          >
            Configure
          </button>
        </div>
      </div>

      {/* Two-column body */}
      <div className="flex flex-1 overflow-hidden">

        {/* Left: review queue */}
        <div className="flex-1 overflow-y-auto border-r border-adj-border px-5 py-4">
          <div className="flex items-center gap-2 mb-3">
            <span className="text-[10px] text-adj-text-faint uppercase tracking-widest">Pending Reviews</span>
            {pendingItems.length > 0 && (
              <span className="text-[9px] text-amber-400 bg-amber-950/30 border border-amber-900/40 rounded-full px-1.5 py-0.5 font-medium">
                {pendingItems.length}
              </span>
            )}
          </div>

          {pendingItems.length === 0 && (
            <p className="text-[12px] text-adj-text-faint">No pending reviews.</p>
          )}

          <div className="space-y-3">
            {pendingItems.map(item => (
              <div
                key={item.id}
                className={`bg-adj-panel border border-adj-border border-l-2 rounded-lg px-4 py-3 ${REVIEW_COLORS[item.action_type ?? ''] ?? 'border-l-adj-border'}`}
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className="text-[11px] font-medium text-adj-text-primary">{item.title}</span>
                  </div>
                  <span className="text-[10px] text-adj-text-faint">{relDate(item.created_at)}</span>
                </div>
                <p className="text-[11px] text-adj-text-secondary leading-relaxed mb-3 line-clamp-3">{item.description}</p>
                <div className="flex gap-2">
                  <button onClick={() => onResolveReview(item.id, 'approved')} className="text-[10px] text-green-400 bg-green-950/30 border border-green-900/40 rounded px-2.5 py-1 hover:bg-green-950/60 transition-colors">
                    Approve
                  </button>
                  <button onClick={() => onResolveReview(item.id, 'skipped')} className="text-[10px] text-adj-text-faint bg-adj-elevated border border-adj-border rounded px-2.5 py-1 hover:text-adj-text-secondary transition-colors">
                    Dismiss
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right: briefing + run history */}
        <div className="w-72 flex-shrink-0 overflow-y-auto px-4 py-4">

          <div className="text-[10px] text-adj-text-faint uppercase tracking-widest mb-2">Latest Briefing</div>
          {latestRun ? (
            <div className="bg-adj-panel border border-adj-border rounded-lg px-4 py-3 mb-4">
              <div className="text-[11px] text-adj-text-secondary leading-relaxed">
                <MarkdownContent content={latestRun.brief} />
              </div>
              <div className="text-[10px] text-adj-text-faint mt-2 pt-2 border-t border-adj-border">
                {relDate(latestRun.run_at)}
              </div>
            </div>
          ) : (
            <p className="text-[11px] text-adj-text-faint mb-4">No runs yet.</p>
          )}

          <div className="text-[10px] text-adj-text-faint uppercase tracking-widest mb-2">Run History</div>
          <div className="space-y-1.5">
            {runs.map(run => (
              <div key={run.id} className="bg-adj-panel border border-adj-border rounded-md px-3 py-2 flex items-center justify-between">
                <span className="text-[11px] text-adj-text-secondary">Run #{run.id}</span>
                <span className="text-[10px] text-adj-text-faint">{relDate(run.run_at)}</span>
              </div>
            ))}
            {runs.length === 0 && <p className="text-[11px] text-adj-text-faint">No run history.</p>}
          </div>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd ui && npm test -- ChiefPage
```
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add ui/src/components/ChiefPage.tsx ui/src/__tests__/ChiefPage.test.tsx
git commit -m "feat: add ChiefPage component (review queue + briefing)"
```

---

## Task 6: ApiKeysSettings component + SettingsPage grouped sidebar

**Files:**
- Create: `ui/src/components/settings/ApiKeysSettings.tsx`
- Modify: `ui/src/components/SettingsPage.tsx`
- Modify: `ui/src/components/settings/OverviewSettings.tsx` (remove API key section)

- [ ] **Step 1: Read OverviewSettings to find the API key section**

Read `ui/src/components/settings/OverviewSettings.tsx` and identify the block that renders Anthropic and OpenAI key inputs. Note the exact state vars and handlers used.

- [ ] **Step 2: Create ApiKeysSettings**

Extract the key input block into a new component. The API functions are `api.updateAnthropicKey(pw, key)` and `api.updateOpenAIKey(pw, key)` (both return `{ configured: boolean; masked: string }`).

```tsx
// ui/src/components/settings/ApiKeysSettings.tsx
import { useState } from 'react'
import { api } from '../../api'

interface Props { password: string }

export default function ApiKeysSettings({ password }: Props) {
  const [anthropicKey, setAnthropicKey] = useState('')
  const [openaiKey,    setOpenaiKey]    = useState('')
  const [saving,       setSaving]       = useState<'anthropic' | 'openai' | null>(null)
  const [saved,        setSaved]        = useState<'anthropic' | 'openai' | null>(null)

  const save = async (provider: 'anthropic' | 'openai') => {
    setSaving(provider)
    try {
      if (provider === 'anthropic') await api.updateAnthropicKey(password, anthropicKey)
      else                          await api.updateOpenAIKey(password, openaiKey)
      setSaved(provider)
      setTimeout(() => setSaved(null), 2000)
    } finally {
      setSaving(null)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-[15px] font-semibold text-adj-text-primary mb-1">API Keys</h2>
        <p className="text-[11px] text-adj-text-faint">Provider credentials for AI model access.</p>
      </div>

      {[
        { label: 'Anthropic', key: 'anthropic' as const, value: anthropicKey, setter: setAnthropicKey, placeholder: 'sk-ant-…' },
        { label: 'OpenAI', key: 'openai' as const, value: openaiKey, setter: setOpenaiKey, placeholder: 'sk-…', optional: true },
      ].map(({ label, key, value, setter, placeholder, optional }) => (
        <div key={key}>
          <label className="block text-[11px] text-adj-text-secondary mb-1.5">
            {label} {optional && <span className="text-adj-text-faint">(optional)</span>}
          </label>
          <div className="flex gap-2 max-w-md">
            <input
              type="password"
              value={value}
              onChange={e => setter(e.target.value)}
              placeholder={placeholder}
              className="flex-1 bg-adj-panel border border-adj-border rounded-lg px-3 py-2 text-[12px] text-adj-text-primary placeholder:text-adj-text-faint focus:outline-none focus:border-adj-accent/60"
            />
            <button
              onClick={() => save(key)}
              disabled={!value || saving === key}
              className="text-[11px] bg-adj-elevated border border-adj-border text-adj-text-secondary rounded-lg px-3 py-2 hover:border-adj-accent/40 disabled:opacity-40 transition-colors"
            >
              {saved === key ? '✓ Saved' : saving === key ? 'Saving…' : 'Save'}
            </button>
          </div>
        </div>
      ))}
    </div>
  )
}
```

- [ ] **Step 3: Remove API key block from OverviewSettings**

Open `ui/src/components/settings/OverviewSettings.tsx`. Delete the state vars, handlers, and JSX that handle Anthropic and OpenAI key inputs. Keep everything else (agent name, agent config).

- [ ] **Step 4: Restructure SettingsPage with grouped sidebar**

Replace the entire `SettingsPage.tsx` with the new two-panel layout. The new `Tab` type maps to the 5 groups × their items:

```tsx
// ui/src/components/SettingsPage.tsx
import { useState } from 'react'
import { Product, ProductState, Workstream, Objective } from '../types'
import OverviewSettings from './settings/OverviewSettings'
import ApiKeysSettings from './settings/ApiKeysSettings'
import TokenUsageSettings from './settings/TokenUsageSettings'
import AgentModelSettings from './settings/AgentModelSettings'
import ImageGenerationSettings from './settings/ImageGenerationSettings'
import ProductModelSettings from './settings/ProductModelSettings'
import ConnectionsSettings from './settings/ConnectionsSettings'
import GoogleOAuthSettings from './settings/GoogleOAuthSettings'
import IntegrationsSettings from './settings/IntegrationsSettings'
import SocialSettings from './settings/SocialSettings'
import AutonomySettings from './settings/AutonomySettings'
import ProductMCPSettings from './settings/ProductMCPSettings'
import ObjectivesSettings from './settings/ObjectivesSettings'
import HCASettings from './settings/HCASettings'
import GlobalMCPSettings from './settings/GlobalMCPSettings'
import OrchestratorSettings from './settings/OrchestratorSettings'
import SignalsSettings from './settings/SignalsSettings'
import TagsSettings from './settings/TagsSettings'

export type SettingsItem =
  | 'general-workspace' | 'general-api-keys' | 'general-token-usage'
  | 'models-agent' | 'models-image' | 'models-product'
  | 'connections-all' | 'connections-google' | 'connections-slack-discord' | 'connections-social' | 'connections-telegram'
  | 'products-autonomy' | 'products-mcp' | 'products-objectives'
  | 'system-chief' | 'system-global-mcp' | 'system-orchestrator' | 'system-signals' | 'system-tags'

// Keep old Tab as alias so App.tsx callers keep working until Task 9
export type Tab = SettingsItem

interface Group { label: string; items: { key: SettingsItem; label: string }[] }

const GROUPS: Group[] = [
  { label: 'Connections', items: [
    { key: 'connections-all',           label: 'All connections' },
    { key: 'connections-google',        label: 'Google' },
    { key: 'connections-slack-discord', label: 'Slack / Discord' },
    { key: 'connections-social',        label: 'Social' },
    { key: 'connections-telegram',      label: 'Telegram' },
  ]},
  { label: 'General', items: [
    { key: 'general-api-keys',    label: 'API Keys' },
    { key: 'general-token-usage', label: 'Token Usage' },
    { key: 'general-workspace',   label: 'Workspace' },
  ]},
  { label: 'Models', items: [
    { key: 'models-agent',   label: 'Agent default' },
    { key: 'models-image',   label: 'Image generation' },
    { key: 'models-product', label: 'Per-product' },
  ]},
  { label: 'Products', items: [
    { key: 'products-autonomy',   label: 'Autonomy' },
    { key: 'products-mcp',        label: 'MCP servers' },
    { key: 'products-objectives', label: 'Objectives' },
  ]},
  { label: 'System', items: [
    { key: 'system-chief',        label: 'Chief Adjutant' },
    { key: 'system-global-mcp',   label: 'Global MCP' },
    { key: 'system-orchestrator', label: 'Orchestrator' },
    { key: 'system-signals',      label: 'Signals' },
    { key: 'system-tags',         label: 'Tags' },
  ]},
]

interface Props {
  products: Product[]
  activeProductId: string
  productStates: Record<string, ProductState>
  password: string
  initialTab?: SettingsItem
  onClose: () => void
  onSwitchProduct: (id: string) => void
  onNewProduct: () => void
  onRefreshData: (productId: string) => void
  onWorkstreamUpdated: (wsId: number, patch: Partial<Workstream>) => void
  onObjectiveUpdated: (objId: number, patch: Partial<Objective>) => void
  onProductUpdated: (productId: string, updates: { name?: string; icon_label?: string; color?: string }) => void
  onProductDeleted: (productId: string) => void
}

export default function SettingsPage({
  products, activeProductId, productStates, password,
  initialTab = 'general-workspace',
  onClose, onSwitchProduct, onNewProduct, onRefreshData,
  onWorkstreamUpdated, onObjectiveUpdated, onProductUpdated, onProductDeleted,
}: Props) {
  const [active, setActive] = useState<SettingsItem>(initialTab)
  const activeProduct = products.find(p => p.id === activeProductId)
  const activeState   = productStates[activeProductId]

  const renderContent = () => {
    switch (active) {
      case 'general-workspace':    return <OverviewSettings products={products} activeProductId={activeProductId} password={password} onProductUpdated={onProductUpdated} onProductDeleted={onProductDeleted} onNewProduct={onNewProduct} />
      case 'general-api-keys':     return <ApiKeysSettings password={password} />
      case 'general-token-usage':  return <TokenUsageSettings password={password} />
      case 'models-agent':         return <AgentModelSettings password={password} />
      case 'models-image':         return <ImageGenerationSettings password={password} />
      case 'models-product':       return <ProductModelSettings products={products} activeProductId={activeProductId} password={password} onSwitchProduct={onSwitchProduct} />
      case 'connections-all':      return <ConnectionsSettings products={products} activeProductId={activeProductId} password={password} onSwitchProduct={onSwitchProduct} />
      case 'connections-google':   return <GoogleOAuthSettings password={password} />
      case 'connections-slack-discord': return <IntegrationsSettings password={password} />
      case 'connections-social':   return <SocialSettings password={password} />
      case 'connections-telegram': return <IntegrationsSettings password={password} />
      case 'products-autonomy':    return <AutonomySettings products={products} activeProductId={activeProductId} password={password} onSwitchProduct={onSwitchProduct} />
      case 'products-mcp':         return <ProductMCPSettings products={products} activeProductId={activeProductId} password={password} onSwitchProduct={onSwitchProduct} />
      case 'products-objectives':  return activeState ? <ObjectivesSettings productId={activeProductId} objectives={activeState.objectives} password={password} onObjectiveUpdated={onObjectiveUpdated} onRefresh={() => onRefreshData(activeProductId)} /> : null
      case 'system-chief':         return <HCASettings password={password} />
      case 'system-global-mcp':    return <GlobalMCPSettings password={password} />
      case 'system-orchestrator':  return activeProduct ? <OrchestratorSettings product={activeProduct} password={password} /> : null
      case 'system-signals':       return <SignalsSettings password={password} />
      case 'system-tags':          return <TagsSettings password={password} />
      default:                     return null
    }
  }

  return (
    <div className="flex flex-1 overflow-hidden bg-adj-base">

      {/* Grouped sidebar */}
      <div className="w-44 bg-adj-surface border-r border-adj-border overflow-y-auto flex-shrink-0 py-3">
        {GROUPS.map(group => (
          <div key={group.label} className="mb-1 px-3">
            <div className="text-[9px] text-adj-text-faint uppercase tracking-widest px-1 mb-1">{group.label}</div>
            {group.items.map(item => (
              <button
                key={item.key}
                onClick={() => setActive(item.key)}
                className={`w-full text-left text-[11px] rounded-md px-2 py-1.5 mb-0.5 transition-colors ${
                  active === item.key
                    ? 'bg-adj-elevated border border-adj-border text-adj-text-primary'
                    : 'text-adj-text-faint hover:text-adj-text-secondary hover:bg-adj-elevated/50'
                }`}
              >
                {item.label}
              </button>
            ))}
            <div className="h-px bg-adj-border my-2" />
          </div>
        ))}
      </div>

      {/* Content area */}
      <div className="flex-1 overflow-y-auto px-6 py-5">
        {renderContent()}
      </div>
    </div>
  )
}
```

- [ ] **Step 5: Run full test suite to check for regressions**

```bash
cd ui && npm test
```
Expected: existing settings tests pass; no new failures from the Tab → SettingsItem rename (the `Tab` alias preserves compatibility)

- [ ] **Step 6: Commit**

```bash
git add ui/src/components/SettingsPage.tsx ui/src/components/settings/ApiKeysSettings.tsx ui/src/components/settings/OverviewSettings.tsx
git commit -m "feat: restructure SettingsPage with grouped alphabetical sidebar"
```

---

## Task 7: SessionsPanel refactor

**Files:**
- Modify: `ui/src/components/SessionsPanel.tsx`

- [ ] **Step 1: Read the current SessionsPanel**

Read `ui/src/components/SessionsPanel.tsx` in full to understand current props and JSX.

- [ ] **Step 2: Add productName and liveAgents props, restructure layout**

The new SessionsPanel renders: product header (name + session count) at top; session list in the middle; live agents pinned at the bottom. The `LiveAgents` component data (running agents) is passed in as a prop instead of rendered separately in App.

Update the interface to add:

```tsx
interface RunningAgent {
  productId: string
  productName: string
  label: string        // e.g. "Research"
  elapsedSeconds: number
}

interface Props {
  productName: string       // NEW
  sessionCount: number      // NEW — total sessions for this product
  sessions: Session[]
  activeSessionId: string | null
  liveAgents: RunningAgent[]  // NEW — passed from App.tsx
  onSwitch:  (sessionId: string) => void
  onCreate:  (name: string) => void
  onRename:  (sessionId: string, name: string) => void
  onDelete:  (sessionId: string) => void
}
```

Add product header block at the top of the return:
```tsx
{/* Product header */}
<div className="px-3 py-3 border-b border-adj-border flex-shrink-0">
  <div className="text-[13px] font-semibold text-adj-text-primary truncate">{productName}</div>
  <div className="text-[10px] text-adj-text-faint mt-0.5">{sessionCount} session{sessionCount !== 1 ? 's' : ''}</div>
</div>
```

Pin live agents at the bottom (after the session list, inside the flex column):
```tsx
{liveAgents.length > 0 && (
  <div className="border-t border-adj-border px-3 py-2 flex-shrink-0">
    <div className="text-[9px] text-adj-text-faint uppercase tracking-widest mb-1.5">Live agents</div>
    {liveAgents.map((agent, i) => (
      <div key={i} className="flex items-center gap-1.5 text-[10px] text-green-400 mb-1">
        <span className="animate-spin">⟳</span>
        <span>{agent.label}</span>
        <span className="text-adj-text-faint ml-auto">{Math.floor(agent.elapsedSeconds / 60)}:{String(agent.elapsedSeconds % 60).padStart(2, '0')}</span>
      </div>
    ))}
  </div>
)}
```

- [ ] **Step 3: Update SessionsPanel test to cover new props**

Open `ui/src/__tests__/` — there is no `SessionsPanel.test.tsx` yet. Skip if absent; just run the full suite.

- [ ] **Step 4: Run full test suite**

```bash
cd ui && npm test
```
Expected: all tests pass (App.tsx not yet wired — SessionsPanel is not yet called with new props, so TypeScript errors will surface in Task 9)

- [ ] **Step 5: Commit**

```bash
git add ui/src/components/SessionsPanel.tsx
git commit -m "feat: add productName header and liveAgents strip to SessionsPanel"
```

---

## Task 8: DirectiveBar — collapse templates to ⚡ toggle

**Files:**
- Modify: `ui/src/components/DirectiveBar.tsx`

- [ ] **Step 1: Read the current DirectiveBar**

Read `ui/src/components/DirectiveBar.tsx` in full. Note how `DirectiveTemplates` is NOT inside DirectiveBar currently — it's rendered in App.tsx above DirectiveBar. The plan is to move it inside DirectiveBar with a toggle.

- [ ] **Step 2: Add templatesProductId + templatesPassword props and ⚡ toggle**

Add to the Props interface:
```tsx
templatesProductId: string
templatesPassword: string
```

Add state inside the component:
```tsx
const [showTemplates, setShowTemplates] = useState(false)
```

Import DirectiveTemplates inside DirectiveBar:
```tsx
import DirectiveTemplates from './DirectiveTemplates'
```

In the JSX, immediately before the `<textarea>` wrapper, add the slide-up panel:
```tsx
{showTemplates && (
  <div className="mb-2 border border-adj-border rounded-lg overflow-hidden">
    <DirectiveTemplates
      productId={templatesProductId}
      password={templatesPassword}
      onSelect={content => { setValue(content); setShowTemplates(false) }}
    />
  </div>
)}
```

In the button row next to Send, add the ⚡ toggle before the Send button:
```tsx
<button
  type="button"
  onClick={() => setShowTemplates(v => !v)}
  title="Templates"
  className={`w-8 h-8 flex items-center justify-center rounded-lg border transition-colors text-sm ${
    showTemplates
      ? 'bg-adj-accent/20 border-adj-accent/50 text-adj-accent'
      : 'bg-adj-elevated border-adj-border text-adj-text-faint hover:text-adj-text-secondary'
  }`}
>
  ⚡
</button>
```

- [ ] **Step 3: Run full test suite**

```bash
cd ui && npm test
```
Expected: `DirectiveTemplates.test.tsx` and `DirectiveBar`-related tests pass

- [ ] **Step 4: Commit**

```bash
git add ui/src/components/DirectiveBar.tsx
git commit -m "feat: move DirectiveTemplates into DirectiveBar as collapsible ⚡ panel"
```

---

## Task 9: App.tsx routing overhaul

**Files:**
- Modify: `ui/src/App.tsx`

This is the largest task. Replace the boolean-flag navigation system with `navSection` + `NavRail`.

- [ ] **Step 1: Add navSection state and remove old flags**

In the state declarations block, replace:
```tsx
const [settingsOpen,    setSettingsOpen]    = useState(false)
const [settingsTab,     setSettingsTab]     = useState<SettingsTab>('overview')
const [showOverview,    setShowOverview]    = useState(false)
const [showHCA,         setShowHCA]         = useState(false)
const [globalViewMode,  setGlobalViewMode]  = useState<'chat' | 'overview'>('overview')
```

With:
```tsx
type NavSection = 'overview' | 'products' | 'chief' | 'settings'
const [navSection,      setNavSection]      = useState<NavSection>('overview')
const [settingsItem,    setSettingsItem]    = useState<SettingsItem>('general-workspace')
```

- [ ] **Step 2: Update localStorage persistence**

Replace all `adjutant_last_view` reads/writes that referenced `showOverview`, `settingsOpen`, `settingsTab` with `navSection` and `settingsItem`.

In the `init` message handler, replace the saved-state restoration block with:
```tsx
const targetSection: NavSection = saved?.navSection ?? 'overview'
const targetProduct = saved?.productId
setNavSection(targetSection)
if (targetProduct && msg.products.some((p: { id: string }) => p.id === targetProduct)) {
  setActiveProductId(targetProduct)
  ws.send(JSON.stringify({ type: 'switch_product', product_id: targetProduct }))
} else if (msg.products[0]?.id) {
  setActiveProductId(msg.products[0].id)
  ws.send(JSON.stringify({ type: 'switch_product', product_id: msg.products[0].id }))
}
if (saved?.settingsItem) setSettingsItem(saved.settingsItem as SettingsItem)
```

- [ ] **Step 3: Replace openSettings helper**

Replace:
```tsx
const openSettings = useCallback((tab: string = 'overview') => {
  setSettingsTab(tab as SettingsTab)
  setSettingsOpen(true)
  setShowHCA(false)
  // ...
}, [])
```

With:
```tsx
const openSettings = useCallback((item: string = 'general-workspace') => {
  setSettingsItem(item as SettingsItem)
  setNavSection('settings')
  const current = (() => { try { return JSON.parse(localStorage.getItem('adjutant_last_view') ?? 'null') } catch { return null } })()
  localStorage.setItem('adjutant_last_view', JSON.stringify({ ...current, navSection: 'settings', settingsItem: item }))
}, [])
```

- [ ] **Step 4: Derive liveAgents before the return**

Above the `return (...)`, compute the `liveAgents` array used by SessionsPanel:

```tsx
const liveAgents = (activeState.events ?? [])
  .filter(e => e.status === 'running')
  .map(e => ({
    productId: activeProductId,
    productName: activeProduct?.name ?? '',
    label: e.agent_type.charAt(0).toUpperCase() + e.agent_type.slice(1),
    elapsedSeconds: Math.floor((Date.now() - new Date(e.created_at.replace(' ', 'T') + 'Z').getTime()) / 1000),
  }))
```

- [ ] **Step 5: Replace the header + body with NavRail layout**

Replace the entire `return (...)` JSX (from `<div className="flex flex-col h-full ...">` to the closing `</div>`) with the new layout:

```tsx
return (
  <div className="flex h-full bg-adj-base text-adj-text-primary overflow-hidden">

    {/* Left nav rail */}
    <NavRail
      section={navSection}
      reviewBadgeCount={pendingReviewCount}
      agentInitial={agentName[0]?.toUpperCase() ?? 'A'}
      onNavigate={section => {
        setNavSection(section)
        localStorage.setItem('adjutant_last_view', JSON.stringify({ navSection: section, productId: activeProductId }))
      }}
    />

    {/* Main content */}
    <div className="flex flex-col flex-1 overflow-hidden">

      {/* Error banner */}
      {errorBanner && (
        <div className="flex items-center gap-3 px-4 py-2.5 bg-red-950/60 border-b border-red-900/60 text-red-300 text-sm flex-shrink-0">
          <span className="text-red-400 flex-shrink-0">⚠</span>
          <span className="flex-1 font-mono text-xs leading-relaxed">{errorBanner}</span>
          <button onClick={() => setErrorBanner(null)} className="flex-shrink-0 text-red-500 hover:text-red-300 text-base leading-none">×</button>
        </div>
      )}

      {/* Section routing */}
      {navSection === 'overview' && (
        <OverviewPage
          products={products}
          productStates={productStates}
          password={pw}
          onOpenProduct={productId => {
            switchProduct(productId)
            setNavSection('products')
          }}
        />
      )}

      {navSection === 'products' && !activeProductId && (
        <ProductPicker
          products={products}
          productStates={productStates}
          onSelect={productId => { switchProduct(productId) }}
          onNewProduct={() => setWizardOpen(true)}
        />
      )}

      {navSection === 'products' && activeProductId && (
        <div className="flex flex-1 overflow-hidden">
          <SessionsPanel
            productName={activeProduct?.name ?? ''}
            sessionCount={activeState.sessions.length}
            sessions={activeState.sessions}
            activeSessionId={activeState.activeSessionId}
            liveAgents={liveAgents}
            onCreate={createSession}
            onSwitch={switchSession}
            onRename={renameSession}
            onDelete={deleteSession}
          />
          <div className="flex flex-col flex-1 overflow-hidden">
            {/* Session header */}
            <div className="flex items-center justify-between px-4 py-2.5 border-b border-adj-border flex-shrink-0">
              <div>
                <span className="text-[13px] font-medium text-adj-text-primary">
                  {activeState.sessions.find(s => s.id === activeState.activeSessionId)?.name ?? 'Session'}
                </span>
              </div>
              <div className="flex gap-2">
                <button onClick={() => setNotesOpen(o => !o)} className="text-[10px] text-adj-text-faint bg-adj-elevated border border-adj-border rounded px-2 py-1 hover:text-adj-text-secondary transition-colors">📝 Notes</button>
                <button onClick={() => setHistoryOpen(o => !o)} className="text-[10px] text-adj-text-faint bg-adj-elevated border border-adj-border rounded px-2 py-1 hover:text-adj-text-secondary transition-colors">📜 History</button>
              </div>
            </div>
            {/* Activity feed */}
            <ActivityFeed
              events={activeState.events}
              directives={directives[activeProductId] ?? []}
              agentMessages={agentMessages[activeProductId] ?? []}
              agentDraft={agentDraftByProduct[activeProductId] ?? ''}
              agentName={agentName}
              reviewItems={activeState.review_items}
              onApprove={id => resolveReview(id, 'approved')}
              onSkip={id => resolveReview(id, 'skipped')}
            />
            {/* Directive bar (templates now inside) */}
            <DirectiveBar
              onSend={sendDirective}
              disabled={connState !== 'ready'}
              productName={activeProduct?.name ?? 'this product'}
              agentName={agentName}
              prefill={directivePrefill}
              onPrefillConsumed={() => setDirectivePrefill('')}
              password={pw}
              templatesProductId={activeProductId}
              templatesPassword={pw}
            />
          </div>
        </div>
      )}

      {navSection === 'chief' && (
        <ChiefPage
          password={pw}
          reviewItems={Object.values(productStates).flatMap(s => s.review_items)}
          onResolveReview={resolveReview}
          onOpenSettings={() => openSettings('system-chief')}
        />
      )}

      {navSection === 'settings' && (
        <SettingsPage
          products={products}
          activeProductId={activeProductId}
          productStates={productStates}
          password={pw}
          initialTab={settingsItem}
          onClose={() => setNavSection('overview')}
          onSwitchProduct={switchProduct}
          onNewProduct={() => { setNavSection('overview'); setWizardOpen(true) }}
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
          onProductUpdated={(productId, updates) =>
            setProducts(prev => prev.map(p => p.id === productId ? { ...p, ...updates } : p))
          }
          onProductDeleted={productId => {
            setProducts(prev => prev.filter(p => p.id !== productId))
            setProductStates(prev => { const next = { ...prev }; delete next[productId]; return next })
            if (activeProductId === productId) setActiveProductId('')
            setNavSection('overview')
          }}
        />
      )}
    </div>

    {/* Drawers (unchanged) */}
    {notesOpen && <NotesDrawer productId={activeProductId} password={pw} onClose={() => setNotesOpen(false)} />}
    {historyOpen && <DirectiveHistoryDrawer productId={activeProductId} password={pw} onClose={() => setHistoryOpen(false)} />}
    {wizardOpen && <ProductWizard onClose={() => setWizardOpen(false)} onLaunch={(name, desc, goal) => { launchProduct(name, desc, goal); setWizardOpen(false) }} />}
  </div>
)
```

- [ ] **Step 5: Update imports in App.tsx**

Add imports for new components; remove imports for retired ones:

Add:
```tsx
import NavRail from './components/NavRail'
import OverviewPage from './components/OverviewPage'
import ProductPicker from './components/ProductPicker'
import ChiefPage from './components/ChiefPage'
import { SettingsItem } from './components/SettingsPage'
```

Remove:
```tsx
import ProductDropdown from './components/ProductDropdown'  // DELETE
import StatusStrip from './components/StatusStrip'          // DELETE
import OverviewPanel from './components/OverviewPanel'      // DELETE
import HCABriefingPanel from './components/HCABriefingPanel' // DELETE
import LiveAgents from './components/LiveAgents'            // DELETE
import DirectiveTemplates from './components/DirectiveTemplates' // DELETE (now inside DirectiveBar)
import SettingsPage, { Tab as SettingsTab } from './components/SettingsPage'  // CHANGE TO:
import SettingsPage from './components/SettingsPage'
```

Also remove the `pendingWizardRef` usage that referenced the old `launch_wizard_active` path if present; remove `globalViewMode` state; remove `openSettings` tab references to old tab names.

- [ ] **Step 6: Fix the pendingReviewCount variable**

Replace `hcaPendingCount` (which only counted `hca_new_product`) with all pending reviews:
```tsx
const pendingReviewCount = Object.values(productStates)
  .flatMap(s => s.review_items)
  .filter(r => r.status === 'pending').length
```

- [ ] **Step 7: Build to check TypeScript**

```bash
cd ui && npm run build
```
Expected: build succeeds with no TypeScript errors. Fix any type errors that appear (they will be related to prop mismatches from the SessionsPanel change in Task 7 or SettingsPage Tab→SettingsItem rename).

- [ ] **Step 8: Run full test suite**

```bash
cd ui && npm test
```
Expected: all tests pass

- [ ] **Step 9: Commit**

```bash
git add ui/src/App.tsx
git commit -m "feat: replace header/flag nav with NavRail + navSection routing"
```

---

## Task 10: Remove retired components

**Files:**
- Delete: `ui/src/components/StatusStrip.tsx`
- Delete: `ui/src/components/OverviewPanel.tsx`
- Delete: `ui/src/components/HCABriefingPanel.tsx`
- Delete: `ui/src/components/ProductDropdown.tsx`
- Delete: `ui/src/components/LiveAgents.tsx` (functionality absorbed into SessionsPanel)
- Delete: `ui/src/__tests__/StatusStrip.test.tsx`
- Delete: `ui/src/__tests__/OverviewPanel.test.tsx`
- Delete: `ui/src/__tests__/HCABriefingPanel.test.tsx`
- Delete: `ui/src/__tests__/ProductDropdown.test.tsx`

- [ ] **Step 1: Verify none of the retired files are imported anywhere**

```bash
grep -r "StatusStrip\|OverviewPanel\|HCABriefingPanel\|ProductDropdown\|LiveAgents" ui/src --include="*.tsx" --include="*.ts" -l
```
Expected: no files listed (Task 9 removed all imports)

If any files are listed, remove the remaining imports before proceeding.

- [ ] **Step 2: Delete the files**

```bash
rm ui/src/components/StatusStrip.tsx \
   ui/src/components/OverviewPanel.tsx \
   ui/src/components/HCABriefingPanel.tsx \
   ui/src/components/ProductDropdown.tsx \
   ui/src/components/LiveAgents.tsx \
   ui/src/__tests__/StatusStrip.test.tsx \
   ui/src/__tests__/OverviewPanel.test.tsx \
   ui/src/__tests__/HCABriefingPanel.test.tsx \
   ui/src/__tests__/ProductDropdown.test.tsx
```

- [ ] **Step 3: Build to confirm no dangling imports**

```bash
cd ui && npm run build
```
Expected: clean build

- [ ] **Step 4: Run full test suite**

```bash
cd ui && npm test
```
Expected: all tests pass

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore: remove retired components (StatusStrip, OverviewPanel, HCABriefingPanel, ProductDropdown, LiveAgents)"
```
