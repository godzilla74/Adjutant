// ui/src/__tests__/WorkstreamsPanel.test.tsx
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import '@testing-library/jest-dom'
import WorkstreamsPanel from '../components/WorkstreamsPanel'
import { Workstream, Objective } from '../types'

const WORKSTREAMS: Workstream[] = [
  { id: 1, name: 'Marketing', status: 'running', display_order: 0 },
  { id: 2, name: 'Growth',    status: 'warn',    display_order: 1 },
  { id: 3, name: 'Content',   status: 'paused',  display_order: 2 },
]

const OBJECTIVES: Objective[] = [
  { id: 1, text: 'Drive 50 trial signups', progress_current: 23, progress_target: 50,  display_order: 0 },
  { id: 2, text: 'Publish 4 SEO posts',    progress_current: 1,  progress_target: 4,   display_order: 1 },
  { id: 3, text: 'Build outreach list',    progress_current: 87, progress_target: null, display_order: 2 },
]

describe('WorkstreamsPanel', () => {
  it('renders all workstream names', () => {
    render(<WorkstreamsPanel workstreams={WORKSTREAMS} objectives={OBJECTIVES} />)
    expect(screen.getByText('Marketing')).toBeInTheDocument()
    expect(screen.getByText('Growth')).toBeInTheDocument()
    expect(screen.getByText('Content')).toBeInTheDocument()
  })

  it('renders objectives with progress', () => {
    render(<WorkstreamsPanel workstreams={WORKSTREAMS} objectives={OBJECTIVES} />)
    expect(screen.getByText('Drive 50 trial signups')).toBeInTheDocument()
    expect(screen.getByText('23 / 50')).toBeInTheDocument()
  })

  it('renders open-ended objective without target', () => {
    render(<WorkstreamsPanel workstreams={WORKSTREAMS} objectives={OBJECTIVES} />)
    expect(screen.getByText('Build outreach list')).toBeInTheDocument()
    expect(screen.getByText('87 so far')).toBeInTheDocument()
  })
})
