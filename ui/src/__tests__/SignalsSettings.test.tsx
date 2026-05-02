import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import '@testing-library/jest-dom'
import SignalsSettings from '../components/settings/SignalsSettings'

const mockSignals = vi.hoisted(() => [
  {
    id: 1, tag_id: 1, tag_name: 'social:linkedin', content_type: 'run_report', content_id: 42,
    product_id: 'p1', tagged_by: 'agent', note: 'Great LinkedIn angle', consumed_at: null,
    created_at: '2026-05-01 10:00:00',
  },
])

vi.mock('../api', () => ({
  api: {
    getSignals: vi.fn().mockResolvedValue(mockSignals),
    consumeSignal: vi.fn().mockResolvedValue({ ok: true, signal_id: 1 }),
    unconsumeSignal: vi.fn().mockResolvedValue({ ok: true, signal_id: 1 }),
  },
}))

beforeEach(() => { vi.clearAllMocks() })

describe('SignalsSettings', () => {
  it('loads and displays pending signals', async () => {
    render(<SignalsSettings productId="p1" password="test" />)
    await waitFor(() => expect(screen.getByText('social:linkedin')).toBeInTheDocument())
    expect(screen.getByText('Great LinkedIn angle')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /consume/i })).toBeInTheDocument()
  })

  it('calls getSignals with include_consumed when checkbox toggled', async () => {
    const { api } = await import('../api')
    render(<SignalsSettings productId="p1" password="test" />)
    await waitFor(() => screen.getByText('social:linkedin'))
    fireEvent.click(screen.getByLabelText(/show consumed/i))
    await waitFor(() => expect(api.getSignals).toHaveBeenCalledWith('test', 'p1', '', true))
  })

  it('calls consumeSignal and reloads when Consume clicked', async () => {
    const { api } = await import('../api')
    render(<SignalsSettings productId="p1" password="test" />)
    await waitFor(() => screen.getByText('social:linkedin'))
    fireEvent.click(screen.getByRole('button', { name: /consume/i }))
    await waitFor(() => expect(api.consumeSignal).toHaveBeenCalledWith('test', 'p1', 1))
    expect(api.getSignals).toHaveBeenCalledTimes(2)
  })

  it('shows empty state when no signals', async () => {
    const { api } = await import('../api')
    vi.mocked(api.getSignals).mockResolvedValueOnce([])
    render(<SignalsSettings productId="p1" password="test" />)
    await waitFor(() => expect(screen.getByText(/no pending signals/i)).toBeInTheDocument())
  })
})
