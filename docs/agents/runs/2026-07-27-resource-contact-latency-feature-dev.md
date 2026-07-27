# Reliable Curated Resource Contact Lookup and Latency — Feature Dev Ledger

## Run

- Run ID: `2026-07-27-resource-contact-latency`
- Loop: `plebdev-feature-dev` v0.4.0
- Target repo: `enclave-free/enclave.free` with the `enclave-free/sage` runtime submodule
- Base branch: `staging` (`origin/staging` at `0abc518` when the run began)
- Feature branch: `feature/resource-contact-latency`
- Human owner: plebdev
- Started: 2026-07-27
- Current status: Awaiting approval of tracer-bullet ticket granularity and blocking edges
- Skill setup status: Complete; GitHub issue tracking, triage labels, and multi-context domain docs are configured

## Goal

Implement the accepted quick follow-on fixes end to end: make contact-detail
follow-ups perform a fresh Curated Resources lookup, improve exact and hybrid
contact matching, disclose bounded Resource Tool results so Sage cannot overclaim
completeness, expose Tool-selection and latency evidence, and add conservative
timeouts and retries for read-only Curated Resources and Knowledge Search calls.

## Durable Artifacts

- CONTEXT updates: `CONTEXT.md` defines Curated Resource, Resource Directory, and Tool Selection Observation
- ADRs: None; the accepted design applies ADR-0023, ADR-0024, and ADR-0027 without changing their boundaries
- Prototype source branch, if any: None; existing public seams and contracts were sufficient
- Spec issue: https://github.com/enclave-free/enclave.free/issues/533
- Tickets: Proposed; awaiting human approval before publication
- Ticket sessions: Pending
- Agent briefs: Pending ticket publication
- Review packets: Pending implementation
- Local CodeRabbit report: Pending implementation
- PR URL: Pending

## Commands

- Install: `python3 -m pip install -r backend/requirements.txt`; `cd runtime/sage && cargo fetch`; `cd frontend && npm ci`
- Typecheck: `cd runtime/sage && cargo check -p sage-core --bin enclave_web`; `cd frontend && npm run build`
- Test: `python3 -m unittest discover -s backend/tests -p 'test_*.py'`; `cd runtime/sage && LIBRARY_PATH=/opt/homebrew/opt/libpq/lib DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/opt/libpq/lib cargo test -p sage-core --lib`; `cd frontend && npm test`
- Build: `cd frontend && npm run build`; Compose build/smoke only when integration verification requires it
- Visual verification: focused Conversation Activity component tests followed by local browser inspection of Activity rows when the stack is available

## Proposed Ticket Graph

1. **Find precise Curated Resources with honest bounded results** — no blockers.
   Deliver exact and hybrid organization/contact matching, offset continuation,
   total/page metadata, Resource Tool warnings, and completeness-safe final-answer
   instructions through the Resource Directory and Sage Tool contract.
2. **Ground contact follow-ups in a fresh Curated Resources call** — blocked by 1.
   Deliver the model-planning and final-answer policy for email, phone, website,
   address, secure channel, and equivalent English/Spanish follow-ups while
   preserving the enabled Tool Set boundary.
3. **Show why Curated Resources was selected or missed** — blocked by 2.
   Deliver content-free Tool Selection Observations from planning through Trace,
   Activity, and structured logs, including selected, attempted, terminal, and
   expected-but-missed states without exposing prompts or contact values.
4. **Bound and retry read-only lookup failures** — blocked by 3.
   Deliver conservative timeout/retry policies for Curated Resources and
   Knowledge Search with visible retry, timeout, and terminal evidence; writes
   remain unretried.
5. **Attribute Conversation latency to its real phases** — blocked by 3 and 4.
   Deliver separate planning, final inference, provider header/first-event proxy,
   Resource Directory, Retrieval, Tool, retry-delay, and total-turn timing in
   Trace, Activity, and privacy-safe structured logs.
6. **Prove the reported customer journeys across User Types** — blocked by 1–5.
   Deliver public Conversation/Resource contract regression coverage and replay
   the affected contact and bounded-inventory prompts across the relevant User
   Types, followed by the full backend, Sage, and frontend verification gates.

All six proposed tickets are AFK. Their validation is agent-performable with the
existing local test seams and already-authorized development tooling. Production
deployment, live customer data, WLC-specific ranking, missing Bitcoin content,
provider failover, and controlled degraded-cluster experiments remain out of
scope.

## Ticket Ledger

| Issue | Type | Status | Review thread | Fixes needed | Verified |
| --- | --- | --- | --- | --- | --- |
| Proposed 1 | AFK | Awaiting graph approval | Pending | Pending | No |
| Proposed 2 | AFK | Awaiting graph approval | Pending | Pending | No |
| Proposed 3 | AFK | Awaiting graph approval | Pending | Pending | No |
| Proposed 4 | AFK | Awaiting graph approval | Pending | Pending | No |
| Proposed 5 | AFK | Awaiting graph approval | Pending | Pending | No |
| Proposed 6 | AFK | Awaiting graph approval | Pending | Pending | No |

## Parked HITL Slices

| Issue | Why parked | Blocks | Required human action | Final PR decision |
| --- | --- | --- | --- | --- |
| None | — | — | — | — |

## Issue Session Ledger

| Issue | Fixed point | Worker session | Commit | Review result | Checks |
| --- | --- | --- | --- | --- | --- |
| Pending | Pending | Pending | Pending | Pending | Pending |

## Open Questions

- Does the proposed six-ticket granularity and blocking graph have human approval?

## Escalations

- None.
