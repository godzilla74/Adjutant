// ui/src/__tests__/DirectiveTemplates.test.tsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import '@testing-library/jest-dom'
import DirectiveTemplates from '../components/DirectiveTemplates'

const mockOnSelect = vi.fn()

beforeEach(() => {
  localStorage.clear()
  mockOnSelect.mockClear()
})

describe('DirectiveTemplates', () => {
  it('renders default templates when localStorage is empty', () => {
    render(<DirectiveTemplates productId="retainerops" onSelect={mockOnSelect} />)
    expect(screen.getByText('Check email')).toBeInTheDocument()
  })

  it('calls onSelect with template content when chip clicked', () => {
    render(<DirectiveTemplates productId="retainerops" onSelect={mockOnSelect} />)
    fireEvent.click(screen.getByText('Check email'))
    expect(mockOnSelect).toHaveBeenCalledWith('Check and summarize recent emails')
  })

  it('adds a new template via input', () => {
    render(<DirectiveTemplates productId="retainerops" onSelect={mockOnSelect} />)
    const addBtn = screen.getByTitle('Add template')
    fireEvent.click(addBtn)
    const input = screen.getByPlaceholderText('Template text…')
    fireEvent.change(input, { target: { value: 'Run weekly report' } })
    fireEvent.keyDown(input, { key: 'Enter' })
    expect(screen.getByText('Run weekly report')).toBeInTheDocument()
  })

  it('removes a template on delete click', () => {
    render(<DirectiveTemplates productId="retainerops" onSelect={mockOnSelect} />)
    const deleteButtons = screen.getAllByTitle('Remove template')
    const count = deleteButtons.length
    fireEvent.click(deleteButtons[0])
    expect(screen.getAllByTitle('Remove template')).toHaveLength(count - 1)
  })

  it('persists templates to localStorage per productId', () => {
    const { unmount } = render(<DirectiveTemplates productId="retainerops" onSelect={mockOnSelect} />)
    const addBtn = screen.getByTitle('Add template')
    fireEvent.click(addBtn)
    const input = screen.getByPlaceholderText('Template text…')
    fireEvent.change(input, { target: { value: 'My custom template' } })
    fireEvent.keyDown(input, { key: 'Enter' })
    unmount()
    render(<DirectiveTemplates productId="retainerops" onSelect={mockOnSelect} />)
    expect(screen.getByText('My custom template')).toBeInTheDocument()
  })
})
