import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import '@testing-library/jest-dom'
import ProductDropdown from '../components/ProductDropdown'
import { Product } from '../types'

const PRODUCTS: Product[] = [
  { id: 'p1', name: 'Acme Corp',  icon_label: '🏢', color: '#6366f1' },
  { id: 'p2', name: 'Side Project', icon_label: '🚀', color: '#ec4899' },
]

describe('ProductDropdown', () => {
  it('renders current product name as trigger', () => {
    render(
      <ProductDropdown
        products={PRODUCTS}
        activeProductId="p1"
        onSelect={vi.fn()}
        onNewProduct={vi.fn()}
      />
    )
    expect(screen.getByText('Acme Corp')).toBeInTheDocument()
  })

  it('opens dropdown on click and shows all products', () => {
    render(
      <ProductDropdown
        products={PRODUCTS}
        activeProductId="p1"
        onSelect={vi.fn()}
        onNewProduct={vi.fn()}
      />
    )
    fireEvent.click(screen.getByText('Acme Corp'))
    expect(screen.getByText('Side Project')).toBeInTheDocument()
    expect(screen.getByText('New Product')).toBeInTheDocument()
  })

  it('calls onSelect with product id when a product is clicked', () => {
    const onSelect = vi.fn()
    render(
      <ProductDropdown
        products={PRODUCTS}
        activeProductId="p1"
        onSelect={onSelect}
        onNewProduct={vi.fn()}
      />
    )
    fireEvent.click(screen.getByText('Acme Corp'))
    fireEvent.click(screen.getByText('Side Project'))
    expect(onSelect).toHaveBeenCalledWith('p2')
  })

  it('calls onNewProduct when New Product is clicked', () => {
    const onNew = vi.fn()
    render(
      <ProductDropdown
        products={PRODUCTS}
        activeProductId="p1"
        onSelect={vi.fn()}
        onNewProduct={onNew}
      />
    )
    fireEvent.click(screen.getByText('Acme Corp'))
    fireEvent.click(screen.getByText('New Product'))
    expect(onNew).toHaveBeenCalled()
  })

  it('shows checkmark on active product', () => {
    render(
      <ProductDropdown
        products={PRODUCTS}
        activeProductId="p1"
        onSelect={vi.fn()}
        onNewProduct={vi.fn()}
      />
    )
    fireEvent.click(screen.getByText('Acme Corp'))
    const p1Item = screen.getByTestId('product-item-p1')
    expect(p1Item).toHaveTextContent('✓')
  })

  it('closes on Escape key', () => {
    render(
      <ProductDropdown
        products={PRODUCTS}
        activeProductId="p1"
        onSelect={vi.fn()}
        onNewProduct={vi.fn()}
      />
    )
    fireEvent.click(screen.getByText('Acme Corp'))
    expect(screen.getByText('Side Project')).toBeInTheDocument()
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.queryByText('Side Project')).not.toBeInTheDocument()
  })
})
