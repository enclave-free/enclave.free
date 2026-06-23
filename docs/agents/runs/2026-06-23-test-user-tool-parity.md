# Test User Tool Parity Feature Dev Run

## Run

- Run ID: 2026-06-23-test-user-tool-parity
- Loop: Feature Dev
- Target repo: enclave-free/enclave.free-prototype
- Base branch: staging
- Feature branch: feature/test-user-tool-parity
- Human owner: Austin
- Started: 2026-06-23
- Current status: Implementation verified; PR pending
- Skill setup status: Present. Repo has AGENTS.md, docs/agents/issue-tracker.md, docs/agents/triage-labels.md, and docs/agents/domain.md.

## Goal

Remediate the Admin Test & Feedback "Test as User" path so an admin-run test user session exercises the same user-authorized Tool Sets, Sage tool loop, trace evidence, and saved feedback path that a real signed-in User Conversation uses.

## Source Artifacts

- plebdev-loops/workflows/feature-dev/orchestrator-prompt.md
- plebdev-loops/workflows/feature-dev/loop.yaml
- plebdev-loops/docs/loops/feature-dev.md
- plebdev-loops/docs/reference/matt-pocock-skills-pipeline.md
- plebdev-loops/docs/reference/loop-handoffs.md
- docs/tools.md
- docs/adr/0020-use-assistant-ui-for-conversation-ui-surface.md
- docs/adr/0023-unified-model-driven-tool-loop.md
- docs/adr/0024-transparent-reasoning-and-tool-trace-posture.md
- CONTEXT.md

## Durable Artifacts

- CONTEXT updates: Not needed yet; existing Conversation, Tool Set, Tool, Conversation Trace, User Conversation, and Conversation UI Surface terms cover this change.
- ADRs: Not needed; this implements ADR-0023/0024/0020 parity rather than introducing a new hard-to-reverse decision.
- PRD issue: https://github.com/enclave-free/enclave.free-prototype/issues/435
- Slice issues: #436, #437
- Issue sessions: Orchestrator implemented #436 and #437 together because the request payload and saved transcript shape share one Test-as-User seam.
- Agent briefs: Pending
- Review packets: Local standards/spec fallback review completed.
- Local CodeRabbit report: `coderabbit review --agent --type all --base staging` attempted and blocked by CodeRabbit org rate limit (`waitTime`: 14 minutes 19 seconds). Fallback review used.
- PR URL: Pending

## Commands

- Install: `cd frontend && npm install`
- Typecheck: `cd frontend && npm run build`
- Test: `cd frontend && npm run test`; targeted frontend tests first; Sage/backend tests if request or trace contracts change
- Build: `docker compose --env-file .env -p enclavefree-prototype -f docker-compose.infra.yml -f docker-compose.app.yml up --build -d`
- Visual verification: Test & Feedback at `http://127.0.0.1:5173/admin/test-and-feedback`; gateway health at `http://127.0.0.1:18000/health`

## Alignment Decisions

- Test-as-User should be a real non-admin User Conversation exercise, not a stripped-down no-tool chat shim.
- The test session should inherit normal user Tool Set defaults: `curated-resources` default-on, `knowledge-search` when default documents exist, and `web-search` when enabled for the selected User Type.
- Admin-only Tool Sets (`admin-config`, `db-query`) must remain unavailable while impersonating the test User.
- Tool use should be visible enough for admin feedback: the active test conversation and saved transcript should preserve assistant turn trace/tool metadata returned by Sage.
- Selected Documents remain Knowledge Search Tool constraints, not hidden prompt context.

## Slice Ledger

| Issue | Type | Status | Review thread | Fixes needed | Verified |
| --- | --- | --- | --- | --- | --- |
| #436 Enable real user Tool Set defaults in Test-as-User sessions | AFK | Implemented | Orchestrator | None | Yes |
| #437 Preserve Test-as-User Conversation Trace in feedback logs | AFK | Implemented | Orchestrator | None | Yes |

## Parked HITL Slices

| Issue | Why parked | Blocks | Required human action | Final PR decision |
| --- | --- | --- | --- | --- |
| None | | | | |

## Issue Session Ledger

| Issue | Fixed point | Worker session | Commit | Review result | Checks |
| --- | --- | --- | --- | --- | --- |
| #436 | staging | Orchestrator | Pending | Fallback review pass: no standards/spec findings | `npm run test -- TestAsUserView.test.tsx`; `npm run build`; `npm run test`; `git diff --check` |
| #437 | staging | Orchestrator | Pending | Fallback review pass: no standards/spec findings | `npm run test -- FeedbackView.test.tsx`; direct `SessionLogSaveTranscript` schema preservation check; `npm run build`; `npm run test`; `git diff --check` |

## Verification Evidence

- `cd frontend && npm run test -- TestAsUserView.test.tsx` passed: 1 file, 8 tests.
- `cd frontend && npm run test -- FeedbackView.test.tsx` passed: 1 file, 5 tests.
- `PYTHONPATH=backend/app python3 - <<'PY' ... SessionLogSaveTranscript ... PY` passed with `ok`, proving trace/tool metadata survives model validation.
- `cd frontend && npm run build` passed. Vite emitted existing chunk-size warnings only.
- `cd frontend && npm run test` passed: 66 files, 327 tests. Output includes the existing `App.routing.test.tsx` intentional error-path console noise.
- `git diff --check` passed.
- Host backend unittest for `backend.tests.test_session_logs.SessionLogsTest.test_session_log_save_payload_preserves_trace_and_tool_metadata` was not runnable because host Python is missing `coincurve`; the app container also did not include the `tests` module. The direct Pydantic schema check above covered the touched backend contract.

## Review Evidence

- Standards review against `AGENTS.md`, `CLAUDE.md`, `CONTEXT.md`, ADR-0023, ADR-0024, and ADR-0013 found no blocking findings. The change keeps Tool Set selection in the frontend and Tool execution/trace generation in Sage, preserves the synthetic User bearer-token boundary, and does not introduce admin-only Tool Sets.
- Spec review against PRD #435 and slice issues #436/#437 found no blocking findings. Covered: session defaults by User Type, `curated-resources` default, `knowledge-search` when default documents exist, `web-search` when enabled, `job_ids` constraints, synthetic bearer token, trace/tool metadata preservation, feedback rendering, and regression tests.
- CodeRabbit CLI review was attempted but rate-limited before analysis; no CodeRabbit findings were returned.

## Open Questions

- None. Recommended answer adopted: Test-as-User should mirror real non-admin user defaults and surface trace evidence, because ADR-0023 makes selected Tool Sets the user-facing control and ADR-0024 makes tool trace visible in the transparent prototype phase.

## Escalations

- None.
