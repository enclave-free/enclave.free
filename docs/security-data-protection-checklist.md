# Security and Data Protection Checklist

Last updated: 2026-05-17
Scope: Enclave current repository state (code/config review)

## Purpose

Use this checklist to:
- Track what security and data protection controls are currently implemented.
- Identify production blockers and remediation priorities.
- Validate protections from both the user and admin perspective.

## How to use this document

1. Treat Section 4 as release-blocking work for any internet-exposed deployment.
2. Create one ticket/PR per unchecked blocker; link it in the tracker below.
3. Attach objective evidence in each PR (test output, curl checks, screenshots, config diff).
4. Re-run Section 8 sign-off criteria before deployment.
5. Update `Last updated` and this document in the same PR as security changes.

### Status legend

- `todo`: not started
- `in_progress`: being implemented
- `blocked`: waiting on decision/dependency
- `done`: merged and verified

---

## 0. Critical Remediation Tracker (Current Sprint)

| ID | Blocker | Priority | Owner | Status | Tracking |
|---|---|---|---|---|---|
| S4-1 | Protect ingest endpoints with auth | P0 | - | done | `backend/app/ingest.py` (Section 11 evidence) |
| S4-2 | Restrict `/vector-search` and remove unsafe payload exposure | P0 | - | done | `backend/app/main.py` (Section 11 evidence) |
| S4-3 | Enforce public query-session record ownership checks | P0 | - | done | Sage-owned public query-session routes (Section 11 evidence) |
| S4-4 | Replace wildcard CORS with explicit allowlist | P0 | - | done | `backend/app/main.py` (Section 11 evidence) |
| S4-5 | Move bearer tokens out of `localStorage` | P0 | - | done | `frontend/src/utils/adminApi.ts`, `frontend/src/pages/VerifyMagicLink.tsx` (Section 11 evidence) |
| S4-6 | Remove query-param token usage | P0 | - | done | `backend/app/main.py`, `frontend/src/pages/VerifyMagicLink.tsx` (Section 11 evidence) |
| S4-7 | Lock down published service ports | P0 | - | done | `docker-compose.app.yml`, `docker-compose.infra.yml` (Section 11 evidence) |

---

## 1. Current Security Posture Snapshot

### 1.1 Confirmed protections currently present

- [x] Passwordless auth is implemented for users (magic link + signed session token).
  Evidence: `backend/app/auth.py`, `backend/app/main.py`
- [x] Admin auth uses signed Nostr events with event kind, tag, timestamp, and Schnorr signature checks.
  Evidence: `backend/app/main.py`, `backend/app/nostr.py`
- [x] Single-admin constraint is enforced.
  Evidence: `backend/app/main.py`, `backend/app/database.py`
- [x] Core chat/query routes require admin or approved user auth.
  Evidence: Sage-owned public Agent Runtime routes; Python issues and validates Enclave session material for Control Plane routes.
- [x] User PII fields (email/name and encrypted custom fields) are encrypted at rest in SQLite.
  Evidence: `backend/app/database.py`, `backend/app/encryption.py`
- [x] Email blind index exists for encrypted email lookup.
  Evidence: `backend/app/database.py`, `backend/app/encryption.py`
- [x] Deployment config secrets are masked in standard API reads.
  Evidence: `backend/app/database.py`, `backend/app/deployment_config.py`
- [x] Admin key migration includes signed authorization checks and transactional migration.
  Evidence: `backend/app/key_migration.py`
- [x] Baseline security headers and API CSP are applied at middleware level.
  Evidence: `backend/app/main.py`
- [x] Cookie-authenticated unsafe requests enforce CSRF origin + token checks.
  Evidence: `backend/app/main.py`, `frontend/src/utils/secureFetch.ts`
- [x] Admin-visible lifecycle status identifies current Data Retention, Data Deletion, and Audit Log coverage by Instance data class.
  Evidence: `backend/app/lifecycle.py`, `frontend/src/pages/AdminDeploymentConfig.tsx`

### 1.2 Previously identified gaps (status)

- [x] Ingest endpoints are auth-protected (admin or approved-user scoped by route).
  Evidence: `backend/app/ingest.py`, `backend/app/auth.py`
- [x] `/vector-search` is restricted to admin authentication.
  Evidence: `backend/app/main.py`, `backend/app/auth.py`
- [x] Query sessions are owner-scoped and enforce access checks on create/reuse/read/delete.
  Evidence: Public query-session routes are Sage-owned; Python lifecycle evidence covers Sage-to-Python deletion/tombstone reporting.
- [x] Primary auth/session token usage moved to secure cookie flows (no active token-in-localStorage requirement).
  Evidence: `frontend/src/utils/adminApi.ts`, `frontend/src/pages/VerifyMagicLink.tsx`, `frontend/src/pages/ChatPage.tsx`
- [x] Active auth flows no longer use query-string tokens for verification/session checks.
  Evidence: `backend/app/main.py`, `frontend/src/pages/VerifyMagicLink.tsx`, `frontend/src/pages/TestDashboard.tsx`
- [x] CORS now uses explicit allowlist origins compatible with credentialed cookies.
  Evidence: `backend/app/main.py`
- [x] New Uploaded Document artifacts are encrypted at rest by default when a Content Encryption Key is configured; operators may explicitly choose plaintext artifact storage.
  Evidence: `backend/app/content_artifacts.py`, `backend/app/ingest.py`, `backend/tests/test_ingest_batch_replacement.py`
- [x] New Retrieval Index writes store vectors and minimal metadata only; encrypted chunk text lives in SQLite.
  Evidence: `backend/app/store.py`, `backend/app/ingest_db.py`, `backend/tests/test_store_minimized_payload.py`, `backend/tests/test_ingest_batch_replacement.py`
- [x] Legacy Retrieval Index plaintext repair support has been removed; current writes use minimized Qdrant payloads and encrypted chunk hydration from SQLite.
  Evidence: `docs/adr/0011-minimize-retrieval-index-and-encrypt-chunk-text.md`, `docs/lifecycle-confidentiality-runbook.md`
- [x] Legacy User Profile plaintext fallback support has been removed; current lookup is blind-index-only and the admin migration endpoints are absent.
  Evidence: `docs/user-profile-plaintext-migration-plan.md`
- [x] Deployment secrets are now encrypted at rest in SQLite.
  Evidence: `backend/app/database.py` (Section 3.3, Section 5.2)
- [x] User approval, auto-approval, User Type administration, and User Type migration actions are covered by the tamper-evident Audit Log.
  Evidence: `backend/app/main.py`, `backend/app/deployment_config.py`, `backend/tests/test_user_audit_coverage.py`
- [x] Document upload, replacement, access/default changes, deletion, cleanup, and user/document Data Deletion outcomes are covered by the tamper-evident Audit Log.
  Evidence: `backend/app/ingest.py`, `backend/app/main.py`, `backend/tests/test_ingest_batch_replacement.py`, `backend/tests/test_user_deletion_lifecycle.py`
- [x] Confirmed Admin Conversation User Memory writes are auditable, and direct database mutation paths are constrained to read-only inspection.
  Evidence: `docs/adr/0007-audit-log-is-a-product-boundary-but-coverage-is-partial.md`, `backend/tests/test_admin_subject_user_memory.py`
- [x] Operators can invoke Data Retention execution for stale active Conversation state and failed/superseded Document artifacts with structured status and Audit Log coverage.
  Evidence: `backend/app/lifecycle.py`, `backend/tests/test_retention_execution.py`

---

## 2. User Perspective Checklist

### 2.1 Authentication and account access

- [x] Magic link token is signed and time-limited.
- [x] User session token is signed and time-limited.
- [x] Chat/query access requires authenticated and approved users.
- [x] Add anti-enumeration response behavior for auth endpoints.
- [x] Add abuse-resistant rate limiting that works across multiple backend instances for:
  - Auth endpoints
  - File upload endpoints
  - Vector search operations
  - Query/chat operations
  Evidence: `backend/app/rate_limit.py`, `gateway/nginx.conf`, `backend/tests/test_rate_limit.py`, `docs/adr/0018-shared-rate-limiting-uses-self-hosted-valkey.md`

### 2.2 Data confidentiality and privacy

- [x] User PII fields are encrypted before DB write after admin initialization.
- [x] User document access for Knowledge Search is filtered by allowed `job_id`s for user type.
- [x] Eliminate unauthenticated ingest/chunk/vector endpoints that bypass user document controls.
- [x] Prevent session data leakage across users (session ownership checks).
- [x] Move user auth tokens from `localStorage` to secure, httpOnly cookies.
- [x] Stop passing user session tokens in query strings.
- [x] Minimize deliberate browser-side storage and clear known local product markers on logout.
  Evidence: `frontend/src/utils/browserStoragePosture.ts`, `frontend/src/utils/browserStoragePosture.test.ts`, `backend/tests/test_browser_storage_posture_docs.py`, `docs/browser-storage-posture.md`
- [x] Encrypt new uploaded document artifacts at rest by default when `CONTENT_ENCRYPTION_KEY` is configured.
  Evidence: `backend/app/content_artifacts.py`, `backend/app/ingest.py`, `backend/tests/test_ingest_batch_replacement.py`
- [x] Remove plaintext chunk text from new Retrieval Index payloads.
  Evidence: `backend/app/store.py`, `backend/tests/test_store_minimized_payload.py`

### 2.3 Web application security

- [x] Implement CSRF tokens for state-changing operations.
- [x] Sanitize/escape user input to prevent XSS (reflected, stored, DOM-based).
  Evidence: `frontend/src/components/chat/ChatMessage.tsx`, `frontend/src/components/chat/ChatMessage.test.tsx`, `docs/security-rendering.md`
- [x] Implement Content Security Policy (CSP) headers.
- [x] Add X-Frame-Options and X-Content-Type-Options headers.

### 2.4 User safety and transparency

- [x] Explicitly tracks approved vs pending user access states.
- [x] Add user-visible privacy notice clarifying what data may leave local infra when external providers are enabled (embeddings/LLM mode).
  Evidence: `frontend/src/pages/UserAuth.tsx`, `frontend/src/pages/UserOnboarding.tsx`, `TERMS_OF_SERVICE.md`
- [x] Add user-facing data retention and deletion policy UI text.
  Evidence: `frontend/src/pages/UserAuth.tsx`, `frontend/src/i18n/locales/en.json`

---

## 3. Admin Perspective Checklist

### 3.1 Admin auth and governance

- [x] Nostr event verification includes signature + freshness checks.
- [x] Single-admin ownership model enforced.
- [x] Admin session token exists and is validated server-side.
- [x] Move admin token storage from `localStorage` to secure cookie/session mechanism.
- [x] Add explicit admin session revocation/logout invalidation strategy.
  Evidence: `backend/app/database.py`, `backend/app/auth.py`, `backend/app/main.py`
- [x] Add an admin-visible Data Lifecycle Status surface as the current source of truth for lifecycle coverage and known gaps.
  Evidence: `GET /admin/lifecycle/status`, `frontend/src/pages/AdminDeploymentConfig.tsx`
- [x] Data Lifecycle Status distinguishes Active Storage Lifecycle from unsupported Deployment Surfaces, reports Scheduled Retention Policy separately from Retention Scheduler execution, and exposes Content Encryption Key / Artifact Encryption Posture.
  Evidence: `backend/app/lifecycle.py`, `frontend/src/pages/AdminDeploymentConfig.tsx`, `backend/tests/test_lifecycle_status.py`
- [x] Data Lifecycle Status reports Retention Scheduler Observation from metadata-only Retention Run Records created by manual or external Retention Scheduler execution.
  Evidence: `backend/app/database.py`, `backend/app/lifecycle.py`, `frontend/src/pages/AdminDeploymentConfig.tsx`, `docs/adr/0015-external-retention-scheduler-with-product-owned-run-records.md`

### 3.2 Admin data access and key management

- [x] Admin can decrypt encrypted user fields client-side with NIP-07.
- [x] Key migration flow validates signature and prevents partial migration.
- [x] Add formal backup and recovery runbook for admin private key loss.
- [x] Add key migration drills and recovery tests.

### 3.3 Deployment and secret handling

- [x] Secrets are masked in normal config reads.
- [x] Secret reveal/export endpoints are admin-only.
- [x] Encrypt secrets at rest in `deployment_config` (not just masked in API output).
- [x] Restrict/monitor `.env` export usage and treat as high-risk operation.
- [x] Add immutable audit controls for privileged config changes.
- [x] Add immutable audit coverage for user approval and User Type governance changes.
  Evidence: `backend/tests/test_user_audit_coverage.py`
- [x] Add immutable audit coverage for Document governance and Data Deletion workflows.
  Evidence: `backend/tests/test_ingest_batch_replacement.py`, `backend/tests/test_user_deletion_lifecycle.py`
- [x] Define and enforce the Admin Conversation/direct database mutation audit posture.
  Evidence: `docs/adr/0007-audit-log-is-a-product-boundary-but-coverage-is-partial.md`, `backend/tests/test_admin_subject_user_memory.py`

---

## 4. Critical Production Blockers (Must Fix Before Internet Exposure)

- [x] Protect ingest endpoints with auth:
  - `/ingest/wipe`
  - `/ingest/upload`
  - `/ingest/status/{job_id}`
  - `/ingest/pending`
  - `/ingest/chunk/{chunk_id}`
  - `/ingest/pipeline-stats`
- [x] Restrict `/vector-search` (admin-only or remove payload text and enforce doc scoping).
- [x] Enforce session ownership checks for:
  - `GET /query/sessions`
  - `GET /query/session/{session_id}`
  - `PATCH /query/session/{session_id}`
  - `DELETE /query/session/{session_id}`
- [x] Replace wildcard CORS with deployment-configured allowlist.
- [x] Move bearer tokens out of `localStorage`.
- [x] Remove query-param token usage for active auth/session APIs.
- [x] Lock down published service ports to least privilege.

### 4.1 Post-implementation validation criteria (pending before Section 8 sign-off)

- [x] Auth-protected endpoint returns `401/403` without valid auth and succeeds with valid auth.
- [x] Access control behavior is covered by automated tests (or documented temporary manual test).
- [x] Frontend behavior remains functional after auth/token changes.
- [x] No wildcard network exposure remains in Docker/infra defaults.
- [x] Evidence is recorded in PR description and linked in Section 0 tracker.

> **Note:** Automated regression tests (`test_3c_auth_hardening_regression.py`, `test_3d_phase3_config_integrity.py`) now cover S4-1 through S4-4 and S4-7; results are recorded in Section 11. S4-5 (localStorage token removal) and S4-6 (query-param token removal) require manual browser verification via DevTools; see Section 11 evidence.

---

## 5. Data Protection Model Checklist

### 5.1 Data classification and input validation

- [x] Maintain explicit classification for:
  - PII fields (email/name/user fields)
  - Uploaded documents
  - Derived chunks/embeddings
  - Secrets and credentials
  Evidence: `backend/app/data_classification.py`, `backend/tests/test_data_classification_and_input_validation.py`, `docs/data-classification.md`
- [x] Verify supported SQL paths are constrained to read-only inspection and parameterized/allowlisted access.
  Evidence: `backend/app/sql_safety.py`, `backend/app/main.py`, `backend/app/tools/sqlite_query.py`, `backend/tests/test_sql_safety.py`, `backend/tests/test_admin_db_query_endpoint.py`, `docs/sql-safety.md`
- [x] Implement input validation for all user-supplied data (length, type, format).
  Evidence: `backend/app/models.py`, `backend/tests/test_data_classification_and_input_validation.py`

### 5.2 At-rest controls

- [x] PII fields in `users`/`user_field_values` are encrypted.
- [x] Uploaded files in `uploads/` encrypted at rest when a Content Encryption Key is configured.
  Evidence: `backend/app/content_artifacts.py`, `backend/app/ingest.py`, `backend/tests/test_ingest_batch_replacement.py`, `backend/app/lifecycle.py`, `docs/active-content-encryption.md`
- [x] Qdrant payload text minimized for new ingestion.
  Evidence: `backend/app/store.py`, `backend/tests/test_store_minimized_payload.py`
- [x] Deployment secrets encrypted at rest in SQLite.

### 5.3 In-transit controls

- [x] Enforce TLS end-to-end guidance and visible production validation for frontend/backend public origins.
  Evidence: `backend/app/deployment_config.py`, `backend/tests/test_deployment_config_rate_limits.py`, `docs/production-network-tls.md`
- [x] Ensure external provider calls use HTTPS in production, with documented local/internal Compose exceptions.
  Evidence: `backend/app/deployment_config.py`, `backend/tests/test_deployment_config_rate_limits.py`, `docs/production-network-tls.md`
- [x] Ensure reverse proxy HTTPS, HSTS, and trusted proxy guidance is documented and visible in validation.
  Evidence: `backend/app/main.py`, `backend/app/deployment_config.py`, `docs/production-network-tls.md`

### 5.4 Retention and deletion

- [x] Admin can delete active Documents with structured per-target status for metadata, uploaded artifact, Retrieval entries, and runtime state.
- [x] Retention can clean up failed, superseded, abandoned, and orphaned Document artifacts without deleting current successful Documents or their current retrieval entries.
- [x] User deletion removes active User Profile/access state, purges Sage-owned User Memory, and clears active Conversation state with structured lifecycle status.
- [x] Add operator-invoked retention execution for stale active Conversation state and failed/superseded Document artifacts.
- [x] Add admin-visible metadata-only deletion tombstones for incomplete Session Memory deletion during operator-invoked retention.
  Evidence: `backend/app/database.py`, `backend/app/lifecycle.py`, `backend/tests/test_retention_execution.py::test_retention_creates_metadata_only_tombstone_when_session_memory_deletion_fails`, `docs/adr/0010-session-memory-deletion-uses-retryable-tombstones.md`
- [x] Add admin manual retry for incomplete Session Memory deletion tombstones.
  Evidence: `backend/app/lifecycle.py`, `backend/tests/test_retention_execution.py::test_admin_can_retry_incomplete_session_memory_tombstone`, `docs/adr/0010-session-memory-deletion-uses-retryable-tombstones.md`
- [x] Define the first Sage Session Memory lifecycle deletion contract.
  Evidence: `runtime/sage/crates/sage-core/src/web_runtime.rs`, `backend/app/lifecycle.py::post_sage_session_memory_delete`, `backend/tests/test_retention_execution.py::test_retention_uses_sage_lifecycle_contract_and_sanitizes_failures`, `docs/internal-agent-contract.md`, `docs/adr/0010-session-memory-deletion-uses-retryable-tombstones.md`
- [x] Route public Conversation deletion through shared Session Memory lifecycle handling.
  Evidence: Public query-session routes are Sage-owned; Python lifecycle evidence covers Sage-to-Python deletion/tombstone reporting in `backend/app/lifecycle.py`, `backend/tests/test_retention_execution.py::test_user_conversation_delete_uses_shared_session_memory_lifecycle`, and `docs/adr/0010-session-memory-deletion-uses-retryable-tombstones.md`.
- [x] Route User deletion through shared Session Memory lifecycle handling and create metadata-only tombstones for incomplete targets.
  Evidence: `backend/app/main.py`, `backend/app/lifecycle.py`, `backend/tests/test_user_deletion_lifecycle.py::test_user_deletion_creates_metadata_only_tombstone_when_session_memory_deletion_fails`, `docs/adr/0010-session-memory-deletion-uses-retryable-tombstones.md`
- [x] Emit privacy-preserving lifecycle Audit Log evidence for Conversation deletion and tombstone retry workflows.
  Evidence: `backend/app/lifecycle.py::audit_lifecycle_deletion`, `backend/tests/test_retention_execution.py::test_user_conversation_delete_uses_shared_session_memory_lifecycle`, `backend/tests/test_retention_execution.py::test_admin_can_retry_incomplete_session_memory_tombstone`, `docs/adr/0007-audit-log-is-a-product-boundary-but-coverage-is-partial.md`
- [x] Re-check Conversation retention eligibility immediately before deletion and report skipped active candidates.
  Evidence: `backend/app/lifecycle.py::run_retention`, `backend/tests/test_retention_execution.py::test_retention_rechecks_conversation_activity_before_deleting_candidate`, `docs/adr/0010-session-memory-deletion-uses-retryable-tombstones.md`
- [x] Make Conversation retention semantics explicit for opening, viewing, inspecting, exporting, lifecycle scanning, ordinary history visibility, metadata-only lifecycle evidence, and Admin-visible tombstones.
  Evidence: `docs/sessions.md`, `backend/tests/test_conversation_retention_docs.py`, `backend/tests/test_lifecycle_status.py::test_lifecycle_status_exposes_conversation_retention_semantics`, `frontend/src/utils/exportChat.test.ts`
- [x] Seed conservative Scheduled Retention Policy defaults for supported expirable Lifecycle Data Classes and audit retention policy changes.
  Evidence: `backend/app/lifecycle.py`, `backend/tests/test_lifecycle_status.py::test_lifecycle_status_includes_conservative_default_retention_policy_for_enforced_classes`, `backend/tests/test_lifecycle_status.py::test_admin_can_update_retention_policy_for_lifecycle_data_class`
- [x] Document implemented Active Storage Lifecycle guarantees and remaining limitations across security docs, session docs, runbooks, ADR-0006, ADR-0007, ADR-0015, and ADR-0016.
- [x] State that active User Profiles, current Document Library records, current Retrieval Index entries, Inference Verification Records, and Retention Run Records are not scheduled for deletion in this milestone.
- [x] State that Inference Verification Records and Retention Run Records remain indefinitely retained until a separate evidence-retention policy exists.
- [x] Add Lifecycle Readiness review/staleness behavior and unsupported Deployment Surface category acknowledgement guidance.
  Evidence: `backend/app/lifecycle.py`, `frontend/src/pages/AdminDeploymentConfig.tsx`, `backend/tests/test_lifecycle_status.py::test_admin_can_review_lifecycle_readiness_and_lifecycle_changes_make_it_stale`, `backend/tests/test_lifecycle_status.py::test_admin_can_acknowledge_unsupported_deployment_surface_category`, `frontend/src/pages/AdminDeploymentConfig.test.tsx::shows unsupported deployment surface categories and lets admins acknowledge one`, `docs/lifecycle-confidentiality-runbook.md`
- [x] Document Copied Exports, browser-held copies, and irreversible Audit Log detail compaction boundaries.
  Evidence: `backend/app/lifecycle.py`, `backend/tests/test_admin_db_query_endpoint.py::test_database_export_creates_copied_export_audit_evidence`, `backend/tests/test_retention_execution.py::test_audit_log_retention_compacts_sensitive_detail_without_full_deletion`, `backend/tests/test_deployment_config_rate_limits.py::test_full_sensitive_audit_log_detail_retention_is_not_exposed_as_config`, `frontend/src/utils/exportChat.ts`, `frontend/src/utils/exportChat.test.ts`, `docs/lifecycle-confidentiality-runbook.md`
- [x] Define external retention policies for unsupported Deployment Surfaces such as logs, WAL files, backups, snapshots, browser caches, copied exports, and provider traces.
  Evidence: `backend/app/lifecycle.py`, `backend/tests/test_lifecycle_status.py`, `docs/deployment-surface-retention.md`
- [x] Keep Secure Erase out of product claims unless a concrete Deployment process exists.
  Evidence: `backend/app/lifecycle.py`, `docs/deployment-surface-retention.md`, `docs/active-content-encryption.md`
- [x] Define complete historical log/session retention separately from active Session Memory deletion.
  Evidence: `backend/app/lifecycle.py`, `backend/tests/test_lifecycle_status.py`, `docs/deployment-surface-retention.md`

---

## 6. Configuration and Environment Hardening Checklist

- [x] Set production env indicator (`ENCLAVE_ENV=production` or equivalent).
  Evidence: `backend/app/auth.py`, `backend/app/deployment_config.py`, `backend/tests/test_deployment_config_rate_limits.py`, `docs/production-configuration-guardrails.md`
- [x] Ensure `MOCK_EMAIL=false` in production.
- [x] Auth simulation flags are not part of the supported deployment surface.
- [x] Set strong, stable `SECRET_KEY` via secret manager.
  Evidence: `backend/app/deployment_config.py`, `backend/tests/test_deployment_config_rate_limits.py`, `docs/production-configuration-guardrails.md`
- [x] Restrict backend and infra ports to private networks/VPN where possible.
  Evidence: `docker-compose.app.yml`, `docker-compose.infra.yml`, `backend/app/deployment_config.py`, `docs/production-configuration-guardrails.md`
- [x] Remove dev-only reload mode in production runtime.
  Evidence: `docker-compose.app.yml`, `backend/app/deployment_config.py`, `backend/tests/test_deployment_config_rate_limits.py`
- [ ] Use non-root containers and hardened container runtime settings.

---

## 7. Monitoring, Testing, and Verification Checklist

- [x] Add automated security tests for auth on all endpoints.
  Evidence: `.github/workflows/security-regression.yml`
- [x] Add regression tests specifically for:
  - ingest endpoint authorization
  - vector-search authorization/scope
  - public query-session record ownership
- [x] Add SAST/dependency scanning in CI.
  Evidence: `.github/workflows/security-regression.yml`, `backend/tests/test_security_ci_workflow.py`
- [x] Add runtime alerting for:
  - repeated auth failures
  - unusual admin actions
  - destructive endpoint usage
  Evidence: `GET /admin/deployment/operational-readiness`, `docs/operational-monitoring-and-recovery.md`, `backend/tests/test_deployment_config_rate_limits.py::test_operational_readiness_exposes_monitoring_and_recovery_drills`
- [x] Add periodic backup + restore test for SQLite and config.
  Evidence: `GET /admin/deployment/operational-readiness`, `docs/operational-monitoring-and-recovery.md`, `backend/tests/test_operational_readiness_docs.py`

### 7.1 Minimum manual verification commands (interim evidence until Section 4.1 automated tests are implemented)

Run from repo root with stack running:

```bash
# S4-1/S4-2: Unauthenticated requests should fail on protected endpoints
curl -i http://localhost:8000/ingest/pending
curl -i -X POST http://localhost:8000/vector-search \
  -H 'Content-Type: application/json' \
  -d '{"query":"test","top_k":1}'

# S4-3: Public query-session routes are Sage-owned.
# Replace SESSION_ID with a Sage-owned query session created by OWNER_TOKEN
# through POST /query. The public query-session resource is:
#   /query/session/{SESSION_ID}
curl -i -X DELETE "http://localhost:8000/query/session/${SESSION_ID}" \
  -H "Authorization: Bearer ${OTHER_AGENT_TOKEN}"
# Expected: 403 Forbidden. Body is the gateway auth error; no deletion summary.

curl -i -X DELETE "http://localhost:8000/query/session/${SESSION_ID}" \
  -H "Authorization: Bearer ${OWNER_TOKEN}"
# Expected: 200 OK with {"status":"deleted","deletion":{"status":"succeeded",...}}
# and sanitized lifecycle results including delete_session_record.

python3 scripts/tests/TOOLS/test_5g_conversation_delete_lifecycle.py --api-base http://localhost:8000
# Expected: owner delete succeeds; non-owner delete is forbidden; the deleted
# session cannot be resumed and disappears from /query/sessions. Python-side
# lifecycle evidence is reported through backend/app/lifecycle.py
# post_sage_session_memory_delete(), which calls the Sage Agent Runtime
# /internal/lifecycle/session-memory/delete endpoint used for deletion and
# tombstone retry reporting.

# S4-4: CORS should reject disallowed origins
curl -i -X OPTIONS http://localhost:8000/health \
  -H 'Origin: https://evil.example.com' \
  -H 'Access-Control-Request-Method: GET'

# S4-7: Verify only expected ports are published
docker compose -f docker-compose.infra.yml -f docker-compose.app.yml ps --format 'table {{.Name}}\t{{.Ports}}'
lsof -nP -iTCP:8000 -sTCP:LISTEN

# Smoke checks expected to remain available
curl -i http://localhost:8000/test
curl -i http://localhost:8000/llm/test
docker exec enclave-api-gateway wget -qO- http://127.0.0.1:8000/test
docker exec enclave-api-gateway wget -qO- http://127.0.0.1:8000/llm/test
```

Expected outcome:
- Protected endpoints return `401` or `403` when unauthenticated.
- CORS preflight for disallowed origins does not return `Access-Control-Allow-Origin`.
- Published ports match least-privilege expectations (no `0.0.0.0` binds on internal services).
- Health/smoke endpoints continue to return successful responses from the Compose `enclave-api-gateway` container. If `lsof` shows another local process bound to `127.0.0.1:8000`, stop it before trusting host `localhost:8000` smoke results.

**Note:** S4-5 (localStorage token removal) and S4-6 (query-param token removal) require browser DevTools inspection — verify that `localStorage` no longer stores session tokens and that auth flows do not pass tokens in URL query strings.

---

## 8. Sign-off Criteria

Mark release as security-ready only when all are true:

- [x] All critical production blockers in Section 4 are complete.
- [x] Token handling is migrated away from `localStorage`.
- [x] CORS and network exposure are least-privilege.
- [x] Simulation and mock auth modes are verified off in production.
  Evidence: `backend/app/deployment_config.py`, `backend/tests/test_deployment_config_rate_limits.py`
- [x] Security regression tests pass in CI.
  Evidence: `.github/workflows/security-regression.yml`, `backend/tests/test_security_ci_workflow.py`
- [x] Incident response and key recovery runbooks are documented and tested.
  Evidence: `docs/operational-monitoring-and-recovery.md`, `docs/admin-key-recovery-runbook.md`, `backend/tests/test_operational_readiness_docs.py`

---

## 9. Notes

- This checklist reflects a repository review, not a full external penetration test.
- Re-run this checklist after major auth, ingest, or deployment config changes.
- Keep product copy aligned with actual controls; avoid absolute claims like "fully private" or "breach-proof".
- Where admin configuration can weaken privacy (for example disabling encryption or sharing data with external providers), surface this clearly in admin and user UI.

---

## 10. Messaging Guardrails (Docs + UI Copy)

Use these guardrails while security fixes are in progress:

- [x] Avoid absolute language (`private by default`, `only you can view`, `protects against breaches`) unless technically guaranteed in all deployment modes.
  Evidence: `frontend/src/pages/UserOnboarding.tsx`, `frontend/src/i18n/locales/en.json`
- [x] State role boundaries explicitly: instance admins configure retention, encryption behavior, and external-provider usage.
  Evidence: `frontend/src/pages/UserAuth.tsx`, `TERMS_OF_SERVICE.md`
- [x] Add user-facing notice where relevant: data handling is instance-configured and may include external processing if enabled.
  Evidence: `frontend/src/pages/UserAuth.tsx`, `frontend/src/pages/UserOnboarding.tsx`
- [x] Add admin-facing attestation before disabling encryption or enabling AI-sharing of sensitive fields.
  Evidence: `frontend/src/components/onboarding/FieldEditor.tsx`

---

## 11. Verification Evidence (2026-02-08 — 2026-05-14)

- Automated regression suite:
  - `PYTHONPATH=.vendorpy python3 scripts/tests/AUTH/test_3c_auth_hardening_regression.py --api-base http://localhost:8000`
    - Result: `OVERALL RESULT: PASSED`
  - `PYTHONPATH=.vendorpy python3 scripts/tests/AUTH/test_3d_phase3_config_integrity.py --api-base http://localhost:8000`
    - Result: `OVERALL RESULT: PASSED`
- Manual Section 7.1 checks:
  - `GET /ingest/pending` unauthenticated: `401`
  - `POST /vector-search` unauthenticated: `401`
  - Public query-session ownership: replay against Sage-owned `/query/session/{SESSION_ID}`:
    `DELETE /query/session/${SESSION_ID}` with `Authorization: Bearer ${OTHER_AGENT_TOKEN}` -> `403 Forbidden`, gateway auth error, no deletion summary.
    `DELETE /query/session/${SESSION_ID}` with `Authorization: Bearer ${OWNER_TOKEN}` -> `200 OK`, `{"status":"deleted","deletion":{"status":"succeeded",...}}` with sanitized lifecycle results including `delete_session_record`.
  - Python lifecycle evidence: run `python3 scripts/tests/TOOLS/test_5g_conversation_delete_lifecycle.py --api-base http://localhost:8000`.
    Expected tombstone lifecycle outcome: owner delete succeeds, non-owner delete is forbidden, the deleted session cannot be resumed and disappears from `/query/sessions`; `backend/app/lifecycle.py::post_sage_session_memory_delete()` is the Agent Runtime gateway client used for Sage Session Memory deletion and tombstone retry reporting through `/internal/lifecycle/session-memory/delete`.
  - Disallowed CORS preflight (`Origin: https://evil.example.com`): rejected (`400 Disallowed CORS origin`, no allow-origin echo)
  - Published ports: `enclave-backend` and `enclave-frontend` bound to `127.0.0.1`, no `0.0.0.0` exposure
  - Smoke endpoints: `GET /test` -> `200`, `GET /llm/test` -> `200`
- S4-5 / S4-6 manual browser verification (DevTools):
  - S4-5 (localStorage token removal): Inspected `Application > Local Storage` in browser DevTools after login — no auth/session tokens stored in `localStorage`. Tokens are transmitted exclusively via secure cookies.
  - S4-6 (query-param token removal): Inspected `Network` tab during auth flows — no tokens appear as URL query parameters. Magic-link verification submits the token in the request body, not the URL.
- Frontend availability smoke:
  - `GET http://localhost:5173/` -> `200`
- Session Memory lifecycle verification (2026-05-14):
  - `python3 -m unittest backend.tests.test_retention_execution backend.tests.test_user_deletion_lifecycle backend.tests.test_data_deletion_results backend.tests.test_lifecycle_status` (activate the repository virtualenv first, if used)
    - Result: `Ran 23 tests ... OK`
  - Audit evidence location: `GET /admin/deployment/audit-log?table_name=data_deletion`; tamper verification: `GET /admin/deployment/audit-log/verify?table_name=data_deletion`.
  - Sage contract verification: `cargo check -p sage-core` from `runtime/sage` returned `Finished dev profile`.
