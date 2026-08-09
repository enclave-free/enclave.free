# Shared Test User Conversation — feature ledger

## Run

- Run ID: 2026-08-08-shared-test-user-conversation
- Loop: Feature Dev
- Target repo: enclave-free/enclave.free
- Base branch: `staging` at `c00023241e8aaeeffe4677eca7db89e29b9c9f27`
- Feature branch: `feature/shared-test-user-conversation`
- Human owner: Austin
- Started: 2026-08-08
- Current status: Staging PR #615 open; hosted Round 1 fixes verified, final hosted refresh pending
- Skill setup status: Present. `AGENTS.md` and all three `docs/agents` setup files exist; GitHub, canonical triage labels, and multi-context domain guidance are configured.

## Goal

Make Admin Test User Sessions use the real User Conversation implementation inside a thin persona-and-feedback wrapper, delete the standalone chat client, and finish with a polished, reviewed, verified non-draft PR into `staging` that is ready for manual smoke testing.

## Durable artifacts

- CONTEXT updates: `Test User Session` added as a real synthetic-User Conversation, not a simplified test chat.
- ADRs: ADR-0032, Test User Sessions Reuse the User Conversation Module.
- Prototype source branch: None; source inspection and the existing shared modules resolve the seam without throwaway code.
- Spec issue: #612 — https://github.com/enclave-free/enclave.free/issues/612
- Tickets: #613 and #614, published in dependency order with `ready-for-agent`.
- Ticket sessions: Issue #613 session recorded in `2026-08-08-shared-test-user-conversation-issue-session-613.md`.
- Ticket sessions: Issue #614 session recorded in `2026-08-08-shared-test-user-conversation-issue-session-614.md`.
- Agent briefs: Approved tickets are published directly as `ready-for-agent`.
- Review packets: Issue #613 packet recorded in `2026-08-08-shared-test-user-conversation-review-613.md`.
- Review packets: Issue #614 packet recorded in `2026-08-08-shared-test-user-conversation-review-614.md`.
- Local CodeRabbit report: `2026-08-08-shared-test-user-conversation-coderabbit-local.md`.
- PR URL: https://github.com/enclave-free/enclave.free/pull/615

## Commands

- Install: `cd frontend && npm install`
- Typecheck: `cd frontend && npm run build`
- Test: `cd frontend && npm run test`
- Build: `cd frontend && npm run build`
- Visual verification: run the frontend against the local Compose stack; compare `/chat` as a logged-in User with `/admin/test-and-feedback` as the same User Type; verify live Activity, markdown, running state, reset, encrypted save, and Feedback review.

## Alignment decisions

- The backend actor, model, Tool defaults, Document Access, and Sage runtime path are already aligned; frontend ownership is the root correction.
- One shared User Conversation module owns execution and presentation. Logged-in and synthetic-user contexts are two adapters at its seam.
- The Admin harness owns persona selection and encrypted evidence capture, not a second message state machine.
- Synthetic Users intentionally simulate a User Type with an otherwise blank User Profile.
- Real User history and User Reachout side effects stay outside Test User Sessions.
- The user confirmed the public testing seams and approved autonomous tracer-bullet granularity and blocking edges.

## Ticket ledger

| Issue | Type | Status | Review thread | Fixes needed | Verified |
| --- | --- | --- | --- | --- | --- |
| #613 Extract the shared User Conversation execution module | AFK | Complete | Architecture seam review completed | Two unique P1 findings fixed | Yes |
| #614 Migrate Test User Sessions onto the shared module | AFK | Complete | Standards/spec, local and hosted CodeRabbit, and final independent review completed | Two spec gaps, five CodeRabbit findings, and one terminal-pairing edge case fixed | Yes |

## Parked HITL slices

| Issue | Why parked | Blocks | Required human action | Final PR decision |
| --- | --- | --- | --- | --- |
| None | | | | |

## Issue session ledger

| Issue | Fixed point | Worker session | Commit | Review result | Checks |
| --- | --- | --- | --- | --- | --- |
| #613 | `722665ede5ce9ffef56b538e41425a3b0a10d1f2` | First full Codex worker session | `14e09e2346897fd6cb36dff5d8390f777cc6d156` | Two unique P1 findings fixed; two-axis review passed | 60 targeted and 396 full-suite tests pass; production build passes; hook-only `GIT_INDEX_FILE` baseline defect recorded |
| #614 | `ad7afa874b7e6482294b3f580ea5bbc1363be87d` | Second full Codex worker session | `ba04e26950f041af5ddc5deb1df41b27b1e6319c` plus review corrections | Two spec gaps, five CodeRabbit findings, and one independent-review edge case fixed; final independent review passed | 26 final focused tests pass; 403-test full suite, TypeScript, and production build pass; deterministic rendered-component verification passed; hook-only `GIT_INDEX_FILE` baseline defect recorded |

## Open questions

- None.

## Escalations

- None.
