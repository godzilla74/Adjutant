import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import '@testing-library/jest-dom'
import OverviewPage from '../components/OverviewPage'
import { Product, ProductState } from '../types'

vi.mock('../api', () => ({
  api: {
    getOverview: vi.fn().mockResolvedValue([
      { id: 'p1', name: 'Content Co', icon_label: 'CC', color: '#7c3aed',
        running_ws: 2, warn_ws: 0, paused_ws: 1, pending_reviews: 1, running_agents: 0 },
    ]),
    updateWorkstream: vi.fn().mockResolvedValue({}),
  },
}))

const PRODUCTS: Product[] = [
  { id: 'p1', name: 'Content Co', icon_label: 'CC', color: '#7c3aed' },
]

const PRODUCT_STATES: Record<string, ProductState> = {
  p1: {
    workstreams: [
      { id: 1, name: 'Blog publisher', status: 'running', display_order: 0, last_run_at: '2026-05-03T10:00:00' },
      { id: 2, name: 'Email drip', status: 'paused', display_order: 1 },
    ],
    objectives: [], events: [], review_items: [], sessions: [], activeSessionId: null,
  },
}

describe('OverviewPage', () => {
  beforeEach(() => vi.clearAllMocks())

  it('renders product name', async () => {
    render(<OverviewPage products={PRODUCTS} productStates={PRODUCT_STATES} password="pw" onOpenProduct={vi.fn()} />)
    await waitFor(() => expect(screen.getByText('Content Co')).toBeInTheDocument())
  })

  it('renders workstream chips for the product', async () => {
    render(<OverviewPage products={PRODUCTS} productStates={PRODUCT_STATES} password="pw" onOpenProduct={vi.fn()} />)
    await waitFor(() => expect(screen.getByText('Blog publisher')).toBeInTheDocument())
    expect(screen.getByText('Email drip')).toBeInTheDocument()
  })

  it('shows stats from getOverview', async () => {
    render(<OverviewPage products={PRODUCTS} productStates={PRODUCT_STATES} password="pw" onOpenProduct={vi.fn()} />)
    await waitFor(() => expect(screen.getByText('2')).toBeInTheDocument()) // running_ws
  })

  it('calls onOpenProduct when Open workspace clicked', async () => {
    const onOpenProduct = vi.fn()
    render(<OverviewPage products={PRODUCTS} productStates={PRODUCT_STATES} password="pw" onOpenProduct={onOpenProduct} />)
    await waitFor(() => screen.getByText('Open workspace →'))
    screen.getByText('Open workspace →').click()
    expect(onOpenProduct).toHaveBeenCalledWith('p1')
  })
})
