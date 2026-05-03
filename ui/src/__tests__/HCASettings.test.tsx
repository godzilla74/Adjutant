// ui/src/__tests__/HCASettings.test.tsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import '@testing-library/jest-dom'
import HCASettings from '../components/settings/HCASettings'

const mockConfig = vi.hoisted(() => ({
  id: 1, enabled: 0,
  schedule: 'weekly on mondays at 8am',
  pa_run_threshold: 10,
  next_run_at: null, last_run_at: null,
  hca_slack_channel_id: '', hca_discord_channel_id: '', hca_telegram_chat_id: '',
}))

vi.mock('../api', () => ({
  api: {
    getHCAConfig: vi.fn().mockResolvedValue(mockConfig),
    updateHCAConfig: vi.fn().mockResolvedValue({ ...mockConfig, enabled: 1 }),
  },
}))

beforeEach(() => { vi.clearAllMocks() })

describe('HCASettings', () => {
  it('renders enable toggle, schedule and threshold inputs', async () => {
    render(<HCASettings password="test" />)
    await waitFor(() => screen.getByText('Chief Adjutant'))
    expect(screen.getByRole('checkbox')).toBeInTheDocument()
    expect(screen.getByDisplayValue('weekly on mondays at 8am')).toBeInTheDocument()
    expect(screen.getByDisplayValue('10')).toBeInTheDocument()
  })

  it('renders channel ID inputs', async () => {
    render(<HCASettings password="test" />)
    await waitFor(() => screen.getByText('Chief Adjutant'))
    expect(screen.getByPlaceholderText(/slack channel/i)).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/discord channel/i)).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/telegram chat/i)).toBeInTheDocument()
  })

  it('calls updateHCAConfig on save', async () => {
    const { api } = await import('../api')
    render(<HCASettings password="test" />)
    await waitFor(() => screen.getByText('Chief Adjutant'))
    fireEvent.click(screen.getByRole('checkbox'))
    fireEvent.click(screen.getByRole('button', { name: /save/i }))
    await waitFor(() => expect(api.updateHCAConfig).toHaveBeenCalled())
  })
})
