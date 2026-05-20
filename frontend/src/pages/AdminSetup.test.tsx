import { cleanup, render, screen, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AdminSetup } from './AdminSetup'
import { isAdminAuthenticated } from '../utils/adminApi'

vi.mock('../utils/adminApi', () => ({
  isAdminAuthenticated: vi.fn(),
}))

const mockIsAdminAuthenticated = vi.mocked(isAdminAuthenticated)

describe('AdminSetup', () => {
  beforeEach(() => {
    mockIsAdminAuthenticated.mockReturnValue(true)
  })

  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it('gives admins a clear first-run path into Deployment Readiness review', () => {
    render(
      <MemoryRouter initialEntries={['/admin/setup']}>
        <Routes>
          <Route path="/admin/setup" element={<AdminSetup />} />
        </Routes>
      </MemoryRouter>
    )

    const readiness = screen.getByRole('region', { name: 'Deployment Readiness' })
    expect(readiness).toHaveTextContent('Review readiness before inviting users')
    expect(within(readiness).getByRole('link', { name: 'Open Readiness Review' })).toHaveAttribute('href', '/admin/deployment')
  })

  it('uses domain setting names without blending Deployment Readiness into configuration', () => {
    render(
      <MemoryRouter initialEntries={['/admin/setup']}>
        <Routes>
          <Route path="/admin/setup" element={<AdminSetup />} />
        </Routes>
      </MemoryRouter>
    )

    const settings = screen.getByRole('region', { name: 'Admin Settings' })
    expect(within(settings).getByRole('link', { name: /Instance Settings/ })).toHaveAttribute('href', '/admin/instance')
    expect(within(settings).getByRole('link', { name: /Agent Settings/ })).toHaveAttribute('href', '/admin/ai')
    expect(within(settings).getByRole('link', { name: /Deployment Settings/ })).toHaveAttribute('href', '/admin/deployment')
    expect(screen.getByRole('region', { name: 'Deployment Readiness' })).toBeInTheDocument()
    expect(screen.queryByText('Instance Configuration')).not.toBeInTheDocument()
    expect(screen.queryByText('Deployment Configuration')).not.toBeInTheDocument()
  })

  it('shows a reviewable Admin first-run path from setup through readiness and diagnostics', () => {
    render(
      <MemoryRouter initialEntries={['/admin/setup']}>
        <Routes>
          <Route path="/admin/setup" element={<AdminSetup />} />
        </Routes>
      </MemoryRouter>
    )

    const path = screen.getByRole('region', { name: 'Admin first-run path' })
    const steps = within(path).getAllByRole('listitem')

    expect(steps).toHaveLength(3)
    expect(steps[0]).toHaveTextContent('Configure the Instance baseline')
    expect(within(steps[0]).getByRole('link', { name: 'Open Instance Settings' })).toHaveAttribute('href', '/admin/instance')
    expect(steps[1]).toHaveTextContent('Review Deployment Readiness')
    expect(within(steps[1]).getByRole('link', { name: 'Open Deployment Wizard' })).toHaveAttribute('href', '/admin/deployment#wizard')
    expect(steps[2]).toHaveTextContent('Use diagnostics only when investigating')
    expect(within(steps[2]).getByRole('link', { name: 'Open Diagnostics' })).toHaveAttribute('href', '/diagnostics/test-dashboard')
  })

  it('sends the first-run readiness step directly to the Deployment Wizard review', () => {
    render(
      <MemoryRouter initialEntries={['/admin/setup']}>
        <Routes>
          <Route path="/admin/setup" element={<AdminSetup />} />
        </Routes>
      </MemoryRouter>
    )

    const path = screen.getByRole('region', { name: 'Admin first-run path' })
    const readinessStep = within(path).getByText('Review Deployment Readiness').closest('li')

    expect(readinessStep).not.toBeNull()
    expect(within(readinessStep as HTMLElement).getByRole('link', { name: 'Open Deployment Wizard' })).toHaveAttribute('href', '/admin/deployment#wizard')
  })

  it('surfaces the Admin IA review terms that must remain distinct', () => {
    render(
      <MemoryRouter initialEntries={['/admin/setup']}>
        <Routes>
          <Route path="/admin/setup" element={<AdminSetup />} />
        </Routes>
      </MemoryRouter>
    )

    const checklist = screen.getByRole('region', { name: 'Admin IA review checklist' })

    expect(checklist).toHaveTextContent('Deployment Settings')
    expect(checklist).toHaveTextContent('Instance Settings')
    expect(checklist).toHaveTextContent('Agent Settings')
    expect(checklist).toHaveTextContent('Lifecycle Readiness')
    expect(checklist).toHaveTextContent('Deployment Readiness')
    expect(checklist).toHaveTextContent('diagnostic surfaces')
  })

  it('keeps the deployment automation boundary review handoff visible with the issue target', () => {
    render(
      <MemoryRouter initialEntries={['/admin/setup']}>
        <Routes>
          <Route path="/admin/setup" element={<AdminSetup />} />
        </Routes>
      </MemoryRouter>
    )

    const handoff = screen.getByRole('region', { name: 'Human review handoff' })

    expect(handoff).toHaveTextContent('External Deployment Automation contract review required')
    expect(handoff).toHaveTextContent('Operator-run runtime env apply is decided; design any future external Deployment Automation contract in issue #190')
    expect(within(handoff).getByRole('link', { name: 'Open issue #190' })).toHaveAttribute('href', 'https://github.com/enclave-free/enclave.free-prototype/issues/190')
  })

  it('keeps Data & Content focused on document content instead of diagnostics', () => {
    render(
      <MemoryRouter initialEntries={['/admin/setup']}>
        <Routes>
          <Route path="/admin/setup" element={<AdminSetup />} />
        </Routes>
      </MemoryRouter>
    )

    const content = screen.getByRole('region', { name: 'Data & Content' })

    expect(within(content).getByRole('link', { name: /Document Upload/ })).toHaveAttribute('href', '/admin/upload')
    expect(within(content).queryByRole('link', { name: /Database Explorer/ })).not.toBeInTheDocument()
  })

  it('keeps diagnostic tools reachable in a separate Diagnostics region', () => {
    render(
      <MemoryRouter initialEntries={['/admin/setup']}>
        <Routes>
          <Route path="/admin/setup" element={<AdminSetup />} />
        </Routes>
      </MemoryRouter>
    )

    const diagnostics = screen.getByRole('region', { name: 'Diagnostics' })

    expect(within(diagnostics).getByRole('link', { name: /Database Explorer/ })).toHaveAttribute('href', '/admin/database')
    expect(within(diagnostics).getByRole('link', { name: /Diagnostics Test Dashboard/ })).toHaveAttribute('href', '/diagnostics/test-dashboard')
  })

  it('lets human reviewers open an external automation contract follow-up issue from the handoff', () => {
    render(
      <MemoryRouter initialEntries={['/admin/setup']}>
        <Routes>
          <Route path="/admin/setup" element={<AdminSetup />} />
        </Routes>
      </MemoryRouter>
    )

    const handoff = screen.getByRole('region', { name: 'Human review handoff' })
    const followUp = within(handoff).getByRole('link', { name: 'Create automation-contract follow-up' })

    expect(followUp).toHaveAttribute('href', expect.stringContaining('https://github.com/enclave-free/enclave.free-prototype/issues/new'))
    expect(followUp).toHaveAttribute('href', expect.stringContaining('labels=enhancement'))
    expect(followUp).toHaveAttribute('href', expect.stringContaining('Deployment%20Automation%20contract%20follow-up'))
    expect(followUp).toHaveAttribute('href', expect.stringContaining('%23190'))
  })
})
