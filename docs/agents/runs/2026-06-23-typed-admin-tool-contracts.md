# Typed Admin Tool Contracts Feature Dev Run

## Run

- Run ID: 2026-06-23-typed-admin-tool-contracts
- Loop: Feature Dev
- Target repo: enclave-free/enclave.free-prototype
- Base branch: staging
- Feature branch: feature/typed-admin-tool-contracts
- Human owner: Austin
- Started: 2026-06-23
- Current status: PR open
- Skill setup status: Present. Repo has AGENTS.md, docs/agents/issue-tracker.md, docs/agents/triage-labels.md, and docs/agents/domain.md.

## Goal

Replace brittle, slow, free-form Admin Config proposal JSON generation with strict typed Tool contracts backed by deterministic proposal builders, so Sage models express product intent while code owns canonical control-plane change sets, validation, and Change Confirmation.

## Source Artifacts

- plebdev-loops/workflows/feature-dev/orchestrator-prompt.md
- plebdev-loops/workflows/feature-dev/loop.yaml
- plebdev-loops/docs/loops/feature-dev.md
- plebdev-loops/docs/reference/matt-pocock-skills-pipeline.md
- plebdev-loops/docs/reference/loop-handoffs.md
- docs/adr/0004-admin-conversations-can-apply-confirmed-control-plane-changes.md
- docs/adr/0023-unified-model-driven-tool-loop.md
- docs/adr/0025-typed-admin-config-proposal-tools.md
- docs/admin-config-assistant.md

## Durable Artifacts

- CONTEXT updates: Typed Proposal Tool
- ADRs: docs/adr/0025-typed-admin-config-proposal-tools.md
- PRD issue: https://github.com/enclave-free/enclave.free-prototype/issues/418
- Slice issues: #419, #420, #421
- Issue sessions: Pending
- Agent briefs: Pending
- Review packets: Pending
- Local CodeRabbit report: initial all-diff review raised 5 minor issues; fixed 4 in-scope issues and skipped 1 unrelated untracked file note for `docs/apple-container-sidecar.md`; committed-diff rerun raised 0 issues
- PR URL: https://github.com/enclave-free/enclave.free-prototype/pull/422

## Commands

- Install: `cd frontend && npm install`
- Typecheck: `cd frontend && npm run build`
- Test: `cd frontend && npm run test`; backend/Sage targeted tests to be selected after slicing
- Build: `docker compose --env-file .env -p enclavefree-prototype -f docker-compose.infra.yml -f docker-compose.app.yml up --build -d`
- Visual verification: local admin chat/config assistant smoke through `http://127.0.0.1:5173`; API smoke through `http://127.0.0.1:18000/health` and `/llm/test`

## Alignment Decisions

- Scope Admin Config write/proposal Tools first.
- Leave DB Query, Web Search, Knowledge Search, Curated Resources, and Admin Config read Tools unchanged unless benchmark coverage proves they share the same typed-contract problem.
- Keep Change Confirmation and the existing Apply panel as the control boundary.
- Let models express product-level write intent; deterministic code builds canonical Enclave Control Plane request shapes.

## Slice Ledger

| Issue | Type | Status | Review thread | Fixes needed | Verified |
| --- | --- | --- | --- | --- | --- |
| #419 Add typed Admin Config bootstrap proposal Tool | AFK | Complete | Gauss + Meitner | Fixed stale docs, removed nested JSON typed fields, added onboarding question support, added validation tests | `cargo fmt --all`; `LIBRARY_PATH=/opt/homebrew/opt/libpq/lib DYLD_LIBRARY_PATH=/opt/homebrew/opt/libpq/lib cargo test -p sage-core admin_config_bootstrap --lib`; `LIBRARY_PATH=/opt/homebrew/opt/libpq/lib DYLD_LIBRARY_PATH=/opt/homebrew/opt/libpq/lib cargo test -p sage-core selected_tool_sets_expand_to_model_callable_tool_contracts --lib`; `git diff --check`; `git -C runtime/sage diff --check` |
| #420 Prefer typed bootstrap proposals in Admin Config conversations | AFK | Complete | Self-review | Updated default prompt rules, retired obsolete generic-write defaults during merge, and aligned docs | `cargo fmt --all`; `LIBRARY_PATH=/opt/homebrew/opt/libpq/lib DYLD_LIBRARY_PATH=/opt/homebrew/opt/libpq/lib cargo test -p sage-core prompt_rules --lib`; `LIBRARY_PATH=/opt/homebrew/opt/libpq/lib DYLD_LIBRARY_PATH=/opt/homebrew/opt/libpq/lib cargo test -p sage-core selected_tool_sets_expand_to_model_callable_tool_contracts --lib`; `git diff --check`; `git -C runtime/sage diff --check` |
| #421 Benchmark typed Admin Config proposals against existing Tool Sets | AFK | Complete | Self-review | Expanded bootstrap scenario to require typed tool evidence, onboarding fields, behavior rules, and generic-tool fallback warning | `python3 -m unittest scripts.benches.test_conversation_model_bench`; `git diff --check` |

## Parked HITL Slices

| Issue | Why parked | Blocks | Required human action | Final PR decision |
| --- | --- | --- | --- | --- |
| None | | | | |

## Issue Session Ledger

| Issue | Fixed point | Worker session | Commit | Review result | Checks |
| --- | --- | --- | --- | --- | --- |
| #419 | ba8d46f | Hume (019ef4df-a342-7f41-ab94-ce6bba5ed356) + orchestrator follow-up | parent c102871, Sage cad2309 | Standards doc drift fixed; spec review gaps fixed except prompt preference deferred to #420 | 10 bootstrap tests passed; Tool Set exposure test passed; diff checks clean |
| #420 | 48d6f0a | Orchestrator | Pending | Default rules now prefer `propose_admin_config_bootstrap`; stale exact defaults are removed on merge; docs aligned | 4 prompt-rule tests passed; Tool Set exposure test passed; diff checks clean |
| #421 | 6c0f175 | Orchestrator | parent acbd509 plus Sage follow-ups 2693d6a and 237d63f | Bench now fails bootstrap if typed proposal Tool is not used and checks onboarding/user-field plus behavior-rule requests; live Gemma run exposed and fixed plain-language access-policy normalization | 29 benchmark unittest cases passed; focused live `admin_config_bootstrap` passed on `gemma4-31b` with artifact `/tmp/conversation-model-bench-typed-admin-bootstrap-2026-06-23-rerun2.json` |

## Live Verification Notes

- Rebuilt local `sage` service with `docker compose -f docker-compose.infra.yml -f docker-compose.app.yml up -d --build sage`.
- Health passed at `http://127.0.0.1:18000/health`.
- Focused live command: `python3 scripts/benches/conversation_model_bench.py --api-base http://127.0.0.1:18000 --scenario admin_config_bootstrap --timeout 300 --output /tmp/conversation-model-bench-typed-admin-bootstrap-2026-06-23-rerun2.json`.
- Result: passed on `gemma4-31b`; typed bootstrap Tool used; generic change-set Tool not used; staged request paths were `/admin/settings`, two `/admin/user-types`, two `/admin/user-fields`, and `/admin/ai-config/prompt_rules`; completion was about 14.3s.

## Open Questions

- None.

## Escalations

- None.
