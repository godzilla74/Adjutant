import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import '@testing-library/jest-dom'
import StatusStrip from '../components/StatusStrip'
import { Workstream, ReviewItem, ActivityEvent, Objective } from '../types'

const WS: Workstream[] = [
  { id: 1, name: 'Social Posts', status: 'running', display_order: 0, schedule: 'daily' },
  { id: 2, name: 'Newsletter',   status: 'paused',  display_order: 1 },
]
const REVIEW: ReviewItem = {
  id: 10, title: 'Publish blog', description: 'Ready to go', risk_label: 'high',
  status: 'pending', created_at: '2026-01-01',
}
const EVENT: ActivityEvent = {
  id: 5, agent_type: 'research', headline: 'Analyzing data', rationale: '',
  status: 'running', created_at: '2026-01-01',
}
const OBJ: Objective = {
  id: 1, text: 'Grow followers', progress_current: 200, progress_target: 1000, display_order: 0,
}

const DEFAULT_PROPS = {
  workstreams: WS,
  reviewItems: [REVIEW],
  events: [EVENT],
  objectives: [OBJ],
  onResolveReview: vi.fn(),
  onCancelAgent: vi.fn(),
  onOpenSettings: vi.fn(),
}

describe('StatusStrip', () => {
  it('shows counts for each category', () => {
    render(<StatusStrip {...DEFAULT_PROPS} />)
    expect(screen.getByText('2')).toBeInTheDocument() // workstreams
    expect(screen.getByText('1 review')).toBeInTheDocument()
    expect(screen.getByText('1 active')).toBeInTheDocument()
  })

  it('opens workstreams popover on pill click', () => {
    render(<StatusStrip {...DEFAULT_PROPS} />)
    fireEvent.click(screen.getByTestId('pill-workstreams'))
    expect(screen.getByText('Social Posts')).toBeInTheDocument()
    expect(screen.getByText('Newsletter')).toBeInTheDocument()
  })

  it('opens reviews popover showing review title', () => {
    render(<StatusStrip {...DEFAULT_PROPS} />)
    fireEvent.click(screen.getByTestId('pill-reviews'))
    expect(screen.getByText('Publish blog')).toBeInTheDocument()
    expect(screen.getByText('Approve')).toBeInTheDocument()
    expect(screen.getByText('Skip')).toBeInTheDocument()
  })

  it('calls onResolveReview(id, approved) when Approve clicked', () => {
    const onResolve = vi.fn()
    render(<StatusStrip {...DEFAULT_PROPS} onResolveReview={onResolve} />)
    fireEvent.click(screen.getByTestId('pill-reviews'))
    fireEvent.click(screen.getByText('Approve'))
    expect(onResolve).toHaveBeenCalledWith(10, 'approved')
  })

  it('calls onResolveReview(id, skipped) when Skip clicked', () => {
    const onResolve = vi.fn()
    render(<StatusStrip {...DEFAULT_PROPS} onResolveReview={onResolve} />)
    fireEvent.click(screen.getByTestId('pill-reviews'))
    fireEvent.click(screen.getByText('Skip'))
    expect(onResolve).toHaveBeenCalledWith(10, 'skipped')
  })

  it('closes open popover when same pill clicked again', () => {
    render(<StatusStrip {...DEFAULT_PROPS} />)
    fireEvent.click(screen.getByTestId('pill-workstreams'))
    expect(screen.getByText('Social Posts')).toBeInTheDocument()
    fireEvent.click(screen.getByTestId('pill-workstreams'))
    expect(screen.queryByText('Social Posts')).not.toBeInTheDocument()
  })

  it('switches to different popover when another pill clicked', () => {
    render(<StatusStrip {...DEFAULT_PROPS} />)
    fireEvent.click(screen.getByTestId('pill-workstreams'))
    expect(screen.getByText('Social Posts')).toBeInTheDocument()
    fireEvent.click(screen.getByTestId('pill-reviews'))
    expect(screen.queryByText('Social Posts')).not.toBeInTheDocument()
    expect(screen.getByText('Publish blog')).toBeInTheDocument()
  })

  it('shows Cancel button in agents popover and calls onCancelAgent', () => {
    const onCancel = vi.fn()
    render(<StatusStrip {...DEFAULT_PROPS} onCancelAgent={onCancel} />)
    fireEvent.click(screen.getByTestId('pill-agents'))
    fireEvent.click(screen.getByText('Cancel'))
    expect(onCancel).toHaveBeenCalledWith('5')
  })

  it('shows elapsed time in agents popover', () => {
    render(<StatusStrip {...DEFAULT_PROPS} />)
    fireEvent.click(screen.getByTestId('pill-agents'))
    // elapsed time shown (any string ending in s/m/h)
    expect(screen.getByText(/agent ·/)).toBeInTheDocument()
  })

  it('shows manage workstreams label', () => {
    render(<StatusStrip {...DEFAULT_PROPS} />)
    fireEvent.click(screen.getByTestId('pill-workstreams'))
    expect(screen.getByText('Manage workstreams →')).toBeInTheDocument()
  })
})
