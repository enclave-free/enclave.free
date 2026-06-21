# Goal Ledger: Admin Config Agent Settings Apply

## Run

- Run ID: 2026-06-21-admin-config-agent-settings-apply
- Loop: Feature Dev
- Target repo: enclave-free/enclave.free-prototype
- Base branch: jc/dev, per user request to branch off the current PR branch
- Feature branch: feature/admin-config-agent-settings-apply
- Human owner: Austin
- Started: 2026-06-21T17:03:32Z
- Current status: implementation and verification complete for #402/#403/#404; follow-up #406 implemented locally, CodeRabbit clean, and awaiting commit/push.
- Skill setup status: present; repo has AGENTS.md plus docs/agents issue tracker, triage labels, and domain docs.

## Goal

Fix the Admin Configuration Assistant failure where a behavior-rule request is treated as if it staged changes for Apply, while the actual proposal was rejected because `prompt_rules` was sent as an Instance Setting instead of an Agent Setting.

## Durable Artifacts

- CONTEXT updates: not needed yet; existing glossary already has Agent Settings, Instance Settings, Admin Config, and Change Confirmation.
- ADRs: not needed yet; existing ADR-0004 and ADR-0023 already define the boundary.
- PRD issue: #401
- Slice issues: #402, #403, #404, #406
- Issue sessions: current orchestrator thread implemented #402/#403/#404 and follow-up #406.
- Agent briefs: GitHub issues #402, #403, #404, and #406.
- Review packets: self-review against #401-#404 completed in current orchestrator thread; CodeRabbit follow-up docs/tests for `prompt_forbidden` and scoped `prompt_rules` covered; #406 self-review and CodeRabbit clean.
- Local CodeRabbit report: passed; `coderabbit review --agent --type all --base jc/dev` completed with 0 findings before push.
- PR URL: https://github.com/enclave-free/enclave.free-prototype/pull/405

## Commands

- Install: `cd frontend && npm install`; Sage runtime through Docker Compose.
- Typecheck: `cd frontend && npm run build`; `cd runtime/sage && cargo check -p sage-core --bin enclave_web`.
- Test: `cd frontend && npm test`; `COMPOSE_PROJECT_NAME=enclavefree-prototype LLM_API_KEY=test npm test`; `LIBRARY_PATH=/opt/homebrew/opt/libpq/lib cargo test -p sage-core --lib`; targeted admin assistant Vitest suites; targeted Sage proposal/settings tests when `libpq` is linkable.
- Build: `docker compose -p enclavefree-prototype -f docker-compose.infra.yml -f docker-compose.app.yml up --build -d`.
- Visual verification: local Chromium at `http://localhost:5173/admin/setup` with Admin Configuration Assistant sidebar.

## Slice Ledger

| Issue                                                                | Type | Status      | Review thread | Fixes needed | Verified                                                                                                                                                         |
| -------------------------------------------------------------------- | ---- | ----------- | ------------- | ------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| #402 Stage Agent Settings behavior-rule changes from Admin Config    | AFK  | implemented | self-review   | none         | Sage unit tests, frontend change-set tests, docs updated                                                                                                         |
| #403 Stop false Apply handoffs after rejected Admin Config proposals | AFK  | implemented | self-review   | none         | Sage unit tests, frontend no-pending tests, Chromium no-pending smoke                                                                                            |
| #404 Smoke test Admin Config behavior-rule Apply end to end          | AFK  | implemented | self-review   | none         | Compose `/test` and `/llm/test` pass; browser smoke shows pending Apply panel for `PUT /admin/ai-config/prompt_rules`; direct Agent Settings apply path verified |
| #406 Keep Admin Config Agent Settings reads and Apply memory consistent | AFK | implemented | CodeRabbit | none | Sage `read_agent_settings` now sources Sage-owned Agent Settings; Apply summaries bridge into session-backed turns; successful Admin Config tool calls persist sanitized context |

## Parked HITL Slices

| Issue | Why parked | Blocks | Required human action | Final PR decision |
| ----- | ---------- | ------ | --------------------- | ----------------- |
| None  | n/a        | n/a    | n/a                   | n/a               |

## Issue Session Ledger

| Issue | Fixed point                              | Worker session              | Commit                                      | Review result | Checks                                                                                                              |
| ----- | ---------------------------------------- | --------------------------- | ------------------------------------------- | ------------- | ------------------------------------------------------------------------------------------------------------------- |
| #402  | 883c34f42b57cb384d9ecff8381d0e2459bdbcbb | current orchestrator thread | current parent feature commit; Sage 12e1b41 | pass          | `cargo test -p sage-core --lib`; focused Vitest; Prettier; frontend build                                           |
| #403  | 883c34f42b57cb384d9ecff8381d0e2459bdbcbb | current orchestrator thread | current parent feature commit; Sage 12e1b41 | pass          | `cargo test -p sage-core --lib`; focused Vitest; Chromium no-pending smoke                                          |
| #404  | 883c34f42b57cb384d9ecff8381d0e2459bdbcbb | current orchestrator thread | current parent feature commit; Sage 12e1b41 | pass          | `/test` pass; `/llm/test` pass; Chromium sidebar smoke shows Apply panel for model-generated behavior-rule proposal |
| #406  | 6b6d73505dfd9d55a2d051eb69ad1730ebda0572 | current orchestrator thread | current parent feature commit; Sage 4b39e74 | pass | `LIBRARY_PATH=/opt/homebrew/opt/libpq/lib cargo test -p sage-core --lib`; `npm test -- src/utils/llmChat.test.ts`; `npm run build`; `COMPOSE_PROJECT_NAME=enclavefree-prototype LLM_API_KEY=test npm test` |

## Open Questions

- None.

## Escalations

- None.
