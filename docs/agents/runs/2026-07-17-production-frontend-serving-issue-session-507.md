# Production Frontend Serving — Issue Session #507

## Issue

- Issue: [#507](https://github.com/enclave-free/enclave.free/issues/507)
- Fixed point before session: `55e5ef4fb1aa3379cedb3923e8480fadb2e6e500`
- Worker session: `/root/frontend_prod_worker`
- Implementation commits: `d122b03`, `9a4906d`
- Status: complete

## Inputs

- Spec issue: [#506](https://github.com/enclave-free/enclave.free/issues/506)
- Ticket: [#507](https://github.com/enclave-free/enclave.free/issues/507)
- Relevant glossary terms: Deployment, Single-Instance Deployment, Gateway
- Relevant ADRs: none; this reversible deployment-packaging change does not alter a product-domain boundary
- Prototype answer and source branch, if any: not applicable

## Implementation

- Public interface used: rendered Compose service configuration and the built frontend container's HTTP port
- Behaviors covered: production image target; stable host port; no production source bind; frontend health; root/user/admin SPA routes; hashed-asset caching; refreshable entry document; no Vite client; no frontend `/api` ownership; explicit Vite development override
- `tdd` used: yes; Compose and HTTP contract checks were red against the previous Vite-default topology before each production/development slice was implemented
- Commands run during implementation: `python3 scripts/tests/DEPLOYMENT/test_frontend_compose_contract.py`; `scripts/test_frontend_runtime.sh apple`; `cd frontend && npx tsc --noEmit`; `cd frontend && npm run build`; `LLM_API_KEY=test INTERNAL_AGENT_TOKEN=test SECRET_KEY=0123456789abcdef0123456789abcdef docker compose -f docker-compose.infra.yml -f docker-compose.app.yml -f docker-compose.frontend-dev.yml config -q`; `bash -n scripts/test_frontend_runtime.sh`
- Full suite command: `cd frontend && npm test` — 76 files and 419 tests passed

## Review

- Review fixed point: `55e5ef4fb1aa3379cedb3923e8480fadb2e6e500`
- Standards findings: the frontend guide did not identify the repository-root working directory; the runtime smoke duplicated runtime dispatch and allowed an unsupported value to reach Docker cleanup
- Spec findings: the smoke did not execute the configured health probe or verify runtime health/state; initial browser evidence was unavailable in the worker session
- Local CodeRabbit findings: unsupported BusyBox health flags; immutable cache header on asset 404s; partial dev-command assertion; ambiguous bind-mount wording; incomplete Compose validation command evidence
- Worthy fixes applied: documented the Compose working directory; selected one cleanup/build/start/health adapter after validating the runtime; executed the exact in-container health probe; verified Apple `running` state; made Docker wait for declared `healthy` state; completed the user/admin browser gate in the primary session against the exact Apple image; addressed all five local CodeRabbit findings, added a missing-asset cache regression, and recorded the exact three-file Compose validation command
- Findings ignored with reasons: none

## Browser Verification

- Image and address: `enclave-frontend-ticket-507:local` at `127.0.0.1:15175`
- User route rendered the language-selection UI (847 visible-text characters); `/admin` rendered Admin Setup/Nostr UI (170 visible-text characters)
- Neither route had a framework overlay or `/@vite/client`; each loaded exactly the hashed production asset script
- Zero console messages matched Vite, WebSocket, or HMR
- `/healthz`, root, and admin probes returned HTTP 200 before browser verification
- Expected standalone `/instance-status` 404 warnings confirmed that `/api` remains outside the frontend container

## Risks

- None identified within this ticket's deployment-packaging scope.
