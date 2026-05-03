# enclave.free-prototype Current Architecture

This document describes the active architecture on `proto/dumb-gateway-foundation`.

The hard cut to Sage is still in place, but the important refinement on this branch is that the gateway is no longer part of the application logic. nginx is now just the stable public entrypoint and path router.

## Service Map

| Service | Runtime | Responsibility |
| --- | --- | --- |
| `frontend` | Vite + React | User and admin UI |
| `backend` | nginx | Public gateway on `:8000`; routes AI paths to Sage and everything else to Python |
| `core-backend` | FastAPI + SQLite | Auth issuance, users/admins/settings, ingest, document visibility, deployment config, and Sage support endpoints |
| `sage` | Axum + Rust | `enclave_web` runtime; native auth/CORS/CSRF; AI config; tool orchestration; query-session ownership |
| `postgres` | Postgres + pgvector | Sage memory tables, `web_sessions`, `external_identities`, `ai_config`, `ai_config_user_type_overrides` |
| `qdrant` | Qdrant | Enclave document embeddings and retrieval index |
| `tinfoil-proxy` | Tinfoil CLI proxy | OpenAI-compatible chat, embedding, and vision backend |
| `searxng` | SearXNG | Web-search backend for Sage tools |

## Public Topology

```text
frontend
  -> backend (nginx gateway, host port 8000)
      -> core-backend (FastAPI control plane)
      -> sage (Axum AI runtime)
```

The public origin stays the same. The browser still talks to `:8000`. The difference is that nginx no longer compensates for auth or browser semantics on Sage-owned routes.

## Public Route Ownership

Routes forwarded to Sage by `gateway/nginx.conf`:

| Route family | Current owner | Notes |
| --- | --- | --- |
| `/health` | core-backend | public stack health target |
| `/llm/chat` | Sage public route | stateless assistant-style route; legacy Python handler remains in `backend/app/main.py` |
| `/query` | Sage public route | stateful retrieval-first route; legacy Python router remains in `backend/app/query.py` |
| `/query/session/*` | Sage | session inspection and delete |
| `/session-defaults` | Sage public route | local AI defaults + Python document access defaults; legacy Python handler remains in `backend/app/main.py` |
| `/admin/tools/execute` | Sage public route | admin-only public route; Python executes the safe DB action privately and also keeps a legacy handler in `backend/app/main.py` |
| `/admin/ai-config/*` | Sage | public ownership and storage both live in Sage |
| everything else | core-backend | existing Enclave product/control-plane APIs |

Legacy Python implementations of `/llm/chat`, `/query`, `/session-defaults`, and `/admin/tools/execute` still exist in `backend/app/main.py` and `backend/app/query.py`. They are not the public path on this branch because `gateway/nginx.conf` routes those public requests to Sage, with Python used behind the internal agent contract where needed.

## Gateway Role

The gateway now does only:

- path routing
- generic proxy headers
- stable public origin exposure

The gateway does not do:

- cookie-to-bearer auth synthesis
- route-specific CORS responses
- route-specific preflight handling
- CSRF logic
- session semantics

That logic lives in Sage for Sage-owned routes.

## Sage To Python Private Contract

Sage does not reimplement Enclave data ownership rules. It calls private FastAPI endpoints under `/internal/agent/*`, protected by `INTERNAL_AGENT_TOKEN`.

Active endpoints in the current Sage call graph:

| Endpoint | Used for |
| --- | --- |
| `GET /internal/agent/users/{user_id}` | hydrate user identity after Sage verifies a user token |
| `GET /internal/agent/admins/by-pubkey/{pubkey}` | hydrate admin identity and current session nonce |
| `GET /internal/agent/user-types/{user_type_id}` | user-type metadata for AI config and admin responses |
| `GET /internal/agent/document-access` | available/default documents for a user type |
| `GET /internal/agent/user-profile-context/{user_id}` | user profile context for prompts |
| `POST /internal/agent/document-search` | document retrieval with Enclave access control |
| `POST /internal/agent/admin-db-query` | safe read-only admin DB access |

Compatibility endpoints still exist in Python but are not part of the main branch call graph:

- `POST /internal/agent/auth-context`
- `GET /internal/agent/session-defaults`
- `GET /internal/agent/ai-config/effective`

## Request Flows

### `/llm/chat`

1. frontend calls `http://localhost:8000/llm/chat`
2. `gateway/nginx.conf` forwards the public path to Sage, even though a legacy Python handler still exists in `backend/app/main.py`
3. Sage verifies auth natively from bearer or cookie session state
4. Sage enforces CSRF if the request is cookie-authenticated and unsafe
5. Sage loads effective AI config from Postgres
6. Sage optionally runs server-side tools:
   - `web_search` via SearXNG
   - `db_query` via Python private endpoint, admin only
7. Sage calls Tinfoil and returns the answer

This route is intentionally stateless. It uses `SageAgent::new_without_memory(...)`.

### `/query`

1. frontend calls `http://localhost:8000/query`
2. `gateway/nginx.conf` forwards the public path to Sage, even though the legacy Python router still exists in `backend/app/query.py`
3. Sage verifies auth natively from bearer or cookie session state
4. Sage loads effective AI config from Postgres
5. Sage loads or creates a durable `web_session` in Postgres
6. Sage fetches document-access metadata and initial document context from Python
7. Sage updates memory blocks, stores the user turn, and runs the agent
8. Sage may call:
   - `knowledge_search` for additional document retrieval
   - `web_search` when enabled
   - `db_query` when enabled by an admin
9. Sage stores the assistant turn and returns `session_id`, `sources`, and the answer

This route is retrieval-first and session-backed.

## Data Ownership

| Data | Current owner | Storage |
| --- | --- | --- |
| auth sessions, admins, users, deployment config, ingest metadata | core-backend | SQLite |
| document embeddings | core-backend ingest path | Qdrant |
| document visibility/default rules | core-backend | SQLite |
| Sage conversation memory (`messages`, `blocks`, `passages`, `summaries`) | Sage | Postgres |
| query-session ownership (`web_sessions`) | Sage | Postgres |
| external identity records | Sage | Postgres |
| AI config and user-type overrides | Sage | Postgres |

Notes:

- Python still issues the auth tokens and cookies Sage verifies.
- `DELETE /query/session/{session_id}` currently deletes the `web_sessions` record only. It does not act as a full Sage-memory purge contract.

## Auth, Cookies, And CSRF

The public auth model stays aligned across Python and Sage:

- Python issues the session tokens and cookies.
- Sage independently verifies the same `itsdangerous` contract.
- bearer auth bypasses CSRF checks
- cookie-authenticated unsafe requests require:
  - trusted `Origin` or `Referer`
  - `X-CSRF-Token` matching the CSRF cookie

Shared cookie/env values must stay aligned across Python, Sage, and the frontend:

- `SECRET_KEY`
- `USER_SESSION_COOKIE_NAME`
- `ADMIN_SESSION_COOKIE_NAME`
- `CSRF_COOKIE_NAME`
- `FRONTEND_URL`
- `CORS_ORIGINS`

The gateway simply forwards `Authorization`, `Cookie`, and `X-CSRF-Token`. It does not interpret them.

## Deployment And Config Ownership

Current config ownership is intentionally split:

| Concern | Current owner | Where it lives |
| --- | --- | --- |
| public route forwarding | gateway | `gateway/nginx.conf` |
| auth issuance, deployment config UI, ingest config | Python | SQLite + `core-backend` env |
| AI config CRUD and prompt preview | Sage | Postgres + `sage` runtime |
| Sage runtime startup, Tinfoil access, Postgres memory, CSRF/origin checks | Sage | `sage` env |
| model transport | Tinfoil proxy | `tinfoil-proxy` container |

Important shared values still need coordinated configuration:

- `INTERNAL_AGENT_TOKEN`
- cookie names
- `FRONTEND_URL`
- `CORS_ORIGINS`
- Tinfoil connection details

## Temporary Boundaries To Keep In Mind

- Python still contains legacy AI route implementations because the cutover is done at the gateway, not by deleting old code yet.
- The strongest long-term coupling is now the private `/internal/agent/*` contract, not nginx.
- Deployment config is still not a single source of truth for the entire stack.
- Query-session deletion is still a session-record delete, not a full-memory purge contract.
