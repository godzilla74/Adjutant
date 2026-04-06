// ui/src/__tests__/ActivityCard.test.tsx
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import '@testing-library/jest-dom'
import ActivityCard from '../components/ActivityCard'
import { ActivityEvent } from '../types'

const BASE: ActivityEvent = {
  id: 1,
  agent_type: 'research',
  headline: 'Researching competitor pricing',
  rationale: 'HoneyBook raised prices 20% last month',
  status: 'running',
  output_preview: null,
  summary: null,
  created_at: '2026-04-06T09:00:00',
}

describe('ActivityCard', () => {
  it('renders headline', () => {
    render(<ActivityCard event={BASE} />)
    expect(screen.getByText('Researching competitor pricing')).toBeInTheDocument()
  })

  it('renders rationale', () => {
    render(<ActivityCard event={BASE} />)
    expect(screen.getByText(/HoneyBook raised prices/)).toBeInTheDocument()
  })

  it('shows running indicator when status is running', () => {
    render(<ActivityCard event={BASE} />)
    expect(screen.getByText(/running/i)).toBeInTheDocument()
  })

  it('shows summary when done', () => {
    const done: ActivityEvent = { ...BASE, status: 'done', summary: 'Found 4 competitors' }
    render(<ActivityCard event={done} />)
    expect(screen.getByText('Found 4 competitors')).toBeInTheDocument()
  })

  it('shows output preview when needs_review', () => {
    const review: ActivityEvent = { ...BASE, status: 'needs_review', output_preview: '"Tired of chasing clients..."' }
    render(<ActivityCard event={review} />)
    expect(screen.getByText(/"Tired of chasing clients\.\.\."/)).toBeInTheDocument()
  })

  it('renders agent badge for email agent', () => {
    const email: ActivityEvent = { ...BASE, agent_type: 'email' }
    render(<ActivityCard event={email} />)
    expect(screen.getByText('Email Agent')).toBeInTheDocument()
  })
})
