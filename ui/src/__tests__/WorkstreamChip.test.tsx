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
