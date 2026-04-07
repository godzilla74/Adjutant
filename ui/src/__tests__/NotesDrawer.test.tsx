// ui/src/__tests__/NotesDrawer.test.tsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import '@testing-library/jest-dom'
import NotesDrawer from '../components/NotesDrawer'

vi.mock('../api', () => ({
  api: {
    getNotes: vi.fn().mockResolvedValue({ content: 'Existing note text', updated_at: '2024-01-01 10:00:00' }),
    updateNotes: vi.fn().mockResolvedValue({ content: 'New content', updated_at: '2024-01-01 11:00:00' }),
  },
}))

const defaultProps = {
  productId: 'retainerops',
  password: 'test',
  onClose: vi.fn(),
}

beforeEach(() => {
  vi.clearAllMocks()
  defaultProps.onClose.mockClear()
})

describe('NotesDrawer', () => {
  it('loads and displays existing notes', async () => {
    render(<NotesDrawer {...defaultProps} />)
    await waitFor(() => expect(screen.getByDisplayValue('Existing note text')).toBeInTheDocument())
  })

  it('saves notes when Save button is clicked', async () => {
    const { api } = await import('../api')
    render(<NotesDrawer {...defaultProps} />)
    await waitFor(() => screen.getByDisplayValue('Existing note text'))
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'New content' } })
    fireEvent.click(screen.getByText('Save'))
    await waitFor(() => expect(api.updateNotes).toHaveBeenCalledWith('test', 'retainerops', 'New content'))
  })

  it('closes when backdrop is clicked', async () => {
    render(<NotesDrawer {...defaultProps} />)
    await waitFor(() => screen.getByDisplayValue('Existing note text'))
    fireEvent.click(document.querySelector('.fixed.inset-0')!)
    expect(defaultProps.onClose).toHaveBeenCalled()
  })
})
