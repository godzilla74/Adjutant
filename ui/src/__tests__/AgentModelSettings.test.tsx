import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import '@testing-library/jest-dom'
import AgentModelSettings from '../components/settings/AgentModelSettings'

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
})
