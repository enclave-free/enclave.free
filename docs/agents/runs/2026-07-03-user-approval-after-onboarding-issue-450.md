# Issue Session: #450 Route Pending-Approval Users Through User Onboarding

## Issue

- Issue: #450 Route pending-approval Users through User Onboarding before pending approval
- Fixed point before session: staging (`66fbf3c45e00c7575813e436d677a7f47caec810`)
- Worker session: Current Codex thread
- Commit: Pending
- Status: Implemented and locally verified

## Inputs

- PRD issue: #449
- Slice issue: #450
- Relevant glossary terms: User Approval, User Onboarding, User Type, Onboarding Question, User Profile, Conversation
- Relevant ADRs: None required; this is a reversible routing-order correction at existing user entry seams.
- Prototype answer, if any: None.

## Implementation

- Public interface used: React route/page behavior for magic-link verification, root auth redirection, and direct `/chat` entry.
- Behaviors covered:
  - Magic-link verified pending-approval Users route to `/user-type` when `needs_user_type` is true.
  - Magic-link verified pending-approval Users route to `/profile` when onboarding questions remain.
  - Direct `/chat` entry checks `/users/me/onboarding-status` before redirecting pending-approval Users to `/pending`.
  - Authenticated root redirect sends non-admin Users through `/chat` so the server-authoritative onboarding-before-approval gate can run.
  - Chat API `403` handling remains the final approval backstop.
- `tdd` used: Yes. Focused route tests were added first and failed against the original approval-before-onboarding behavior.
- Commands run during implementation:
  - `cd frontend && npm install`
  - `cd frontend && npm run test -- ChatPage.test.tsx VerifyMagicLink.test.tsx useAuthFlow.test.ts`
  - `cd frontend && npm run build`
  - `cd frontend && npm run test`
  - `git diff --check`
- Full suite command: `cd frontend && npm run test`

## Review

- Review fixed point: staging
- Standards findings: No blocking findings. Diff follows existing route/page seams, uses existing storage constants in tests, keeps backend contracts unchanged, and preserves repo-scoped terminology in `CONTEXT.md`.
- Spec findings: One local spec review finding was fixed before completion: `VerifyMagicLink` needed `needs_user_type` to win independently, not only when `needs_onboarding` was also true. The route logic and test fixture now cover that case.
- Worthy fixes applied: Reordered magic-link routing to check `needs_user_type`, then `needs_onboarding`, then pending approval; added `hasOnboardingWork` for matching success copy.
- Findings ignored with reasons: None.

## Risks

- Direct root navigation now routes authenticated non-admin Users through `/chat`, which means `/chat` owns the single onboarding-before-approval gate for both approved and pending Users. This is intended, but any future change that removes the `/chat` onboarding-status check would affect root routing too.
