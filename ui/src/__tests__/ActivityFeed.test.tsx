// ui/src/__tests__/ActivityFeed.test.tsx
import { describe, it, expect, beforeAll } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import '@testing-library/jest-dom'
import ActivityFeed from '../components/ActivityFeed'

// jsdom doesn't implement scrollIntoView
beforeAll(() => {
  window.HTMLElement.prototype.scrollIntoView = () => {}
})
import { ActivityEvent } from '../types'

const makeEvent = (id: number, agent_type: 'research' | 'general', headline: string): ActivityEvent => ({
  id,
  agent_type,
  headline,
  rationale: '',
  status: 'done',
  output_preview: null,
  summary: 'Result summary',
  created_at: `2026-04-07 10:00:0${id}`,
})

const EVENTS = [
  makeEvent(1, 'research', 'Researching competitor pricing'),
  makeEvent(2, 'general',  'Drafting quarterly goals'),
  makeEvent(3, 'research', 'Checking domain availability'),
]

const EMPTY_PROPS = {
  events: EVENTS,
  directives: [],
  agentMessages: [],
  agentDraft: '',
  agentName: 'Hannah',
}

describe('ActivityFeed filtering', () => {
  it('shows all events by default', () => {
    render(<ActivityFeed {...EMPTY_PROPS} />)
    expect(screen.getByText('Researching competitor pricing')).toBeInTheDocument()
    expect(screen.getByText('Drafting quarterly goals')).toBeInTheDocument()
  })

  it('filters by search text', () => {
    render(<ActivityFeed {...EMPTY_PROPS} />)
    const input = screen.getByPlaceholderText('Search activity…')
    fireEvent.change(input, { target: { value: 'competitor' } })
    expect(screen.getByText('Researching competitor pricing')).toBeInTheDocument()
    expect(screen.queryByText('Drafting quarterly goals')).not.toBeInTheDocument()
  })

  it('filters by agent type chip', () => {
    render(<ActivityFeed {...EMPTY_PROPS} />)
    fireEvent.click(screen.getByText('Research'))
    expect(screen.getByText('Researching competitor pricing')).toBeInTheDocument()
    expect(screen.getByText('Checking domain availability')).toBeInTheDocument()
    expect(screen.queryByText('Drafting quarterly goals')).not.toBeInTheDocument()
  })

  it('clears filter chip on second click', () => {
    render(<ActivityFeed {...EMPTY_PROPS} />)
    fireEvent.click(screen.getByText('Research'))
    fireEvent.click(screen.getByText('Research'))
    expect(screen.getByText('Drafting quarterly goals')).toBeInTheDocument()
  })
})

describe('ActivityFeed agentName', () => {
  it('renders agentName as byline on agent messages', () => {
    render(<ActivityFeed
      events={[]}
      directives={[]}
      agentMessages={[{ type: 'agent', content: 'Hello!', ts: '2026-04-08 10:00:00' }]}
      agentDraft=""
      agentName="Aria"
    />)
    expect(screen.getByText('Aria')).toBeInTheDocument()
    expect(screen.getByText('Hello!')).toBeInTheDocument()
  })
})
