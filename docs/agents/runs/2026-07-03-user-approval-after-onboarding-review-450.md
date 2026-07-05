# Review Packet: #450 User Approval After User Onboarding

## Issue

- Issue: #450 Route pending-approval Users through User Onboarding before pending approval
- Slice type: AFK
- Acceptance criteria:
  - Verified pending-approval Users route to User Type selection when `needs_user_type=true`.
  - Verified pending-approval Users route to profile completion when onboarding questions remain.
  - Verified pending-approval Users with complete onboarding route to pending approval.
  - Direct non-admin chat entry checks authenticated onboarding status before local pending approval redirect.
  - Direct pending-approval chat entry routes to User Type selection, profile completion, or pending approval according to server onboarding status.
  - Existing approved-user, admin, and chat API `403` approval backstop behavior remains intact.
  - Focused route tests, build, full frontend tests, and whitespace check pass.
- Baseline: staging (`66fbf3c45e00c7575813e436d677a7f47caec810`)
- Current diff: `git diff staging`

## Implementation Summary

Pending-approval Users now complete required User Onboarding before they are blocked from Conversation access. Magic-link verification chooses User Type selection or profile completion before pending approval. Direct `/chat` entry asks the server for onboarding status before using local `USER_APPROVED=false` to redirect to `/pending`. Root auth routing sends authenticated non-admin Users through `/chat` so the same server-authoritative gate runs consistently.

## Implementation Evidence

- `implement` session: Current Codex thread
- `tdd` used: Yes
- Red test, if applicable: Focused route tests initially failed because pending approval rendered before User Type/profile routes.
- Green implementation, if applicable: Route order changed in `VerifyMagicLink`, `ChatPage`, and `useAuthFlow`.
- Refactor, if applicable: None beyond routing-order cleanup and shared route test helpers.
- Commands run:
  - `cd frontend && npm run test -- ChatPage.test.tsx VerifyMagicLink.test.tsx useAuthFlow.test.ts` passed: 3 files, 54 tests.
  - `cd frontend && npm run build` passed with existing large-chunk warnings.
  - `cd frontend && npm run test` passed: 68 files, 348 tests.
  - `git diff --check` passed.

## Review Instructions

Review only this issue's slice unless you find a severe cross-slice regression. Keep standards and spec findings separate.

Check:

- Acceptance criteria are met.
- Tests verify behavior through public route/page interfaces.
- No implementation-only tests are masquerading as behavior tests.
- No obvious incomplete work, TODO placeholders, or unrelated changes.
- Relevant test, typecheck, build, or visual verification commands pass.

## Reviewer Output

```text
STANDARDS_STATUS: pass
STANDARDS_FINDINGS:
- No blocking standards findings. The implementation stays on existing route/page seams, does not introduce backend/schema changes, and records the resolved User Approval/User Onboarding language in CONTEXT.md.

SPEC_STATUS: pass
SPEC_FINDINGS:
- Initial local review found that magic-link routing should treat needs_user_type=true as sufficient to route to User Type selection even if needs_onboarding is false. Fixed before completion and covered by VerifyMagicLink.test.tsx.
```
