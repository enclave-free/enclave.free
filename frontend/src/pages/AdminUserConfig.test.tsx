import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AdminUserConfig } from './AdminUserConfig'
import { adminFetch } from '../utils/adminApi'

vi.mock('../utils/adminApi', () => ({
  adminFetch: vi.fn(),
  isAdminAuthenticated: vi.fn(() => true),
}))

const mockAdminFetch = vi.mocked(adminFetch)

describe('AdminUserConfig', () => {
  beforeEach(() => {
    mockAdminFetch.mockImplementation((endpoint: string, options?: RequestInit) => {
      if (endpoint === '/admin/user-types') {
        return Promise.resolve(Response.json({ types: [] }))
      }
      if (endpoint === '/admin/user-fields') {
        return Promise.resolve(Response.json({ fields: [] }))
      }
      if (endpoint === '/admin/users') {
        return Promise.resolve(Response.json({ users: [] }))
      }
      if (endpoint === '/admin/settings' && options?.method === 'PUT') {
        return Promise.resolve(Response.json({ settings: { auto_approve_users: 'true' } }))
      }
      if (endpoint === '/admin/settings') {
        return Promise.resolve(Response.json({
          settings: {
            auto_approve_users: 'false',
            reachout_enabled: 'false',
          },
        }))
      }
      return Promise.resolve(Response.json({}))
    })
  })

  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it('lets an admin configure whether new users require User Approval', async () => {
    const user = userEvent.setup()

    render(
      <MemoryRouter initialEntries={['/admin/users']}>
        <Routes>
          <Route path="/admin/users" element={<AdminUserConfig />} />
        </Routes>
      </MemoryRouter>
    )

    const manualApproval = await screen.findByRole('checkbox', {
      name: /require manual approval for new users/i,
    })

    expect(manualApproval).toBeChecked()

    await user.click(manualApproval)
    await user.click(screen.getByRole('button', { name: /save user approval/i }))

    await waitFor(() => {
      expect(mockAdminFetch).toHaveBeenCalledWith('/admin/settings', expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify({ auto_approve_users: 'true' }),
      }))
    })

    expect(await screen.findByRole('note', { name: /user approval saved/i })).toHaveTextContent('Saved')
  })
})
