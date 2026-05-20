# Admin Deployment Configuration

The admin deployment UI at `/admin/deployment` still exists on this prototype, but it no longer controls the whole runtime by itself. Current deployment behavior is split across:

- Python deployment config stored in SQLite
- Sage runtime environment variables
- Gateway route config
- Tinfoil proxy environment

This doc describes that split so operators know which setting changes what.

## What The Admin UI Still Owns

The public admin deployment API is still Python-owned:

- UI: `/admin/deployment`
- API: `/admin/deployment/*`
- storage: SQLite `deployment_config` and `config_audit_log`

It remains the canonical place for:

- SMTP and email settings
- frontend/domain/CORS settings exposed through Python
- deployment health checks
- Model Provider metadata used by Python-side health reporting and deployment diagnostics

It is no longer the owner of Agent Settings. `/admin/ai-config/*` now belongs to Sage and is stored in Sage Postgres.

## Current Ownership Split

| Concern | Current owner | Notes |
| --- | --- | --- |
| public route forwarding | Gateway | `gateway/nginx.conf` routes AI paths to Sage |
| auth issuance, admin UI, ingest, deployment config storage | Python | `core-backend` + SQLite |
| Agent Settings and prompt preview | Sage | Postgres + `sage` runtime |
| `enclave_web` startup, Postgres memory, AI turn execution | Sage | `sage` container env |
| Model Provider transport | Tinfoil proxy | `tinfoil-proxy` container |

Important consequence: changing admin deployment config records desired Deployment Settings. It does not mutate live Sage process state until the Operator or Deployment Automation applies generated runtime env and restarts affected services.

## Model Provider Deployment Settings On This Prototype

Recommended current values in admin deployment config:

- `LLM_PROVIDER=sage`
- `LLM_API_URL=http://tinfoil-proxy:8089/v1`
- `LLM_MODEL=kimi-k2-6`
- `LLM_API_KEY=<tinfoil key or matching override>`

These deployment keys keep existing environment names and UI labels stable while Sage runtime configuration remains env-driven. What they affect today:

| Key | Primary effect |
| --- | --- |
| `LLM_PROVIDER` | Python-side Model Provider labeling and validation |
| `LLM_API_URL` | Python health checks against the configured Model Provider endpoint |
| `LLM_MODEL` | Python-side model metadata and diagnostics |
| `LLM_API_KEY` | Python-side Model Provider auth from Deployment Settings |

What actually drives Sage:

- `TINFOIL_API_URL`
- `TINFOIL_API_KEY`
- `TINFOIL_MODEL`
- `TINFOIL_EMBEDDING_MODEL`
- `DATABASE_URL`
- `ENCLAVE_BACKEND_URL`
- `INTERNAL_AGENT_TOKEN`

Those are supplied to the `sage` container through Compose environment interpolation. The admin deployment UI can export a Sage runtime env artifact that maps desired Deployment Settings onto the runtime keys Sage actually reads.

## Sage Runtime Env Export

`GET /admin/deployment/runtime-env/sage` exports an audited, secret-bearing dotenv artifact for Sage. The admin UI exposes this as **Export Sage env**. The older `/admin/deployment/config/runtime-env/sage` path remains as a compatibility alias for current tooling.

The first export slice maps:

| Deployment Setting | Sage runtime env |
| --- | --- |
| `LLM_API_URL` | `TINFOIL_API_URL` |
| `LLM_API_KEY` | `TINFOIL_API_KEY` |
| `LLM_MODEL` | `TINFOIL_MODEL` |
| `EMBEDDING_MODEL` | `TINFOIL_EMBEDDING_MODEL` |
| `FRONTEND_URL` | `FRONTEND_URL` |
| `CORS_ORIGINS` | `CORS_ORIGINS` |
| `SEARXNG_URL` | `SEARXNG_URL` |

Apply flow:

```bash
mkdir -p runtime/generated
# Save the exported Sage env artifact to runtime/generated/sage.env.
docker compose --env-file .env --env-file runtime/generated/sage.env -f docker-compose.infra.yml -f docker-compose.app.yml up -d sage
```

The product records when the Sage runtime env was exported and Deployment Readiness reports whether Deployment Settings changed afterward. Applying and restarting remains a Deployment responsibility, not a live product mutation.

The Service Health panel also shows Runtime Config Alignment:

- Desired: whether the Deployment Settings used by the Sage runtime env export are configured.
- Generated: whether the exported Sage env is missing, current, or stale compared with desired Deployment Settings.
- Running: whether Sage's safe internal runtime-config fingerprint matches the desired Deployment Settings when the Sage endpoint is reachable. If the fingerprint cannot be read, the panel falls back to restart-required evidence and service health.

Sage exposes `GET /internal/runtime-config/fingerprint` for this comparison. The route requires `X-Internal-Agent-Token` and returns non-secret runtime values plus a fingerprint for secret-bearing values, not raw secret material.

## Health Checks

`GET /admin/deployment/health` currently reports across the split system:

- Qdrant health
- Agent Runtime health via `SAGE_WEB_URL/health`
- Tinfoil proxy health via `LLM_API_URL/models`
- SearXNG health
- Shared Rate Limit Store health when Valkey-backed rate limiting is configured
- SMTP health

This makes the page useful for the prototype even though config ownership is split.

## Other Important Settings

### Shared Security And Routing Values

These values need to stay aligned across services:

- `FRONTEND_URL`
- `CORS_ORIGINS`
- `INTERNAL_AGENT_TOKEN`
- `USER_SESSION_COOKIE_NAME`
- `ADMIN_SESSION_COOKIE_NAME`
- `CSRF_COOKIE_NAME`

The admin UI stores some of these on the Python side, but the Sage container still needs matching env values for the public AI routes to behave correctly.

### Storage And Search

Python deployment config still owns:

- `SQLITE_PATH`
- `UPLOADS_DIR`
- `QDRANT_HOST`
- `QDRANT_PORT`
- `SEARXNG_URL`
- `CONTENT_ENCRYPTION_KEY`
- `DOCUMENT_ARTIFACT_ENCRYPTION`

Sage depends on Enclave Python for document retrieval, so mismatches here can break `/query` even when Sage itself is healthy.

`CONTENT_ENCRYPTION_KEY` enables backend-readable encryption for new Uploaded Document artifacts and Retrieval chunk text in active storage. `DOCUMENT_ARTIFACT_ENCRYPTION` defaults to `required`; set it to `disabled` only when the operator explicitly chooses plaintext Uploaded Document artifact storage. Retrieval chunk text still requires the Content Encryption Key even when uploaded artifacts are plaintext by operator choice.

New Retrieval Index writes store vectors and minimal metadata in Qdrant, while encrypted chunk text lives in SQLite. This is active storage confidentiality for product-owned artifacts and retrieval content, not Secure Erase. Legacy Retrieval Index plaintext repair support has been removed, so active retrieval now depends on minimized Qdrant payloads and chunk hydration from product-owned storage.

## Data Lifecycle Status

The Data Lifecycle Status panel is the current operator-visible inventory for the Active Storage Lifecycle. It deliberately separates:

- Active Storage Lifecycle coverage for supported product data classes
- unsupported Deployment Surfaces such as logs, WAL files, backups, snapshots, and provider traces
- Scheduled Retention Policy settings from Retention Scheduler execution
- Content Encryption Key status from Artifact Encryption Posture

This split is important because a class can have deletion, retention, audit, and confidentiality states that move independently.

Scheduled retention is deployment-owned in this milestone. Use an external Retention Scheduler to call the automation endpoint, then verify Retention Scheduler Observation in this panel. Observation is derived from metadata-only Retention Run Records and can report disabled, never observed, healthy, stale, or failing. See `docs/adr/0015-external-retention-scheduler-with-product-owned-run-records.md` and `docs/lifecycle-confidentiality-runbook.md`.

Lifecycle Readiness records Admin review of the current lifecycle posture. Conservative retention defaults may already be active, but readiness can be needs-review or stale after lifecycle-relevant changes. Stale readiness is an Admin warning in v1 and does not block ordinary User Conversations.

The Active Storage Lifecycle does not schedule active User Profiles, current Document Library records, current Retrieval Index entries, Inference Verification Records, or Retention Run Records for deletion in this milestone. Inference Verification Records remain indefinitely retained until a separate evidence-retention policy exists. Retention Run Records remain metadata-only lifecycle evidence until a separate evidence-retention policy exists.

Unsupported Deployment Surfaces are grouped by category: runtime logs, database internals, backups/snapshots, browser-held copies, copied exports, and provider traces. Category acknowledgement records operator review and guidance, but does not promote those surfaces into Lifecycle Data Classes. Copied Exports and browser-held copies remain outside Active Storage Lifecycle after creation. Audit Log detail compaction replaces old sensitive detail irreversibly while preserving governance facts and hash-chain verification.

## Common Operator Workflow

1. use the admin deployment UI to inspect health and manage desired Deployment Settings
2. export Sage runtime env after changing Model Provider, origin, or search settings that Sage reads
3. apply the generated runtime env through the Deployment and restart affected services when changing any setting marked `requires_restart`
4. review Deployment Readiness for stale runtime env, restart-required settings, service health, and lifecycle posture

## Desired State And Running State

Deployment Settings express desired operator-controlled runtime configuration. Deployment Readiness reports whether running services match that desired state, including restart-required settings and stale runtime posture.

The first unified Deployment Settings slice covers operator-facing integration and origin settings. Low-level infrastructure wiring remains outside the first unified Deployment Settings slice, including database URLs, internal service tokens, cookie names, gateway route maps, and container host/port topology.

Known temporary state:

- Sage runtime config is still Compose/env-driven at process start
- Gateway behavior is still file-configured in `gateway/nginx.conf`
- Agent Settings are no longer part of the Python deployment-config story; they are Sage-owned and Postgres-backed

That split is expected on this prototype. The point of this doc is to make the split obvious instead of hiding it behind legacy Maple-era assumptions.
