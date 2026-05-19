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

  it('keeps the human product review handoff visible with a follow-up issue target', () => {
    render(
      <MemoryRouter initialEntries={['/admin/setup']}>
        <Routes>
          <Route path="/admin/setup" element={<AdminSetup />} />
        </Routes>
      </MemoryRouter>
    )

    const handoff = screen.getByRole('region', { name: 'Human review handoff' })

    expect(handoff).toHaveTextContent('Human product/design review still required')
    expect(handoff).toHaveTextContent('Record remaining follow-ups in issue #176')
    expect(within(handoff).getByRole('link', { name: 'Open issue #176' })).toHaveAttribute('href', 'https://github.com/enclave-free/enclave.free-prototype/issues/176')
  })
})
