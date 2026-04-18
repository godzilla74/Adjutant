import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import '@testing-library/jest-dom'
import ProductWizard from '../components/ProductWizard'
import { api } from '../api'

vi.mock('../api', () => ({
  api: {
    getWizardPlan: vi.fn().mockResolvedValue({
      workstreams: [{ name: 'Daily Posts', mission: 'Post on social', schedule: 'daily' }],
      objectives:  [{ text: 'Grow followers', progress_target: 1000 }],
      required_integrations: ['twitter'],
    }),
  },
}))

const DEFAULT_PROPS = {
  password: 'pw',
  onComplete: vi.fn(),
  onClose: vi.fn(),
}

beforeEach(() => vi.clearAllMocks())

describe('ProductWizard', () => {
  it('renders step 1 with intent textarea', () => {
    render(<ProductWizard {...DEFAULT_PROPS} />)
    expect(screen.getByText(/What do you want Adjutant to do/i)).toBeInTheDocument()
    expect(screen.getByRole('textbox')).toBeInTheDocument()
  })

  it('disables "Build My Plan" when intent is empty', () => {
    render(<ProductWizard {...DEFAULT_PROPS} />)
    expect(screen.getByText('Build My Plan →')).toBeDisabled()
  })

  it('enables "Build My Plan" when intent has text', () => {
    render(<ProductWizard {...DEFAULT_PROPS} />)
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'I want to post on social media' } })
    expect(screen.getByText('Build My Plan →')).not.toBeDisabled()
  })

  it('advances to step 2 (Basics) on Continue', async () => {
    render(<ProductWizard {...DEFAULT_PROPS} />)
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Manage my social' } })
    fireEvent.click(screen.getByText('Build My Plan →'))
    await waitFor(() => {
      expect(screen.getByLabelText(/Product Name/i)).toBeInTheDocument()
    })
  })

  it('shows AI suggestions on step 3 after getWizardPlan resolves', async () => {
    render(<ProductWizard {...DEFAULT_PROPS} />)
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Manage my social' } })
    fireEvent.click(screen.getByText('Build My Plan →'))
    // advance past step 2
    await waitFor(() => screen.getByLabelText(/Product Name/i))
    fireEvent.change(screen.getByLabelText(/Product Name/i), { target: { value: 'My Brand' } })
    fireEvent.click(screen.getByText('Continue →'))
    await waitFor(() => {
      expect(screen.getByText('Daily Posts')).toBeInTheDocument()
      expect(screen.getByText('Grow followers')).toBeInTheDocument()
    })
  })

  it('allows adding a custom workstream on step 3', async () => {
    render(<ProductWizard {...DEFAULT_PROPS} />)
    // navigate to step 3
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Test' } })
    fireEvent.click(screen.getByText('Build My Plan →'))
    await waitFor(() => screen.getByLabelText(/Product Name/i))
    fireEvent.change(screen.getByLabelText(/Product Name/i), { target: { value: 'X' } })
    fireEvent.click(screen.getByText('Continue →'))
    await waitFor(() => screen.getByText('+ Add workstream'))
    fireEvent.click(screen.getByText('+ Add workstream'))
    expect(screen.getByPlaceholderText(/What should Adjutant do/i)).toBeInTheDocument()
  })

  it('calls onClose when × is clicked', () => {
    const onClose = vi.fn()
    render(<ProductWizard {...DEFAULT_PROPS} onClose={onClose} />)
    fireEvent.click(screen.getByTitle('Close'))
    expect(onClose).toHaveBeenCalled()
  })
})
