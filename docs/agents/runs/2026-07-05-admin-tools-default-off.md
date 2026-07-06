# Admin Tools Default Off Feature Dev Run

## Run

- Run ID: 2026-07-05-admin-tools-default-off
- Loop: plebdev-feature-dev
- Target repo: enclave-free/enclave.free
- Base branch: staging
- Base SHA: 2534c9565e85c6baa6bab2ae0e4a8e3168bc5227
- Feature branch: feature/admin-tools-default-off
- Human owner: plebdev
- Started: 2026-07-06T01:03:02Z
- Current status: Commit created, PR pending
- Skill setup status: Present. `AGENTS.md`, `docs/agents/issue-tracker.md`, `docs/agents/triage-labels.md`, and `docs/agents/domain.md` exist. Current remote truth is `enclave-free/enclave.free`; stale issue-tracker references to the previous repo name were corrected in this run.

## Goal

Config Tool should not be on by default for admins. No tools on by default. Do this on fresh in-sync staging as the first feature of the next minor release.

## Alignment

- Normal Admin Conversation surfaces should render Tool Set controls but start with no Tool Sets selected.
- Admins can explicitly enable Config, Knowledge, Resources, Web, or Database when a turn needs those tools.
- Guided first-run onboarding keeps its locked Config setup dependency because that path stages setup changes for Change Confirmation and is not a normal toggle default.
- No new glossary term or ADR is required; this tightens behavior at the existing Tool Set selection seam.

## Durable Artifacts

- CONTEXT updates: None.
- ADRs: None.
- PRD issue: #473
- Slice issues: #474
- Issue sessions: Current thread
- Agent briefs: None.
- Review packets: Local two-axis review completed in current thread; sub-agent review was not used because the available multi-agent tool requires an explicit user request for subagents.
- Local CodeRabbit report: `coderabbit review --agent --type all --base origin/staging -c AGENTS.md` completed with 0 findings.
- PR URL: Pending.

## Commands

- Install: `cd frontend && npm install` if dependencies are missing
- Typecheck: `cd frontend && npm run build`
- Test: `cd frontend && npm test -- --run src/pages/ChatPage.test.tsx src/components/admin/AdminConfigAssistant.test.tsx`
- Build: `cd frontend && npm run build`
- Visual verification: Not required unless the tests reveal a visible layout change.

## Slice Ledger

| Issue | Type | Status | Review thread | Fixes needed | Verified |
| --- | --- | --- | --- | --- | --- |
| #474 Start normal Admin Conversations with no Tool Sets selected | AFK | Implemented | Local review completed | None pending | Focused and full frontend checks passed |

## Parked HITL Slices

| Issue | Why parked | Blocks | Required human action | Final PR decision |
| --- | --- | --- | --- | --- |
| None | N/A | N/A | N/A | N/A |

## Issue Session Ledger

| Issue | Fixed point | Worker session | Commit | Review result | Checks |
| --- | --- | --- | --- | --- | --- |
| #474 | 2534c9565e85c6baa6bab2ae0e4a8e3168bc5227 | Current thread | feature branch HEAD | Pass after one fix | `npm test -- --run src/pages/ChatPage.test.tsx src/components/admin/AdminConfigAssistant.test.tsx`; `npm run build`; `npm test -- --run`; `git diff --check` |

## Review

- Standards review: Pass. Changes follow existing React state/test patterns and documented repo style.
- Spec review: Pass after one fix. The review found that unexpected structured Admin Config payloads could be staged while Config was off and later appear if Config was enabled. The UI now gates structured change-set staging behind the Config Tool Set, with regression coverage in both normal Admin Conversation surfaces.
- CodeRabbit local review: Pass, 0 findings.

## Verification

- `npm test -- --run src/pages/ChatPage.test.tsx src/components/admin/AdminConfigAssistant.test.tsx`: passed, 81 tests.
- `npm run build`: passed.
- `npm test -- --run`: passed, 370 tests across 71 files.
- `git diff --check`: passed.
- `coderabbit review --agent --type all --base origin/staging -c AGENTS.md`: passed, 0 findings.

## Open Questions

- None.

## Escalations

- None.
