// ui/src/__tests__/WorkstreamsPanel.test.tsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import '@testing-library/jest-dom'
import WorkstreamsPanel from '../components/WorkstreamsPanel'
import { Workstream } from '../types'
import { api } from '../api'

vi.mock('../api', () => ({
  api: {
    updateWorkstream: vi.fn().mockResolvedValue(undefined),
    triggerWorkstreamRun: vi.fn().mockResolvedValue({ queued: false }),
  },
}))

const WORKSTREAMS: Workstream[] = [
  { id: 1, name: 'Marketing', status: 'running', display_order: 0 },
  { id: 2, name: 'Growth',    status: 'warn',    display_order: 1 },
  { id: 3, name: 'Content',   status: 'paused',  display_order: 2 },
]

const WS_SCHEDULED: Workstream[] = [
  {
    id: 10, name: 'Growth', status: 'running', display_order: 0,
    mission: 'Research growth tactics', schedule: 'daily',
    next_run_at: '2099-12-31T09:00:00', last_run_at: null,
  },
  {
    id: 11, name: 'Outreach', status: 'paused', display_order: 1,
    mission: '', schedule: 'weekly',
    next_run_at: null, last_run_at: null,
  },
]

const DEFAULT_PROPS = {
  workstreams: WS_SCHEDULED,
  password: 'test-pw',
  onWorkstreamUpdated: vi.fn(),
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('WorkstreamsPanel — basic rendering', () => {
  it('renders all workstream names', () => {
    render(<WorkstreamsPanel {...DEFAULT_PROPS} workstreams={WORKSTREAMS} />)
    expect(screen.getByText('Marketing')).toBeInTheDocument()
    expect(screen.getByText('Growth')).toBeInTheDocument()
    expect(screen.getByText('Content')).toBeInTheDocument()
  })
})

describe('WorkstreamsPanel — schedule display', () => {
  it('shows schedule label for scheduled workstreams', () => {
    render(<WorkstreamsPanel {...DEFAULT_PROPS} />)
    expect(screen.getByText('daily')).toBeInTheDocument()
  })

  it('shows next-run countdown for scheduled workstreams', () => {
    render(<WorkstreamsPanel {...DEFAULT_PROPS} />)
    expect(screen.getByText(/^in /)).toBeInTheDocument()
  })
})

describe('WorkstreamsPanel — run button', () => {
  it('calls api.triggerWorkstreamRun with workstream id when play button clicked', async () => {
    render(<WorkstreamsPanel {...DEFAULT_PROPS} />)
    fireEvent.click(screen.getAllByTitle('Run now')[0])
    await waitFor(() => {
      expect(api.triggerWorkstreamRun).toHaveBeenCalledWith('test-pw', 10)
    })
  })

  it('does not show play button for workstream without a mission', () => {
    render(<WorkstreamsPanel {...DEFAULT_PROPS} />)
    // Only one play button should exist — for WS_SCHEDULED[0] (Growth, has mission)
    // WS_SCHEDULED[1] (Outreach, mission: '') should NOT have one
    const playButtons = screen.queryAllByTitle('Run now')
    expect(playButtons).toHaveLength(1)
  })
})

describe('WorkstreamsPanel — inline edit', () => {
  it('clicking gear opens edit form with prepopulated fields', () => {
    render(<WorkstreamsPanel {...DEFAULT_PROPS} />)
    fireEvent.click(screen.getAllByTitle('Edit workstream')[0])
    expect(screen.getByDisplayValue('Growth')).toBeInTheDocument()
    expect(screen.getByDisplayValue('Research growth tactics')).toBeInTheDocument()
    // schedule select should show 'daily'
    expect((screen.getByRole('combobox') as HTMLSelectElement).value).toBe('daily')
  })

  it('clicking cancel closes the form without calling api', () => {
    render(<WorkstreamsPanel {...DEFAULT_PROPS} />)
    fireEvent.click(screen.getAllByTitle('Edit workstream')[0])
    fireEvent.click(screen.getByText('Cancel'))
    expect(screen.queryByText('Save')).not.toBeInTheDocument()
    expect(api.updateWorkstream).not.toHaveBeenCalled()
  })

  it('pressing Escape closes the form without calling api', () => {
    render(<WorkstreamsPanel {...DEFAULT_PROPS} />)
    fireEvent.click(screen.getAllByTitle('Edit workstream')[0])
    fireEvent.keyDown(window, { key: 'Escape' })
    expect(screen.queryByText('Save')).not.toBeInTheDocument()
    expect(api.updateWorkstream).not.toHaveBeenCalled()
  })

  it('clicking Save calls api.updateWorkstream and onWorkstreamUpdated', async () => {
    const onWorkstreamUpdated = vi.fn()
    render(<WorkstreamsPanel {...DEFAULT_PROPS} onWorkstreamUpdated={onWorkstreamUpdated} />)
    fireEvent.click(screen.getAllByTitle('Edit workstream')[0])

    // Change the name
    fireEvent.change(screen.getByDisplayValue('Growth'), { target: { value: 'Growth v2' } })
    fireEvent.click(screen.getByText('Save'))

    await waitFor(() => {
      expect(api.updateWorkstream).toHaveBeenCalledWith('test-pw', 10, {
        name: 'Growth v2',
        schedule: 'daily',
        mission: 'Research growth tactics',
      })
      expect(onWorkstreamUpdated).toHaveBeenCalledWith(10, {
        name: 'Growth v2',
        schedule: 'daily',
        mission: 'Research growth tactics',
      })
    })
    // form should close after save
    expect(screen.queryByText('Save')).not.toBeInTheDocument()
  })

  it('opening gear on a second row closes the first', () => {
    render(<WorkstreamsPanel {...DEFAULT_PROPS} />)
    const gears = screen.getAllByTitle('Edit workstream')
    fireEvent.click(gears[0]) // open first
    expect(screen.getByDisplayValue('Growth')).toBeInTheDocument()
    fireEvent.click(gears[1]) // open second — first should close
    expect(screen.queryByDisplayValue('Growth')).not.toBeInTheDocument()
    expect(screen.getByDisplayValue('Outreach')).toBeInTheDocument()
  })
})
