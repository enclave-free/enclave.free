# Feature Dev Run Ledger: Production Frontend Serving

## Run

- Run ID: `2026-07-17-production-frontend-serving`
- Loop: Feature Dev `0.4.0`
- Target repo: `enclave-free/enclave.free`
- Base branch: `staging` (`55e5ef4fb1aa3379cedb3923e8480fadb2e6e500` at start)
- Feature branch: `feature/production-frontend-serving`
- Human owner: plebdev
- Started: 2026-07-17
- Current status: final hosted CodeRabbit round 1 passed with zero new issues; round 2 pending
- Skill setup status: present; GitHub issue tracker and triage vocabulary documented under `docs/agents/`

## Goal

Replace the deployed Vite development server with production static frontend serving so the public app has no development HMR client or websocket errors while preserving the existing frontend and `/api` routing behavior.

## Durable Artifacts

- CONTEXT updates: none; deployment packaging did not resolve or change a domain term
- ADRs: none expected; deployment packaging is reversible and not a product-domain decision
- Prototype source branch, if any: not planned
- Spec issue: [#506](https://github.com/enclave-free/enclave.free/issues/506)
- Tickets: [#507](https://github.com/enclave-free/enclave.free/issues/507)
- Ticket sessions: `docs/agents/runs/2026-07-17-production-frontend-serving-issue-session-507.md`
- Agent briefs: worker brief delivered to `/root/frontend_prod_worker`
- Review packets: `docs/agents/runs/2026-07-17-production-frontend-serving-review-507.md`
- Local CodeRabbit reports: `docs/agents/runs/2026-07-17-production-frontend-serving-coderabbit-local-507.md`, `docs/agents/runs/2026-07-17-production-frontend-serving-coderabbit-local-round-2-507.md`, and `docs/agents/runs/2026-07-17-production-frontend-serving-coderabbit-local-round-3-507.md` — six findings addressed across three completed rounds; round 3 corrected an earlier broad comparison by pinning `origin/staging`
- PR URL: [#510](https://github.com/enclave-free/enclave.free/pull/510)
- PR CodeRabbit round 1: one valid trivial timeout finding addressed with bounded `curl` and BusyBox-compatible `wget` probes; CodeRabbit acknowledged the fix and returned a passing status; generic docstring coverage warning dismissed as inapplicable to the repository's shell/test conventions
- Final staging-gate round 1: CodeRabbit completed with zero new issues and no unresolved threads

## Commands

- Install: `cd frontend && npm ci`
- Typecheck: `cd frontend && npx tsc --noEmit`
- Test: `cd frontend && npm test`
- Build: `cd frontend && npm run build`; `scripts/test_frontend_runtime.sh apple` for the production OCI image on this machine
- Visual verification: run the production frontend image locally through Apple Containers, then verify the public routes, SPA fallback, assets, absence of Vite client/HMR traffic, and browser console state

## Ticket Ledger

| Issue | Type | Status   | Review thread                                                                   | Fixes needed | Verified                                                                                                                |
| ----- | ---- | -------- | ------------------------------------------------------------------------------- | ------------ | ----------------------------------------------------------------------------------------------------------------------- |
| #507  | AFK  | complete | Standards pass; Spec pass; local CodeRabbit 6/6 addressed; PR round 1 addressed | none         | Apple HTTP, health, Compose, typecheck, build, full suite, browser verification, and three local CodeRabbit rounds pass |

## Parked HITL Slices

| Issue | Why parked | Blocks | Required human action | Final PR decision |
| ----- | ---------- | ------ | --------------------- | ----------------- |
| none  | n/a        | none   | none                  | n/a               |

## Issue Session Ledger

| Issue | Fixed point                                | Worker session                                                                | Commit                                                                                 | Review result                                                                   | Checks                                                                                                                                     |
| ----- | ------------------------------------------ | ----------------------------------------------------------------------------- | -------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| #507  | `55e5ef4fb1aa3379cedb3923e8480fadb2e6e500` | `/root/frontend_prod_worker` plus primary browser and CodeRabbit verification | `d122b03`, `9a4906d`, `4366996`, `22e1993`, `6ebe340`, `801add3`, `ece03d2`, `5c7f0d1` | Standards pass; Spec pass; local CodeRabbit 6/6 and PR CodeRabbit 1/1 addressed | Compose contracts; Apple HTTP and BusyBox probe; typecheck; build; 76 files/419 tests; user/admin browser verification; all PR checks pass |

## Open Questions

- None. The human delegated loop decisions to the orchestrator. The orchestrator confirmed the built container HTTP interface as the primary testing seam and approved one AFK tracer-bullet ticket with no blockers.

## Escalations

- None. The primary session completed the browser gate against the exact Apple-built image after the worker browser runtime was unavailable.

## Browser Evidence

- Exact image: `enclave-frontend-ticket-507:local`, served at `127.0.0.1:15175`
- User route: rendered the language-selection UI with 847 visible-text characters
- Admin route: rendered the Admin Setup/Nostr UI with 170 visible-text characters
- Both routes: no framework overlay, no `/@vite/client` script, exactly one hashed production asset script, and zero console messages matching Vite, WebSocket, or HMR
- `/healthz`, root, and admin probes returned HTTP 200 before browser verification
- Standalone `/instance-status` 404 warnings were expected because `/api` intentionally remains outside the frontend container
