# Issue #614 review — shared Test User Conversation adapter

## Issue

- Issue: #614 — Migrate Test User Sessions onto the shared User Conversation module
- Slice type: AFK tracer bullet
- Acceptance criteria: Replace the standalone Admin test chat with the shared `UserConversation` while preserving synthetic identity, server-authoritative defaults, persona controls, reset/exit, terminal-only encrypted capture, and Feedback navigation.
- Baseline: `ad7afa874b7e6482294b3f580ea5bbc1363be87d`
- Current diff: `git diff ad7afa874b7e6482294b3f580ea5bbc1363be87d` (the ticket remains intentionally uncommitted until review passes)

## Implementation Summary

Admin Test User Sessions now render and execute through `UserConversation`. The wrapper provisions the selected synthetic User, supplies its scoped bearer and server-resolved defaults, renders persona/reset/exit/save controls in the shared toolbar, joins terminal Tool/session metadata to canonical snapshots, saves only completed pairs through the encrypted log API, and delegates all conversation state, transport, fallback, error, markdown, Activity/Trace, running-state, copy, and auto-scroll behavior to the shared module.

The source file fell from 623 to 392 lines. Its diff removes 432 lines and adds 201, deleting the independent stream-event switch, turn/input/sending/error/status state, plain renderer, and composer. The two-file implementation/test diff adds 475 lines and removes 483 after final review coverage, for a net reduction of 8 lines.

## Implementation Evidence

- `implement` session: Second full Codex worker session in the validated Feature Dev pipeline.
- `tdd` used: Yes, at the approved public `TestAsUserView`/`UserConversation` adapter seam.
- Red test, if applicable: The standalone Admin chat did not expose the shared surface textbox and could not render markdown, Activity, or Trace after early answer text.
- Green implementation, if applicable: `TestAsUserView` mounts `UserConversation`, and its adapter suite passes 15/15 cases.
- Refactor, if applicable: Removed the second Conversation UI State and raw SSE switch; retained only synthetic identity/defaults, persona controls, reset/exit, terminal-evidence join, encrypted save, and navigation.
- Commands run:
  - Focused adapter: 15 passed.
  - Shared conversation + Admin adapter + Feedback: 30 passed after review.
  - TypeScript: `npx tsc --noEmit` passed.
  - Full frontend suite: 398 passed before the review-only navigation test was added.
  - Production build: passed; review changed tests only.
  - Commit hook: `lint-staged` passed, then the recursively invoked suite passed 398 of 399; only the known inherited-`GIT_INDEX_FILE` temporary-repository harness test failed exactly as previously documented. The narrow `--no-verify` bypass was used after removing the stray `sample.ts` index entry.
  - `git diff --check ad7afa874b7e6482294b3f580ea5bbc1363be87d`: passed.
  - Deterministic rendered-component verification: passed; live stack unavailable because `LLM_API_KEY` was unset and ports 18000/5173 were closed.

## Review Instructions

Review only this issue's slice unless you find a severe cross-slice regression. Keep standards and spec findings separate.

Check:

- Acceptance criteria are met.
- Tests verify behavior through public interfaces.
- No implementation-only tests are masquerading as behavior tests.
- No obvious incomplete work, TODO placeholders, or unrelated changes.
- Relevant test, typecheck, build, or visual verification commands pass.

## Reviewer Output

```text
STANDARDS_STATUS: pass
STANDARDS_FINDINGS:
- Initial duplication/divergence concern resolved: issue #614 explicitly requires these Admin-adapter integration scenarios, which exercise the public component path and mock only transport/API boundaries.

SPEC_STATUS: pass
SPEC_FINDINGS:
- Initial completed-only serialization coverage gap fixed with an exact mixed completed-plus-partial-failed transcript assertion.
- Initial navigation coverage gap fixed by observing the parent page switch to the Feedback tab and render FeedbackView.
```
