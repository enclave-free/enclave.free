# Sage Hard-Cut Prototype

This repo is the Enclave experiment that moved the public AI runtime from the old Python path to Sage while keeping the public API origin stable at `:8000`.

On `proto/dumb-gateway-foundation`, the cutover is still the same hard cut, but the integration boundary is cleaner than the first prototype pass: the gateway only routes, and Sage owns public AI-route correctness itself.

## What Changed

- the public AI routes no longer terminate in FastAPI
- `backend` is now a compatibility gateway only
- `sage` runs `enclave_web` and owns the public AI runtime path
- `core-backend` remains the Enclave control plane for auth issuance, config, ingest, and business logic
- Tinfoil replaces the old Maple-centered runtime story
- AI config is now stored and served by Sage, not proxied through Python
- Sage no longer depends on Python `auth-context` resolution

## Runtime Ownership

| Component | Current role |
| --- | --- |
| `frontend` | UI entrypoint |
| `backend` | boring gateway and route splitter |
| `core-backend` | auth issuance, admin/product APIs, ingest, private support APIs |
| `sage` | AI orchestration, auth/CORS/CSRF, tool execution, session continuity, AI config, memory persistence |
| `tinfoil-proxy` | model backend |
| `postgres` | Sage runtime state |
| `qdrant` | Enclave document retrieval |

## Public Routes Sage Owns

- `POST /llm/chat`
- `POST /query`
- `GET /query/session/{session_id}`
- `DELETE /query/session/{session_id}`
- `GET /session-defaults`
- `POST /admin/tools/execute`
- `/admin/ai-config/*`

Public ownership now matches actual runtime ownership. The main exception is still `POST /admin/tools/execute`, where Sage owns the public route and authorization but Python remains the internal executor for safe read-only DB access.

## Sage To Python Contract

Active private control-plane endpoints used by Sage:

- `GET /internal/agent/users/{user_id}`
- `GET /internal/agent/admins/by-pubkey/{pubkey}`
- `GET /internal/agent/user-types/{user_type_id}`
- `GET /internal/agent/document-access`
- `GET /internal/agent/user-profile-context/{user_id}`
- `POST /internal/agent/document-search`
- `POST /internal/agent/admin-db-query`

These endpoints are protected by `INTERNAL_AGENT_TOKEN` and are the real integration seam of the prototype.

## What This Branch Finished

- gateway no longer performs auth/cookie bridging
- gateway no longer performs route-specific CORS behavior for Sage
- Sage verifies Enclave bearer and cookie sessions natively
- Sage enforces CSRF for its own unsafe cookie-authenticated routes
- Sage stores AI config and user-type overrides in Postgres
- Sage handles public admin AI config routes directly

## Why The Coupling Still Matters

The gateway itself is now mechanically simple.

The stronger long-term coupling is that Sage still relies on Enclave Python for:

- user/admin records after token verification
- document-access filtering and retrieval
- user profile context
- admin SQLite query safety rules

If this prototype gets productized, the biggest architecture decision is no longer "keep nginx or not." It is whether the `/internal/agent/*` contract becomes a stable internal API, gets consolidated into shared services, or is collapsed into one runtime later.

## Current Temporary Pieces

- deployment/runtime config is still split across Python deployment config, Sage env, and gateway config
- legacy Python `/llm/chat` and `/query` code still exists in-repo even though the gateway bypasses it
- deleting a query session deletes the session record, not the full underlying Sage memory history
- compatibility internal endpoints such as `/internal/agent/auth-context` and `/internal/agent/ai-config/effective` still exist in Python even though Sage no longer needs them on this branch

## Branch Note

The pinned Sage runtime lives in `runtime/sage`.

For the current branch-specific direction, pair this file with:

- [dumb-gateway-foundation.md](dumb-gateway-foundation.md)
- [../ARCHITECTURE_CURRENT.md](../ARCHITECTURE_CURRENT.md)
