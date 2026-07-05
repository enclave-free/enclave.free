# Admin Signer-Decrypted DB Context

## Run

- Run ID: 2026-07-05-admin-signer-decrypt-db-context
- Loop: plebdev-feature-dev
- Target repo: enclave-free/enclave.free
- Base branch: staging
- Feature branch: feature/admin-signer-decrypt-db-context
- Human owner: plebdev
- Started: 2026-07-05T22:45:47Z
- Current status: PR open against `staging`; local checks passed; PR-side CodeRabbit review requested.
- Skill setup status: Present. `AGENTS.md` and `docs/agents/{issue-tracker,triage-labels,domain}.md` exist.

## Goal

Let an approved Admin Database-enabled conversation delegate bounded plaintext decrypted by the Admin browser signer into the current encrypted inference turn. This lets Sage interpret encrypted User identity/profile values alongside safe database query results without giving the backend or Sage custody of the Admin private key.

## Durable Artifacts

- CONTEXT updates: Added **Admin Signer-Decrypted Context**.
- ADRs: Not planned; this extends the existing Sage-owned model-driven Tool loop and encrypted inference posture.
- PRD issue: https://github.com/enclave-free/enclave.free/issues/469
- Slice issue: https://github.com/enclave-free/enclave.free/issues/470
- Issue sessions: This run ledger.
- Agent briefs: None.
- Review packets: Manual review complete; local CodeRabbit first pass fixed; PR-side CodeRabbit requested.
- Local CodeRabbit report: First pass found two minor docs issues; both fixed. Rerun was stopped after a bounded wait while still heartbeating.
- PR URL: https://github.com/enclave-free/enclave.free/pull/471

## Commands

- Install: Not needed yet.
- Typecheck: `npm run build` passed.
- Test: Focused frontend tests, Sage web runtime tests, backend DB safety/docs tests, and diff checks passed.
- Build: `npm run build` passed with the existing Vite large chunk warning.
- Visual verification: Not planned; this is a request/runtime behavior change without new visible layout.

## Slice Ledger

| Issue                                                                                  | Type | Status  | Review thread                      | Fixes needed | Verified |
| -------------------------------------------------------------------------------------- | ---- | ------- | ---------------------------------- | ------------ | -------- |
| #470 Delegate encrypted User context from the Admin signer into Database conversations | AFK  | PR open | Local CodeRabbit and manual review | None known   | Yes      |

## Parked HITL Slices

| Issue | Why parked | Blocks | Required human action | Final PR decision |
| ----- | ---------- | ------ | --------------------- | ----------------- |
| None  |            |        |                       |                   |

## Issue Session Ledger

| Issue | Fixed point                   | Worker session       | Commit                           | Review result                                                   | Checks                                                                                                                 |
| ----- | ----------------------------- | -------------------- | -------------------------------- | --------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| #470  | `origin/staging` at `97e5b5a` | Current Codex thread | Sage `782aaa7`; parent PR branch | Local CodeRabbit minor docs fixed; PR-side CodeRabbit requested | Frontend Vitest focused suite; Sage `web_runtime::tests`; backend DB safety/docs unittest; frontend build; diff checks |

## Verification Log

- Added red Vitest coverage for building Admin signer-decrypted User context from `/admin/users`.
- Added red chat transport coverage for sending `client_decrypted_context` only when an Admin Database turn opts in.
- Added red Sage coverage for including Admin Signer-Decrypted Context in Admin `db-query` turn input and ignoring it otherwise.
- Implemented a browser-only context builder using the existing NIP-04 `decryptField` path; the key remains inside the Admin signer.
- Wired Admin `/chat` and the admin sidebar assistant to opt in only when Database is enabled for the submitted turn.
- Sage accepts `client_decrypted_context` but only renders it into model input for authenticated Admin turns with the `db-query` Tool Set enabled.
- Focused frontend tests passed: `npm test -- --run src/utils/adminSignerContext.test.ts src/utils/llmChat.test.ts src/components/admin/AdminConfigAssistant.test.tsx`.
- Initial Sage focused test passed: `LIBRARY_PATH=/opt/homebrew/opt/libpq/lib DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/opt/libpq/lib cargo test -p sage-core client_decrypted_context`.
- Final Sage web runtime tests passed: `LIBRARY_PATH=/opt/homebrew/opt/libpq/lib DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/opt/libpq/lib cargo test -p sage-core web_runtime::tests` passed: 89 tests.
- Backend DB safety/docs tests passed: `python3 -m unittest backend.tests.test_admin_db_query_endpoint backend.tests.test_sql_safety backend.tests.test_prototype_compatibility_docs` passed: 49 tests.
- Frontend build passed: `npm run build`. The build emitted the existing large Vite chunk warning. Generated `frontend/dist/index.html` changes were restored because generated assets are ignored in this worktree.
- Diff checks passed: `git diff --check && git -C runtime/sage diff --check`.
- Local CodeRabbit found two minor docs findings: clarify that the browser sends `client_decrypted_context`, and remove the local Python executable path from this ledger. Both were fixed.
- CodeRabbit rerun was stopped after a bounded wait while still heartbeating.
- Opened PR: https://github.com/enclave-free/enclave.free/pull/471. Added `@coderabbit full review` comment.
- Added the `0.2.0` minor release checkpoint on the PR branch: `VERSION`, frontend package files, backend version strings, and `CHANGELOG.md` now agree on `0.2.0`.

## Review Notes

- Standards axis: no blocking findings in manual review. The implementation preserves the Sage-owned Tool loop and keeps signer-decrypted plaintext out of traces.
- Spec axis: no blocking findings in manual review. The implementation matches the browser signer delegation boundary from #470.

## Open Questions

- None. The chosen boundary is browser signer delegation into encrypted inference, not backend private-key custody or backend decryption.

## Escalations

- None.
