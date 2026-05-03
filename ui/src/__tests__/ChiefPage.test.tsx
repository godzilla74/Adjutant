import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import '@testing-library/jest-dom'
import ChiefPage from '../components/ChiefPage'
import { ReviewItem } from '../types'
import { api } from '../api'

vi.mock('../api', () => ({
  api: {
    getHCARuns: vi.fn().mockResolvedValue([
      { id: 47, triggered_by: 'schedule', run_at: '2026-05-03T09:52:00', status: 'complete',
        decisions: [], brief: '• Content Co on track\n• Dev Studio sprint review due Friday' },
    ]),
    getHCADirectives: vi.fn().mockResolvedValue([]),
    getHCAConfig: vi.fn().mockResolvedValue({
      enabled: 1, schedule: 'every 1 hours', pa_run_threshold: 3,
      next_run_at: '2026-05-03T10:52:00', last_run_at: '2026-05-03T09:52:00',
      hca_slack_channel_id: '', hca_discord_channel_id: '', hca_telegram_chat_id: '',
    }),
    triggerHCA: vi.fn().mockResolvedValue({ queued: true }),
  },
}))

const REVIEWS: ReviewItem[] = [
  { id: 1, title: 'LinkedIn post', description: 'Q2 recap post draft', risk_label: 'Public', status: 'pending', created_at: '2026-05-03T09:00:00', action_type: 'social_post' },
]

describe('ChiefPage', () => {
  beforeEach(() => vi.clearAllMocks())

  it('renders the page heading', async () => {
    render(<ChiefPage password="pw" reviewItems={[]} onResolveReview={vi.fn()} onOpenSettings={vi.fn()} />)
    expect(screen.getByText('Chief Adjutant')).toBeInTheDocument()
  })

  it('renders pending review items', async () => {
    render(<ChiefPage password="pw" reviewItems={REVIEWS} onResolveReview={vi.fn()} onOpenSettings={vi.fn()} />)
    expect(screen.getByText('LinkedIn post')).toBeInTheDocument()
  })

  it('calls onResolveReview with approved when Approve clicked', async () => {
    const onResolveReview = vi.fn()
    render(<ChiefPage password="pw" reviewItems={REVIEWS} onResolveReview={onResolveReview} onOpenSettings={vi.fn()} />)
    fireEvent.click(screen.getByText('Approve'))
    expect(onResolveReview).toHaveBeenCalledWith(1, 'approved')
  })

  it('calls triggerHCA when Run now clicked', async () => {
    render(<ChiefPage password="pw" reviewItems={[]} onResolveReview={vi.fn()} onOpenSettings={vi.fn()} />)
    await waitFor(() => screen.getByText('Run now'))
    fireEvent.click(screen.getByText('Run now'))
    await waitFor(() => expect(api.triggerHCA).toHaveBeenCalledWith('pw'))
  })

  it('shows latest briefing after load', async () => {
    render(<ChiefPage password="pw" reviewItems={[]} onResolveReview={vi.fn()} onOpenSettings={vi.fn()} />)
    await waitFor(() => expect(screen.getByText(/Content Co on track/)).toBeInTheDocument())
  })
})
