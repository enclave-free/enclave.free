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

const makeTombstoneFixture = (completed = false, overrides: Record<string, unknown> = {}) => ({
  id: completed ? 8 : 7,
  lifecycle_data_class: 'sage_session_memory',
  conversation_id: completed ? 'conversation-456' : 'conversation-123',
  former_subject_ref: 'deleted_user:42',
  status: completed ? 'completed' : 'incomplete',
  source: 'retention_execution',
  workflow: 'run_retention',
  retry_count: completed ? 1 : 0,
  updated_at: completed ? '2026-05-14T13:05:00Z' : '2026-05-14T13:00:00Z',
  deletion: {
    status: completed ? 'succeeded' : 'failed',
    retryable: !completed,
    counts: completed
      ? { succeeded: 1, skipped: 0, failed: 0 }
      : { succeeded: 0, skipped: 0, failed: 1 },
    results: completed ? [] : [
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
  ...overrides,
})

describe('AdminDeploymentConfig', () => {
  let tombstoneRetryCompleted = false
  let tombstonesFixture: unknown[] | null

  beforeEach(() => {
    tombstoneRetryCompleted = false
    tombstonesFixture = null
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
      if (endpoint.startsWith('/admin/lifecycle/deletion-tombstones')) {
        const status = endpoint.includes('?status=completed')
          ? 'completed'
          : endpoint.includes('?status=incomplete')
            ? 'incomplete'
            : null
        const tombstones = tombstonesFixture ?? [makeTombstoneFixture(tombstoneRetryCompleted)]
        const filteredTombstones = status
          ? tombstones.filter((tombstone) => {
            return typeof tombstone === 'object'
              && tombstone !== null
              && 'status' in tombstone
              && tombstone.status === status
          })
          : tombstones
        return Promise.resolve(Response.json({
          tombstones: filteredTombstones,
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
    expect(within(tombstones).getAllByText('Incomplete').length).toBeGreaterThan(0)
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
    await waitFor(() => {
      expect(within(tombstones).getAllByText('Completed').length).toBeGreaterThan(0)
    })
    expect(within(tombstones).queryByRole('button', { name: 'Retry deletion tombstone 7' })).not.toBeInTheDocument()
  })

  it('shows an empty tombstone state when no lifecycle deletion needs retry', async () => {
    tombstonesFixture = []

    render(
      <MemoryRouter initialEntries={['/admin/deployment']}>
        <Routes>
          <Route path="/admin/deployment" element={<AdminDeploymentConfig />} />
        </Routes>
      </MemoryRouter>
    )

    const tombstones = await screen.findByRole('group', { name: 'Deletion Tombstones' })
    expect(within(tombstones).getByText('No deletion tombstones are waiting for retry.')).toBeInTheDocument()
    expect(within(tombstones).queryByRole('button', { name: /Retry deletion tombstone/i })).not.toBeInTheDocument()
  })

  it('filters deletion tombstones by lifecycle status', async () => {
    const user = userEvent.setup()
    tombstonesFixture = [
      makeTombstoneFixture(false),
      makeTombstoneFixture(true),
    ]

    render(
      <MemoryRouter initialEntries={['/admin/deployment']}>
        <Routes>
          <Route path="/admin/deployment" element={<AdminDeploymentConfig />} />
        </Routes>
      </MemoryRouter>
    )

    const tombstones = await screen.findByRole('group', { name: 'Deletion Tombstones' })
    expect(within(tombstones).getByText('conversation-123')).toBeInTheDocument()
    expect(within(tombstones).getByText('conversation-456')).toBeInTheDocument()

    await user.click(within(tombstones).getByRole('button', { name: 'Completed tombstones' }))

    await waitFor(() => {
      expect(mockAdminFetch).toHaveBeenCalledWith('/admin/lifecycle/deletion-tombstones?status=completed')
    })
    expect(within(tombstones).queryByText('conversation-123')).not.toBeInTheDocument()
    expect(await within(tombstones).findByText('conversation-456')).toBeInTheDocument()
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
