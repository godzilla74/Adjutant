import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import '@testing-library/jest-dom'
import TagsSettings from '../components/settings/TagsSettings'

const mockTags = vi.hoisted(() => [
  { id: 1, name: 'social:linkedin', description: 'LinkedIn opportunity', created_at: '2026-01-01', updated_at: '2026-01-01' },
  { id: 2, name: 'email:customers', description: 'Customer email', created_at: '2026-01-01', updated_at: '2026-01-01' },
])

vi.mock('../api', () => ({
  api: {
    listTags: vi.fn().mockResolvedValue(mockTags),
    createTag: vi.fn().mockResolvedValue({ id: 3, name: 'content:blog', description: 'Blog', created_at: '2026-01-01', updated_at: '2026-01-01' }),
    updateTag: vi.fn().mockResolvedValue({ id: 1, name: 'social:instagram', description: 'Instagram', created_at: '2026-01-01', updated_at: '2026-01-01' }),
    deleteTag: vi.fn().mockResolvedValue(undefined),
  },
}))

beforeEach(() => { vi.clearAllMocks() })

describe('TagsSettings', () => {
  it('loads and displays all tags', async () => {
    render(<TagsSettings password="test" />)
    await waitFor(() => expect(screen.getByText('social:linkedin')).toBeInTheDocument())
    expect(screen.getByText('email:customers')).toBeInTheDocument()
    expect(screen.getByText('LinkedIn opportunity')).toBeInTheDocument()
  })

  it('shows add form when Add Tag button is clicked', async () => {
    render(<TagsSettings password="test" />)
    await waitFor(() => screen.getByText('social:linkedin'))
    fireEvent.click(screen.getByText('+ Add Tag'))
    expect(screen.getByPlaceholderText(/namespace:tag/i)).toBeInTheDocument()
  })

  it('calls createTag and reloads on form submit', async () => {
    const { api } = await import('../api')
    render(<TagsSettings password="test" />)
    await waitFor(() => screen.getByText('social:linkedin'))
    fireEvent.click(screen.getByText('+ Add Tag'))
    fireEvent.change(screen.getByPlaceholderText(/namespace:tag/i), { target: { value: 'content:blog' } })
    fireEvent.change(screen.getByPlaceholderText(/description/i), { target: { value: 'Blog posts' } })
    fireEvent.click(screen.getByRole('button', { name: 'Add' }))
    await waitFor(() => expect(api.createTag).toHaveBeenCalledWith('test', 'content:blog', 'Blog posts'))
    expect(api.listTags).toHaveBeenCalledTimes(2)
  })

  it('shows edit form when tag name is clicked', async () => {
    render(<TagsSettings password="test" />)
    await waitFor(() => screen.getByText('social:linkedin'))
    fireEvent.click(screen.getByText('social:linkedin'))
    expect(screen.getByDisplayValue('social:linkedin')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Save' })).toBeInTheDocument()
  })

  it('calls updateTag on save', async () => {
    const { api } = await import('../api')
    render(<TagsSettings password="test" />)
    await waitFor(() => screen.getByText('social:linkedin'))
    fireEvent.click(screen.getByText('social:linkedin'))
    const input = screen.getByDisplayValue('social:linkedin')
    fireEvent.change(input, { target: { value: 'social:instagram' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(api.updateTag).toHaveBeenCalledWith('test', 1, expect.objectContaining({ name: 'social:instagram' })))
  })

  it('calls deleteTag after confirm', async () => {
    const { api } = await import('../api')
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    render(<TagsSettings password="test" />)
    await waitFor(() => screen.getByText('social:linkedin'))
    fireEvent.click(screen.getAllByRole('button', { name: /delete tag/i })[0])
    await waitFor(() => expect(api.deleteTag).toHaveBeenCalledWith('test', 1))
  })
})
