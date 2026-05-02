import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import '@testing-library/jest-dom'
import ReportsTab from '../components/ReportsTab'

const mockReports = vi.hoisted(() => [
  { id: 1, workstream_id: 1, workstream_name: 'Research', created_at: '2026-05-01 10:00:00', preview: 'Market trends…' },
])
const mockTags = vi.hoisted(() => [
  { id: 1, name: 'social:linkedin', description: 'LinkedIn', created_at: '2026-01-01', updated_at: '2026-01-01' },
  { id: 2, name: 'email:customers', description: 'Email', created_at: '2026-01-01', updated_at: '2026-01-01' },
])

vi.mock('../api', () => ({
  api: {
    listTags: vi.fn().mockResolvedValue(mockTags),
    createSignal: vi.fn().mockResolvedValue({
      id: 10, tag_id: 1, tag_name: 'social:linkedin', content_type: 'run_report',
      content_id: 1, product_id: 'p1', tagged_by: 'user', note: 'Great angle',
      consumed_at: null, created_at: '2026-05-01 10:00:00',
    }),
  },
}))

beforeEach(() => {
  vi.clearAllMocks()
  global.fetch = vi.fn()
    .mockResolvedValueOnce({ ok: true, json: async () => mockReports })
    .mockResolvedValueOnce({ ok: true, json: async () => ({ ...mockReports[0], full_output: 'Full content here' }) })
})

describe('ReportsTab', () => {
  it('shows Tag button in report detail view', async () => {
    render(<ReportsTab productId="p1" password="test" />)
    await waitFor(() => screen.getByText('Research'))
    fireEvent.click(screen.getByText('Research'))
    await waitFor(() => screen.getByText('Full content here'))
    expect(screen.getByRole('button', { name: /tag this report/i })).toBeInTheDocument()
  })

  it('shows tag form with dropdown when Tag button clicked', async () => {
    render(<ReportsTab productId="p1" password="test" />)
    await waitFor(() => screen.getByText('Research'))
    fireEvent.click(screen.getByText('Research'))
    await waitFor(() => screen.getByText('Full content here'))
    fireEvent.click(screen.getByRole('button', { name: /tag this report/i }))
    await waitFor(() => expect(screen.getByRole('combobox')).toBeInTheDocument())
    expect(screen.getByText('social:linkedin')).toBeInTheDocument()
  })

  it('calls createSignal with selected tag and note', async () => {
    const { api } = await import('../api')
    render(<ReportsTab productId="p1" password="test" />)
    await waitFor(() => screen.getByText('Research'))
    fireEvent.click(screen.getByText('Research'))
    await waitFor(() => screen.getByText('Full content here'))
    fireEvent.click(screen.getByRole('button', { name: /tag this report/i }))
    await waitFor(() => screen.getByRole('combobox'))
    fireEvent.change(screen.getByRole('combobox'), { target: { value: '1' } })
    fireEvent.change(screen.getByPlaceholderText(/handoff note/i), { target: { value: 'Great LinkedIn angle' } })
    fireEvent.click(screen.getByRole('button', { name: /^tag it$/i }))
    await waitFor(() =>
      expect(api.createSignal).toHaveBeenCalledWith('test', 'p1', 1, 'run_report', 1, 'Great LinkedIn angle')
    )
  })
})
