// ui/src/__tests__/DirectiveTemplates.test.tsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import '@testing-library/jest-dom'
import DirectiveTemplates from '../components/DirectiveTemplates'

// Mock the API module
vi.mock('../api', () => ({
  api: {
    getTemplates: vi.fn().mockResolvedValue([
      { id: 1, label: 'Check email',   content: 'Check and summarize recent emails',         display_order: 0 },
      { id: 2, label: 'Weekly status', content: 'Give me a full status update on all active workstreams and objectives', display_order: 1 },
      { id: 3, label: 'Growth ideas',  content: 'Research and suggest three growth initiatives we should prioritize this week', display_order: 2 },
    ]),
    createTemplate: vi.fn().mockImplementation((_pw, _pid, label, content) =>
      Promise.resolve({ id: 99, label, content, display_order: 3 }),
    ),
    updateTemplate: vi.fn().mockResolvedValue(undefined),
    deleteTemplate: vi.fn().mockResolvedValue(undefined),
  },
}))

const mockOnSelect = vi.fn()
const defaultProps = { productId: 'product-alpha', password: 'test', onSelect: mockOnSelect }

beforeEach(() => {
  localStorage.clear()
  mockOnSelect.mockClear()
  vi.clearAllMocks()
})

describe('DirectiveTemplates', () => {
  it('renders templates loaded from API', async () => {
    render(<DirectiveTemplates {...defaultProps} />)
    await waitFor(() => expect(screen.getByText('Check email')).toBeInTheDocument())
  })

  it('calls onSelect with template content when chip clicked', async () => {
    render(<DirectiveTemplates {...defaultProps} />)
    await waitFor(() => screen.getByText('Check email'))
    fireEvent.click(screen.getByText('Check email'))
    expect(mockOnSelect).toHaveBeenCalledWith('Check and summarize recent emails')
  })

  it('adds a new template via two-field form', async () => {
    render(<DirectiveTemplates {...defaultProps} />)
    await waitFor(() => screen.getByTitle('Add template'))
    fireEvent.click(screen.getByTitle('Add template'))
    fireEvent.change(screen.getByPlaceholderText('Chip name (short)…'), { target: { value: 'Weekly report' } })
    fireEvent.change(screen.getByPlaceholderText('Full directive text…'), { target: { value: 'Run the full weekly report' } })
    fireEvent.click(screen.getByText('Add'))
    await waitFor(() => expect(screen.getByText('Weekly report')).toBeInTheDocument())
  })

  it('removes a template on delete click', async () => {
    render(<DirectiveTemplates {...defaultProps} />)
    await waitFor(() => screen.getAllByTitle('Remove template'))
    const deleteButtons = screen.getAllByTitle('Remove template')
    fireEvent.click(deleteButtons[0])
    await waitFor(() =>
      expect(screen.getAllByTitle('Remove template')).toHaveLength(deleteButtons.length - 1)
    )
  })

  it('edits an existing template label and content', async () => {
    render(<DirectiveTemplates {...defaultProps} />)
    await waitFor(() => screen.getAllByTitle('Edit template'))
    fireEvent.click(screen.getAllByTitle('Edit template')[0])
    fireEvent.change(screen.getByPlaceholderText('Chip name (short)…'), { target: { value: 'Renamed' } })
    fireEvent.click(screen.getByText('Save'))
    await waitFor(() => expect(screen.getByText('Renamed')).toBeInTheDocument())
  })
})
