# enclave.free-prototype Current Architecture

This document describes the active architecture on `proto/dumb-gateway-foundation`.

The hard cut to Sage is still in place, but the important refinement on this branch is that the gateway is no longer part of the application logic. nginx is now just the stable public entrypoint and path router.

## Service Map

| Service | Runtime | Responsibility |
| --- | --- | --- |
| `frontend` | Vite + React | User and admin UI |
| `backend` | nginx | Public Gateway on `:8000`; routes AI paths to Sage and everything else to Python |
| `core-backend` | FastAPI + SQLite | Enclave Control Plane for auth issuance, users/admins/settings, ingest, Document visibility, deployment config, and Sage private control-plane endpoints |
| `sage` | Axum + Rust | `enclave_web` Agent Runtime; native auth/CORS/CSRF; Agent Settings; Tool orchestration; public query-session records |
| `postgres` | Postgres + pgvector | Sage Session Memory tables, `web_sessions`, `external_identities`, `ai_config`, `ai_config_user_type_overrides` |
| `qdrant` | Qdrant | Enclave document embeddings and retrieval index |
| `tinfoil-proxy` | Tinfoil CLI proxy | OpenAI-compatible transport for chat, embedding, and vision Model Provider calls |
| `searxng` | SearXNG | Web-search backend for Sage tools |

## Public Topology

```text
frontend
  -> backend (nginx gateway, host port 8000)
      -> core-backend (FastAPI Enclave Control Plane)
      -> sage (Axum Agent Runtime)
```

The public origin stays the same. The browser still talks to `:8000`. The difference is that nginx no longer compensates for auth or browser semantics on Sage-owned routes.

## Current Retrieval Posture

The current Document Library Retrieval architecture is intentionally a half-RAG, half-agent path: chunk Retrieval for Sage context, not graph-first RAG.

The Enclave Control Plane owns Document Ingestion, Document Access, chunk embeddings, and Retrieval hydration. New Document writes chunk and embedding records into the Retrieval Index with minimized Qdrant payloads, while chunk text is hydrated from product-owned storage after access filtering.

Sage owns Conversation behavior and consumes retrieved chunks as Agent Runtime context. In `/query`, Sage asks the Enclave Control Plane for available/default Documents and initial retrieved context, then may use `knowledge_search` for additional Document Library Retrieval during the turn.

Graph-first RAG remains deferred. Neo4j, Graphiti, ontology extraction, entity normalization, and graph export are future architecture options, not the current completeness bar for this prototype.

## Public Route Ownership

Routes forwarded to Sage by `gateway/nginx.conf`:

| Route family | Current owner | Notes |
| --- | --- | --- |
| `/health` | core-backend | public stack health target |
| `/llm/chat` | Sage public route | stateless assistant-style route; no Python public handler |
| `/query` | Sage public route | stateful retrieval-first route; no Python public handler |
| `/query/session/*` | Sage | session inspection and delete |
| `/session-defaults` | Sage public route | local AI defaults + Python document access defaults; no Python public handler |
| `/admin/tools/execute` | Sage public route | admin-only public route; Python executes the safe DB action privately |
| `/admin/ai-config/*` | Sage | public ownership and storage both live in Sage |
| everything else | core-backend | existing Enclave product/control-plane APIs |

Python does not expose public handlers for `/llm/chat`, `/query`, `/session-defaults`, or `/admin/tools/execute`. Public requests go through `gateway/nginx.conf` to Sage, with Python used only behind the private control-plane contract where needed.

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

## Sage To Python Private Control-Plane Contract

Sage does not reimplement Enclave Control Plane ownership rules. It calls private FastAPI endpoints under `/internal/agent/*`, protected by `INTERNAL_AGENT_TOKEN`.

Active endpoints in the current Sage call graph:

| Endpoint | Used for |
| --- | --- |
| `GET /internal/agent/users/{user_id}` | hydrate user identity after Sage verifies a user token |
| `GET /internal/agent/admins/by-pubkey/{pubkey}` | hydrate admin identity and current session nonce |
| `GET /internal/agent/user-types/{user_type_id}` | user-type metadata for Agent Settings and admin responses |
| `GET /internal/agent/document-access` | available/default documents for a user type |
| `GET /internal/agent/user-profile-context/{user_id}` | user profile context for prompts |
| `POST /internal/agent/document-search` | document retrieval with Enclave access control |
| `POST /internal/agent/admin-db-query` | safe read-only Enclave Control Plane DB access |

Obsolete compatibility endpoints are absent from Python and are not part of the Sage call graph.

## Request Flows

### `/llm/chat`

1. frontend calls `http://localhost:8000/llm/chat`
2. `gateway/nginx.conf` forwards the public path to Sage; Python has no public handler for this route
3. Sage verifies auth natively from bearer or cookie session state
4. Sage enforces CSRF if the request is cookie-authenticated and unsafe
5. Sage loads effective Agent Settings from Postgres
6. Sage optionally runs server-side tools:
   - `web_search` via SearXNG
   - `db_query` via Python private endpoint, admin only
7. Sage calls Tinfoil and returns the answer

This route is intentionally stateless. It uses `SageAgent::new_without_memory(...)`.

### `/query`

1. frontend calls `http://localhost:8000/query`
2. `gateway/nginx.conf` forwards the public path to Sage; Python has no public handler for this route
3. Sage verifies auth natively from bearer or cookie session state
4. Sage loads effective Agent Settings from Postgres
5. Sage loads or creates a durable public query-session record in Postgres
6. Sage fetches document-access metadata and initial document context from Python
7. Sage updates memory blocks, stores the user turn, and runs the agent
8. Sage may call:
   - `knowledge_search` for additional document retrieval
   - `web_search` when enabled
   - `db_query` when enabled by an admin
9. Sage stores the assistant turn and returns `session_id`, `sources`, and the answer

This route is Retrieval-first and backed by a public session record plus Sage Session Memory.

## Data Ownership

| Data | Current owner | Storage |
| --- | --- | --- |
| auth sessions, admins, users, deployment config, ingest metadata | core-backend | SQLite |
| document embeddings | core-backend ingest path | Qdrant |
| document visibility/default rules | core-backend | SQLite |
| Sage Session Memory (`messages`, `blocks`, `passages`, `summaries`) | Sage | Postgres |
| public query-session records (`web_sessions`) | Sage | Postgres |
| external identity records | Sage | Postgres |
| Agent Settings (`ai_config`) and user-type overrides | Sage | Postgres |

Notes:

- Python still issues the auth tokens and cookies Sage verifies.
- `DELETE /query/session/{session_id}` currently deletes the `web_sessions` record only. It does not act as a full Session Memory Deletion contract.

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
| Agent Settings CRUD and prompt preview | Sage | Postgres + `sage` runtime |
| Sage runtime startup, Tinfoil access, Postgres memory, CSRF/origin checks | Sage | `sage` env |
| Model Provider transport | Tinfoil proxy | `tinfoil-proxy` container |

Important shared values still need coordinated configuration:

- `INTERNAL_AGENT_TOKEN`
- cookie names
- `FRONTEND_URL`
- `CORS_ORIGINS`
- Tinfoil connection details

## Temporary Boundaries To Keep In Mind

- Python no longer contains public Agent Runtime tombstones; obsolete public Agent Runtime routes are absent from the Enclave Control Plane.
- The strongest long-term coupling is now the private `/internal/agent/*` contract, not nginx.
- Deployment config is still not a single source of truth for the entire stack.
- Query-session deletion is still a public session-record delete, not full Session Memory Deletion.
