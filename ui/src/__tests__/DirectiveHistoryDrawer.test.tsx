// ui/src/__tests__/DirectiveHistoryDrawer.test.tsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import '@testing-library/jest-dom'
import DirectiveHistoryDrawer from '../components/DirectiveHistoryDrawer'

vi.mock('../api', () => ({
  api: {
    getDirectiveHistory: vi.fn().mockResolvedValue([
      { id: 3, content: 'Research competitor pricing', created_at: '2024-01-15 14:00:00' },
      { id: 2, content: 'Draft three blog post ideas', created_at: '2024-01-15 10:00:00' },
      { id: 1, content: 'Check email and summarize', created_at: '2024-01-14 09:00:00' },
    ]),
  },
}))

const mockOnSelect = vi.fn()
const defaultProps = {
  productId: 'product-alpha',
  password: 'test',
  onClose: vi.fn(),
  onSelect: mockOnSelect,
}

beforeEach(() => {
  vi.clearAllMocks()
  defaultProps.onClose.mockClear()
  mockOnSelect.mockClear()
})

describe('DirectiveHistoryDrawer', () => {
  it('loads and displays past directives', async () => {
    render(<DirectiveHistoryDrawer {...defaultProps} />)
    await waitFor(() => expect(screen.getByText('Research competitor pricing')).toBeInTheDocument())
    expect(screen.getByText('Draft three blog post ideas')).toBeInTheDocument()
  })

  it('calls onSelect when Use button is clicked', async () => {
    render(<DirectiveHistoryDrawer {...defaultProps} />)
    await waitFor(() => screen.getAllByText('Use'))
    fireEvent.click(screen.getAllByText('Use')[0])
    expect(mockOnSelect).toHaveBeenCalledWith('Research competitor pricing')
    expect(defaultProps.onClose).not.toHaveBeenCalled()
  })

  it('closes when backdrop is clicked', async () => {
    render(<DirectiveHistoryDrawer {...defaultProps} />)
    await waitFor(() => screen.getByText('Research competitor pricing'))
    fireEvent.click(document.querySelector('.fixed.inset-0')!)
    expect(defaultProps.onClose).toHaveBeenCalled()
  })
})
