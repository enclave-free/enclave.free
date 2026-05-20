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
  let tombstoneRetryShouldFail = false
  let tombstoneFetchShouldFail = false
  let tombstonesFixture: unknown[] | null
  let acknowledgedSurfaceKeys: string[]
  let acknowledgedSurfaceCategories: string[]
  let artifactEncryptionPosture: 'required' | 'disabled'
  let verificationStatus = 'current'
  let verificationRecordDetailRequested = false
  let readinessStatus = 'blocked'
  let sessionMemoryRetentionPolicy = {
    enabled: false,
    retention_window_days: 30,
    scheduled_enforcement_enabled: false,
  }

  beforeEach(() => {
    tombstoneRetryCompleted = false
    tombstoneRetryShouldFail = false
    tombstoneFetchShouldFail = false
    tombstonesFixture = null
    acknowledgedSurfaceKeys = []
    acknowledgedSurfaceCategories = []
    artifactEncryptionPosture = 'required'
    verificationStatus = 'current'
    verificationRecordDetailRequested = false
    readinessStatus = 'blocked'
    sessionMemoryRetentionPolicy = {
      enabled: false,
      retention_window_days: 30,
      scheduled_enforcement_enabled: false,
    }
    vi.stubGlobal('localStorage', {
      getItem: vi.fn(() => null),
      removeItem: vi.fn(),
      setItem: vi.fn(),
    })
    const nativeUrl = globalThis.URL
    function MockUrl(input: string | URL, base?: string | URL) {
      return new nativeUrl(input, base)
    }
    Object.setPrototypeOf(MockUrl, nativeUrl)
    MockUrl.prototype = nativeUrl.prototype
    vi.stubGlobal('URL', Object.assign(MockUrl, {
      createObjectURL: vi.fn(() => 'blob:test-sage-env'),
      revokeObjectURL: vi.fn(),
    }))

    mockAdminFetch.mockImplementation((endpoint: string, options?: RequestInit) => {
      if (endpoint === '/admin/deployment/config') {
        return Promise.resolve(Response.json({
          llm: [
            {
              key: 'LLM_PROVIDER',
              value: 'sage',
              is_secret: false,
              requires_restart: true,
              category: 'llm',
              description: 'Model Provider',
            },
          ],
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
      if (endpoint === '/admin/deployment/runtime-env/sage') {
        return Promise.resolve(new Response('TINFOIL_MODEL=kimi-k2-6\n', {
          headers: { 'content-type': 'text/plain' },
        }))
      }
      if (endpoint === '/admin/deployment/runtime-env/core-backend') {
        return Promise.resolve(new Response('LLM_MODEL=kimi-k2-6\n', {
          headers: { 'content-type': 'text/plain' },
        }))
      }
      if (endpoint === '/admin/deployment/health') {
        return Promise.resolve(Response.json({
          services: [],
          restart_required: false,
          changed_keys_requiring_restart: [],
          runtime_env: {
            sage: {
              desired: { status: 'configured', configured_keys: 7, total_keys: 7 },
              generated: { status: 'current', latest_export_at: '2026-05-19T12:00:00+00:00' },
              running: {
                status: 'not_directly_introspected',
                summary: 'Sage live runtime env is not directly introspected in this slice; use service health plus generated env freshness.',
                changed_keys_requiring_restart: [],
              },
            },
            core_backend: {
              desired: { status: 'configured', configured_keys: 7, total_keys: 7 },
              generated: { status: 'current', latest_export_at: '2026-05-19T12:00:00+00:00' },
              running: {
                status: 'matches_desired',
                summary: 'Core backend running runtime config matches desired Deployment Settings.',
              },
            },
          },
        }))
      }
      if (endpoint === '/admin/deployment/readiness') {
        return Promise.resolve(Response.json({
          status: readinessStatus,
          summary: {
            blockers: readinessStatus === 'blocked' ? 1 : 0,
            warnings: 3,
            ready: readinessStatus === 'blocked' ? 2 : 3,
            total: 6,
          },
          items: [
            {
              key: 'verifiable_inference',
              label: 'Verifiable Inference',
              source: 'inference_verification',
              severity: readinessStatus === 'blocked' ? 'blocker' : 'ready',
              status: readinessStatus === 'blocked' ? 'missing' : 'current',
              summary: readinessStatus === 'blocked'
                ? 'Current Verifiable Inference is required before normal Conversations can run.'
                : 'Current Verifiable Inference evidence is available for normal Conversations.',
              next_action: readinessStatus === 'blocked'
                ? 'Run Model Provider verification or repair provider configuration.'
                : 'No action required.',
              conversation_blocking: readinessStatus === 'blocked',
            },
            {
              key: 'lifecycle_readiness',
              label: 'Lifecycle Readiness',
              source: 'lifecycle_readiness',
              severity: 'warning',
              status: 'stale',
              summary: 'Lifecycle Readiness is stale and needs Admin review.',
              next_action: 'Review lifecycle status and unsupported Deployment Surfaces.',
              conversation_blocking: false,
            },
            {
              key: 'deployment_validation',
              label: 'Deployment Validation',
              source: 'deployment_validation',
              severity: 'ready',
              status: 'valid',
              summary: 'Deployment Settings are valid.',
              next_action: 'No action required.',
              conversation_blocking: false,
            },
            {
              key: 'sage_runtime_env',
              label: 'Sage Runtime Env',
              source: 'runtime_env',
              severity: 'warning',
              status: 'drifted',
              summary: 'Running Sage runtime config differs from desired Deployment Settings.',
              next_action: 'Investigate Sage runtime config drift, apply the generated Sage env, and restart Sage.',
              conversation_blocking: false,
            },
            {
              key: 'backup_restore_drill',
              label: 'Backup And Restore Drill',
              source: 'operational_readiness',
              severity: 'warning',
              status: 'operator_evidence_required',
              summary: 'Record restore drill evidence in the operator checklist.',
              next_action: 'Record a restore drill for the Single-Instance Deployment.',
              conversation_blocking: false,
            },
            {
              key: 'restart_required',
              label: 'Restart Required',
              source: 'restart_required',
              severity: 'ready',
              status: 'current',
              summary: 'No restart-required Deployment Settings have changed since service start.',
              next_action: 'No action required.',
              conversation_blocking: false,
            },
          ],
        }))
      }
      if (endpoint === '/admin/deployment/inference-verification/status') {
        return Promise.resolve(Response.json({
          status: verificationStatus,
          checked_at: '2026-05-15T12:00:00Z',
          expires_at: '2026-05-16T12:00:00Z',
          expected_claims_fingerprint: 'expected-fingerprint',
          configured_provider: {
            provider_identity: 'sage',
            provider_endpoint: 'https://inference.tinfoil.sh/v1',
            model_identifier: 'kimi-k2-6',
          },
          record: verificationStatus === 'current'
            ? {
              id: 42,
              provider_identity: 'sage',
              provider_endpoint: 'https://inference.tinfoil.sh/v1',
              model_identifier: 'kimi-k2-6',
              checked_at: '2026-05-15T12:00:00Z',
              expires_at: '2026-05-16T12:00:00Z',
              verifier_version: 'test-verifier/1',
            }
            : null,
        }))
      }
      if (endpoint === '/admin/deployment/inference-verification/records') {
        return Promise.resolve(Response.json({
          records: [
            {
              id: 42,
              status: 'success',
              trigger: 'manual',
              provider_identity: 'sage',
              provider_endpoint: 'https://inference.tinfoil.sh/v1',
              model_identifier: 'kimi-k2-6',
              checked_at: '2026-05-15T12:00:00Z',
              expires_at: '2026-05-16T12:00:00Z',
              verifier_version: 'test-verifier/1',
            },
          ],
        }))
      }
      if (endpoint === '/admin/deployment/inference-verification/records/42') {
        verificationRecordDetailRequested = true
        return Promise.resolve(Response.json({
          id: 42,
          status: 'success',
          trigger: 'manual',
          attestation_material: {
            quote: 'full-attestation-material',
          },
        }))
      }
      if (endpoint === '/admin/deployment/inference-verification/verify') {
        verificationStatus = 'current'
        return Promise.resolve(Response.json({
          id: 43,
          status: 'success',
          trigger: 'manual',
          provider_identity: 'sage',
          provider_endpoint: 'https://inference.tinfoil.sh/v1',
          model_identifier: 'kimi-k2-6',
          checked_at: '2026-05-15T12:05:00Z',
          expires_at: '2026-05-16T12:05:00Z',
          attestation_material: {
            quote: 'manual-attestation-material',
          },
        }))
      }
      if (endpoint.startsWith('/admin/deployment/audit-log')) {
        return Promise.resolve(Response.json({ entries: [] }))
      }
      if (endpoint === '/admin/lifecycle/status') {
        return Promise.resolve(Response.json({
          lifecycle_scope: {
            key: 'active_storage_lifecycle',
            label: 'Active Storage Lifecycle',
            summary: 'Lifecycle controls apply to supported Lifecycle Data Classes in active product storage.',
            excludes: 'Deployment Surfaces such as logs and backups.',
          },
          content_encryption: {
            status: 'configured',
            summary: 'Content Encryption Key is configured for backend-readable active content storage.',
          },
          artifact_encryption: {
            posture: artifactEncryptionPosture,
            status: artifactEncryptionPosture === 'required' ? 'encrypted' : 'plaintext_by_operator_choice',
            summary: artifactEncryptionPosture === 'required'
              ? 'Uploaded Document artifacts are encrypted in active storage for new writes.'
              : 'Uploaded Document artifacts are stored as plaintext by explicit Operator choice.',
          },
          retention_scheduler: {
            status: 'external_or_manual',
            summary: 'Scheduled Retention Policy marks classes for retention; this prototype does not include its own Retention Scheduler.',
            observation: {
              status: sessionMemoryRetentionPolicy.scheduled_enforcement_enabled ? 'stale' : 'disabled',
              enabled_classes: sessionMemoryRetentionPolicy.scheduled_enforcement_enabled ? ['sage_session_memory'] : [],
              last_run: sessionMemoryRetentionPolicy.scheduled_enforcement_enabled
                ? {
                    id: 7,
                    status: 'succeeded',
                    trigger: 'machine',
                    actor: 'machine:scheduled-retention',
                    finished_at: '2026-05-16T12:00:00Z',
                  }
                : null,
              summary: sessionMemoryRetentionPolicy.scheduled_enforcement_enabled
                ? 'The most recent Retention Scheduler run is older than the expected observation window.'
                : 'No Lifecycle Data Classes have scheduled Retention Execution enabled.',
            },
          },
          lifecycle_readiness: {
            status: 'stale',
            reviewed: false,
            reviewed_at: '2026-05-15T12:00:00Z',
            reviewed_by: 'admin-pubkey',
            stale_reason: 'retention_policy_changed',
            summary: 'Lifecycle Readiness is stale and needs Admin review.',
            acknowledged_unsupported_surface_categories: ['client_storage', 'runtime_logs'],
          },
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
              confidentiality: {
                status: 'partial',
                summary: 'Persistent Session Memory confidentiality is owned by Sage.',
              },
              retention_policy: {
                lifecycle_data_class: 'sage_session_memory',
                ...sessionMemoryRetentionPolicy,
              },
              notes: ['Session Memory belongs to the Agent Runtime.'],
            },
          ],
          secure_erase: {
            status: 'unsupported',
            summary: 'Secure Erase is out of scope for v1; lifecycle controls apply to stated active-storage targets and exclude unsupported Deployment Surfaces.',
          },
          unsupported_deployment_surfaces: [
            {
              key: 'docker_logs',
              label: 'Docker Logs',
              category: 'runtime_logs',
              summary: 'Container stdout/stderr logs are managed by the deployment runtime, not product lifecycle controls.',
              status: 'unsupported',
              acknowledged: acknowledgedSurfaceKeys.includes('docker_logs'),
            },
            {
              key: 'sqlite_wal',
              label: 'SQLite WAL',
              category: 'database_internals',
              summary: 'SQLite write-ahead-log files are database runtime artifacts.',
              status: 'unsupported',
              acknowledged: false,
            },
          ],
          unsupported_deployment_surface_categories: [
            {
              category: 'runtime_logs',
              label: 'Runtime Logs',
              status: 'unsupported',
              guidance: 'Configure deployment log retention outside the product.',
              acknowledged: acknowledgedSurfaceCategories.includes('runtime_logs'),
              acknowledged_by: acknowledgedSurfaceCategories.includes('runtime_logs') ? 'admin-pubkey' : null,
              acknowledged_at: acknowledgedSurfaceCategories.includes('runtime_logs') ? '2026-05-17T12:00:00Z' : null,
              posture_version: acknowledgedSurfaceCategories.includes('runtime_logs') ? 'posture-version' : null,
              surfaces: [
                {
                  key: 'docker_logs',
                  label: 'Docker Logs',
                  category: 'runtime_logs',
                  summary: 'Container stdout/stderr logs are managed by the deployment runtime, not product lifecycle controls.',
                  status: 'unsupported',
                  acknowledged: acknowledgedSurfaceKeys.includes('docker_logs'),
                },
              ],
            },
            {
              category: 'database_internals',
              label: 'Database Internals',
              status: 'unsupported',
              guidance: 'Manage WAL and database maintenance artifacts through database operator policy.',
              acknowledged: false,
              acknowledged_by: null,
              acknowledged_at: null,
              posture_version: null,
              surfaces: [
                {
                  key: 'sqlite_wal',
                  label: 'SQLite WAL',
                  category: 'database_internals',
                  summary: 'SQLite write-ahead-log files are database runtime artifacts.',
                  status: 'unsupported',
                  acknowledged: false,
                },
              ],
            },
          ],
          scheduled_retention: {
            enabled_classes: sessionMemoryRetentionPolicy.scheduled_enforcement_enabled ? ['sage_session_memory'] : [],
          },
          audit_coverage: {
            summary: {
              total: 8,
              audited: 6,
              documented_exceptions: 2,
              missing: 0,
              guardrail_passed: true,
            },
          },
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
      if (endpoint === '/admin/lifecycle/artifact-encryption-posture') {
        const body = JSON.parse(String(options?.body ?? '{}'))
        artifactEncryptionPosture = body.posture === 'disabled' ? 'disabled' : 'required'
        return Promise.resolve(Response.json({
          artifact_encryption: {
            posture: artifactEncryptionPosture,
            status: artifactEncryptionPosture === 'required' ? 'encrypted' : 'plaintext_by_operator_choice',
            summary: 'Artifact Encryption Posture updated.',
          },
        }))
      }
      if (endpoint === '/admin/lifecycle/unsupported-deployment-surfaces/docker_logs/acknowledgement') {
        const body = JSON.parse(String(options?.body ?? '{}'))
        acknowledgedSurfaceKeys = body.acknowledged === true ? ['docker_logs'] : []
        return Promise.resolve(Response.json({
          unsupported_deployment_surfaces: [
            {
              key: 'docker_logs',
              label: 'Docker Logs',
              category: 'runtime_logs',
              summary: 'Container stdout/stderr logs are managed by the deployment runtime, not product lifecycle controls.',
              status: 'unsupported',
              acknowledged: acknowledgedSurfaceKeys.includes('docker_logs'),
            },
          ],
        }))
      }
      if (endpoint === '/admin/lifecycle/unsupported-deployment-surface-categories/runtime_logs/acknowledgement') {
        const body = JSON.parse(String(options?.body ?? '{}'))
        acknowledgedSurfaceCategories = body.acknowledged === true ? ['runtime_logs'] : []
        return Promise.resolve(Response.json({
          unsupported_deployment_surface_categories: [],
        }))
      }
      if (endpoint === '/admin/lifecycle/retention-policies/sage_session_memory') {
        sessionMemoryRetentionPolicy = JSON.parse(String(options?.body))
        return Promise.resolve(Response.json({
          policy: {
            lifecycle_data_class: 'sage_session_memory',
            ...sessionMemoryRetentionPolicy,
          },
        }))
      }
      if (endpoint === '/admin/lifecycle/retention/preview') {
        return Promise.resolve(Response.json({
          status: 'preview',
          destructive: false,
          counts: {
            stale_conversations: 1,
            document_artifacts: 2,
            skipped_classes: 0,
          },
        }))
      }
      if (endpoint === '/admin/lifecycle/retention/scheduled/run') {
        return Promise.resolve(Response.json({
          status: 'succeeded',
          enabled_classes: ['sage_session_memory'],
          retry_results: [{ tombstone_id: 7, status: 'completed' }],
        }))
      }
      if (endpoint === '/admin/lifecycle/deletion-tombstones/7/retry') {
        if (tombstoneRetryShouldFail) {
          return Promise.resolve(Response.json({ detail: 'completed' }, { status: 409 }))
        }
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
        if (tombstoneFetchShouldFail) {
          return Promise.resolve(Response.json({ detail: 'unavailable' }, { status: 500 }))
        }
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

  it('lets admins export a Sage runtime env artifact from Deployment Settings', async () => {
    const user = userEvent.setup()

    render(
      <MemoryRouter initialEntries={['/admin/deployment']}>
        <Routes>
          <Route path="/admin/deployment" element={<AdminDeploymentConfig />} />
        </Routes>
      </MemoryRouter>
    )

    await screen.findByText('Chat Rate Limit')
    await user.click(screen.getAllByRole('button', { name: 'Export Sage env' })[0])

    await waitFor(() => {
      expect(mockAdminFetch).toHaveBeenCalledWith('/admin/deployment/runtime-env/sage')
    })
  })

  it('shows Sage env apply guidance after export without implying Sage changed live', async () => {
    const user = userEvent.setup()

    render(
      <MemoryRouter initialEntries={['/admin/deployment']}>
        <Routes>
          <Route path="/admin/deployment" element={<AdminDeploymentConfig />} />
        </Routes>
      </MemoryRouter>
    )

    await screen.findByText('Runtime Config Alignment')
    await user.click(screen.getAllByRole('button', { name: 'Export Sage env' })[0])

    expect(await screen.findByText('Sage env exported')).toBeInTheDocument()
    expect(screen.getByText('Treat sage.env as sensitive deployment material.')).toBeInTheDocument()
    expect(screen.getByText('docker compose --env-file .env --env-file runtime/generated/sage.env -f docker-compose.infra.yml -f docker-compose.app.yml up -d sage')).toBeInTheDocument()
    expect(screen.getByText('Exporting the artifact does not change the running Sage process until an Operator applies it and restarts Sage.')).toBeInTheDocument()
  })

  it('lets admins export a core-backend runtime env artifact with apply guidance', async () => {
    const user = userEvent.setup()

    render(
      <MemoryRouter initialEntries={['/admin/deployment']}>
        <Routes>
          <Route path="/admin/deployment" element={<AdminDeploymentConfig />} />
        </Routes>
      </MemoryRouter>
    )

    await screen.findByText('Runtime Config Alignment')
    await user.click(screen.getAllByRole('button', { name: 'Export core-backend env' })[0])

    await waitFor(() => {
      expect(mockAdminFetch).toHaveBeenCalledWith('/admin/deployment/runtime-env/core-backend')
    })
    expect(await screen.findByText('Core-backend env exported')).toBeInTheDocument()
    expect(screen.getByText('Treat core-backend.env as sensitive deployment material.')).toBeInTheDocument()
    expect(screen.getByText('docker compose --env-file .env --env-file runtime/generated/core-backend.env -f docker-compose.infra.yml -f docker-compose.app.yml up -d core-backend')).toBeInTheDocument()
    expect(screen.getByText('Exporting the artifact does not change the running backend process until an Operator applies it and restarts core-backend.')).toBeInTheDocument()
  })

  it('shows desired generated and running runtime config alignment', async () => {
    render(
      <MemoryRouter initialEntries={['/admin/deployment']}>
        <Routes>
          <Route path="/admin/deployment" element={<AdminDeploymentConfig />} />
        </Routes>
      </MemoryRouter>
    )

    await screen.findByText('Runtime Config Alignment')
    expect(screen.getByText('Desired')).toBeInTheDocument()
    expect(screen.getByText('Generated')).toBeInTheDocument()
    expect(screen.getByText('Running')).toBeInTheDocument()
    expect(screen.getByText('7 of 7 keys configured')).toBeInTheDocument()
    expect(screen.getByText('Sage live runtime env is not directly introspected in this slice; use service health plus generated env freshness.')).toBeInTheDocument()
    expect(screen.getByText('Core Backend')).toBeInTheDocument()
    expect(screen.getByText('Core backend running runtime config matches desired Deployment Settings.')).toBeInTheDocument()
  })

  it('shows lifecycle readiness warnings without implying user conversations are blocked', async () => {
    render(
      <MemoryRouter initialEntries={['/admin/deployment']}>
        <Routes>
          <Route path="/admin/deployment" element={<AdminDeploymentConfig />} />
        </Routes>
      </MemoryRouter>
    )

    const lifecycleStatus = await screen.findByRole('group', { name: 'Data Lifecycle Status' })
    expect(within(lifecycleStatus).getByText('Lifecycle Readiness: Stale')).toBeInTheDocument()
    expect(within(lifecycleStatus).getByText('Lifecycle Readiness is stale and needs Admin review.')).toBeInTheDocument()
    expect(within(lifecycleStatus).getByText('User Conversations are not blocked by Lifecycle Readiness warnings in v1.')).toBeInTheDocument()
  })

  it('shows Deployment Readiness blockers, warnings, and next actions', async () => {
    render(
      <MemoryRouter initialEntries={['/admin/deployment']}>
        <Routes>
          <Route path="/admin/deployment" element={<AdminDeploymentConfig />} />
        </Routes>
      </MemoryRouter>
    )

    const readiness = await screen.findByRole('group', { name: 'Deployment Readiness' })
    expect(within(readiness).getByText('Deployment Readiness: Blocked')).toBeInTheDocument()
    expect(within(readiness).getByText('1 blockers')).toBeInTheDocument()
    expect(within(readiness).getByText('3 warnings')).toBeInTheDocument()
    expect(within(readiness).getByText('Verifiable Inference')).toBeInTheDocument()
    expect(within(readiness).getByText('Current Verifiable Inference is required before normal Conversations can run.')).toBeInTheDocument()
    expect(within(readiness).getByText('Run Model Provider verification or repair provider configuration.')).toBeInTheDocument()
    expect(within(readiness).getByText('Sage Runtime Env')).toBeInTheDocument()
    expect(within(readiness).getByText('Running Sage runtime config differs from desired Deployment Settings.')).toBeInTheDocument()
    expect(within(readiness).getByText('Investigate Sage runtime config drift, apply the generated Sage env, and restart Sage.')).toBeInTheDocument()
    expect(within(readiness).getByRole('link', { name: 'Review Runtime Env Export' })).toHaveAttribute('href', '#runtime-config-alignment')
    const lifecycleItem = within(readiness).getByText('Lifecycle Readiness').closest('.bg-surface')
    expect(lifecycleItem).not.toBeNull()
    expect(within(lifecycleItem as HTMLElement).getByText('Warning')).toBeInTheDocument()

    await waitFor(() => {
      expect(mockAdminFetch).toHaveBeenCalledWith('/admin/deployment/readiness')
    })
  })

  it('guides admins through Deployment Wizard readiness review steps', async () => {
    const user = userEvent.setup()

    render(
      <MemoryRouter initialEntries={['/admin/deployment']}>
        <Routes>
          <Route path="/admin/deployment" element={<AdminDeploymentConfig />} />
        </Routes>
      </MemoryRouter>
    )

    const readiness = await screen.findByRole('group', { name: 'Deployment Readiness' })
    await user.click(within(readiness).getByRole('button', { name: 'Open Readiness Review' }))

    const wizard = await screen.findByRole('dialog', { name: 'Deployment Wizard' })
    expect(within(wizard).getByText('Step 1 of 6')).toBeInTheDocument()
    expect(within(wizard).getByText('Verifiable Inference')).toBeInTheDocument()
    expect(within(wizard).getByRole('link', { name: 'Review Inference Verification' })).toHaveAttribute('href', '#inference-verification')

    await user.click(within(wizard).getByRole('button', { name: 'Next' }))

    expect(within(wizard).getByText('Step 2 of 6')).toBeInTheDocument()
    expect(within(wizard).getByText('Lifecycle Readiness')).toBeInTheDocument()
    expect(within(wizard).getByRole('link', { name: 'Review Data Lifecycle Status' })).toHaveAttribute('href', '#data-lifecycle-status')

    await user.click(within(wizard).getByRole('button', { name: 'Next' }))

    expect(within(wizard).getByText('Step 3 of 6')).toBeInTheDocument()
    expect(within(wizard).getByText('Deployment Validation')).toBeInTheDocument()
    expect(within(wizard).getByRole('link', { name: 'Review Deployment Settings' })).toHaveAttribute('href', '#deployment-settings')
    expect(document.getElementById('deployment-settings')).not.toBeNull()

    await user.click(within(wizard).getByRole('button', { name: 'Next' }))

    expect(within(wizard).getByText('Step 4 of 6')).toBeInTheDocument()
    expect(within(wizard).getByText('Sage Runtime Env')).toBeInTheDocument()
    expect(within(wizard).getByRole('link', { name: 'Review Runtime Env Export' })).toHaveAttribute('href', '#runtime-config-alignment')
    expect(document.getElementById('runtime-config-alignment')).not.toBeNull()

    await user.click(within(wizard).getByRole('button', { name: 'Next' }))

    expect(within(wizard).getByText('Step 5 of 6')).toBeInTheDocument()
    expect(within(wizard).getByText('Backup And Restore Drill')).toBeInTheDocument()
    expect(within(wizard).getByRole('link', { name: 'Review Operational Readiness' })).toHaveAttribute('href', '#operational-readiness')
    expect(document.getElementById('operational-readiness')).not.toBeNull()

    await user.click(within(wizard).getByRole('button', { name: 'Next' }))

    expect(within(wizard).getByText('Step 6 of 6')).toBeInTheDocument()
    expect(within(wizard).getByText('Restart Required')).toBeInTheDocument()
    expect(within(wizard).getByRole('link', { name: 'Review Restart Required' })).toHaveAttribute('href', '#restart-required')
    expect(document.getElementById('restart-required')).not.toBeNull()
  })

  it('shows current Model Provider verification status', async () => {
    render(
      <MemoryRouter initialEntries={['/admin/deployment']}>
        <Routes>
          <Route path="/admin/deployment" element={<AdminDeploymentConfig />} />
        </Routes>
      </MemoryRouter>
    )

    const verification = await screen.findByRole('group', { name: 'Inference Verification' })
    expect(within(verification).getByText('Current')).toBeInTheDocument()
    expect(within(verification).getByText('sage')).toBeInTheDocument()
    expect(within(verification).getByText('kimi-k2-6')).toBeInTheDocument()
    expect(within(verification).getByText('https://inference.tinfoil.sh/v1')).toBeInTheDocument()
    expect(within(verification).getByText(/Expected claims: expected-fingerprint/)).toBeInTheDocument()
  })

  it('lets admins trigger manual inference verification', async () => {
    const user = userEvent.setup()
    verificationStatus = 'missing'

    render(
      <MemoryRouter initialEntries={['/admin/deployment']}>
        <Routes>
          <Route path="/admin/deployment" element={<AdminDeploymentConfig />} />
        </Routes>
      </MemoryRouter>
    )

    const verification = await screen.findByRole('group', { name: 'Inference Verification' })
    expect(within(verification).getByText('Missing')).toBeInTheDocument()

    await user.click(within(verification).getByRole('button', { name: 'Verify Now' }))

    await waitFor(() => {
      expect(mockAdminFetch).toHaveBeenCalledWith(
        '/admin/deployment/inference-verification/verify',
        expect.objectContaining({ method: 'POST' }),
      )
    })
    expect(await within(verification).findByText('Manual verification succeeded')).toBeInTheDocument()
  })

  it('shows verification history and full attestation detail on demand', async () => {
    const user = userEvent.setup()

    render(
      <MemoryRouter initialEntries={['/admin/deployment']}>
        <Routes>
          <Route path="/admin/deployment" element={<AdminDeploymentConfig />} />
        </Routes>
      </MemoryRouter>
    )

    const verification = await screen.findByRole('group', { name: 'Inference Verification' })
    expect(within(verification).getByText('Record #42')).toBeInTheDocument()
    expect(within(verification).queryByText('full-attestation-material')).not.toBeInTheDocument()

    await user.click(within(verification).getByRole('button', { name: 'Inspect Attestation' }))

    expect(await within(verification).findByText(/full-attestation-material/)).toBeInTheDocument()
    expect(verificationRecordDetailRequested).toBe(true)
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
    expect(screen.getByText('Active Storage Lifecycle')).toBeInTheDocument()
    expect(screen.getByText('Content Encryption Key: Configured')).toBeInTheDocument()
    expect(screen.getByText('Artifact Encryption Posture: Encrypted')).toBeInTheDocument()
    expect(screen.getByText('Retention Scheduler: External or manual')).toBeInTheDocument()
    expect(screen.getByText('Observation: Disabled')).toBeInTheDocument()
    expect(screen.getByText('Scheduler enabled classes: None')).toBeInTheDocument()
    expect(screen.getByText('Confidentiality: Partial')).toBeInTheDocument()
    expect(screen.getByText('Secure Erase: Unsupported')).toBeInTheDocument()
    expect(screen.getByText(/Secure Erase is out of scope for v1/)).toBeInTheDocument()
    expect(screen.getByText('Incomplete tombstones: 1')).toBeInTheDocument()
    expect(screen.getByText('Completed tombstones: 1')).toBeInTheDocument()

    await waitFor(() => {
      expect(mockAdminFetch).toHaveBeenCalledWith('/admin/lifecycle/status')
    })
  })

  it('lets admins mark uploaded artifacts as plaintext by operator choice', async () => {
    const user = userEvent.setup()

    render(
      <MemoryRouter initialEntries={['/admin/deployment']}>
        <Routes>
          <Route path="/admin/deployment" element={<AdminDeploymentConfig />} />
        </Routes>
      </MemoryRouter>
    )

    const lifecycleStatus = await screen.findByRole('group', { name: 'Data Lifecycle Status' })
    const lifecycleStatusCallsBeforeToggle = mockAdminFetch.mock.calls.filter(([endpoint]) => endpoint === '/admin/lifecycle/status').length
    await user.click(within(lifecycleStatus).getByRole('button', { name: 'Disabled' }))

    await waitFor(() => {
      expect(mockAdminFetch).toHaveBeenCalledWith(
        '/admin/lifecycle/artifact-encryption-posture',
        expect.objectContaining({
          method: 'PUT',
          body: JSON.stringify({ posture: 'disabled' }),
        }),
      )
    })
    await waitFor(() => {
      const lifecycleStatusCalls = mockAdminFetch.mock.calls.filter(([endpoint]) => endpoint === '/admin/lifecycle/status')
      expect(lifecycleStatusCalls.length).toBeGreaterThan(lifecycleStatusCallsBeforeToggle)
    })
    expect(await within(lifecycleStatus).findByText('Artifact Encryption Posture: Plaintext by Operator Choice')).toBeInTheDocument()
  })

  it('shows unsupported deployment surface categories and lets admins acknowledge one', async () => {
    const user = userEvent.setup()

    render(
      <MemoryRouter initialEntries={['/admin/deployment']}>
        <Routes>
          <Route path="/admin/deployment" element={<AdminDeploymentConfig />} />
        </Routes>
      </MemoryRouter>
    )

    const lifecycleStatus = await screen.findByRole('group', { name: 'Data Lifecycle Status' })
    expect(within(lifecycleStatus).getByText('Unsupported Deployment Surfaces')).toBeInTheDocument()
    expect(within(lifecycleStatus).getByText('Runtime Logs')).toBeInTheDocument()
    expect(within(lifecycleStatus).getByText('Database Internals')).toBeInTheDocument()
    expect(within(lifecycleStatus).getByText('Docker Logs')).toBeInTheDocument()

    const runtimeLogsCard = within(lifecycleStatus).getByText('Runtime Logs').closest('div.bg-surface')
    expect(runtimeLogsCard).not.toBeNull()
    await user.click(within(runtimeLogsCard as HTMLElement).getByRole('button', { name: 'Acknowledge' }))

    await waitFor(() => {
      expect(mockAdminFetch).toHaveBeenCalledWith(
        '/admin/lifecycle/unsupported-deployment-surface-categories/runtime_logs/acknowledgement',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ acknowledged: true }),
        }),
      )
    })
    expect(await within(lifecycleStatus).findByRole('button', { name: 'Acknowledged' })).toBeInTheDocument()
  })

  it('lets admins edit retention policy for a lifecycle data class', async () => {
    const user = userEvent.setup()

    render(
      <MemoryRouter initialEntries={['/admin/deployment']}>
        <Routes>
          <Route path="/admin/deployment" element={<AdminDeploymentConfig />} />
        </Routes>
      </MemoryRouter>
    )

    const lifecycleStatus = await screen.findByRole('group', { name: 'Data Lifecycle Status' })
    const sessionMemoryCard = within(lifecycleStatus).getByText('Sage Session Memory').closest('.bg-surface')
    expect(sessionMemoryCard).not.toBeNull()
    const card = within(sessionMemoryCard as HTMLElement)

    await user.click(card.getByLabelText('Enabled'))
    await user.clear(card.getByRole('spinbutton', { name: /Window/i }))
    await user.type(card.getByRole('spinbutton', { name: /Window/i }), '45')
    await user.click(card.getByLabelText('Scheduled'))
    await user.click(card.getByRole('button', { name: 'Save Policy' }))

    await waitFor(() => {
      expect(mockAdminFetch).toHaveBeenCalledWith(
        '/admin/lifecycle/retention-policies/sage_session_memory',
        expect.objectContaining({
          method: 'PUT',
          body: JSON.stringify({
            enabled: true,
            retention_window_days: 45,
            scheduled_enforcement_enabled: true,
          }),
        }),
      )
    })
    expect(await within(lifecycleStatus).findByText('Scheduler enabled classes: sage_session_memory')).toBeInTheDocument()
    expect(within(lifecycleStatus).getByText('Last run status: Succeeded')).toBeInTheDocument()
  })

  it('lets admins preview retention, run scheduled retention, and see audit coverage', async () => {
    const user = userEvent.setup()

    render(
      <MemoryRouter initialEntries={['/admin/deployment']}>
        <Routes>
          <Route path="/admin/deployment" element={<AdminDeploymentConfig />} />
        </Routes>
      </MemoryRouter>
    )

    const lifecycleStatus = await screen.findByRole('group', { name: 'Data Lifecycle Status' })
    expect(within(lifecycleStatus).getByText('Audit coverage: 6 audited, 2 exceptions, 0 missing.')).toBeInTheDocument()
    expect(within(lifecycleStatus).getByText('Scheduled classes: None')).toBeInTheDocument()

    await user.click(within(lifecycleStatus).getByRole('button', { name: 'Preview Retention' }))
    expect(await within(lifecycleStatus).findByText('Preview: 1 conversations, 2 document artifacts, 0 skipped classes.')).toBeInTheDocument()

    await user.click(within(lifecycleStatus).getByRole('button', { name: 'Run Scheduled' }))
    expect(await within(lifecycleStatus).findByText('Scheduled run: succeeded with 1 tombstone retries.')).toBeInTheDocument()

    await waitFor(() => {
      expect(mockAdminFetch).toHaveBeenCalledWith(
        '/admin/lifecycle/retention/preview',
        expect.objectContaining({ method: 'POST' }),
      )
      expect(mockAdminFetch).toHaveBeenCalledWith(
        '/admin/lifecycle/retention/scheduled/run',
        expect.objectContaining({ method: 'POST' }),
      )
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

  it('shows a tombstone fetch error instead of an empty state', async () => {
    tombstoneFetchShouldFail = true

    render(
      <MemoryRouter initialEntries={['/admin/deployment']}>
        <Routes>
          <Route path="/admin/deployment" element={<AdminDeploymentConfig />} />
        </Routes>
      </MemoryRouter>
    )

    const tombstones = await screen.findByRole('group', { name: 'Deletion Tombstones' })
    expect(await within(tombstones).findByText('Unable to load deletion tombstones.')).toBeInTheDocument()
    expect(within(tombstones).queryByText('No deletion tombstones are waiting for retry.')).not.toBeInTheDocument()
  })

  it('refreshes deletion tombstones after a retry conflict', async () => {
    const user = userEvent.setup()
    tombstoneRetryShouldFail = true

    render(
      <MemoryRouter initialEntries={['/admin/deployment']}>
        <Routes>
          <Route path="/admin/deployment" element={<AdminDeploymentConfig />} />
        </Routes>
      </MemoryRouter>
    )

    const tombstones = await screen.findByRole('group', { name: 'Deletion Tombstones' })
    await user.click(within(tombstones).getByRole('button', { name: 'Retry deletion tombstone 7' }))

    await waitFor(() => {
      expect(mockAdminFetch).toHaveBeenCalledWith('/admin/lifecycle/deletion-tombstones/7/retry', { method: 'POST' })
    })
    await waitFor(() => {
      const listCalls = mockAdminFetch.mock.calls.filter(([endpoint]) => endpoint === '/admin/lifecycle/deletion-tombstones')
      expect(listCalls.length).toBeGreaterThanOrEqual(2)
    })
    expect(within(tombstones).getByText('Retry failed.')).toBeInTheDocument()
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
