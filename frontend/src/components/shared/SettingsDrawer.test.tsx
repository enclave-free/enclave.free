import { cleanup, render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { SettingsDrawer } from './SettingsDrawer'
import { useAuthFlow } from '../../hooks/useAuthFlow'

vi.mock('../../hooks/useAuthFlow', () => ({
  clearAllAuth: vi.fn(),
  useAuthFlow: vi.fn(),
}))

const mockUseAuthFlow = vi.mocked(useAuthFlow)

describe('SettingsDrawer', () => {
  beforeEach(() => {
    mockUseAuthFlow.mockReturnValue({
      isAdmin: true,
      isAuthenticated: true,
      isApproved: true,
      userEmail: 'admin@example.test',
      userName: 'Admin',
      redirectPath: '/chat',
    })
  })

  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it('keeps diagnostics reachable as a secondary section outside primary Admin tools', () => {
    render(
      <MemoryRouter>
        <SettingsDrawer open onClose={vi.fn()} />
      </MemoryRouter>
    )

    const adminTools = screen.getByRole('region', { name: 'Admin Tools' })
    expect(within(adminTools).getByRole('link', { name: /Admin Dashboard/ })).toHaveAttribute('href', '/admin/setup')
    expect(within(adminTools).getByRole('link', { name: /Deployment Settings/ })).toHaveAttribute('href', '/admin/deployment')
    expect(within(adminTools).queryByRole('link', { name: /Diagnostics Test Dashboard/ })).not.toBeInTheDocument()

    const diagnostics = screen.getByRole('region', { name: 'Diagnostics' })
    expect(within(diagnostics).getByRole('link', { name: /Diagnostics Test Dashboard/ })).toHaveAttribute('href', '/diagnostics/test-dashboard')
  })
})
