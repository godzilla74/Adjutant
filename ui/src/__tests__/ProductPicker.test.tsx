import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import '@testing-library/jest-dom'
import ProductPicker from '../components/ProductPicker'
import { Product, ProductState } from '../types'

const PRODUCTS: Product[] = [
  { id: 'p1', name: 'Content Co', icon_label: 'CC', color: '#7c3aed' },
  { id: 'p2', name: 'Dev Studio', icon_label: 'DS', color: '#2563eb' },
]

const STATES: Record<string, ProductState> = {
  p1: { workstreams: [{ id: 1, name: 'Blog', status: 'running', display_order: 0 }], objectives: [], events: [], review_items: [], sessions: [], activeSessionId: null },
  p2: { workstreams: [], objectives: [], events: [], review_items: [], sessions: [], activeSessionId: null },
}

describe('ProductPicker', () => {
  it('renders all product names', () => {
    render(<ProductPicker products={PRODUCTS} productStates={STATES} onSelect={vi.fn()} onNewProduct={vi.fn()} />)
    expect(screen.getByText('Content Co')).toBeInTheDocument()
    expect(screen.getByText('Dev Studio')).toBeInTheDocument()
  })

  it('calls onSelect with product id when clicked', () => {
    const onSelect = vi.fn()
    render(<ProductPicker products={PRODUCTS} productStates={STATES} onSelect={onSelect} onNewProduct={vi.fn()} />)
    fireEvent.click(screen.getByText('Content Co').closest('button')!)
    expect(onSelect).toHaveBeenCalledWith('p1')
  })

  it('shows workstream count per product', () => {
    render(<ProductPicker products={PRODUCTS} productStates={STATES} onSelect={vi.fn()} onNewProduct={vi.fn()} />)
    expect(screen.getByText('1 workstream')).toBeInTheDocument()
    expect(screen.getByText('No workstreams')).toBeInTheDocument()
  })

  it('calls onNewProduct when + New product clicked', () => {
    const onNewProduct = vi.fn()
    render(<ProductPicker products={PRODUCTS} productStates={STATES} onSelect={vi.fn()} onNewProduct={onNewProduct} />)
    fireEvent.click(screen.getByText('+ New product'))
    expect(onNewProduct).toHaveBeenCalled()
  })

  it('shows empty state when no products', () => {
    render(<ProductPicker products={[]} productStates={{}} onSelect={vi.fn()} onNewProduct={vi.fn()} />)
    expect(screen.getByText(/no products yet/i)).toBeInTheDocument()
  })
})
