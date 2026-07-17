# Feature Dev Run Ledger: Production Frontend Serving

## Run

- Run ID: `2026-07-17-production-frontend-serving`
- Loop: Feature Dev `0.4.0`
- Target repo: `enclave-free/enclave.free`
- Base branch: `staging` (`55e5ef4fb1aa3379cedb3923e8480fadb2e6e500` at start)
- Feature branch: `feature/production-frontend-serving`
- Human owner: plebdev
- Started: 2026-07-17
- Current status: primary-session browser verification pending
- Skill setup status: present; GitHub issue tracker and triage vocabulary documented under `docs/agents/`

## Goal

Replace the deployed Vite development server with production static frontend serving so the public app has no development HMR client or websocket errors while preserving the existing frontend and `/api` routing behavior.

## Durable Artifacts

- CONTEXT updates: pending alignment; none expected unless a domain term is resolved
- ADRs: none expected; deployment packaging is reversible and not a product-domain decision
- Prototype source branch, if any: not planned
- Spec issue: [#506](https://github.com/enclave-free/enclave.free/issues/506)
- Tickets: [#507](https://github.com/enclave-free/enclave.free/issues/507)
- Ticket sessions: `docs/agents/runs/2026-07-17-production-frontend-serving-issue-session-507.md`
- Agent briefs: worker brief delivered to `/root/frontend_prod_worker`
- Review packets: `docs/agents/runs/2026-07-17-production-frontend-serving-review-507.md`
- Local CodeRabbit report: pending
- PR URL: pending

## Commands

- Install: `cd frontend && npm ci`
- Typecheck: `cd frontend && npx tsc --noEmit`
- Test: `cd frontend && npm test`
- Build: `cd frontend && npm run build`; production image build command to be fixed during specification
- Visual verification: run the production frontend image locally through Apple Containers, then verify the public routes, SPA fallback, assets, absence of Vite client/HMR traffic, and browser console state

## Ticket Ledger

| Issue | Type | Status | Review thread | Fixes needed | Verified |
| --- | --- | --- | --- | --- | --- |
| #507 | AFK | in-review | Standards pass; Spec browser evidence pending | rendered browser/console gate | Apple HTTP, health, Compose, typecheck, build, and full suite yes; browser pending |

## Parked HITL Slices

| Issue | Why parked | Blocks | Required human action | Final PR decision |
| --- | --- | --- | --- | --- |
| none | n/a | none | none | n/a |

## Issue Session Ledger

| Issue | Fixed point | Worker session | Commit | Review result | Checks |
| --- | --- | --- | --- | --- | --- |
| #507 | `55e5ef4fb1aa3379cedb3923e8480fadb2e6e500` | `/root/frontend_prod_worker` | `d122b03` plus review fixes | Standards pass; Spec changes requested only for browser evidence | Compose contracts; Apple HTTP, probe, and state; typecheck; build; 76 files/419 tests pass |

## Open Questions

- None. The human delegated loop decisions to the orchestrator. The orchestrator confirmed the built container HTTP interface as the primary testing seam and approved one AFK tracer-bullet ticket with no blockers.

## Escalations

- The installed automated browser runtime reported no available browser, so rendered-content and console inspection cannot run in the worker environment. The primary session will run that final gate against the Apple image. The Apple Container HTTP checks prove that user/admin SPA routes resolve to compiled content without the Vite client, and the exact in-container health probe passes with runtime state `running`.
