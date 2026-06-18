# Sage Hard-Cut Prototype

This repo is the Enclave experiment that moved the public Agent Runtime from the old Python path to Sage while keeping the public API origin stable at `:8000`.

On the current `staging` snapshot, the cutover is still the same hard cut, but the integration boundary is cleaner than the first prototype pass: the gateway only routes, and Sage owns public AI-route correctness itself.

## What Changed

- the public AI routes no longer terminate in FastAPI
- `backend` is now a compatibility gateway only
- `sage` runs `enclave_web` and owns the public Agent Runtime path
- `core-backend` remains the Enclave control plane for auth issuance, config, ingest, and business logic
- Tinfoil replaces the old Maple-centered runtime story
- Agent Settings are now stored and served by Sage, not proxied through Python
- Sage no longer depends on Python `auth-context` resolution

## Runtime Ownership

| Component | Current role |
| --- | --- |
| `frontend` | UI entrypoint |
| `backend` | boring gateway and route splitter |
| `core-backend` | Enclave Control Plane for auth issuance, admin/product APIs, ingest, and private control-plane endpoints |
| `sage` | Agent Runtime for AI orchestration, auth/CORS/CSRF, Tool execution, Conversation continuity, Agent Settings, and Session Memory |
| `tinfoil-proxy` | Tinfoil transport for Model Provider calls |
| `postgres` | Sage runtime state |
| `qdrant` | Enclave document retrieval |

## Public Routes (Sage-owned)

Sage owns the public route, auth, CORS/CSRF, and Conversation boundary for these paths. Some operations still call Python internally for Enclave Control Plane logic, most notably safe DB execution.

- `POST /llm/chat`
- `POST /llm/chat/stream`
- `POST /query`
- `GET /query/sessions`
- `GET /query/session/{session_id}`
- `PATCH /query/session/{session_id}`
- `DELETE /query/session/{session_id}`
- `GET /session-defaults`
- `POST /admin/tools/execute`
- `/admin/ai-config/*`

Route ownership now matches the public Agent Runtime boundary. `POST /llm/chat`, `POST /llm/chat/stream`, `POST /query`, `GET /query/sessions`, `GET /query/session/{session_id}`, `PATCH /query/session/{session_id}`, `DELETE /query/session/{session_id}`, and `GET /session-defaults` are implemented in Sage. `POST /admin/tools/execute` is routed and authorized by Sage, while Python remains the internal executor for safe read-only Enclave Control Plane DB access.

`POST /llm/chat/stream` is the streaming Conversation transport. ADR-0014 describes the earlier bounded two-phase streaming slice; [ADR-0023](adr/0023-unified-model-driven-tool-loop.md) is the current direction for unified model-driven Tool loop work across streaming and non-streaming Conversation transports.

## Sage To Python Private Control-Plane Contract

Active private control-plane endpoints used by Sage today:

- `GET /internal/agent/users/{user_id}`
- `GET /internal/agent/admins/by-pubkey/{pubkey}`
- `GET /internal/agent/user-types/{user_type_id}`
- `GET /internal/agent/document-access`
- `GET /internal/agent/user-profile-context/{user_id}`
- `POST /internal/agent/document-search`
- `POST /internal/agent/admin-db-query`

ADR-0023 adds this target endpoint family for the model-driven Tool loop hard cut:

- `POST /internal/agent/admin-config/*`

These endpoints are protected by `INTERNAL_AGENT_TOKEN` and are the real integration seam of the prototype.

## What This Branch Finished

- gateway no longer performs auth/cookie bridging
- gateway no longer performs route-specific CORS behavior for Sage
- Sage verifies Enclave bearer and cookie sessions natively
- Sage enforces CSRF for its own unsafe cookie-authenticated routes
- Sage stores Agent Settings and user-type overrides in Postgres
- Sage handles public admin Agent Settings routes directly

## Why The Coupling Still Matters

The gateway itself is now mechanically simple.

The stronger long-term coupling is that Sage still relies on the Enclave Control Plane for:

- user/admin records after token verification
- document-access filtering and retrieval
- user profile context
- admin SQLite query safety rules

If this prototype gets productized, the biggest architecture decision is no longer "keep nginx or not." It is whether the `/internal/agent/*` contract becomes a stable internal API, gets consolidated into shared services, or is collapsed into one runtime later.

## Current Temporary Pieces

- deployment/runtime config is still split across Python Deployment Settings, Sage env, and Gateway config
- Python no longer exposes public Agent Runtime handlers; the supported path is Gateway to Sage
- supported active Conversation deletion now removes the public `/query` session record and associated Sage Session Memory, but scheduled retention for all historical Session Memory/log surfaces is still future work
- Obsolete internal compatibility endpoints are not part of the accepted contract; Scoped Config Context is not a supported integration path

## Branch Note

The pinned Sage runtime lives in `runtime/sage`.

### Runtime/Sage Audit

- Submodule provenance: `runtime/sage` is pinned to commit `b66e63114188392105ff6ba3a7566663c89c8593` from `https://github.com/enclave-free/sage.git`.
- Upstream stability: Sage is an internal Enclave runtime, so reviewer validation should use repository activity rather than package releases: inspect recent commits, open issues/PRs, and maintainer activity before advancing the submodule pointer.
- Integration evidence: this prototype exercises the submodule through the Docker Compose `sage` service and the documented Sage contract checks, including `cargo check -p sage-core` from `runtime/sage` and the `backend/tests/test_5b_sage_route_smoke.py` smoke coverage listed in `docs/integration-tests.md`.
- Security/stability checks: verify the Sage license and dependency tree at the pinned commit, review toolchain requirements from the submodule manifests, run dependency audit tooling appropriate for the Rust workspace, and regenerate an SBOM/checksum before merging a pointer update.
- Reproducible verification:
  1. `git submodule update --init runtime/sage`
  2. `cd runtime/sage && git rev-parse HEAD` should print `b66e63114188392105ff6ba3a7566663c89c8593`.
  3. `cargo check -p sage-core`
  4. From the prototype root, run the Sage route smoke tests documented in `docs/integration-tests.md`.
  5. Regenerate the SBOM or checksum artifact used by the release process and attach it with the CI job names/artifacts that exercised `runtime/sage`.

For the current branch-specific direction, pair this file with:

- [dumb-gateway-foundation.md](dumb-gateway-foundation.md)
- [../ARCHITECTURE_CURRENT.md](../ARCHITECTURE_CURRENT.md)
