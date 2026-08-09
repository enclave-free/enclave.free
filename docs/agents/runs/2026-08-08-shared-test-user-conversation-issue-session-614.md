# Issue #614 session — shared Test User Conversation adapter

## Issue

- Issue: #614 — Migrate Test User Sessions onto the shared User Conversation module
- Fixed point before session: `ad7afa874b7e6482294b3f580ea5bbc1363be87d`
- Worker session: Second full Codex worker session in the validated Feature Dev pipeline
- Commit: `ba04e26950f041af5ddc5deb1df41b27b1e6319c`
- Status: Complete

## Inputs

- Spec issue: #612
- Ticket: #614
- Relevant glossary terms: Test User Session, User Conversation, Conversation UI State, Conversation Streaming Transport, Conversation UI Surface, Activity, Trace Delta, User Type, Document Access
- Relevant ADRs: ADR-0032, Test User Sessions Reuse the User Conversation Module
- Prototype answer and source branch, if any: None; ticket #613 established the approved `UserConversation` adapter seam.

## Implementation

- Public interface used: `TestAsUserView` supplies synthetic User identity and server-resolved Tool/Document defaults to `UserConversation`, observes canonical snapshots through `onSnapshot`, receives terminal session/Tool metadata through `onTerminalTurn`, and uses the handle only for reset and auth-failure lifecycle commands.
- Behaviors covered: shared assistant-ui surface, markdown, Activity and Trace Deltas after early answer text, stable running state, synthetic bearer use on streaming and fallback transports, server-authoritative defaults, persona controls, reset without reprovisioning, exit, partial-output preservation, pre-output fallback, exact completed-only transcript capture with final Trace and Tool metadata, encrypted save, and parent navigation into Feedback.
- `tdd` used: Yes. The first public-adapter test failed because the standalone input/plain renderer exposed no shared-surface textbox, markdown, Activity, or Trace. Migrating the adapter made that slice green. Existing and added adapter tests then drove selectors and expectations through the shared surface; review-added mixed-transcript and page-navigation cases verified already-implemented behavior without production changes.
- Commands run during implementation:
  - `npm run test -- --run src/components/admin/testfeedback/TestAsUserView.test.tsx -t "renders markdown plus live Activity"` — red against the standalone Admin chat, then green after migration.
  - `npm run test -- --run src/components/admin/testfeedback/TestAsUserView.test.tsx --reporter=dot` — 14 passed before review.
  - `npx tsc --noEmit` — passed during implementation and after review.
  - `npm run test -- --run src/components/chat/UserConversation.test.tsx src/components/admin/testfeedback/TestAsUserView.test.tsx src/components/admin/testfeedback/FeedbackView.test.tsx --reporter=dot` — 29 passed before review; 30 passed after review fixes.
  - `npx prettier --write src/components/admin/testfeedback/TestAsUserView.tsx src/components/admin/testfeedback/TestAsUserView.test.tsx` — scoped formatting passed.
  - `git diff --check ad7afa874b7e6482294b3f580ea5bbc1363be87d` — passed.
- Full suite command: `cd frontend && npm run test -- --reporter=dot` — passed 398 tests before review; after all local, independent, and hosted review corrections, `npm test -- --run --reporter=dot` passed 76 files / 403 tests.
- Production build: `cd frontend && npm run build` — passed after the successful full suite; review changed tests only.
- Commit hook: `npm run verify:pre-commit` completed `lint-staged`, then its recursively invoked suite passed 398 of 399 tests. Only `scripts/preCommitHooks.test.ts` failed because the hook's inherited `GIT_INDEX_FILE` pointed at the real worktree index while that test ran `lint-staged` inside a temporary repository, producing `Current directory is not a git directory!`. This exactly reproduced the documented baseline defect after the standalone full suite had passed. The hook-created `sample.ts` index entry was removed, and the issue commit uses the narrow `--no-verify` workaround.
- Deterministic rendered-component verification: the real `UserConversation` React surface was rendered with controlled Sage events and verified early markdown, live Activity/Trace ordering, stable running/composer state, partial failure, fallback, reset, encrypted save, and Feedback navigation.
- Live-stack availability: unavailable. Compose required an unset `LLM_API_KEY`, and neither `localhost:18000` nor `localhost:5173` was listening.
- Remaining staging smoke steps:
  1. Start the configured stack with `scripts/reset_local_instance.sh` and confirm the gateway `/test` and `/llm/test` endpoints.
  2. As an ordinary logged-in User, run a markdown-producing prompt that uses an enabled Tool and observe early answer text, live Activity/Trace, and the running indicator through terminal completion.
  3. In `/admin/test-and-feedback`, choose the same User Type and run the same prompt; compare the Conversation UI Surface, Activity/Trace, assistant identity, and server-resolved Tool/Document behavior.
  4. Reset the Test User Session and confirm the same synthetic persona starts a fresh Sage session; Exit must return to the User Type picker.
  5. End and save a completed trial, confirm automatic Feedback navigation, approve transcript decryption, and verify the saved answer includes final Trace/Tool evidence while incomplete turns are absent.

## Review

- Review fixed point: `ad7afa8`
- Standards findings: Initial concern that shared streaming/rendering cases duplicated `UserConversation` tests; final reviewer accepted them as ticket-required public-adapter integration checks that mock only system boundaries. Final status: pass.
- Spec findings: Two coverage gaps — no exact mixed completed/failed transcript assertion, and no parent-page observation of Feedback navigation.
- Worthy fixes applied: Added an exact mixed transcript test including Trace/Tool metadata and excluding the failed pair; added an `AdminTestAndFeedback` integration test that observes the selected Feedback tab and mounted Feedback view. Final spec status: pass.
- Findings ignored with reasons: The initial standards duplication concern was not removed because issue #614 explicitly requires Admin adapter integration coverage for shared surface, markdown, Activity/Trace, stable running state, fallback, and partial failure. The final standards reviewer agreed this is requirement-driven seam coverage rather than accidental duplication.
- Local CodeRabbit: Two findings were accepted. Transcript reconstruction now emits only explicitly associated completed User/Assistant pairs and uses checked Tool metadata, and Exit confirms before discarding completed unsaved turns. The corrected shared-module and adapter suites passed 23/23 before the final independent-review regressions, and TypeScript/build checks passed.
- Final independent review: One high edge case was accepted. The first strict-pair implementation still assumed global even/odd alignment after failures. Terminal evidence now carries the exact submitted User turn ID, so capture pairs each terminal answer with its actual question across failed requests and activity-only stream fallback. Two regressions were added; the corrected focused suite passes 25/25 and the full suite passes 402/402.
- Hosted CodeRabbit: One minor and two nitpicks were accepted. Reset now protects unsaved completed turns, transcript-save retries reuse one pending encrypted log, and the terminal-state assertion waits explicitly. Regression coverage passes 26/26 focused and 403/403 full-suite tests; TypeScript and the production build pass.

## Risks

- Live parity and encrypted decryption remain staging smoke steps because no configured local stack was running. Deterministic component verification covers all agent-performable behavior available in this worktree.
- Baseline harness defect: recursive pre-commit execution leaks `GIT_INDEX_FILE` into `scripts/preCommitHooks.test.ts`. The complete standalone suite passes; only the hook-nested temporary-repository test fails.
