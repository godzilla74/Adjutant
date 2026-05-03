import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import '@testing-library/jest-dom'
import NavRail from '../components/NavRail'

describe('NavRail', () => {
  const onNavigate = vi.fn()
  const defaultProps = {
    section: 'overview' as const,
    reviewBadgeCount: 0,
    agentInitial: 'A',
    onNavigate,
  }

  it('renders all four nav items', () => {
    render(<NavRail {...defaultProps} />)
    expect(screen.getByTitle('Overview')).toBeInTheDocument()
    expect(screen.getByTitle('Products')).toBeInTheDocument()
    expect(screen.getByTitle('Chief')).toBeInTheDocument()
    expect(screen.getByTitle('Settings')).toBeInTheDocument()
  })

  it('calls onNavigate with correct section on click', () => {
    render(<NavRail {...defaultProps} />)
    fireEvent.click(screen.getByTitle('Chief'))
    expect(onNavigate).toHaveBeenCalledWith('chief')
  })

  it('shows badge on Chief when reviewBadgeCount > 0', () => {
    render(<NavRail {...defaultProps} reviewBadgeCount={3} />)
    expect(screen.getByText('3')).toBeInTheDocument()
  })

  it('does not show badge when reviewBadgeCount is 0', () => {
    render(<NavRail {...defaultProps} reviewBadgeCount={0} />)
    expect(screen.queryByText('0')).not.toBeInTheDocument()
  })

  it('highlights the active section', () => {
    render(<NavRail {...defaultProps} section="chief" />)
    const chiefBtn = screen.getByTitle('Chief')
    expect(chiefBtn.closest('div')).toHaveClass('bg-adj-accent/20')
  })
})
