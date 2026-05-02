import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import '@testing-library/jest-dom'
import BriefingTab from '../components/BriefingTab'

const mockRuns = vi.hoisted(() => [
  {
    id: 1,
    product_id: 'p1',
    triggered_by: 'schedule',
    run_at: '2026-05-02 08:00:00',
    status: 'complete',
    decisions: [
      { action: 'update_mission', workstream_id: 1, new_mission: 'New mission',
        reason: 'drift detected', _status: 'applied', _note: 'workstream 1 mission updated' },
      { action: 'pause_workstream', workstream_id: 2, reason: 'underperforming',
        _status: 'queued', _review_item_id: 5 },
    ],
    brief: 'LinkedIn Research is drifting from brand voice. Pausing Email workstream pending review.',
    error: null,
  },
])

const mockReviewItems = vi.hoisted(() => [
  { id: 5, title: 'pause_workstream', description: '[orchestrator_run:1] underperforming',
    risk_label: 'medium', status: 'pending', created_at: '2026-05-02 08:00:01',
    action_type: 'orchestrator_pause_workstream', payload: null, auto_approve_at: null },
])

vi.mock('../api', () => ({
  api: {
    getOrchestratorRuns: vi.fn().mockResolvedValue(mockRuns),
    triggerOrchestrator: vi.fn().mockResolvedValue({ queued: true }),
  },
}))

describe('BriefingTab', () => {
  it('renders the latest run brief', async () => {
    render(<BriefingTab productId="p1" password="pw" reviewItems={mockReviewItems} onApprove={vi.fn()} onSkip={vi.fn()} />)
    await waitFor(() => screen.getByText(/LinkedIn Research is drifting/i))
  })

  it('shows applied decision as green', async () => {
    render(<BriefingTab productId="p1" password="pw" reviewItems={mockReviewItems} onApprove={vi.fn()} onSkip={vi.fn()} />)
    await waitFor(() => screen.getByText(/update_mission/i))
    expect(screen.getByText(/update_mission/i).closest('[data-status]')).toHaveAttribute('data-status', 'applied')
  })

  it('shows pending approval card with Approve and Skip buttons', async () => {
    const onApprove = vi.fn()
    render(<BriefingTab productId="p1" password="pw" reviewItems={mockReviewItems} onApprove={onApprove} onSkip={vi.fn()} />)
    await waitFor(() => screen.getByRole('button', { name: /approve/i }))
    fireEvent.click(screen.getByRole('button', { name: /approve/i }))
    expect(onApprove).toHaveBeenCalledWith(5)
  })

  it('shows run history entries', async () => {
    render(<BriefingTab productId="p1" password="pw" reviewItems={mockReviewItems} onApprove={vi.fn()} onSkip={vi.fn()} />)
    await waitFor(() => screen.getByText(/run history/i))
  })
})
