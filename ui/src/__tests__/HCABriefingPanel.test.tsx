// ui/src/__tests__/HCABriefingPanel.test.tsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import '@testing-library/jest-dom'
import HCABriefingPanel from '../components/HCABriefingPanel'
import type { ReviewItem } from '../types'

const mockRuns = vi.hoisted(() => [
  {
    id: 1, triggered_by: 'schedule', run_at: '2026-05-02 08:00:00',
    status: 'complete', brief: 'Portfolio is performing well.',
    decisions: [
      { action: 'issue_directive', product_id: 'p1', content: 'Focus on enterprise',
        reason: 'market shift', _status: 'applied' },
    ],
    error: null,
  },
])
const mockDirectives = vi.hoisted(() => [
  { id: 1, product_id: 'p1', content: 'Focus on enterprise', hca_run_id: 1,
    status: 'active', created_at: '2026-05-02 08:00:00' },
])

vi.mock('../api', () => ({
  api: {
    getHCARuns: vi.fn().mockResolvedValue(mockRuns),
    getHCADirectives: vi.fn().mockResolvedValue(mockDirectives),
    triggerHCA: vi.fn().mockResolvedValue({ queued: true }),
    deleteHCADirective: vi.fn().mockResolvedValue(undefined),
  },
}))

const pendingItem: ReviewItem = {
  id: 10, title: 'New product: Acme Analytics', description: 'Opportunity from briefs',
  risk_label: 'High · owner approval required', status: 'pending',
  created_at: '2026-05-02 08:00:00', action_type: 'hca_new_product',
  auto_approve_at: null, payload: null, scheduled_for: null,
}

beforeEach(() => { vi.clearAllMocks() })

describe('HCABriefingPanel', () => {
  it('renders latest run brief', async () => {
    render(<HCABriefingPanel password="test" reviewItems={[]} onApprove={() => {}} onSkip={() => {}} />)
    await waitFor(() => screen.getByText('Portfolio is performing well.'))
  })

  it('renders decision list with applied status', async () => {
    render(<HCABriefingPanel password="test" reviewItems={[]} onApprove={() => {}} onSkip={() => {}} />)
    await waitFor(() => screen.getByText(/issue_directive/i))
  })

  it('renders pending proposal card with approve and skip buttons', async () => {
    render(
      <HCABriefingPanel
        password="test"
        reviewItems={[pendingItem]}
        onApprove={() => {}}
        onSkip={() => {}}
      />
    )
    await waitFor(() => screen.getByText('New product: Acme Analytics'))
    expect(screen.getByRole('button', { name: /approve/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /skip/i })).toBeInTheDocument()
  })

  it('calls onApprove when approve button clicked', async () => {
    const onApprove = vi.fn()
    render(
      <HCABriefingPanel
        password="test"
        reviewItems={[pendingItem]}
        onApprove={onApprove}
        onSkip={() => {}}
      />
    )
    await waitFor(() => screen.getByText('New product: Acme Analytics'))
    fireEvent.click(screen.getByRole('button', { name: /approve/i }))
    expect(onApprove).toHaveBeenCalledWith(10)
  })

  it('renders active directives list with retire button', async () => {
    render(<HCABriefingPanel password="test" reviewItems={[]} onApprove={() => {}} onSkip={() => {}} />)
    await waitFor(() => screen.getByText('Focus on enterprise'))
    expect(screen.getByRole('button', { name: /retire/i })).toBeInTheDocument()
  })

  it('calls deleteHCADirective and removes directive when retire clicked', async () => {
    const { api } = await import('../api')
    render(<HCABriefingPanel password="test" reviewItems={[]} onApprove={() => {}} onSkip={() => {}} />)
    await waitFor(() => screen.getByText('Focus on enterprise'))
    fireEvent.click(screen.getByRole('button', { name: /retire/i }))
    await waitFor(() => expect(api.deleteHCADirective).toHaveBeenCalledWith('test', 1))
    await waitFor(() => expect(screen.queryByText('Focus on enterprise')).not.toBeInTheDocument())
  })
})
