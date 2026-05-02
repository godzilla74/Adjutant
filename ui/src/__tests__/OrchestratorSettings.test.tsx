import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import '@testing-library/jest-dom'
import OrchestratorSettings from '../components/settings/OrchestratorSettings'

const mockConfig = vi.hoisted(() => ({
  product_id: 'p1',
  enabled: 0,
  schedule: 'daily at 8am',
  signal_threshold: 5,
  next_run_at: null,
  autonomy_settings: {
    route_signal: 'autonomous',
    update_mission: 'autonomous',
    update_schedule: 'autonomous',
    update_subscriptions: 'autonomous',
    create_objective: 'autonomous',
    consume_signal: 'autonomous',
    pause_workstream: 'approval_required',
    create_workstream: 'approval_required',
    external_action: 'approval_required',
    capability_gap: 'autonomous',
  },
}))

vi.mock('../api', () => ({
  api: {
    getOrchestratorConfig: vi.fn().mockResolvedValue(mockConfig),
    updateOrchestratorConfig: vi.fn().mockResolvedValue(mockConfig),
  },
}))

beforeEach(() => {
  vi.clearAllMocks()
})

describe('OrchestratorSettings', () => {
  it('renders enable toggle and schedule input', async () => {
    render(<OrchestratorSettings productId="p1" password="pw" />)
    await waitFor(() => screen.getByText(/product adjutant/i))
    expect(screen.getByRole('checkbox')).toBeInTheDocument()
    expect(screen.getByDisplayValue('daily at 8am')).toBeInTheDocument()
  })

  it('renders all 10 autonomy action rows', async () => {
    render(<OrchestratorSettings productId="p1" password="pw" />)
    await waitFor(() => screen.getByText(/route signal/i))
    expect(screen.getByText(/pause workstream/i)).toBeInTheDocument()
    expect(screen.getByText(/create workstream/i)).toBeInTheDocument()
  })

  it('calls updateOrchestratorConfig on save', async () => {
    const { api } = await import('../api')
    render(<OrchestratorSettings productId="p1" password="pw" />)
    await waitFor(() => screen.getByText(/save/i))
    fireEvent.click(screen.getByRole('button', { name: /save/i }))
    await waitFor(() => expect(api.updateOrchestratorConfig).toHaveBeenCalled())
  })
})
