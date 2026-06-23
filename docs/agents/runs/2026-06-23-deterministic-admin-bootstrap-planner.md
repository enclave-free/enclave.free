# Deterministic Admin Bootstrap Planner

## Run

- Run ID: 2026-06-23T16-16-26Z
- Loop: feature-dev
- Target repo: enclave-free/enclave.free-prototype
- Base branch: staging
- Feature branch: feature/deterministic-admin-bootstrap-planner
- Human owner: Austin
- Started: 2026-06-23T16-16-26Z
- Current status: prototype and Sage PRs opened; PR-side CodeRabbit requested
- Skill setup status: present; `AGENTS.md`, `CONTEXT.md`, and `docs/agents/*` exist

## Goal

Hard-cut the slow Kimi Admin Config bootstrap flow by moving exact bootstrap change-set construction into Sage deterministic code. Kimi should identify and call a high-level Admin Config proposal tool; Sage should normalize/build the canonical reviewable change set from the current Admin message and avoid extra model calls once a proposal succeeds.

## Durable Artifacts

- CONTEXT updates: none planned unless new glossary term is needed
- ADRs: ADR-0025 updated
- PRD issue: #423
- Slice issues: #424, #425, #426
- Issue sessions: local orchestrator implementation
- Agent briefs: issue bodies #424, #425, #426
- Review packets: Sage PR enclave-free/sage#19; prototype PR enclave-free/enclave.free-prototype#427
- Local CodeRabbit report: parent review had one unrelated untracked-doc finding skipped; Sage rerun passed with zero findings
- PR URL: https://github.com/enclave-free/enclave.free-prototype/pull/427
- Sage PR URL: https://github.com/enclave-free/sage/pull/19

## Commands

- Install: existing local Docker/Cargo/npm setup
- Typecheck: `cargo fmt --all`; parent and Sage `git diff --check`
- Test: full Sage core library tests and backend Agent Settings unittest passed
- Build: `docker compose --env-file .env -f docker-compose.infra.yml -f docker-compose.app.yml up -d --build sage`
- Visual verification: focused `conversation_model_bench.py` Kimi admin bootstrap passed

## Slice Ledger

| Issue | Type | Status | Review thread | Fixes needed | Verified |
| --- | --- | --- | --- | --- | --- |
| #423 | PRD | Published | n/a | n/a | Pending PR |
| #424 | AFK | Implemented locally | Sage CodeRabbit clean | Fixed fallback injection finding | Full Sage tests passed |
| #425 | AFK | Implemented locally | Sage CodeRabbit clean | Fixed canonical-message finding | Full Sage tests passed |
| #426 | AFK | Benchmark passed locally | Sage CodeRabbit clean | n/a | Kimi focused benchmark passed |

## Parked HITL Slices

| Issue | Why parked | Blocks | Required human action | Final PR decision |
| --- | --- | --- | --- | --- |
| None | n/a | n/a | n/a | n/a |

## Issue Session Ledger

| Issue | Fixed point | Worker session | Commit | Review result | Checks |
| --- | --- | --- | --- | --- | --- |
| #424 | origin/staging | current thread | Sage `dde99a1`, prototype `6fa5ef2` | Sage CodeRabbit passed | `cargo test -p sage-core --lib` |
| #425 | origin/staging | current thread | Sage `dde99a1`, prototype `6fa5ef2` | Sage CodeRabbit passed | `cargo test -p sage-core --lib` |
| #426 | origin/staging | current thread | Sage `dde99a1`, prototype `6fa5ef2` | Sage CodeRabbit passed | Local Docker rebuild + Kimi benchmark |

## Open Questions

- None. Proceed with a model-called high-level Admin Config bootstrap planner tool, not a hidden route pre-classifier, to stay aligned with ADR-0023 and ADR-0025.

## Escalations

- None.

## Evidence

- Full Sage tests passed: `LIBRARY_PATH=/opt/homebrew/opt/libpq/lib DYLD_LIBRARY_PATH=/opt/homebrew/opt/libpq/lib cargo test -p sage-core --lib` (`98 passed`).
- Backend Agent Settings default test passed: `python3 -m unittest backend.tests.test_ai_config_defaults`.
- Local rebuilt Sage health passed: `curl -fsS http://127.0.0.1:18000/health`.
- Live focused Kimi benchmarks passed:
  - Baseline before this feature: `/tmp/conversation-model-bench-kimi-admin-bootstrap-after-2026-06-23.json` at `66.1s done / 65.9s first answer`, with four Admin Config read tools before the proposal.
  - Best pre-review post-fix run: `/tmp/conversation-model-bench-kimi-admin-bootstrap-fallback-notes-2026-06-23.json` at `20.7s done / 20.5s first answer`, using only `propose_admin_config_bootstrap`.
  - Final reviewed rebuilt-service run: `/tmp/conversation-model-bench-kimi-admin-bootstrap-reviewed-2026-06-23.json` at `5.1s done / 4.9s first answer`, zero warnings, using only `propose_admin_config_bootstrap`.
- All post-fix benchmark runs staged the same six canonical Admin Config requests: settings, two user types, two onboarding fields, and prompt rules.
- Parent local CodeRabbit finding skipped: `docs/apple-container-sidecar.md` is an unrelated untracked local file and is not part of this branch.
- Sage local CodeRabbit rerun passed with zero findings after fixing fallback setup-note injection and canonical proposal-message handling.
