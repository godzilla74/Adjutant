// ui/src/__tests__/ReviewCard.test.tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import '@testing-library/jest-dom'
import ReviewCard from '../components/ReviewCard'
import { ReviewItem } from '../types'

const ITEM: ReviewItem = {
  id: 1,
  title: 'LinkedIn post: launch announcement',
  description: 'Scheduled for 9am Tuesday. Highest-scoring variation.',
  risk_label: 'Public-facing · irreversible',
  status: 'pending',
  created_at: '2026-04-06T09:00:00',
}

describe('ReviewCard', () => {
  it('renders title and View button; description shown in modal', async () => {
    render(<ReviewCard item={ITEM} onResolve={() => {}} />)
    expect(screen.getByText('LinkedIn post: launch announcement')).toBeInTheDocument()
    // Description not shown on card — only after clicking View
    expect(screen.queryByText(/Scheduled for 9am Tuesday/)).not.toBeInTheDocument()
    fireEvent.click(screen.getByText('View'))
    await waitFor(() => expect(screen.getByText(/Scheduled for 9am Tuesday/)).toBeInTheDocument())
  })

  it('renders risk label', () => {
    render(<ReviewCard item={ITEM} onResolve={() => {}} />)
    expect(screen.getByText('Public-facing · irreversible')).toBeInTheDocument()
  })

  it('calls onResolve with approve when Approve clicked', () => {
    const onResolve = vi.fn()
    render(<ReviewCard item={ITEM} onResolve={onResolve} />)
    fireEvent.click(screen.getByText('Approve'))
    expect(onResolve).toHaveBeenCalledWith(1, 'approved')
  })

  it('calls onResolve with skipped when Skip clicked', () => {
    const onResolve = vi.fn()
    render(<ReviewCard item={ITEM} onResolve={onResolve} />)
    fireEvent.click(screen.getByText('Skip'))
    expect(onResolve).toHaveBeenCalledWith(1, 'skipped')
  })
})
