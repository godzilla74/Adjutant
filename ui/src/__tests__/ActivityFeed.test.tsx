// ui/src/__tests__/ActivityFeed.test.tsx
import { describe, it, expect, beforeAll } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import '@testing-library/jest-dom'
import ActivityFeed from '../components/ActivityFeed'
import { ActivityEvent } from '../types'

beforeAll(() => {
  window.HTMLElement.prototype.scrollIntoView = () => {}
})

const makeEvent = (
  id: number,
  agent_type: 'research' | 'general',
  headline: string,
  status: ActivityEvent['status'] = 'done',
): ActivityEvent => ({
  id,
  agent_type,
  headline,
  rationale: '',
  status,
  output_preview: null,
  summary: 'Result summary',
  created_at: `2026-04-07 10:00:0${id}`,
})

const EVENTS = [
  makeEvent(1, 'research', 'Researching competitor pricing'),
  makeEvent(2, 'general',  'Drafting quarterly goals'),
  makeEvent(3, 'research', 'Checking domain availability'),
]

const DIRECTIVES = [
  { type: 'directive' as const, content: 'Draft a content plan', ts: '2026-04-08 10:00:01' },
]

const AGENT_MESSAGES = [
  { type: 'agent' as const, content: 'On it!', ts: '2026-04-08 10:00:02' },
]

const BASE_PROPS = {
  events:        EVENTS,
  directives:    DIRECTIVES,
  agentMessages: AGENT_MESSAGES,
  agentDraft:    '',
  agentName:     'Hannah',
}

describe('ActivityFeed — Chat tab (default)', () => {
  it('shows directive bubbles', () => {
    render(<ActivityFeed {...BASE_PROPS} />)
    expect(screen.getByText('Draft a content plan')).toBeInTheDocument()
  })

  it('shows agent message bubbles', () => {
    render(<ActivityFeed {...BASE_PROPS} />)
    expect(screen.getByText('On it!')).toBeInTheDocument()
  })

  it('does NOT show activity event headlines on chat tab', () => {
    render(<ActivityFeed {...BASE_PROPS} />)
    expect(screen.queryByText('Researching competitor pricing')).not.toBeInTheDocument()
  })

  it('renders agentName as byline on agent messages', () => {
    render(<ActivityFeed {...BASE_PROPS} agentName="Aria" />)
    expect(screen.getByText('Aria')).toBeInTheDocument()
    expect(screen.getByText('On it!')).toBeInTheDocument()
  })

  it('shows empty state when no chat entries', () => {
    render(<ActivityFeed {...BASE_PROPS} directives={[]} agentMessages={[]} />)
    expect(screen.getByText('No activity yet')).toBeInTheDocument()
    expect(screen.getByText('Give Hannah a directive below to get started.')).toBeInTheDocument()
  })

  it('shows agentDraft with cursor on chat tab', () => {
    render(<ActivityFeed {...BASE_PROPS} agentDraft="Thinking about this..." />)
    expect(screen.getByText(/Thinking about this\.\.\./)).toBeInTheDocument()
  })
})

describe('ActivityFeed — Activity tab', () => {
  it('shows events after switching to Activity tab', () => {
    render(<ActivityFeed {...BASE_PROPS} />)
    fireEvent.click(screen.getByRole('button', { name: /activity/i }))
    expect(screen.getByText('Researching competitor pricing')).toBeInTheDocument()
    expect(screen.getByText('Drafting quarterly goals')).toBeInTheDocument()
  })

  it('does NOT show directives or agent messages on activity tab', () => {
    render(<ActivityFeed {...BASE_PROPS} />)
    fireEvent.click(screen.getByRole('button', { name: /activity/i }))
    expect(screen.queryByText('Draft a content plan')).not.toBeInTheDocument()
    expect(screen.queryByText('On it!')).not.toBeInTheDocument()
  })

  it('filters by search text', () => {
    render(<ActivityFeed {...BASE_PROPS} />)
    fireEvent.click(screen.getByRole('button', { name: /activity/i }))
    fireEvent.change(screen.getByPlaceholderText('Search activity…'), { target: { value: 'competitor' } })
    expect(screen.getByText('Researching competitor pricing')).toBeInTheDocument()
    expect(screen.queryByText('Drafting quarterly goals')).not.toBeInTheDocument()
  })

  it('filters by agent type chip', () => {
    render(<ActivityFeed {...BASE_PROPS} />)
    fireEvent.click(screen.getByRole('button', { name: /activity/i }))
    fireEvent.click(screen.getByText('Research'))
    expect(screen.getByText('Researching competitor pricing')).toBeInTheDocument()
    expect(screen.getByText('Checking domain availability')).toBeInTheDocument()
    expect(screen.queryByText('Drafting quarterly goals')).not.toBeInTheDocument()
  })

  it('shows empty state when events array is empty', () => {
    render(<ActivityFeed {...BASE_PROPS} events={[]} />)
    fireEvent.click(screen.getByRole('button', { name: /activity/i }))
    expect(screen.getByText('No agent activity yet.')).toBeInTheDocument()
  })

  it('clears filter chip on second click', () => {
    render(<ActivityFeed {...BASE_PROPS} />)
    fireEvent.click(screen.getByRole('button', { name: /activity/i }))
    fireEvent.click(screen.getByText('Research'))
    fireEvent.click(screen.getByText('Research'))
    expect(screen.getByText('Drafting quarterly goals')).toBeInTheDocument()
  })
})

describe('ActivityFeed — tab badge', () => {
  it('shows running count badge when agents are running', () => {
    const running = makeEvent(99, 'research', 'Running task', 'running')
    render(<ActivityFeed {...BASE_PROPS} events={[...EVENTS, running]} />)
    expect(screen.getByText('(1)')).toBeInTheDocument()
  })

  it('shows no badge when no agents are running', () => {
    render(<ActivityFeed {...BASE_PROPS} />)
    expect(screen.queryByText(/\(\d+\)/)).not.toBeInTheDocument()
  })
})
