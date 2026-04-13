// ui/src/__tests__/ProductRail.test.tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import '@testing-library/jest-dom'
import ProductRail from '../components/ProductRail'
import { Product } from '../types'

const PRODUCTS: Product[] = [
  { id: 'retainerops', name: 'RetainerOps',        icon_label: 'RO', color: '#2563eb' },
  { id: 'ignitara',    name: 'Ignitara',            icon_label: 'IG', color: '#ea580c' },
  { id: 'bullsi',      name: 'Bullsi',              icon_label: 'BU', color: '#7c3aed' },
  { id: 'eligibility', name: 'Eligibility Console', icon_label: 'EC', color: '#059669' },
]

describe('ProductRail', () => {
  it('renders all product icon labels', () => {
    render(<ProductRail products={PRODUCTS} activeProductId="retainerops" onSwitch={() => {}} onOverview={() => {}} onLaunch={() => {}} />)
    expect(screen.getByText('RO')).toBeInTheDocument()
    expect(screen.getByText('IG')).toBeInTheDocument()
    expect(screen.getByText('BU')).toBeInTheDocument()
    expect(screen.getByText('EC')).toBeInTheDocument()
  })

  it('calls onSwitch with product id when clicked', () => {
    const onSwitch = vi.fn()
    render(<ProductRail products={PRODUCTS} activeProductId="retainerops" onSwitch={onSwitch} onOverview={() => {}} onLaunch={() => {}} />)
    fireEvent.click(screen.getByText('IG'))
    expect(onSwitch).toHaveBeenCalledWith('ignitara')
  })

  it('marks active product with aria-current', () => {
    render(<ProductRail products={PRODUCTS} activeProductId="bullsi" onSwitch={() => {}} onOverview={() => {}} onLaunch={() => {}} />)
    const buBtn = screen.getByText('BU').closest('button')
    expect(buBtn).toHaveAttribute('aria-current', 'true')
    const igBtn = screen.getByText('IG').closest('button')
    expect(igBtn).not.toHaveAttribute('aria-current', 'true')
  })
})
