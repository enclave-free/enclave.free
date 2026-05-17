# enclave.free-prototype

Prototype fork of `enclave.free` that keeps the public API at `:8000` while hard-cutting Agent Runtime behavior from the legacy Python path to Sage + Tinfoil.

On `proto/dumb-gateway-foundation`, the gateway is intentionally boring: nginx only routes requests. Sage now owns auth verification, CORS, CSRF, Agent Settings, and the public Agent Runtime route contract directly.

## System Summary

- `frontend` still talks to `http://localhost:8000`.
- `backend` is an nginx gateway, not the product backend.
- `core-backend` remains the FastAPI Enclave Control Plane for auth issuance, admin/product APIs, ingest, document access, and the private Sage control-plane contract.
- `sage` runs the `enclave_web` Axum binary and owns the Agent Runtime: public AI routes, route auth, CSRF, CORS, Agent Settings, and Conversation continuity.
- `tinfoil-proxy` is the OpenAI-compatible Tinfoil transport used by Sage's preferred Model Provider path.
- `postgres` stores Sage Session Memory and `web_sessions`.
- `qdrant` stays the Enclave document retrieval index.

## Topology

```text
frontend -> gateway(:8000) -> { core-backend(:8000 internal), sage(:3000 internal) }
```

Public route ownership on this branch:

| Route family | Owner |
| --- | --- |
| `/llm/chat` | Sage |
| `/llm/chat/stream` | Sage |
| `/query` | Sage |
| `/query/session/*` | Sage |
| `/session-defaults` | Sage |
| `/admin/tools/execute` | Sage public entry, executed through Python private control-plane endpoint |
| `/admin/ai-config/*` | Sage |
| everything else | `core-backend` |

The short version is: Sage is the Agent Runtime, Python is still the Enclave Control Plane, and the Gateway keeps the public API stable without owning application behavior. `/llm/chat/stream` is the assistant-style streaming companion to `/llm/chat`; it emits early assistant-turn, trace-status, answer-delta, final-trace, and completion events while keeping `/llm/chat` as the non-streaming companion path.

## Quick Start

### Prerequisites

- Docker and Docker Compose
- around 4 GB free disk for model cache and containers

### Configure Environment

```bash
cp .env.example .env
# required: LLM_API_KEY and TINFOIL_API_KEY for Compose
# required: INTERNAL_AGENT_TOKEN
# required: SECRET_KEY
# optional: SMTP_* and FRONTEND_URL for real email auth flows
```

### Start The Stack

Compose is split into infrastructure and app layers:

- `docker-compose.infra.yml`: `postgres`, `tinfoil-proxy`, `qdrant`, `searxng`
- `docker-compose.app.yml`: `core-backend`, `sage`, `backend` gateway, `frontend`

```bash
# full startup
docker compose -f docker-compose.infra.yml -f docker-compose.app.yml up --build -d

# rebuild only the app layer
docker compose -f docker-compose.infra.yml -f docker-compose.app.yml up --build -d core-backend sage backend frontend
```

First startup will:

1. pull Postgres, Tinfoil, Qdrant, and SearXNG images
2. build the FastAPI backend, Sage runtime, gateway, and frontend
3. download the embedding model cache
4. initialize SQLite and Sage Postgres state

### Verify Setup

```bash
docker compose -f docker-compose.infra.yml -f docker-compose.app.yml ps --format 'table {{.Name}}\t{{.Ports}}'
lsof -nP -iTCP:8000 -sTCP:LISTEN
curl http://localhost:8000/test
curl http://localhost:8000/health
curl http://localhost:8000/llm/test
```

The smoke URLs are expected to hit the Compose `enclave-api-gateway` container. If `lsof` shows a local process such as `python3` already listening on `127.0.0.1:8000`, stop it before trusting `localhost:8000`; otherwise the smoke curls may report another server's 404s instead of the gateway result. To bypass host port ambiguity while debugging the stack, run the same checks from inside the gateway container:

```bash
docker exec enclave-api-gateway wget -qO- http://127.0.0.1:8000/test
docker exec enclave-api-gateway wget -qO- http://127.0.0.1:8000/health
docker exec enclave-api-gateway wget -qO- http://127.0.0.1:8000/llm/test
```

Validate changes via smoke test endpoints (`/test` and `/llm/test`) and the frontend Test Dashboard. Open `http://localhost:5173/` after startup and confirm the dashboard loads and responds.

Only two services are exposed to the host by default:

- frontend: `http://localhost:5173`
- public API gateway: `http://localhost:8000`

Everything else stays on the internal Docker network:

- Sage runtime: `http://sage:3000`
- core backend: `http://core-backend:8000`
- Tinfoil proxy: `http://tinfoil-proxy:8089/v1`
- Qdrant: `http://qdrant:6333`
- Postgres: `postgres://sage:sage@postgres:5432/sage`
- SearXNG: `http://searxng:8080`

### First Admin Setup

The prototype still uses the Enclave admin bootstrap flow:

1. open `http://localhost:5173`
2. complete the first NIP-07 admin login
3. configure instance, user, AI, and deployment settings from the admin UI

Until the first admin authenticates, public user signup remains gated.

## Where To Read Next

- [docs/prototype-sage-cutover.md](docs/prototype-sage-cutover.md): cutover story, route ownership, and private contract
- [docs/dumb-gateway-foundation.md](docs/dumb-gateway-foundation.md): current branch design, native Sage auth, and remaining productization work
- [docs/internal-agent-contract.md](docs/internal-agent-contract.md): private Sage-to-Python contract used by this prototype
- [ARCHITECTURE_CURRENT.md](ARCHITECTURE_CURRENT.md): service topology and request/data flow
- [docs/tools.md](docs/tools.md): `/llm/chat` vs `/query` tool behavior
- [docs/sessions.md](docs/sessions.md): auth, CSRF, and Sage-backed public query-session records plus Session Memory
- [docs/admin-deployment-config.md](docs/admin-deployment-config.md): config ownership split across gateway, Python, Sage, and Tinfoil

## Development

Useful logs:

```bash
docker compose -f docker-compose.infra.yml -f docker-compose.app.yml logs -f core-backend
docker compose -f docker-compose.infra.yml -f docker-compose.app.yml logs -f sage
docker compose -f docker-compose.infra.yml -f docker-compose.app.yml logs -f backend
docker compose -f docker-compose.infra.yml -f docker-compose.app.yml logs -f tinfoil-proxy
```

Stop the stack:

```bash
docker compose -f docker-compose.infra.yml -f docker-compose.app.yml down
docker compose -f docker-compose.infra.yml -f docker-compose.app.yml down -v
```
