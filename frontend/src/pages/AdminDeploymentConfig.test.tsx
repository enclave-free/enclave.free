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
  let tombstoneRetryCompleted = false

  beforeEach(() => {
    tombstoneRetryCompleted = false
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
      if (endpoint === '/admin/lifecycle/status') {
        return Promise.resolve(Response.json({
          data_classes: [
            {
              key: 'sage_session_memory',
              label: 'Sage Session Memory',
              owner: 'Sage',
              storage_targets: ['Postgres'],
              deletion: {
                status: 'complete',
                summary: 'Conversation deletion removes the public session record and associated Sage Session Memory.',
              },
              retention: {
                status: 'partial',
                summary: 'Operators can invoke retention execution for stale active Conversation state; persistent Sage Session Memory retention is not implemented.',
              },
              audit: {
                status: 'not_started',
                summary: 'Session Memory lifecycle actions are not yet represented in the Audit Log.',
              },
              notes: ['Session Memory belongs to the Agent Runtime.'],
            },
          ],
          deletion_tombstones: {
            total: 2,
            incomplete: 1,
            completed: 1,
            by_class: {
              sage_session_memory: {
                total: 2,
                incomplete: 1,
                completed: 1,
              },
            },
          },
        }))
      }
      if (endpoint === '/admin/lifecycle/deletion-tombstones') {
        return Promise.resolve(Response.json({
          tombstones: [
            {
              id: 7,
              lifecycle_data_class: 'sage_session_memory',
              conversation_id: 'conversation-123',
              former_subject_ref: 'deleted_user:42',
              status: tombstoneRetryCompleted ? 'completed' : 'incomplete',
              source: 'retention_execution',
              workflow: 'run_retention',
              retry_count: tombstoneRetryCompleted ? 1 : 0,
              updated_at: tombstoneRetryCompleted ? '2026-05-14T13:05:00Z' : '2026-05-14T13:00:00Z',
              deletion: {
                status: tombstoneRetryCompleted ? 'succeeded' : 'failed',
                retryable: !tombstoneRetryCompleted,
                counts: tombstoneRetryCompleted
                  ? { succeeded: 1, skipped: 0, failed: 0 }
                  : { succeeded: 0, skipped: 0, failed: 1 },
                results: tombstoneRetryCompleted ? [] : [
                  {
                    target_kind: 'session_memory',
                    target_id: 'conversation-123',
                    action: 'delete_session_memory',
                    status: 'failed',
                    retryable: true,
                    detail: 'target_unavailable',
                  },
                ],
              },
            },
          ],
        }))
      }
      if (endpoint === '/admin/lifecycle/deletion-tombstones/7/retry') {
        tombstoneRetryCompleted = true
        return Promise.resolve(Response.json({
          status: 'succeeded',
          retryable: false,
          tombstone: {
            id: 7,
            lifecycle_data_class: 'sage_session_memory',
            conversation_id: 'conversation-123',
            former_subject_ref: 'deleted_user:42',
            status: 'completed',
            source: 'retention_execution',
            workflow: 'run_retention',
            retry_count: 1,
            updated_at: '2026-05-14T13:05:00Z',
            deletion: {
              status: 'succeeded',
              retryable: false,
              counts: { succeeded: 1, skipped: 0, failed: 0 },
              results: [],
            },
          },
          deletion: {
            status: 'succeeded',
            retryable: false,
            counts: { succeeded: 1, skipped: 0, failed: 0 },
            results: [],
          },
        }))
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

  it('shows operator-controlled privacy lifecycle status', async () => {
    render(
      <MemoryRouter initialEntries={['/admin/deployment']}>
        <Routes>
          <Route path="/admin/deployment" element={<AdminDeploymentConfig />} />
        </Routes>
      </MemoryRouter>
    )

    expect(await screen.findByRole('group', { name: 'Data Lifecycle Status' })).toBeInTheDocument()
    expect(screen.getByText('Sage Session Memory')).toBeInTheDocument()
    expect(screen.getByText('Owner: Sage')).toBeInTheDocument()
    expect(screen.getByText('Deletion: Complete')).toBeInTheDocument()
    expect(screen.getByText('Incomplete tombstones: 1')).toBeInTheDocument()
    expect(screen.getByText('Completed tombstones: 1')).toBeInTheDocument()

    await waitFor(() => {
      expect(mockAdminFetch).toHaveBeenCalledWith('/admin/lifecycle/status')
    })
  })

  it('shows deletion tombstones and lets admins retry incomplete Session Memory deletion', async () => {
    const user = userEvent.setup()

    render(
      <MemoryRouter initialEntries={['/admin/deployment']}>
        <Routes>
          <Route path="/admin/deployment" element={<AdminDeploymentConfig />} />
        </Routes>
      </MemoryRouter>
    )

    const tombstones = await screen.findByRole('group', { name: 'Deletion Tombstones' })
    expect(within(tombstones).getByText('conversation-123')).toBeInTheDocument()
    expect(within(tombstones).getByText('Incomplete')).toBeInTheDocument()
    expect(within(tombstones).getByText('target_unavailable')).toBeInTheDocument()
    expect(within(tombstones).getByText(/Updated:/)).toBeInTheDocument()
    expect(within(tombstones).queryByText(/Deleted user conversation content/i)).not.toBeInTheDocument()

    await user.click(within(tombstones).getByRole('button', { name: 'Retry deletion tombstone 7' }))

    await waitFor(() => {
      expect(mockAdminFetch).toHaveBeenCalledWith('/admin/lifecycle/deletion-tombstones/7/retry', { method: 'POST' })
    })
    await waitFor(() => {
      expect(mockAdminFetch).toHaveBeenCalledWith('/admin/lifecycle/deletion-tombstones')
    })
    expect(await within(tombstones).findByText('Completed')).toBeInTheDocument()
    expect(within(tombstones).queryByRole('button', { name: 'Retry deletion tombstone 7' })).not.toBeInTheDocument()
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
