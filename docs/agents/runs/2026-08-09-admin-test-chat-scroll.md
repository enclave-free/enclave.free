# Admin Test Chat Scroll — Feature Dev Ledger

## Run

- Run ID: `2026-08-09-admin-test-chat-scroll`
- Loop: Feature Dev `0.4.0`
- Target repo: `enclave-free/enclave.free`
- Base branch: `staging` at `4a4037d33cde091b443b5a7ad6723a4d4246b1c4`
- Feature branch: `feature/admin-test-chat-scroll`
- Human owner: Austin
- Started: 2026-08-09
- Current status: Implementation and local verification complete; review pending.
- Skill setup status: Present. `AGENTS.md` and all three `docs/agents` setup files configure GitHub, triage labels, and multi-context domain guidance.

## Goal

Make the active Admin Test User chat a viewport-bounded workspace whose Conversation thread scrolls independently, instead of allowing generated messages and expanded Activity to lengthen the entire Test & Feedback page. Preserve persona selection, Reset, Exit, encrypted trial save, and Feedback behavior.

## Durable Artifacts

- CONTEXT updates: None; existing `Conversation UI Surface` and `Test User Session` terms remain authoritative.
- ADRs: None; ADR-0020 and ADR-0032 already place scrolling in the shared Conversation UI Surface and the Admin-specific height constraint in its thin adapter.
- Prototype source branch, if any: None; the live demo and source inspection reproduce the layout defect directly.
- Spec issue: #612 — shared Test User Conversation.
- Tickets: #621 — Keep Admin Test User chat within a scrollable workspace.
- Ticket sessions: This small, isolated, low-risk adapter layout correction is owned by the orchestrator under the loop's sub-agent implementation exception.
- Agent briefs: #621 is published with `ready-for-agent`.
- Review packets: Two-axis review pending from fixed point `4a4037d33cde091b443b5a7ad6723a4d4246b1c4`.
- Local CodeRabbit report: Pending.
- PR URL: Pending.

## Commands

- Install: Existing `frontend/node_modules` installation.
- Typecheck: `cd frontend && npm run build`
- Test: `cd frontend && npm run test -- TestAsUserView.test.tsx`
- Build: `cd frontend && npm run build`
- Visual verification: Render the active Admin Test User session at desktop and compact viewport heights; verify the composer remains visible while a long expanded Activity trace scrolls inside `Conversation thread`.

## Alignment Decisions

- Constrain only the active `TestAsUserView` wrapper; do not change shared Conversation state, streaming, rendering, or Tool behavior.
- Give the active workspace a responsive viewport-relative height with sensible minimum and maximum bounds.
- Preserve the shared thread's existing `overflow-y-auto` ownership so there is one scroll container and the composer remains outside it.
- The user's live demo report and request authorize this one-ticket correction. Existing Spec #612 already defines the public adapter and Conversation Surface testing seams.

## Ticket Ledger

| Issue | Type | Status                      | Review thread           | Fixes needed | Verified |
| ----- | ---- | --------------------------- | ----------------------- | ------------ | -------- |
| #621  | AFK  | Implemented; review pending | Two-axis review pending | None yet     | Yes      |

## Parked HITL Slices

| Issue | Why parked | Blocks | Required human action | Final PR decision |
| ----- | ---------- | ------ | --------------------- | ----------------- |
| None  |            |        |                       |                   |

## Issue Session Ledger

| Issue | Fixed point                                | Worker session                             | Commit  | Review result | Checks                                                                                                                        |
| ----- | ------------------------------------------ | ------------------------------------------ | ------- | ------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| #621  | `4a4037d33cde091b443b5a7ad6723a4d4246b1c4` | Orchestrator, tiny isolated low-risk write | Pending | Pending       | 20/20 focused tests, 76 files/404 full tests, production build, Prettier, generated CSS inspection, and live Zen preview pass |

## Open Questions

- None. The reported behavior and existing shared Conversation Surface contract determine the layout boundary.

## Escalations

- None.

## Verification Notes

- The focused layout regression failed before implementation because no bounded workspace region existed, then passed after the adapter acquired its responsive height boundary.
- The production build emits the expected responsive `height: clamp(...)` declaration.
- A temporary local DOM preview in the user's open Zen browser applied the exact rule to the current long demo trace. The thread showed its internal scrollbar while the persona controls and composer remained visible. The page was refreshed immediately afterward to remove the temporary preview.
- Full-suite stderr includes existing intentional test-path diagnostics and a missing local `LLM_API_KEY` Compose warning; Vitest still completed successfully with 404/404 tests passing.
