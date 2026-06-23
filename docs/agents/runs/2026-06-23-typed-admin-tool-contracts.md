# Typed Admin Tool Contracts Feature Dev Run

## Run

- Run ID: 2026-06-23-typed-admin-tool-contracts
- Loop: Feature Dev
- Target repo: enclave-free/enclave.free-prototype
- Base branch: staging
- Feature branch: feature/typed-admin-tool-contracts
- Human owner: Austin
- Started: 2026-06-23
- Current status: PRD synthesis
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
- Local CodeRabbit report: Pending
- PR URL: Pending

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
| #419 Add typed Admin Config bootstrap proposal Tool | AFK | Pending | Pending | Pending | Pending |
| #420 Prefer typed bootstrap proposals in Admin Config conversations | AFK | Pending | Pending | Pending | Pending |
| #421 Benchmark typed Admin Config proposals against existing Tool Sets | AFK | Pending | Pending | Pending | Pending |

## Parked HITL Slices

| Issue | Why parked | Blocks | Required human action | Final PR decision |
| --- | --- | --- | --- | --- |
| None | | | | |

## Issue Session Ledger

| Issue | Fixed point | Worker session | Commit | Review result | Checks |
| --- | --- | --- | --- | --- | --- |
| Pending | Pending | Pending | Pending | Pending | Pending |

## Open Questions

- None.

## Escalations

- None.
