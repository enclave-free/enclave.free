# enclave.free-prototype Current Architecture

This document describes the active architecture on `staging`.

The hard cut to Sage is still in place, but the important refinement on this branch is that the gateway is no longer part of the application logic. nginx is now just the stable public entrypoint and path router.

Status note: the sections below that describe native Tool calling and the
`admin-config` endpoint family follow ADR-0029, ADR-0030, and ADR-0028, with
ADR-0023 still owning Tool authority and Tool Set boundaries.
Scoped Config Context and prepared-tool context code are not supported fallback
paths in this architecture.

## Service Map

| Service | Runtime | Responsibility |
| --- | --- | --- |
| `frontend` | Vite + React | User and admin UI |
| `backend` | nginx | Public Gateway on `:18000`; routes AI paths to Sage and everything else to Python |
| `core-backend` | FastAPI + SQLite | Enclave Control Plane for auth issuance, users/admins/settings, ingest, Document visibility, deployment config, and Sage private control-plane endpoints |
| `sage` | Axum + Rust | `enclave_web` Agent Runtime; native auth/CORS/CSRF; Agent Settings; Tool orchestration; public query-session records |
| `postgres` | Postgres + pgvector | Sage Session Memory tables, `web_sessions`, `external_identities`, `ai_config`, `ai_config_user_type_overrides` |
| `qdrant` | Qdrant | Enclave document embeddings and retrieval index |
| `tinfoil-proxy` | Tinfoil standalone proxy | OpenAI-compatible transport for chat, embedding, and vision Model Provider calls |
| `searxng` | SearXNG | Web-search backend for Sage tools |

## Public Topology

```text
frontend
  -> backend (nginx gateway, host port 18000)
      -> core-backend (FastAPI Enclave Control Plane)
      -> sage (Axum Agent Runtime)
```

The public port moves from `:8000` to `:18000`; route ownership remains unchanged. The browser talks to `:18000`, and nginx no longer compensates for auth or browser semantics on Sage-owned routes.

## Tool And Retrieval Posture

Document Library Retrieval is a Sage Tool capability over Enclave-owned Documents, not a hidden route mode.

The Enclave Control Plane owns Document Ingestion, Document Access, chunk embeddings, and Retrieval hydration. New Document writes chunk and embedding records into the Retrieval Index with minimized Qdrant payloads, while chunk text is hydrated from product-owned storage after access filtering.

Sage owns Conversation behavior and a bounded native model-driven Tool loop. Each model request receives every enabled, authorized Tool contract. The model may answer directly or select a bounded Tool batch; after correlated results return, it may continue within a four-batch safety ceiling. Sage never executes a fifth batch. When `knowledge-search` is enabled, each `knowledge_search` call retains the actor's selected Document constraints; retrieved chunks return as Tool results with Activity/Trace metadata.

Graph-first RAG remains deferred. Neo4j, Graphiti, ontology extraction, entity normalization, and graph export are future architecture options, not the current completeness bar for this prototype.

## Public Route Ownership

Routes forwarded to Sage by `gateway/nginx.conf`:

| Route family | Current owner | Notes |
| --- | --- | --- |
| `/health` | core-backend | public stack health target |
| `/llm/chat` | Sage public route | Conversation transport; no Python public handler |
| `/query` | Sage public route | stateful Conversation API compatibility shape; no Python public handler |
| `/query/session/*` | Sage | session inspection and delete |
| `/session-defaults` | Sage public route | local AI defaults + Python document access defaults; no Python public handler |
| `/admin/tools/execute` | Sage public route | admin-only public route; Python executes the safe DB action privately |
| `/admin/ai-config/*` | Sage | public ownership and storage both live in Sage |
| everything else | core-backend | existing Enclave product/control-plane APIs |

Python does not expose public handlers for `/llm/chat`, `/query`, `/session-defaults`, or `/admin/tools/execute`. Public requests go through `gateway/nginx.conf` to Sage, with Python used only behind the private control-plane contract where needed.

## Model-Driven Tool Loop Ownership

The Model-Driven Tool Loop is Sage-owned. Sage expands enabled Tool Sets into provider-native Tool contracts, lets the configured model answer or select a Tool batch, and injects every correlated outcome while the same model continues within a four-batch safety ceiling. Direct no-Tool answers complete from the first model request, and no fifth Tool batch can execute. Sage applies Tool output budgets and emits transparent Activity and Conversation Trace metadata with minimal blocklist protection throughout.

Python remains the Enclave Control Plane. It exposes private facts/actions through `/internal/agent/*` contracts, enforces authorization and redaction for the data it owns, and does not own public Agent Runtime Tool orchestration or pre-classify turns into prompt-ready context blobs.

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

Active Admin Config endpoint family:

| Endpoint | Used for |
| --- | --- |
| `/internal/agent/admin-config/*` | product-level admin configuration reads and direct writes with Enclave Control Plane authorization, validation, audit provenance, and redaction |

Obsolete compatibility endpoints are not part of the accepted Sage call graph.
Scoped admin context is not a supported integration path.

## Request Flows

### Conversation Transport Target

1. frontend calls `http://localhost:18000/llm/chat`
2. `gateway/nginx.conf` forwards the public path to Sage; Python has no public handler for this route
3. Sage verifies auth natively from bearer or cookie session state
4. Sage enforces CSRF if the request is cookie-authenticated and unsafe
5. Sage loads effective Agent Settings from Postgres
6. Sage expands enabled Tool Sets:
   - `knowledge-search` into Document Library Retrieval Tools with selected Document constraints
   - `web-search` into Web Search Tools
   - `admin-config` into product-level configuration read and direct-write Tools, admin only
   - `db-query` into read-only database inspection Tools, admin only
7. Sage runs the bounded native Tool loop; it either streams a direct answer or executes at most four model-selected authorized Tool batches before the answer
8. Sage returns the natural answer, Activity, trace metadata, sources, and affected-area refresh hints

The streaming transport uses the same native round and emits content-free Tool-selection facts, Tool attempts and terminal outcomes, measurable timing, and answer deltas as they occur.

### Stateful Conversation API Compatibility

Existing `/query` routes continue to describe stateful Conversation/session API shapes until the public API is renamed or collapsed. They should not preserve a separate retrieval-first mental model.

Stateful Conversations load or create a durable `web_sessions` record, persist user and assistant turns in Sage Session Memory, and then run the same model-driven Tool loop. Document-grounded chat is represented by the `knowledge-search` Tool Set and document constraints.

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
