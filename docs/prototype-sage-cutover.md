# Sage Hard-Cut Prototype

This repo is the `enclave.free-prototype` experiment branch for replacing the legacy Enclave AI path with Sage + Tinfoil.

## Repo Layout

- `origin` points at `enclave-free/enclave.free-prototype`
- `upstream` points at `enclave-free/enclave.free`
- `runtime/sage` is a pinned git submodule of the Sage fork
- implementation branch: `proto/sage-hard-cut`

## Runtime Topology

- `frontend` still talks to `backend:8000`
- `backend` is now the API gateway
- `core-backend` is the original FastAPI product/control plane
- `sage` runs the new `enclave_web` binary and owns:
  - `POST /llm/chat`
  - `POST /query`
  - `GET /query/session/{session_id}`
  - `DELETE /query/session/{session_id}`
  - `GET /session-defaults`
  - `POST /admin/tools/execute`
  - `/admin/ai-config/*`
- `tinfoil-proxy` is the OpenAI-compatible model backend
- `postgres` stores Sage web sessions and memory
- `qdrant` remains the Enclave document vector store

## Python Control Plane

The FastAPI backend now exposes private Sage support routes under `/internal/agent/*`:

- `POST /internal/agent/auth-context`
- `POST /internal/agent/document-search`
- `GET /internal/agent/document-access`
- `GET /internal/agent/session-defaults`
- `GET /internal/agent/user-profile-context/{user_id}`
- `POST /internal/agent/admin-db-query`
- `GET /internal/agent/ai-config/effective`

These endpoints are protected with `INTERNAL_AGENT_TOKEN` and are intended only for the Sage service.

## Current Prototype Boundaries

- Admin AI config CRUD is publicly owned by Sage but currently proxied through to the Python backend for storage.
- Prompt preview is generated in Sage from the compiled Enclave web profile.
- Query sessions are persisted in Sage Postgres.
- Legacy Python `/llm/chat` and `/query` code still exists in the repo but is bypassed by the gateway.
