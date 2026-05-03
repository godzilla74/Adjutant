import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import '@testing-library/jest-dom'
import ChannelSelect from '../components/settings/ChannelSelect'

const mockSlackChannels = vi.hoisted(() => ({
  channels: [
    { id: 'C001', name: 'general' },
    { id: 'C002', name: 'engineering' },
  ],
}))

vi.mock('../api', () => ({
  api: {
    getSlackChannels: vi.fn().mockResolvedValue(mockSlackChannels),
    getDiscordChannels: vi.fn().mockRejectedValue(new Error('not connected')),
  },
}))

beforeEach(() => { vi.clearAllMocks() })

describe('ChannelSelect', () => {
  it('renders channel options after loading', async () => {
    render(
      <ChannelSelect platform="slack" value="" onChange={() => {}} password="pw" />
    )
    await waitFor(() => screen.getByText('#general'))
    expect(screen.getByText('#engineering')).toBeInTheDocument()
    expect(screen.getByText('— global default —')).toBeInTheDocument()
  })

  it('shows selected channel', async () => {
    render(
      <ChannelSelect platform="slack" value="C002" onChange={() => {}} password="pw" />
    )
    await waitFor(() => screen.getByText('#general'))
    expect((screen.getByRole('combobox') as HTMLSelectElement).value).toBe('C002')
  })

  it('calls onChange with channel id when selection changes', async () => {
    const onChange = vi.fn()
    render(
      <ChannelSelect platform="slack" value="" onChange={onChange} password="pw" />
    )
    await waitFor(() => screen.getByText('#general'))
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'C001' } })
    expect(onChange).toHaveBeenCalledWith('C001')
  })

  it('shows disabled state when integration not connected', async () => {
    render(
      <ChannelSelect platform="discord" value="" onChange={() => {}} password="pw" />
    )
    await waitFor(() => expect(screen.getByRole('combobox')).toBeDisabled())
    expect(screen.getByText(/not connected/i)).toBeInTheDocument()
  })
})
