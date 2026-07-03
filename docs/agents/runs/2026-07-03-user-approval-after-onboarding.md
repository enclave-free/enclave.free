# User Approval After Onboarding Feature Dev Run

## Run

- Run ID: 2026-07-03-user-approval-after-onboarding
- Loop: Feature Dev
- Target repo: enclave-free/enclave.free
- Base branch: staging
- Feature branch: feature/user-approval-after-onboarding
- Human owner: Austin
- Started: 2026-07-03
- Current status: #450 implemented and locally verified; local CodeRabbit minor docs finding addressed.
- Skill setup status: Present. Repo has AGENTS.md, docs/agents/issue-tracker.md, docs/agents/triage-labels.md, and docs/agents/domain.md.

## Goal

There's an option where users can be required to be approved before they are accepted into chat. Keep that approval option working, but change staging so a user is not blocked until after they answer any onboarding questions. They should answer all onboarding questions and then get blocked right before getting into chat.

## Source Artifacts

- plebdev-loops/workflows/feature-dev/orchestrator-prompt.md
- plebdev-loops/workflows/feature-dev/loop.yaml
- plebdev-loops/docs/loops/feature-dev.md
- plebdev-loops/docs/reference/matt-pocock-skills-pipeline.md
- plebdev-loops/docs/reference/loop-handoffs.md
- plebdev-loops/docs/templates/goal-ledger.md
- AGENTS.md
- docs/agents/issue-tracker.md
- docs/agents/triage-labels.md
- docs/agents/domain.md
- CONTEXT.md
- frontend/src/pages/ChatPage.tsx

## Durable Artifacts

- CONTEXT updates: Added User Approval/User Onboarding ordering rule.
- ADRs: Not expected yet; this appears to be a reversible flow-ordering correction unless implementation uncovers a harder trade-off.
- PRD issue: https://github.com/enclave-free/enclave.free/issues/449
- Slice issues: #450
- Issue sessions: docs/agents/runs/2026-07-03-user-approval-after-onboarding-issue-450.md
- Agent briefs: Pending
- Review packets: docs/agents/runs/2026-07-03-user-approval-after-onboarding-review-450.md
- Local CodeRabbit report: docs/agents/runs/2026-07-03-user-approval-after-onboarding-coderabbit-local.md
- PR URL: Pending

## Commands

- Install: `cd frontend && npm install`
- Typecheck: `cd frontend && npm run build`
- Test: `cd frontend && npm run test`; targeted frontend tests first for user auth/onboarding/chat routing
- Build: `docker compose -f docker-compose.infra.yml -f docker-compose.app.yml up --build`
- Visual verification: User magic-link flow through `/user-type`, `/profile`, `/pending`, and `/chat` in a local or staging-like instance

## Initial Code Finding

`frontend/src/pages/ChatPage.tsx` currently checks local `USER_APPROVED` and redirects unapproved non-admin users to `/pending` before calling `/users/me/onboarding-status`. That matches the reported problem: the approval gate runs before the onboarding status gate.

`frontend/src/pages/VerifyMagicLink.tsx` also currently redirects unapproved users to `/pending` before considering `needs_user_type` or `needs_onboarding`, so the first post-magic-link route has the same ordering bug.

## Alignment Decisions

- Adopted from Austin's stated behavior: pending-approval **Users** should answer all required **Onboarding Questions** first, then be blocked immediately before **Conversation** entry.
- **User Approval** gates **Conversation** access after required **User Onboarding** is complete; it does not gate **User Type** selection or **User Profile** completion.
- Test seam: existing React route/page behavior for magic-link verification and direct chat entry, with backend onboarding-status left as the source of truth for returning users.

## Slice Ledger

| Issue | Type | Status | Review thread | Fixes needed | Verified |
| --- | --- | --- | --- | --- | --- |
| #450 Route pending-approval Users through User Onboarding before pending approval | AFK | Implemented | Current thread local two-axis review | None | Yes |

## Parked HITL Slices

| Issue | Why parked | Blocks | Required human action | Final PR decision |
| --- | --- | --- | --- | --- |
| None | | | | |

## Issue Session Ledger

| Issue | Fixed point | Worker session | Commit | Review result | Checks |
| --- | --- | --- | --- | --- | --- |
| #450 | staging | Current thread | 3fe31c6 | Pass; one spec-edge finding fixed before completion | `npm run test -- ChatPage.test.tsx VerifyMagicLink.test.tsx useAuthFlow.test.ts`; `npm run build`; `npm run test`; `git diff --check` |

## Verification Evidence

- `cd frontend && npm run test -- ChatPage.test.tsx VerifyMagicLink.test.tsx useAuthFlow.test.ts` passed: 3 files, 54 tests.
- `cd frontend && npm run build` passed. Vite reported existing large-chunk warnings.
- `cd frontend && npm run test` passed: 68 files, 348 tests. Output includes existing intentional test noise for missing `LLM_API_KEY`, Prettier sample failures, jsdom navigation, and lazy-route error fallback.
- `git diff --check` passed.

## Review Evidence

- Local code-review standards axis passed against `AGENTS.md`, `CONTEXT.md`, and documented frontend routing/onboarding guidance.
- Local code-review spec axis found and fixed one edge: magic-link routing now treats `needs_user_type=true` as sufficient to route to User Type selection even if `needs_onboarding=false`.
- Sub-agent review was not used because the currently exposed sub-agent tool requires an explicit user request for delegation; the review was performed locally using the code-review skill's two-axis structure.
- Local CodeRabbit completed and reported one minor docs finding about a machine-specific path in this ledger. The finding was addressed and recorded in docs/agents/runs/2026-07-03-user-approval-after-onboarding-coderabbit-local.md.

## Open Questions

- None. Resolved: yes, pending-approval users should be allowed through every required User Onboarding step, including User Type selection and later-required profile questions for returning users, then be redirected to `/pending` only once onboarding status is complete.

## Escalations

- None.
