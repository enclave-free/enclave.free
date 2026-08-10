# Transient Provider Recovery and User Activity — Feature Ledger

## Run

- Run ID: `2026-08-10-transient-provider-recovery-activity`
- Loop: Feature Dev
- Target repo: `enclave-free/enclave.free`
- Base branch: `staging`
- Feature branch: `feature/transient-provider-recovery-activity`
- Human owner: Austin Kelsay
- Started: 2026-08-10
- Current status: Reviewed non-draft staging PRs published; CI and hosted CodeRabbit pending
- Skill setup status: Complete; GitHub Issues, canonical triage labels, and multi-context domain docs are configured.

## Goal

Correct the remaining model-provider reliability gap exposed by Jim's August 10 testing, make release evidence representative of fresh and degraded request paths, and make field-user Activity visibility and collapse behavior match the product's intended transparency posture without adding model-routing heuristics or changing model behavior.

## Durable Artifacts

- CONTEXT updates: Added Transient Provider Rejection and clarified whole-Activity progressive disclosure.
- ADRs: Updated ADR-0024 and ADR-0030; ADR-0032 remains aligned without changes.
- Prototype source branch, if any: None expected; the deployed failure and deterministic retry seam already provide runnable evidence.
- Spec issue: [#625](https://github.com/enclave-free/enclave.free/issues/625); local PRD `docs/agents/runs/2026-08-10-transient-provider-recovery-activity-prd.md`.
- Tickets: [#626](https://github.com/enclave-free/enclave.free/issues/626), [#627](https://github.com/enclave-free/enclave.free/issues/627), [#628](https://github.com/enclave-free/enclave.free/issues/628), [#629](https://github.com/enclave-free/enclave.free/issues/629).
- Ticket sessions: #626 `df70528`, `3d20898`, and `e7d0581`, merged to Sage staging as `f41321e`; #627 `6d63f3d`; #628 `cdb199b`; #629 current integration session.
- Agent briefs: The issue bodies and durable triage comments for #626–#629.
- Review packets: Issue-specific session and review records for #626–#629.
- CodeRabbit report: the local Sage review's HTTP-date compatibility finding was fixed in `3d20898`; hosted review then found one clock-precision flake in that parser test, fixed in `e7d0581`. Parent's ten local coverage/evidence findings are corrected. The final local parent rerun reached the organization's included-review rate limit before analysis, so full hosted reviews were triggered on both staging PRs.
- PR URLs: parent [#630](https://github.com/enclave-free/enclave.free/pull/630); Sage [#53](https://github.com/enclave-free/sage/pull/53).

## Commands

- Parent tests: from the repository root, `python3 -m unittest scripts.benches.test_conversation_model_bench` passed 67/67 after the final multi-turn failure correction; the backend discovery suite passed 423/423 with test-only secret placeholders.
- Frontend tests: from `frontend`, `npm test` passed 76 files and 405 tests; the focused shared/User/Admin command recorded in the #628 session passed 46/46.
- Frontend build: from `frontend`, `npm run build` passed TypeScript and the Vite production build. The modified Activity files pass targeted Prettier; the repository-wide command reports pre-existing legacy/generated formatting debt outside this feature.
- Sage checks: from `runtime/sage`, `cargo fmt --all -- --check`, `cargo clippy --all-targets --all-features -- -D warnings`, `cargo test --all-features --quiet`, and `cargo check -p sage-core --bin enclave_web` pass with the Homebrew libpq path supplied on macOS; 189 library and 67 executable tests pass.
- Compose contract: `LLM_API_KEY=test-placeholder SECRET_KEY=test-secret-placeholder docker compose -f docker-compose.infra.yml -f docker-compose.app.yml -f docker-compose.frontend-dev.yml config --quiet` passes.
- Local candidate: exact Core, Sage, and frontend images passed Apple-container startup and endpoint health; a 12-turn Admin cohort completed 12/12 with zero warnings, and a four-turn seeded Resource cohort completed 4/4 with zero hard failures.
- Visual verification: the shared logged-in User Conversation and Admin Test User Activity checks passed at 1440x900 and 390x844. The final fresh in-app browser reached the exact candidate's login/Admin setup surfaces but lacked authenticated User and NIP-07 Admin sessions; no auth state was injected.

## Ticket Ledger

| Issue | Type | Status | Review thread | Fixes needed | Verified |
| --- | --- | --- | --- | --- | --- |
| #626 Provider 429 recovery | AFK | reviewed; ready for integration | Standards PASS; Spec PASS | Corrected mixed-exhaustion coverage, typed snapshot policy, and Retry-After date parsing | 189 lib + 67 main Sage tests + fmt/clippy/check pass |
| #627 Reliability cohorts | AFK | reviewed; ready for integration | Standards PASS; Spec PASS | None | 66/66 bench tests pass |
| #628 Whole-Activity collapse | AFK | reviewed; ready for integration | Standards PASS; Spec PASS | Corrected naming and controlled-region findings | 405/405 frontend tests + build + visual checks pass |
| #629 Integration verification | AFK | reviewed; published in PR #630 | Standards PASS; Spec PASS after correction | Corrected multi-turn false-green cohort edge case | 67/67 bench tests, 16/16 fresh live Conversations, health, provider doubles, source gates, and prior dual-adapter visuals pass |

## Parked HITL Slices

| Issue | Why parked | Blocks | Required human action | Final PR decision |
| --- | --- | --- | --- | --- |
| None | — | — | — | — |

## Issue Session Ledger

| Issue | Fixed point | Worker session | Commit | Review result | Checks |
| --- | --- | --- | --- | --- | --- |
| #626 | `50f0157` / Sage `e072834` | Fresh worker + two-axis reviewers | Sage `df70528`, `3d20898`, and `e7d0581`; staging merge `f41321e` | Standards PASS; Spec PASS; CodeRabbit finding fixed and thread resolved | 189 lib + 67 main tests + fmt/clippy/check pass |
| #627 | `cbdb746` | Current full Codex session | `6d63f3d` | Standards PASS; Spec PASS | 66/66 bench tests pass |
| #628 | `cbdb746` | Fresh worker + two-axis reviewers | `cdb199b` | Standards PASS; Spec PASS after correction | 405/405 frontend tests + build + desktop/compact checks pass |
| #629 | `50f0157` / Sage `e072834` | Current full Codex session | Parent integration branch; Sage staging `f41321e` | Standards PASS; Spec PASS after correction; hosted parent checks pass | Parent, frontend, bench, Compose, Sage, Apple health, 17/17 live Conversations, and prior dual-adapter visual gates pass |

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
