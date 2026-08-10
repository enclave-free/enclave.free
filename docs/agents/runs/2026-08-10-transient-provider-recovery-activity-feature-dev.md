# Transient Provider Recovery and User Activity — Feature Ledger

## Run

- Run ID: `2026-08-10-transient-provider-recovery-activity`
- Loop: Feature Dev
- Target repo: `enclave-free/enclave.free`
- Base branch: `staging`
- Feature branch: `feature/transient-provider-recovery-activity`
- Human owner: Austin Kelsay
- Started: 2026-08-10
- Current status: Implementing approved AFK tickets
- Skill setup status: Complete; GitHub Issues, canonical triage labels, and multi-context domain docs are configured.

## Goal

Correct the remaining model-provider reliability gap exposed by Jim's August 10 testing, make release evidence representative of fresh and degraded request paths, and make field-user Activity visibility and collapse behavior match the product's intended transparency posture without adding model-routing heuristics or changing model behavior.

## Durable Artifacts

- CONTEXT updates: Added Transient Provider Rejection and clarified whole-Activity progressive disclosure.
- ADRs: Updated ADR-0024 and ADR-0030; ADR-0032 remains aligned without changes.
- Prototype source branch, if any: None expected; the deployed failure and deterministic retry seam already provide runnable evidence.
- Spec issue: [#625](https://github.com/enclave-free/enclave.free/issues/625); local PRD `docs/agents/runs/2026-08-10-transient-provider-recovery-activity-prd.md`.
- Tickets: [#626](https://github.com/enclave-free/enclave.free/issues/626), [#627](https://github.com/enclave-free/enclave.free/issues/627), [#628](https://github.com/enclave-free/enclave.free/issues/628), [#629](https://github.com/enclave-free/enclave.free/issues/629).
- Ticket sessions: Pending.
- Agent briefs: Pending.
- Review packets: Pending.
- Local CodeRabbit report: Pending.
- PR URL: Pending.

## Commands

- Install: Existing repository dependencies; no new dependencies planned.
- Typecheck: `cd frontend && npm run build`; `cargo check -p sage-core --bin enclave_web` in `runtime/sage`.
- Test: Focused frontend Vitest; focused Sage retry tests; full frontend suite; full Sage workspace suite; parent benchmark-harness tests.
- Build: Frontend production build and Sage `enclave_web` check.
- Visual verification: Shared logged-in User Conversation and Admin Test-as-User Activity behavior at desktop and compact viewport sizes.

## Ticket Ledger

| Issue | Type | Status | Review thread | Fixes needed | Verified |
| --- | --- | --- | --- | --- | --- |
| #626 Provider 429 recovery | AFK | ready-for-agent | Pending | Pending | No |
| #627 Reliability cohorts | AFK | ready-for-agent | Pending | Pending | No |
| #628 Whole-Activity collapse | AFK | ready-for-agent | Pending | Pending | No |
| #629 Integration verification | AFK | blocked by #626–#628 | Pending | Pending | No |

## Parked HITL Slices

| Issue | Why parked | Blocks | Required human action | Final PR decision |
| --- | --- | --- | --- | --- |
| None | — | — | — | — |

## Issue Session Ledger

| Issue | Fixed point | Worker session | Commit | Review result | Checks |
| --- | --- | --- | --- | --- | --- |
| #626 | `50f0157` / Sage `e072834` | Current full Codex session | Pending | Pending | Pending |
| #627 | Pending after #626 | Current full Codex session | Pending | Pending | Pending |
| #628 | Pending after #627 | Current full Codex session | Pending | Pending | Pending |
| #629 | Pending after #626–#628 | Current full Codex session | Pending | Pending | Pending |

## Open Questions

- None. The human delegated full pipeline authority. Existing ADR-0024 resolves actor visibility; this feature adds whole-Activity collapse without actor-specific trace policy.

## Escalations

- None.

## Alignment and Planning Decisions

- Testing seams: the native Model Provider adapter, the public Conversation Model Bench interface, and the shared Conversation Activity module.
- Ticket graph: #626, #627, and #628 can execute independently; #629 integrates and verifies their exact revisions.
- Approval: the human explicitly requested autonomous end-to-end execution of the full Matt Pocock pipeline, so the proposed testing seams, ticket granularity, and blocking edges were accepted under that delegated authority.
- Triage: #626 and #628 are verified bugs; #627 and #629 are verified enhancements. Every ticket has exactly one category role and one ready-for-agent state role, with durable AI-disclaimed triage briefs.

## Investigation Evidence

- Jim observed two failed User turns out of fifteen in the August 10 report.
- The first failed turn was a 30-second pre-response provider stall followed by an upstream HTTP 429 on attempt two; the 429 terminated the shared three-attempt budget before attempt three.
- The second failed turn received an upstream HTTP 429 on attempt one and did not retry.
- A fresh deployed probe recovered only on attempt three after two 30-second stalls and completed in roughly 74 seconds; eleven immediately following fresh sessions completed in roughly 7–10 seconds.
- Retrieval and Curated Resources completed quickly in the failed-window evidence and were not the failure source.
- The Conversation Model Bench uses fresh Conversation identifiers but runs sequentially and has no deterministic provider-side 429/stall fault profile or reliability cohort gate.
- Current User and Admin Conversation Trace assembly ignores legacy actor visibility defaults and emits detailed sanitized Activity to both actor kinds.
- The current `Hide activity details` control hides optional summaries only; it does not collapse the Activity timeline or operational Trace rows.
