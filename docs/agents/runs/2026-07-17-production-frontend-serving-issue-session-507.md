# Production Frontend Serving — Issue Session #507

## Issue

- Issue: [#507](https://github.com/enclave-free/enclave.free/issues/507)
- Fixed point before session: `55e5ef4fb1aa3379cedb3923e8480fadb2e6e500`
- Worker session: `/root/frontend_prod_worker`
- Implementation commit: `d122b03`
- Status: implementation and code review complete; primary-session browser evidence pending

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
- Commands run during implementation: `python3 scripts/tests/DEPLOYMENT/test_frontend_compose_contract.py`; `scripts/test_frontend_runtime.sh apple`; `cd frontend && npx tsc --noEmit`; `cd frontend && npm run build`; Compose config validation; `bash -n scripts/test_frontend_runtime.sh`
- Full suite command: `cd frontend && npm test` — 76 files and 419 tests passed

## Review

- Review fixed point: `55e5ef4fb1aa3379cedb3923e8480fadb2e6e500`
- Standards findings: the frontend guide did not identify the repository-root working directory; the runtime smoke duplicated runtime dispatch and allowed an unsupported value to reach Docker cleanup
- Spec findings: the smoke did not execute the configured health probe or verify runtime health/state; rendered browser and console evidence remains pending
- Worthy fixes applied: documented the Compose working directory; selected one cleanup/build/start/health adapter after validating the runtime; executed the exact in-container health probe; verified Apple `running` state; made Docker wait for declared `healthy` state
- Findings ignored with reasons: none; the primary session owns the remaining browser gate because this worker's installed browser runtime exposed no browser

## Risks

- Apple Containers built and served the production image successfully, passed the in-container health probe, and reported `running`, but the local automated browser runtime exposed no available browser. The HTTP contract proves the compiled route and no-HMR-client behavior; rendered-content and console inspection remain a final orchestration gate.
