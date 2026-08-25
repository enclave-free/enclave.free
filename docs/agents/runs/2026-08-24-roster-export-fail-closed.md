# Fail-closed User Roster Export feature ledger

## Run

- Run ID: `2026-08-24-roster-export-fail-closed`
- Loop: Feature Dev
- Target repo: `enclave-free/enclave.free`
- Base branch: `staging` at merged PR #649 commit `f29b5e2810d7a5be7d1c9d09912b664ac423c294`
- Feature branch: `feature/roster-export-fail-closed`
- Human owner: Austin Kelsay
- Started: 2026-08-24
- Current status: PR #653 open against `staging`; implementation, review, full verification, and build complete.
- Skill setup status: Complete. GitHub Issues, canonical triage labels, and multi-context domain docs are configured.

## Goal

Make both User Roster Export surfaces fail closed. An Admin must prepare a complete browser-decrypted roster snapshot before download is enabled, and one rejected or failed encrypted value must prevent both audit and download.

## Durable artifacts

- CONTEXT updates: User Roster Export completeness rule added on this branch.
- ADRs: None. The rule follows the existing client-only plaintext and Copied Export posture.
- Prototype source branch, if any: None. Existing export and NIP-04 seams are sufficient.
- Spec issue: #643, narrowed by a scope-decision comment for the browser-only enforcement model.
- Tickets: [#650](https://github.com/enclave-free/enclave.free/issues/650).
- Ticket sessions: `/root/roster_export_fail_closed` implemented #650 against fixed point `0f3e91e3e61ffe60d59c8f3b11c9b7aba6f092b7`.
- Agent briefs: The approved implementation contract is captured in #650 with `ready-for-agent` state.
- Review packets: Standards and spec reviewers both passed the fixed-point diff after the review dispositions below. Valid CodeRabbit findings from rounds 1 and 2 were fixed on both export surfaces.
- Local CodeRabbit report: Round 1 found that roster invalidation during in-flight audit silently returned after a successful audit; round 2 found that ordinary invalidation could leave the prior success message visible. Both findings are fixed. Further CodeRabbit passes are unavailable because the organization's included-review quota was exhausted after round 2, so manual and independent review are the fallback.
- PR URL: https://github.com/enclave-free/enclave.free/pull/653

## Commands

- Install: `cd frontend && npm install`.
- Typecheck: `cd frontend && npx tsc --noEmit`.
- Test: focused preparation-module and page tests, then `cd frontend && npm test`.
- Build: `cd frontend && npm run build`.
- Visual verification: both User Settings and User Manager roster-export controls, including successful preparation and failed-decrypt states.

## Ticket ledger

| Issue | Type | Status | Review thread | Fixes needed | Verified |
| --- | --- | --- | --- | --- | --- |
| #650 | AFK | PR #653 open | Standards and spec pass; CodeRabbit rounds 1–2 addressed | Hosted review pending | Full suite and issue-specific checks passed |

## Parked HITL slices

| Issue | Why parked | Blocks | Required human action | Final PR decision |
| --- | --- | --- | --- | --- |
| None | - | - | - | - |

## Issue session ledger

| Issue | Fixed point | Worker session | Commit | Review result | Checks |
| --- | --- | --- | --- | --- | --- |
| #650 | `f29b5e2810d7a5be7d1c9d09912b664ac423c294` | `/root/roster_export_fail_closed` | Rebased focused feature commit | Standards pass; spec pass; CodeRabbit rounds 1–2 fixed | Full suite: 79 files and 434 tests; focused: 35 tests in 4 files; `npx tsc --noEmit`: pass; `npm run build`: pass; `git diff --check`: pass |

## Open questions

- None. The Admin must receive either a complete requested roster or no file.

## Escalations

- None. PR #649 merged and this branch was rebased onto its `staging` merge commit.

## Implementation and verification

- Both User Settings and User Manager now require an explicit, complete browser-decrypted preparation before download is enabled.
- The shared preparation module fails closed when the NIP-07 adapter is unavailable or when any non-null identity or profile ciphertext cannot be decrypted. Optional values with no ciphertext remain valid omissions.
- The prepared snapshot is invalidated when the requested User set or export inputs change. Audit succeeds before the browser download, and neither plaintext nor NIP-07 state is sent to the server.
- Focused command: `cd frontend && npm test -- --run src/utils/userRosterExport.test.ts src/utils/userRosterExportPreparation.test.ts src/pages/AdminUserConfig.test.tsx src/pages/AdminUserManager.test.tsx` — 4 files and 35 tests passed after CodeRabbit round 1.
- Full command after rebasing onto merged PR #649: `cd frontend && npm test -- --run` — 79 files and 434 tests passed.
- The priority-locale prerequisite is now green through merged PR #649; this branch does not alter locale files.
- `cd frontend && npx tsc --noEmit` passed.
- `cd frontend && npm run build` passed: TypeScript and Vite completed after transforming 3,402 modules; only the existing chunk-size warning remained.
- Rendered component tests exercise both export surfaces, including successful preparation, failed decryption, missing-extension fail-closed behavior, optional-no-ciphertext success, invalidation, audit failure, and audit-before-download ordering. Live NIP-07 verification was not feasible without an authenticated local stack and browser extension.

## Review disposition

- Renamed the preparation test helper from `input` to `buildPreparationInput` for clarity.
- Kept the typed failed-decryption target because it makes the shared result diagnosable and directly testable even though the current UI intentionally presents a generic error.
- Did not introduce a shared hook or shared control. Issue #650 explicitly excludes general roster-page refactoring, while the security and completeness rule is already centralized in the preparation module.
- Added only the narrow rendered page-flow cases needed to show missing-extension failure on User Settings and optional-no-ciphertext success on User Manager. The shared module owns the complete rule matrix.
- Final standards review: pass, with no blocking repository-standards issues.
- Final spec review: pass, with no remaining blocking spec issues.
- CodeRabbit round 1: accepted the valid in-flight audit race finding. If roster preparation is invalidated while audit is pending, both pages now clear the snapshot, suppress download, and show their existing prepare-required error. Two rendered regression tests cover the race; the page-only run passed 27 tests in 2 files, the four-file focus passed 35 tests, and `npx tsc --noEmit` passed.
- CodeRabbit round 2: accepted the valid stale-success-message finding. Both invalidation effects now clear their success message with the prepared snapshot, and the existing rendered invalidation flows assert that the ready notice disappears while download becomes disabled. The two page suites passed all 27 tests, `npx tsc --noEmit` passed, and `git diff --check` passed.
- Further CodeRabbit passes are unavailable because the organization's included-review quota was exhausted after round 2. Manual inspection and the independent standards/spec reviews are the fallback for any remaining review.

## Alignment and planning decisions

- The browser is the enforcement point because it alone holds decrypted plaintext. The server continues to require Admin authentication and records the export audit event, but it cannot attest to NIP-07 extension state.
- A shared preparation module is the interface and test seam. It accepts the requested Users, User Types, Onboarding Questions, and a decrypt adapter; it returns a complete workbook snapshot or a typed failure.
- Both export screens use an explicit preparation step. Download remains unavailable until preparation succeeds.
- Any non-null encrypted identity or User Profile value that returns `null` from decryption fails the whole preparation. Missing optional values with no ciphertext are not failures.
- The prepared snapshot stays in browser memory and is invalidated when the requested roster changes.
- Audit must succeed before download, preserving the current Copied Export contract.
- The user explicitly approved the separate-PR breakdown and asked for autonomous end-to-end delivery, which confirms these testing seams and this one-ticket tracer-bullet granularity.
