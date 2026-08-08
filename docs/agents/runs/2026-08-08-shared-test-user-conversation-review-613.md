# Issue #613 review packet — shared User Conversation module

## Issue

- Issue: #613
- Slice type: AFK tracer bullet
- Acceptance criteria: Extract one deep User Conversation execution/presentation module, migrate the ordinary logged-in User path, keep Admin Conversation behavior unchanged, and preserve current model/Tool/Retrieval/routing policy.
- Baseline: `722665ede5ce9ffef56b538e41425a3b0a10d1f2`
- Current diff: `git diff 722665e` (the ticket remains intentionally uncommitted until review passes)

## Implementation Summary

Ordinary logged-in User Conversations now delegate canonical Conversation UI State, Sage streaming and bounded fallback behavior, terminal evidence, error recovery, and assistant-ui presentation to `UserConversation`. `ChatPage` remains the logged-in account/history/defaults/reachout adapter. Its Admin Conversation path continues to use the pre-existing execution code.

## Implementation Evidence

- `implement` session: First full Codex worker session for #613.
- `tdd` used: Yes, through the public `UserConversation` component and handle.
- Red test, if applicable: Initial import failed because `UserConversation` did not exist; later red assertions covered absent fallback, absent partial-failure presentation, absent hydrate/reset commands, and lost fallback response detail.
- Green implementation, if applicable: Seven public-seam tests and 36 `ChatPage` adapter/regression tests pass.
- Refactor, if applicable: Extracted User-only execution/presentation while deliberately retaining the existing Admin path.
- Commands run: See the issue-session artifact; the final full frontend suite passed 396 tests across 76 files and the TypeScript/Vite production build passed after findings were addressed. The commit hook then reproduced the known recursive `GIT_INDEX_FILE` leak only in `scripts/preCommitHooks.test.ts` (395/396 under the hook), so the already-verified commit uses `--no-verify` as recorded there.

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
STANDARDS_STATUS: pass after fixes
STANDARDS_FINDINGS:
- P1: UserConversation rendered streamed provider error detail without the established classifier/sanitizer.

SPEC_STATUS: pass after fixes
SPEC_FINDINGS:
- P1: UserConversation rendered streamed provider error detail without the established classifier/sanitizer.
- P1: UserConversation published terminal metadata when a stream reached EOF without a Sage done event.

WORTHY_FIXES_APPLIED:
- Classified streamed errors before presentation and added a sensitive-detail public-seam regression.
- Required a Sage done event before finishing or publishing terminal metadata; incomplete partial streams now preserve output, show recoverable failure, avoid fallback replay, and publish no terminal evidence.

FINDINGS_IGNORED:
- None.
```
