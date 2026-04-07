// ui/src/__tests__/WorkstreamsPanel.test.tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import '@testing-library/jest-dom'
import WorkstreamsPanel from '../components/WorkstreamsPanel'
import { Workstream, Objective } from '../types'

const WORKSTREAMS: Workstream[] = [
  { id: 1, name: 'Marketing', status: 'running', display_order: 0 },
  { id: 2, name: 'Growth',    status: 'warn',    display_order: 1 },
  { id: 3, name: 'Content',   status: 'paused',  display_order: 2 },
]

const OBJECTIVES: Objective[] = [
  { id: 1, text: 'Drive 50 trial signups', progress_current: 23, progress_target: 50,  display_order: 0 },
  { id: 2, text: 'Publish 4 SEO posts',    progress_current: 1,  progress_target: 4,   display_order: 1 },
  { id: 3, text: 'Build outreach list',    progress_current: 87, progress_target: null, display_order: 2 },
]

const WS_SCHEDULED: Workstream[] = [
  {
    id: 10, name: 'Growth', status: 'running', display_order: 0,
    mission: 'Research growth tactics', schedule: 'daily',
    next_run_at: '2099-12-31T09:00:00', last_run_at: null,
  },
  {
    id: 11, name: 'Outreach', status: 'paused', display_order: 1,
    mission: '', schedule: 'manual', next_run_at: null, last_run_at: null,
  },
]

describe('WorkstreamsPanel', () => {
  it('renders all workstream names', () => {
    render(<WorkstreamsPanel workstreams={WORKSTREAMS} objectives={OBJECTIVES} />)
    expect(screen.getByText('Marketing')).toBeInTheDocument()
    expect(screen.getByText('Growth')).toBeInTheDocument()
    expect(screen.getByText('Content')).toBeInTheDocument()
  })

  it('renders objectives with progress', () => {
    render(<WorkstreamsPanel workstreams={WORKSTREAMS} objectives={OBJECTIVES} />)
    expect(screen.getByText('Drive 50 trial signups')).toBeInTheDocument()
    expect(screen.getByText('23 / 50')).toBeInTheDocument()
  })

  it('renders open-ended objective without target', () => {
    render(<WorkstreamsPanel workstreams={WORKSTREAMS} objectives={OBJECTIVES} />)
    expect(screen.getByText('Build outreach list')).toBeInTheDocument()
    expect(screen.getByText('87 so far')).toBeInTheDocument()
  })
})

describe('WorkstreamsPanel — schedule & run button', () => {
  it('shows schedule label for scheduled workstreams', () => {
    render(<WorkstreamsPanel workstreams={WS_SCHEDULED} objectives={[]} />)
    expect(screen.getByText('daily')).toBeInTheDocument()
  })

  it('shows next-run countdown for scheduled workstreams', () => {
    render(<WorkstreamsPanel workstreams={WS_SCHEDULED} objectives={[]} />)
    // next_run_at is in 2099 so it should say "in X..." (years in the future)
    expect(screen.getByText(/^in /)).toBeInTheDocument()
  })

  it('calls onRunNow with workstream id when run button clicked', () => {
    const onRunNow = vi.fn()
    render(<WorkstreamsPanel workstreams={WS_SCHEDULED} objectives={[]} onRunNow={onRunNow} />)
    // Run button for Growth (has mission) — use getByTitle
    fireEvent.click(screen.getAllByTitle('Run now')[0])
    expect(onRunNow).toHaveBeenCalledWith(10)
  })
})
