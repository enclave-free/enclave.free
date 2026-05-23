# Repository Guidelines

## Agent skills

### Issue tracker

Issues and PRDs for this repo live in GitHub Issues for `enclave-free/enclave.free-prototype`. See `docs/agents/issue-tracker.md`.

### Triage labels

Use the default five-label triage vocabulary: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, and `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Use a multi-context layout rooted one level up at `/Users/plebdev/Desktop/code/enclave-free`, covering `enclave.free`, `sage`, and `enclave.free-prototype`. See `docs/agents/domain.md`.

## Project Structure & Module Organization
Enclave is a Docker Compose stack. The root includes `docker-compose.infra.yml`, `docker-compose.app.yml`, environment files, and `docs/` for longer guides. The FastAPI backend lives in `backend/app/` (LLM providers in `backend/app/llm/`). The Vite + React frontend lives in `frontend/src/` with pages, components, and i18n files under `frontend/src/i18n/locales/`. Runtime ingest artifacts are stored in `uploads/` (mounted into the backend container).

## Build, Test, and Development Commands
Run the full stack from the repo root:
```bash
docker compose -f docker-compose.infra.yml -f docker-compose.app.yml up --build        # build + start all services
docker compose -f docker-compose.infra.yml -f docker-compose.app.yml up --build -d     # detached mode
docker compose -f docker-compose.infra.yml -f docker-compose.app.yml logs -f backend   # follow backend logs
docker compose -f docker-compose.infra.yml -f docker-compose.app.yml down              # stop services
```
Frontend-only development:
```bash
cd frontend
npm install       # also wires Husky via prepare
npm run dev       # http://localhost:5173
npm run build     # typecheck + production build
npm run preview   # serve dist/
npm run format    # apply Prettier to frontend (`prettier --write .` in frontend/package.json)
npm run verify:pre-commit  # lint-staged + vitest (same as the git hook)
```
Commits run `frontend/.husky/pre-commit`, which formats staged files with Prettier and runs the frontend test suite.
Smoke tests:
```bash
docker compose -f docker-compose.infra.yml -f docker-compose.app.yml ps --format 'table {{.Name}}\t{{.Ports}}'
lsof -nP -iTCP:8000 -sTCP:LISTEN
curl http://localhost:8000/test
curl http://localhost:8000/llm/test
```
These curls must reach the Compose `enclave-api-gateway` container. If `lsof` shows another local process bound to `127.0.0.1:8000`, stop that process or verify through the gateway container with `docker exec enclave-api-gateway wget -qO- http://127.0.0.1:8000/test` before treating a 404 as product behavior.

## Coding Style & Naming Conventions
Python uses 4-space indentation and type hints. Prefer `snake_case` for functions/modules and `CamelCase` for classes/Pydantic models. TypeScript/TSX uses 2-space indentation and single quotes; React components are `PascalCase.tsx` (e.g., `ChatPage.tsx`). Keep Tailwind class lists readable and reuse shared components in `frontend/src/components/`.

## Testing Guidelines
No automated test framework is configured yet. Validate changes via the smoke test endpoints and the frontend Test Dashboard (`/` route). Include the exact commands or steps you ran in your PR.

## Commit & Pull Request Guidelines
Commit history favors short, action-oriented messages (often lowercase, e.g., “smoke test successful”). Keep messages concise; use `WIP` only for clearly unfinished work. PRs should include a brief summary, linked issues (if any), testing evidence, and screenshots for UI changes.

## Security & Configuration Tips
Copy `.env.example` to `.env` and set `LLM_API_KEY` plus `TINFOIL_API_KEY` when using Compose; Compose maps `TINFOIL_API_KEY` into the backend's canonical `LLM_API_KEY`, but non-Compose runs read `LLM_API_KEY` directly and will miss provider authentication if it is unset. Never commit secrets. The embedding model cache is stored in a Docker volume, and `uploads/` contains local ingest data that should not be checked in.
