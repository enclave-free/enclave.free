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

## Active Storage Lifecycle Boundaries

Scheduled Retention Execution in this milestone targets only the supported classes exposed in Data Lifecycle Status: stale Sage Session Memory, eligible User Memory, uploaded Document artifacts that are failed, superseded, abandoned, or orphaned, and compactable non-lifecycle Audit Log detail. It does not replace subject-request deletion workflows.

The following active-storage records are not scheduled for deletion in this milestone: active User Profiles, current Document Library records, current Retrieval Index entries, and Inference Verification Records. Inference Verification Records remain indefinitely retained until a separate evidence-retention policy exists, because they are governance evidence for model-provider posture rather than ordinary content.

See `docs/adr/0006-retention-and-deletion-are-operator-controlled-but-incomplete.md` for the overall lifecycle boundary and `docs/adr/0007-audit-log-is-a-product-boundary-but-coverage-is-partial.md` for why governance evidence is preserved while old sensitive detail may be compacted.

## Scheduled Retention Automation

Use external cron, deployment automation, or another trusted external scheduler as the v1 scheduler path. The product exposes a narrow machine endpoint so automation does not reuse a human Admin browser session:

```bash
curl -X POST "$BACKEND_URL/admin/lifecycle/retention/scheduled/automation/run" \
  -H "Content-Type: application/json" \
  -H "X-Retention-Automation-Token: $RETENTION_AUTOMATION_TOKEN" \
  -d '{"retry_limit":3}'
```

The backend reads `RETENTION_AUTOMATION_TOKEN` from environment configuration. Generate a high-entropy token, store it in the deployment secret manager, give only the scheduler access, rotate it by replacing the environment value and redeploying, and revoke it by removing or replacing the value. Audit Log evidence should show `machine:scheduled-retention` rather than a human Admin key.

Every manual or machine-triggered Retention Execution should leave metadata-only Retention Run Records and tamper-evident Audit Log evidence. Retention Run Records store actor, trigger, policy snapshot, timestamps, aggregate status, counts, sanitized per-class results, tombstone references, and Audit Log linkage; they must not preserve Conversation Content, raw User Memory, uploaded Document content, or raw provider attestation material.

Data Lifecycle Status reports Retention Scheduler Observation from Retention Run Records and the current Scheduled Retention Policy. Expected observation states are disabled, never observed, healthy, stale, or failing. Treat `never_observed`, `stale`, and `failing` as operator follow-up signals: confirm the external scheduler is installed, confirm it sends `X-Retention-Automation-Token`, inspect `/admin/lifecycle/retention-runs`, and verify the linked Audit Log evidence.

See `docs/adr/0015-external-retention-scheduler-with-product-owned-run-records.md` for the decision to keep scheduling deployment-owned while making run evidence product-owned.

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
docker compose -f docker-compose.infra.yml -f docker-compose.app.yml ps --format 'table {{.Name}}\t{{.Ports}}'
lsof -nP -iTCP:8000 -sTCP:LISTEN
curl http://localhost:8000/test
curl http://localhost:8000/llm/test
docker exec enclave-api-gateway wget -qO- http://127.0.0.1:8000/test
docker exec enclave-api-gateway wget -qO- http://127.0.0.1:8000/llm/test
curl -H "Authorization: Bearer $ADMIN_TOKEN" http://localhost:8000/admin/lifecycle/status
```

The host curls must reach the Compose `enclave-api-gateway` container. If `lsof` shows another local process bound to `127.0.0.1:8000`, stop it before trusting `localhost:8000` smoke responses.

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

Legacy Retrieval payload repair support can only be removed after the preview reports `support_removal_ready: true`, the active Qdrant index has no legacy plaintext Retrieval payloads, the preview can inspect Qdrant successfully, at least one operator-reviewed execution completed without `retrieval_payload` failures, and backup/rollback expectations are documented. Until then, keep preview, execute, idempotence, and partial-failure tests around the repair path.

## Cleanup Split

Safe documentation and terminology cleanup can remove stale wording that implies the Confidentiality Migration is only planned, provided the docs continue to point operators at the preview and execute endpoints. Data-affecting cleanup remains a separate migration slice: removing legacy plaintext user/profile storage assumptions and removing legacy Qdrant plaintext payload handling require their own operator-reviewed plans and validation evidence. Do not bundle those migrations with wording-only lifecycle cleanup.

## Manual UI Verification

Open the Admin Deployment Config lifecycle view and confirm:

- Lifecycle scope says active product storage.
- Unsupported Deployment Surfaces are visible and can be acknowledged.
- Secure Erase is marked unsupported.
- Content Encryption Key and Artifact Encryption Posture are shown.
- Uploaded Document Artifacts and Retrieval Index report encrypted, mixed, plaintext by operator choice, or not configured honestly.
- Retention preview/run controls and scheduled retention controls still work for human Admins.

Keep this runbook linked from security docs instead of copying detailed implementation notes into multiple places.
