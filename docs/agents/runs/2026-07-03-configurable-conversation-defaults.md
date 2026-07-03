# Configurable Conversation Defaults Run Ledger

## Run

- Run ID: 2026-07-03-configurable-conversation-defaults
- Loop: Feature Dev
- Target repo: `/Users/plebdev/Desktop/Projects/enclave-free/enclave.free-configurable-conversation-defaults`
- Base branch: `staging`
- Feature branch: `feature/configurable-conversation-defaults`
- Human owner: Austin
- Started: 2026-07-03T18:34:13Z
- Current status: implementation verified locally; PR open
- Skill setup status: present (`AGENTS.md`, `docs/agents/issue-tracker.md`, `docs/agents/triage-labels.md`, `docs/agents/domain.md`)

## Goal

Change User Conversations so user-facing chats show no Tool controls by default, while Admins can configure which Tool Sets are default-active and which Knowledge Source scope is active for user sessions.

## Alignment

- User Conversations should have a clean composer by default: no visible Tool Set buttons and no visible Knowledge document selector.
- Admin Conversations keep visible admin Tool Set controls; `admin-config` remains default-active for admin configuration conversations.
- Operator-configured defaults still drive which Tool Sets Sage may use for User Conversations.
- Knowledge Source defaults are explicit:
  - `none`: no Knowledge Search Tool Set by default.
  - `selected`: Knowledge Search is default-active with configured default Document IDs.
  - `all`: Knowledge Search is default-active without `job_ids`, so Sage may search all Documents available to that User Type.
- If session defaults cannot be loaded, User Conversations fall back to no Tool Sets and no Knowledge Sources rather than silently enabling tools.
- Sage must enforce the server-side default Tool Set policy for non-admins instead of trusting user-submitted Tool IDs.

## Durable Artifacts

- CONTEXT updates: none expected unless terminology changes during implementation
- ADRs: `docs/adr/0026-configurable-conversation-defaults.md`
- PRD issue: https://github.com/enclave-free/enclave.free/issues/458
- Slice issues:
  - https://github.com/enclave-free/enclave.free/issues/459
  - https://github.com/enclave-free/enclave.free/issues/460
  - https://github.com/enclave-free/enclave.free/issues/461
- Issue sessions: current orchestrator thread
- Agent briefs: current orchestrator thread
- Review packets: self-review complete
- Local CodeRabbit report: ran locally; first pass raised 2 major issues, both fixed; second pass raised 0 issues
- PR URL: https://github.com/enclave-free/enclave.free/pull/462
- Sage support PR: https://github.com/enclave-free/sage/pull/25

## Commands

- Install: `cd frontend && npm ci`; backend dependencies installed from `backend/requirements.txt` in the bundled Python runtime for local tests
- Typecheck: `cd frontend && npm run build -- --outDir /tmp/enclave-build-config-defaults --emptyOutDir`; `cd runtime/sage && cargo check -p sage-core --bin enclave_web`
- Test: `cd frontend && npm run test -- ChatPage.test.tsx TestAsUserView.test.tsx AdminAIConfig.test.tsx`; backend targeted `python3 -m unittest backend.tests.test_ai_config_max_tokens backend.tests.test_ai_config_defaults`; Sage compile check `cargo check -p sage-core --bin enclave_web`
- Build: `cd frontend && npm run build -- --outDir /tmp/enclave-build-config-defaults --emptyOutDir`
- Visual verification: covered by RTL checks for hidden user controls plus production build; no browser stack smoke run in this local pass

## Slice Ledger

| Issue | Type | Status | Review thread | Fixes needed | Verified |
| --- | --- | --- | --- | --- | --- |
| #459 Add configurable User Conversation default policy | AFK | implemented | current thread | none known | targeted tests + Sage check |
| #460 Hide user chat Tool controls and consume default policy | AFK | implemented | current thread | none known | targeted tests + frontend build |
| #461 Expose Conversation default settings to Admins and update docs | AFK | implemented | current thread | none known | targeted tests + docs |

## Parked HITL Slices

| Issue | Why parked | Blocks | Required human action | Final PR decision |
| --- | --- | --- | --- | --- |
| None | | | | |

## Issue Session Ledger

| Issue | Fixed point | Worker session | Commit | Review result | Checks |
| --- | --- | --- | --- | --- | --- |
| #459 | `986e88c` | current orchestrator thread | Sage `ffe7336`, parent PR commit | self-review complete | frontend/backend/Sage targeted |
| #460 | `986e88c` | current orchestrator thread | Sage `ffe7336`, parent PR commit | self-review complete | frontend targeted/build |
| #461 | `986e88c` | current orchestrator thread | Sage `ffe7336`, parent PR commit | self-review complete | frontend targeted/docs |

## Verification Log

- `python3 -m unittest backend.tests.test_ai_config_max_tokens backend.tests.test_ai_config_defaults` using bundled Python after installing `backend/requirements.txt`: passed, 10 tests.
- `cd frontend && npm test -- ChatPage.test.tsx TestAsUserView.test.tsx AdminAIConfig.test.tsx`: passed, 66 tests after CodeRabbit follow-up.
- `cd frontend && npm run build -- --outDir /tmp/enclave-build-config-defaults --emptyOutDir`: passed; existing large-chunk warning only.
- `cd runtime/sage && cargo check -p sage-core --bin enclave_web`: passed.
- `cd runtime/sage && cargo test -p sage-core --bin enclave_web user_conversation_default_policy_applies_tool_and_knowledge_scope`: blocked locally by missing `libpq` linker library; `cargo check` passed.
- `coderabbit review --agent --type all --base staging`: first pass raised 2 major issues (`TestAsUserView` Knowledge Source scope handling and docs authority wording); both addressed.
- `coderabbit review --agent --type all --base staging`: second pass passed with 0 issues.

## Open Questions

- None. The feature scope is inferred from the user's explicit request and previous codebase scoping.

## Escalations

- None.
