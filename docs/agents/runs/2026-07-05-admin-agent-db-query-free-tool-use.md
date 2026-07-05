# Admin Agent DB Query Free Tool Use

## Run

- Run ID: 2026-07-05-admin-agent-db-query-free-tool-use
- Loop: plebdev-feature-dev
- Target repo: enclave-free/enclave.free
- Base branch: staging
- Feature branch: feature/admin-agent-db-query-free-tool-use
- Human owner: plebdev
- Started: 2026-07-05T21:36:45Z
- Current status: PR open against `staging`; local and GitHub checks passed.
- Skill setup status: Present. `AGENTS.md` and `docs/agents/{issue-tracker,triage-labels,domain}.md` exist.

## Goal

Let an approved Admin use the active `db-query` Tool Set naturally in the agent. Remove the artificial Sage-side barrier that withholds the executable database tool unless the Admin's message is already a direct SQL `SELECT`. Keep Python as the read-only safe SQL executor for validation, authorization, truncation, and redaction.

## Durable Artifacts

- CONTEXT updates: Not planned unless implementation resolves new durable terminology.
- ADRs: Not planned; this reverses an artificial guard while keeping the existing read-only executor boundary.
- PRD issue: Concrete bug report supplied directly in thread; no separate issue yet.
- Slice issues: Single AFK slice: remove natural-language `db-query` withholding and verify local behavior.
- Issue sessions: This run ledger.
- Agent briefs: None.
- Review packets: Manual two-axis code-review gate completed in-thread because sub-agent spawning is gated to explicit user delegation requests.
- Local CodeRabbit report: Clean after fixing one minor ledger portability finding.
- PR URL: https://github.com/enclave-free/enclave.free/pull/467

## Commands

- Install: Not needed yet.
- Typecheck: `cargo test -p sage-core web_runtime::tests` compiled the touched crate/tests.
- Test: Sage `web_runtime` tests, backend DB query/safety tests, docs compatibility tests, and focused frontend chat/admin assistant tests passed.
- Build: Pending if tests require.
- Visual verification: Not applicable unless UI changes appear.

## Slice Ledger

| Issue | Type | Status | Review thread | Fixes needed | Verified |
| --- | --- | --- | --- | --- | --- |
| Remove natural-language `db-query` withholding | AFK | Fixed locally | Manual two-axis review | None | Yes |

## Parked HITL Slices

| Issue | Why parked | Blocks | Required human action | Final PR decision |
| --- | --- | --- | --- | --- |
| None |  |  |  |  |

## Issue Session Ledger

| Issue | Fixed point | Worker session | Commit | Review result | Checks |
| --- | --- | --- | --- | --- | --- |
| Remove natural-language `db-query` withholding | 82f991bf5c3f502e9870c533b27b1d3410d9e3a5 | Current Codex thread | Sage `869720a`; parent pending | No blocking findings | `cargo test -p sage-core web_runtime::tests`; Python unittest DB safety/docs; frontend Vitest focused suite |

## Verification Log

- Reproduced the refusal in code: `build_conversation_tool_registry` withheld `db_query` for Admin `db-query` turns unless the message started with `SELECT`, and tests asserted `direct_select_required`.
- Fixed Sage to register `db_query` whenever an approved Admin enables the `db-query` Tool Set.
- Kept Python as the safety boundary: `POST /internal/agent/admin-db-query` and `/admin/db/query` still validate SELECT-only SQL, blocked keywords, allowlisted tables, truncation, and redaction.
- `LIBRARY_PATH=/opt/homebrew/opt/libpq/lib DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/opt/libpq/lib cargo test -p sage-core database_tool` passed.
- `LIBRARY_PATH=/opt/homebrew/opt/libpq/lib DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/opt/libpq/lib cargo test -p sage-core selected_tool_sets_expand_to_model_callable_tool_contracts` passed.
- `LIBRARY_PATH=/opt/homebrew/opt/libpq/lib DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/opt/libpq/lib cargo test -p sage-core web_runtime::tests` passed: 86 tests.
- `<bundled-python> -m unittest backend.tests.test_admin_db_query_endpoint backend.tests.test_sql_safety` passed: 16 tests.
- `<bundled-python> -m unittest backend.tests.test_prototype_compatibility_docs` passed: 33 tests.
- `npm test -- --run src/utils/llmChat.test.ts src/components/admin/AdminConfigAssistant.test.tsx` passed: 47 tests.
- Local Docker smoke was not run: this worktree has no `.env`, and the local Docker daemon was not available. No local data reset was attempted.
- `coderabbit review --agent --type all --base staging` reported one minor finding about a machine-specific Python path in this ledger; fixed.
- `coderabbit review --agent --type all --base staging` rerun passed with 0 findings.
- PR #467 GitHub checks passed: Backend security regression, Frontend security regression, Demo handoff PDF drift, Dependency and SAST, Semgrep OSS, and CodeRabbit status.

## Review Notes

- Standards axis: no blocking findings. The change removes pre-model branching in the existing tool registry and keeps executor rejection tracing in the established `guarded` path.
- Spec axis: no blocking findings. The implementation matches the user request by removing the artificial natural-language DB gate while retaining read-only SQL enforcement in Python.

## Open Questions

- None. User explicitly wants the Admin-selected `db-query` Tool Set to be available freely while active, with read-only safety enforced by the database executor.

## Escalations

- None.
