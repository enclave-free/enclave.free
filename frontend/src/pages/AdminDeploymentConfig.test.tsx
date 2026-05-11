import { cleanup, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AdminDeploymentConfig } from './AdminDeploymentConfig'
import { adminFetch } from '../utils/adminApi'

vi.mock('../utils/adminApi', () => ({
  adminFetch: vi.fn(),
  clearAdminAuth: vi.fn(),
  isAdminAuthenticated: vi.fn(() => true),
}))

vi.mock('../utils/nostrAuth', () => ({
  hasNostrExtension: vi.fn(() => true),
}))

vi.mock('../utils/encryption', () => ({
  decryptField: vi.fn(),
  hasNip04Support: vi.fn(() => true),
}))

const mockAdminFetch = vi.mocked(adminFetch)

describe('AdminDeploymentConfig', () => {
  beforeEach(() => {
    vi.stubGlobal('localStorage', {
      getItem: vi.fn(() => null),
      removeItem: vi.fn(),
      setItem: vi.fn(),
    })

    mockAdminFetch.mockImplementation((endpoint: string) => {
      if (endpoint === '/admin/deployment/config') {
        return Promise.resolve(Response.json({
          llm: [],
          embedding: [],
          email: [],
          storage: [],
          search: [],
          security: [
            {
              key: 'RATE_LIMIT_CHAT_PER_MINUTE',
              value: '120',
              is_secret: false,
              requires_restart: true,
              category: 'security',
              description: 'Chat requests per minute',
            },
          ],
          domains: [],
          ssl: [],
          general: [],
        }))
      }
      if (endpoint === '/admin/deployment/health') {
        return Promise.resolve(Response.json({
          services: [],
          restart_required: false,
          changed_keys_requiring_restart: [],
        }))
      }
      if (endpoint.startsWith('/admin/deployment/audit-log')) {
        return Promise.resolve(Response.json({ entries: [] }))
      }
      if (endpoint === '/admin/key-migration/prepare') {
        return Promise.resolve(Response.json({
          admin_pubkey: 'a'.repeat(64),
          users: [],
          field_values: [],
          user_count: 2,
          field_value_count: 3,
        }))
      }
      return Promise.resolve(Response.json({}))
    })
  })

  afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
    vi.clearAllMocks()
  })

  it('shows rate limit parameters with operator-friendly labels', async () => {
    render(
      <MemoryRouter initialEntries={['/admin/deployment']}>
        <Routes>
          <Route path="/admin/deployment" element={<AdminDeploymentConfig />} />
        </Routes>
      </MemoryRouter>
    )

    expect(await screen.findByText('Chat Rate Limit')).toBeInTheDocument()
    expect(screen.getByText('Chat requests per minute')).toBeInTheDocument()

    const securitySettings = screen.getByRole('group', { name: 'Security & URLs Settings' })
    expect(within(securitySettings).getByText('Chat Rate Limit')).toBeInTheDocument()
  })

  it('keeps admin key migration behind a named destructive confirmation', async () => {
    const user = userEvent.setup()

    render(
      <MemoryRouter initialEntries={['/admin/deployment']}>
        <Routes>
          <Route path="/admin/deployment" element={<AdminDeploymentConfig />} />
        </Routes>
      </MemoryRouter>
    )

    await screen.findByText('Chat Rate Limit')

    await user.click(screen.getByRole('button', { name: 'Start Migration' }))
    await user.type(screen.getByLabelText('New admin public key'), 'b'.repeat(64))
    await user.click(screen.getByRole('button', { name: 'Continue' }))

    await waitFor(() => {
      expect(mockAdminFetch).toHaveBeenCalledWith('/admin/key-migration/prepare')
    })

    const warning = await screen.findByRole('note', { name: 'Admin key migration destructive warning' })
    expect(warning).toHaveTextContent('Confirm Key Migration')
    expect(warning).toHaveTextContent('old key will no longer be able to decrypt instance data')

    const dialog = screen.getByRole('dialog', { name: 'Admin Key Migration' })
    expect(within(dialog).getByText('Users to migrate')).toBeInTheDocument()
    expect(within(dialog).getByText('2')).toBeInTheDocument()
    expect(within(dialog).getByText('Fields to migrate')).toBeInTheDocument()
    expect(within(dialog).getByText('3')).toBeInTheDocument()
    expect(within(dialog).getByRole('button', { name: 'Confirm & Migrate' })).toHaveClass('btn-danger')
  })
})
