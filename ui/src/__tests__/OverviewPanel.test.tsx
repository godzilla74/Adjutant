// ui/src/__tests__/OverviewPanel.test.tsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import '@testing-library/jest-dom'
import OverviewPanel from '../components/OverviewPanel'

vi.mock('../api', () => ({
  api: {
    getOverview: vi.fn().mockResolvedValue([
      { id: 'retainerops', name: 'RetainerOps', icon_label: 'RO', color: '#2563eb',
        running_ws: 2, warn_ws: 1, paused_ws: 0, pending_reviews: 3, running_agents: 1 },
      { id: 'ignitara', name: 'Ignitara', icon_label: 'IG', color: '#7c3aed',
        running_ws: 0, warn_ws: 0, paused_ws: 3, pending_reviews: 0, running_agents: 0 },
    ]),
    sendDigest: vi.fn().mockResolvedValue({ queued: true }),
  },
}))

const mockOnSelect = vi.fn()
const defaultProps = { password: 'test', onSelectProduct: mockOnSelect }

beforeEach(() => {
  vi.clearAllMocks()
  mockOnSelect.mockClear()
})

describe('OverviewPanel', () => {
  it('loads and displays all product cards', async () => {
    render(<OverviewPanel {...defaultProps} />)
    await waitFor(() => expect(screen.getByText('RetainerOps')).toBeInTheDocument())
    expect(screen.getByText('Ignitara')).toBeInTheDocument()
  })

  it('shows review badge only when pending_reviews > 0', async () => {
    render(<OverviewPanel {...defaultProps} />)
    await waitFor(() => screen.getByText('RetainerOps'))
    expect(screen.getByText('3 pending')).toBeInTheDocument()
    // Ignitara has 0 pending reviews — no badge
    const badges = screen.getAllByText(/pending/)
    expect(badges).toHaveLength(1)
  })

  it('calls onSelectProduct when a product card is clicked', async () => {
    render(<OverviewPanel {...defaultProps} />)
    await waitFor(() => screen.getByText('RetainerOps'))
    fireEvent.click(screen.getByText('RetainerOps'))
    expect(mockOnSelect).toHaveBeenCalledWith('retainerops')
  })

  it('calls api.sendDigest when Send Digest button is clicked', async () => {
    const { api } = await import('../api')
    render(<OverviewPanel {...defaultProps} />)
    await waitFor(() => screen.getByText('RetainerOps'))
    fireEvent.click(screen.getByText('Send Digest'))
    await waitFor(() => expect(api.sendDigest).toHaveBeenCalledWith('test'))
  })
})
