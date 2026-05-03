# Dumb Gateway Foundation

This document describes the current `proto/dumb-gateway-foundation` direction in `enclave.free-prototype`.

The goal of this branch is not to add more gateway behavior. It is to keep the public API stable while making the gateway boring and moving request correctness into Sage.

## What This Branch Changed

Compared with the original Sage hard-cut prototype:

- nginx no longer performs cookie-to-bearer auth bridging
- nginx no longer owns Sage-specific CORS behavior
- nginx no longer owns Sage-specific preflight behavior
- Sage now verifies Enclave bearer and cookie sessions natively
- Sage now enforces CSRF for its own unsafe cookie-authenticated routes
- Sage now stores AI config and per-user-type overrides in Postgres
- Sage no longer depends on `POST /internal/agent/auth-context`

The public route surface is unchanged:

- `POST /llm/chat`
- `POST /query`
- `GET /query/session/{session_id}`
- `DELETE /query/session/{session_id}`
- `GET /session-defaults`
- `/admin/ai-config/*`
- `POST /admin/tools/execute`

## Current Responsibility Split

### Gateway

The gateway is now just a router.

It does:

- path-based routing
- generic proxy headers
- request forwarding to Sage or Python

It does not do:

- auth transformation
- CSRF logic
- route-specific CORS logic
- session semantics

### Sage

Sage is now responsible for public AI-route correctness:

- bearer auth verification
- cookie auth verification
- CSRF validation
- CORS for Sage-owned routes
- admin/user authorization on Sage-owned routes
- AI config CRUD and prompt preview
- `/llm/chat`
- `/query`
- query-session ownership and persistence

### Python

Python remains the Enclave control plane:

- issuing auth tokens and cookies
- users, admins, onboarding, and approvals
- ingest and document visibility rules
- document retrieval and access filtering
- user profile context
- safe admin DB query execution
- deployment config and non-AI product/admin routes

## Internal Sage To Python Contract

Active internal endpoints used by Sage on this branch:

- `GET /internal/agent/users/{user_id}`
- `GET /internal/agent/admins/by-pubkey/{pubkey}`
- `GET /internal/agent/user-types/{user_type_id}`
- `GET /internal/agent/document-access`
- `GET /internal/agent/user-profile-context/{user_id}`
- `POST /internal/agent/document-search`
- `POST /internal/agent/admin-db-query`

The endpoint shapes are documented in [internal-agent-contract.md](internal-agent-contract.md).

Compatibility endpoints still exist in Python, but they are no longer part of the main Sage call graph:

- `GET /internal/agent/session-defaults`
- `GET /internal/agent/ai-config/effective`
- `POST /internal/agent/auth-context`

The important point is that Sage now resolves the actor itself and only asks Python for Enclave-owned facts and actions.

## Auth Model

Python remains the issuer of Enclave auth tokens and cookies.

Sage now independently verifies the same `itsdangerous` session contract:

- user salt: `session`
- admin salt: `admin-session`

This includes Python-compatible handling for compressed admin session payloads.

Practical result:

- bearer user auth works on Sage-owned routes
- bearer admin auth works on Sage-owned routes
- cookie user auth works on Sage-owned routes
- cookie admin auth works on Sage-owned routes
- the gateway does not need to synthesize `Authorization` from cookies

## AI Config Ownership

AI config is now Sage-owned end to end for the public runtime API:

- storage lives in Sage Postgres
- global config lives in `ai_config`
- per-user-type overrides live in `ai_config_user_type_overrides`
- prompt preview is assembled in Sage

Python still owns deployment config, but not runtime AI config on this branch.

## Smoke-Tested Behaviors

The current checkpoint was verified in Docker:

- `GET /health` through the stable public origin
- user bearer `POST /llm/chat`
- user cookie `POST /llm/chat`
- admin bearer `GET /admin/ai-config`
- admin cookie `POST /admin/ai-config/prompts/preview`
- admin `POST /admin/tools/execute`
- non-admin rejection on admin tools
- untyped user gets no document-backed `/query` sources
- typed user gets grounded `/query` sources from allowed docs

That means the branch already demonstrates the intended long-term gateway model in practice, not just in code structure.

## What Still Remains

This branch is the foundation, not the end state.

Best remaining productization tasks:

- make the internal `/internal/agent/*` contract explicit and versioned
- decide whether Python deployment config should eventually control Sage runtime env too
- define whether deleting a query session should also purge underlying Sage memory rows
- add browser-level automated tests for cookie auth + CSRF on Sage-owned routes
- remove or clearly quarantine legacy Python AI implementations that are no longer public
