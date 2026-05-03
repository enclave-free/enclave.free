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
- Model Provider metadata used by Python-side health reporting and remaining legacy paths

It is no longer the owner of Agent Settings. `/admin/ai-config/*` now belongs to Sage and is stored in Sage Postgres.

## Current Ownership Split

| Concern | Current owner | Notes |
| --- | --- | --- |
| public route forwarding | Gateway | `gateway/nginx.conf` routes AI paths to Sage |
| auth issuance, admin UI, ingest, deployment config storage | Python | `core-backend` + SQLite |
| Agent Settings and prompt preview | Sage | Postgres + `sage` runtime |
| `enclave_web` startup, Postgres memory, AI turn execution | Sage | `sage` container env |
| Model Provider transport | Tinfoil proxy | `tinfoil-proxy` container |

Important consequence: changing admin deployment config does not automatically rewrite the Sage container environment.

## Model Provider Compatibility Settings On This Prototype

Recommended current values in admin deployment config:

- `LLM_PROVIDER=sage`
- `LLM_API_URL=http://tinfoil-proxy:8089/v1`
- `LLM_MODEL=kimi-k2-5`
- `LLM_API_KEY=<tinfoil key or matching override>`

These compatibility keys keep existing environment names and UI labels stable. What they affect today:

| Key | Primary effect |
| --- | --- |
| `LLM_PROVIDER` | Python-side Model Provider labeling and compatibility logic |
| `LLM_API_URL` | Python health checks and legacy Python Model Provider client config |
| `LLM_MODEL` | Python-side model metadata / remaining legacy client paths |
| `LLM_API_KEY` | Python-side Model Provider auth unless left empty for env fallback |

What actually drives Sage:

- `TINFOIL_API_URL`
- `TINFOIL_API_KEY`
- `TINFOIL_MODEL`
- `TINFOIL_EMBEDDING_MODEL`
- `DATABASE_URL`
- `ENCLAVE_BACKEND_URL`
- `INTERNAL_AGENT_TOKEN`

Those are currently supplied to the `sage` container through compose or environment, not through the admin deployment UI.

## Health Checks

`GET /admin/deployment/health` currently reports across the split system:

- Qdrant health
- Agent Runtime health via `SAGE_WEB_URL/health`
- Tinfoil proxy health via `LLM_API_URL/models`
- SearXNG health
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

Sage depends on Enclave Python for document retrieval, so mismatches here can break `/query` even when Sage itself is healthy.

## Common Operator Workflow

1. use the admin deployment UI to inspect health and manage Python-owned settings
2. keep Sage env and Python deployment config aligned for shared values
3. restart affected services when changing any setting marked `requires_restart`
4. if the actual Sage Model Provider path changes, update the `sage` container env as well as the admin config view

## Known Temporary State

- the deployment UI is not yet a single source of truth for the whole stack
- Sage runtime config is still partly compose/env-driven
- Gateway behavior is still file-configured in `gateway/nginx.conf`
- Agent Settings are no longer part of the Python deployment-config story; they are Sage-owned and Postgres-backed

That split is expected on this prototype. The point of this doc is to make the split obvious instead of hiding it behind legacy Maple-era assumptions.
