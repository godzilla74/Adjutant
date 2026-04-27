import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import '@testing-library/jest-dom'
import AgentModelSettings from '../components/settings/AgentModelSettings'

const mockConfig = {
  agent_model: 'claude-sonnet-4-6',
  subagent_model: 'claude-sonnet-4-6',
  prescreener_model: 'claude-haiku-4-5-20251001',
  agent_name: 'Adjutant',
}

vi.mock('../api', () => ({
  api: {
    getAgentConfig: vi.fn().mockResolvedValue({
      agent_model: 'claude-sonnet-4-6',
      subagent_model: 'claude-sonnet-4-6',
      prescreener_model: 'claude-haiku-4-5-20251001',
      agent_name: 'Adjutant',
    }),
    updateAgentConfig: vi.fn().mockResolvedValue({
      agent_model: 'claude-sonnet-4-6',
      subagent_model: 'claude-sonnet-4-6',
      prescreener_model: 'claude-haiku-4-5-20251001',
      agent_name: 'Adjutant',
    }),
  },
}))

describe('AgentModelSettings', () => {
  it('renders prescreener model selector with loaded value', async () => {
    render(<AgentModelSettings password="test" />)
    await waitFor(() => {
      expect(screen.getByLabelText(/pre-screener/i)).toBeInTheDocument()
    })
    const select = screen.getByLabelText(/pre-screener/i) as HTMLSelectElement
    expect(select.value).toBe('claude-haiku-4-5-20251001')
  })

  it('updates prescreener model state when user changes selection', async () => {
    render(<AgentModelSettings password="test" />)
    await waitFor(() => screen.getByLabelText(/pre-screener/i))
    const select = screen.getByLabelText(/pre-screener/i) as HTMLSelectElement
    fireEvent.change(select, { target: { value: 'claude-sonnet-4-6' } })
    expect(select.value).toBe('claude-sonnet-4-6')
  })

  it('includes prescreener_model in save call', async () => {
    const { api } = await import('../api')
    render(<AgentModelSettings password="test" />)
    await waitFor(() => screen.getByLabelText(/pre-screener/i))
    fireEvent.click(screen.getByRole('button', { name: /save/i }))
    await waitFor(() => {
      expect(api.updateAgentConfig).toHaveBeenCalledWith(
        'test',
        expect.objectContaining({ prescreener_model: 'claude-haiku-4-5-20251001' })
      )
    })
  })
})
