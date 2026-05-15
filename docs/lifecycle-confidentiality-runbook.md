# Lifecycle Confidentiality Runbook

This runbook supports Issue #57 and Issues #58-#67. It is the operator-facing verification path for Active Storage Lifecycle and Document/Retrieval confidentiality without repeating implementation details that should live in code or ADRs.

## What This Covers

- Lifecycle inventory and posture reporting for active product storage.
- Artifact Encryption Posture and Content Encryption Key checks.
- Encrypted uploaded Document artifacts.
- Encrypted Retrieval chunk text in SQLite.
- Minimized Qdrant payloads.
- Retrieval hydration from encrypted chunk storage.
- Document deletion, retention execution, tombstone retry evidence, and confidentiality migration.

The unsupported Deployment Surfaces remain outside these guarantees: runtime logs, WAL files, database backups, snapshots, provider traces, Docker logs, browser caches, and copied exports. This is not a Secure Erase program.

## Scheduled Retention Automation

Use external cron, deployment automation, or another trusted scheduler as the v1 scheduler path. The product exposes a narrow machine endpoint so automation does not reuse a human Admin browser session:

```bash
curl -X POST "$BACKEND_URL/admin/lifecycle/retention/scheduled/automation/run" \
  -H "Content-Type: application/json" \
  -H "X-Retention-Automation-Token: $RETENTION_AUTOMATION_TOKEN" \
  -d '{"retry_limit":3}'
```

The backend reads `RETENTION_AUTOMATION_TOKEN` from environment configuration. Generate a high-entropy token, store it in the deployment secret manager, give only the scheduler access, rotate it by replacing the environment value and redeploying, and revoke it by removing or replacing the value. Audit Log evidence should show `machine:scheduled-retention` rather than a human Admin key.

Manual Admin controls remain available through `/admin/lifecycle/retention/preview`, `/admin/lifecycle/retention/run`, and `/admin/lifecycle/retention/scheduled/run`.

## Regression Commands

Run the focused backend regression suite:

```bash
python3 -m unittest \
  backend.tests.test_ingest_batch_replacement \
  backend.tests.test_store_minimized_payload \
  backend.tests.test_query_retrieval_hydration \
  backend.tests.test_lifecycle_status \
  backend.tests.test_lifecycle_copy_guardrails
```

Run the frontend lifecycle/admin config check:

```bash
cd frontend
npm test -- --run src/pages/AdminDeploymentConfig.test.tsx
```

Smoke the live backend when the stack is running:

```bash
curl http://localhost:8000/test
curl http://localhost:8000/llm/test
curl -H "Authorization: Bearer $ADMIN_TOKEN" http://localhost:8000/admin/lifecycle/status
```

## Confidentiality Checks

For new Document ingestion, verify uploaded artifacts are not plaintext and start with the encrypted artifact marker. In Qdrant, inspect representative Retrieval payloads and confirm they contain retrieval metadata such as `chunk_id`, `job_id`, `source_file`, and `content_ref`, but not raw `text` or `fact_text`.

Use the Retrieval query path to verify hydration still works after payload minimization. Query sources should remain useful through metadata, while model context is assembled from encrypted product-owned chunk storage.

## Migration Checks

Preview before executing:

```bash
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  "$BACKEND_URL/admin/lifecycle/confidentiality-migration/preview"
```

Execute when the preview is acceptable:

```bash
curl -X POST -H "Authorization: Bearer $ADMIN_TOKEN" \
  "$BACKEND_URL/admin/lifecycle/confidentiality-migration/execute"
```

Confirm per-document results show succeeded, skipped, or failed targets honestly. Migration may encrypt eligible artifacts, create encrypted chunk rows from recoverable legacy payload text, and rewrite Qdrant payloads to remove plaintext. It does not claim Secure Erase.

## Manual UI Verification

Open the Admin Deployment Config lifecycle view and confirm:

- Lifecycle scope says active product storage.
- Unsupported Deployment Surfaces are visible and can be acknowledged.
- Secure Erase is marked unsupported.
- Content Encryption Key and Artifact Encryption Posture are shown.
- Uploaded Document Artifacts and Retrieval Index report encrypted, mixed, plaintext by operator choice, or not configured honestly.
- Retention preview/run controls and scheduled retention controls still work for human Admins.

Keep this runbook linked from security docs instead of copying detailed implementation notes into multiple places.
