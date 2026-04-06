import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import '@testing-library/jest-dom'
import EventItem from '../components/EventItem'
import { AppEvent } from '../types'

describe('EventItem', () => {
  it('renders a user message', () => {
    const ev: AppEvent = { type: 'user_message', content: 'Hello Hannah', ts: '2026-04-06T12:00:00' }
    render(<EventItem event={ev} />)
    expect(screen.getByText('Hello Hannah')).toBeInTheDocument()
    expect(screen.getByText('You')).toBeInTheDocument()
  })

  it('renders a hannah message', () => {
    const ev: AppEvent = { type: 'hannah_message', content: 'Good morning!', ts: '2026-04-06T12:00:00' }
    render(<EventItem event={ev} />)
    expect(screen.getByText('Good morning!')).toBeInTheDocument()
    expect(screen.getByText('Hannah')).toBeInTheDocument()
  })

  it('renders a running task card', () => {
    const ev: AppEvent = { type: 'task', id: '1', agentType: 'email', description: 'Check inbox', status: 'running', ts: '2026-04-06T12:00:00' }
    render(<EventItem event={ev} />)
    expect(screen.getByText('Check inbox')).toBeInTheDocument()
    expect(screen.getByText('Email Agent')).toBeInTheDocument()
  })

  it('renders a done task with summary', () => {
    const ev: AppEvent = { type: 'task', id: '1', agentType: 'research', description: 'Research competitors', status: 'done', summary: 'Found 3 competitors', ts: '2026-04-06T12:00:00' }
    render(<EventItem event={ev} />)
    expect(screen.getByText('Found 3 competitors')).toBeInTheDocument()
  })
})
