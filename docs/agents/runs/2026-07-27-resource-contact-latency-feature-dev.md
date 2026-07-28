# Reliable Curated Resource Contact Lookup and Latency — Feature Dev Ledger

## Run

- Run ID: `2026-07-27-resource-contact-latency`
- Loop: `plebdev-feature-dev` v0.4.0
- Target repo: `enclave-free/enclave.free` with the `enclave-free/sage` runtime submodule
- Base branch: `staging` (`origin/staging` at `0abc518` when the run began)
- Feature branch: `feature/resource-contact-latency`
- Human owner: plebdev
- Started: 2026-07-27
- Current status: Tickets #534–#539 implementation, verification, and independent review complete; local CodeRabbit findings fixed, Sage refresh rate-limited; staging publication and PR review remain
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
- Tickets: #534, #535, #536, #537, #538, and #539
- Ticket sessions: #534 `docs/agents/runs/2026-07-27-resource-contact-latency-issue-534.md`; #535 `docs/agents/runs/2026-07-27-resource-contact-latency-issue-535.md`; #536 `docs/agents/runs/2026-07-27-resource-contact-latency-issue-536.md`; #537 `docs/agents/runs/2026-07-27-resource-contact-latency-issue-537.md`; #538 `docs/agents/runs/2026-07-27-resource-contact-latency-issue-538.md`; #539 `docs/agents/runs/2026-07-27-resource-contact-latency-issue-539.md`
- Agent briefs: Pending ticket publication
- Review packets: #534 `docs/agents/runs/2026-07-27-resource-contact-latency-issue-534-review.md`; #535 `docs/agents/runs/2026-07-27-resource-contact-latency-issue-535-review.md`; #536 `docs/agents/runs/2026-07-27-resource-contact-latency-issue-536-review.md`; #537 `docs/agents/runs/2026-07-27-resource-contact-latency-issue-537-review.md`; #538 `docs/agents/runs/2026-07-27-resource-contact-latency-issue-538-review.md`; #539 `docs/agents/runs/2026-07-27-resource-contact-latency-issue-539-review.md`
- Local CodeRabbit report: Pending implementation
- PR URL: Pending

## Commands

- Install: `python3 -m pip install -r backend/requirements.txt`; `cd runtime/sage && cargo fetch`; `cd frontend && npm ci`
- Typecheck: `cd runtime/sage && cargo check -p sage-core --bin enclave_web`; `cd frontend && npm run build`
- Test: `/Users/plebdev/Desktop/Projects/enclave-free/enclave.free/.venv/bin/python -m unittest discover -s backend/tests -p 'test_*.py'`; `cd runtime/sage && LIBRARY_PATH=/opt/homebrew/opt/libpq/lib DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/opt/libpq/lib cargo test -p sage-core --lib`; `cd frontend && npm test`
- Build: `cd frontend && npm run build`; Compose build/smoke only when integration verification requires it
- Visual verification: focused Conversation Activity component tests followed by local browser inspection of Activity rows when the stack is available

## Proposed Ticket Graph

1. **Find precise Curated Resources with honest bounded results** — no blockers.
   Deliver exact and hybrid organization/contact matching, offset continuation,
   total/page metadata, Resource Tool warnings, and completeness-safe final-answer
   instructions through the Resource Directory and Sage Tool contract.
2. **Ground contact follow-ups in a fresh Curated Resources call** — complete; model-backed Compose execution is scheduled for #539.
   Deliver the model-planning and final-answer policy for email, phone, website,
   address, secure channel, and equivalent English/Spanish follow-ups while
   preserving the enabled Tool Set boundary.
3. **Show why Curated Resources was selected or missed** — complete; #537 is now the next frontier.
   Deliver content-free Tool Selection Observations from planning through Trace,
   Activity, and structured logs, including selected, attempted, terminal, and
   expected-but-missed states without exposing prompts or contact values.
4. **Bound and retry read-only lookup failures** — complete; #538 is the ready frontier.
   Deliver conservative timeout/retry policies for Curated Resources and
   Knowledge Search with visible retry, timeout, and terminal evidence; writes
   remain unretried.
5. **Attribute Conversation latency to its real phases** — complete.
   Deliver separate planning, final inference, provider header/first-event proxy,
   Resource Directory, Retrieval, Tool, retry-delay, and total-turn timing in
   Trace, Activity, and privacy-safe structured logs.
6. **Prove the reported customer journeys across User Types** — complete; final independent specification and standards reviews passed (#539).
   Deliver public Conversation/Resource contract regression coverage and replay
   the affected contact and bounded-inventory prompts across the relevant User
   Types, followed by the full backend, Sage, and frontend verification gates.

The human explicitly approved this six-ticket graph on 2026-07-27 and delegated
routine implementation decisions. All six tickets are AFK. Their validation is agent-performable with the
existing local test seams and already-authorized development tooling. Production
deployment, live customer data, WLC-specific ranking, missing Bitcoin content,
provider failover, and controlled degraded-cluster experiments remain out of
scope.

## Pre-Change Baseline

- Parent fixed point after PRD and run-ledger commits: `97e5b16`.
- Sage fixed point and feature-branch base: `a33e590` on
  `feature/resource-contact-latency`.
- Backend Resource Directory: 17 tests passed with the repository's existing
  Python 3.12 virtual environment. The macOS `/usr/bin/python3` is Python 3.9 and
  cannot evaluate the application's modern type annotations, so it is not a
  valid test interpreter for this run.
- Sage Agent Runtime: 79 `web_runtime::tests` passed.
- Conversation UI Surface: 71 focused ChatMessage, stream-adapter, ChatPage, and
  LLM transport tests passed.

## Ticket Ledger

| Issue | Type | Status | Review thread | Fixes needed | Verified |
| --- | --- | --- | --- | --- | --- |
| #534 | AFK | Complete | Fixed in review | Yes | backend 20 tests; Sage 118 tests; Sage check; fmt check; parent backend 423 tests |
| #535 | AFK | Complete | Fresh Sage replay + durable model-backed eval; fresh spec/standards pass | Yes | Sage 121 tests; check; fmt; eval 5/5 |
| #536 | AFK | Complete | Fresh exact-SHA standards/spec pass | Yes | Sage 124 tests; check; fmt; diff; frontend 375 tests/build |
| #537 | AFK | Complete | Fixed in review | No | parent `8d167d1677346f4a20ac372990c6c03bbf334a8a`; Sage `7bfcfc2911f4987235813e032ce95b4aea78d33e`; independent spec/standards PASS; Sage 136 + frontend 378 |
| #538 | AFK | Complete | Two correction rounds; final exact-SHA standards/spec PASS | Yes | Sage 152; frontend 382 + build |
| #539 | AFK | Complete | Final exact-fixed-point specification/standards PASS | Yes | eval 35; Sage 163; backend 424; frontend 382 + build; current global Spanish 3/3 and metadata inventory 2/2; prior mixed provider evidence retained |

## Parked HITL Slices

| Issue | Why parked | Blocks | Required human action | Final PR decision |
| --- | --- | --- | --- | --- |
| None | — | — | — | — |

## Issue Session Ledger

| Issue | Fixed point | Worker session | Commit | Review result | Checks |
| --- | --- | --- | --- | --- | --- |
| #534 | `133ca477e17d19ce8637a043fdec147f1a200a7e` / `a33e5903f775e5da627eac4269371622a2f1bf99` | `/root/ticket_534` | parent `698a021192acdf9f1aa4855292034989e2e6b55e`; Sage `14de20d2c378ac9af91e26378bd2c488a9b54faa` (prior Sage slice `9964e31498300752289fec6b3ea0c9f37cdcceca`) | Standards/spec hard findings fixed; baseline smells retained as out-of-scope cleanup | backend 20 targeted / 423 full; Sage 118 full; Sage check; fmt check |
| #535 | `fca7379c4ada1dff5f5b2a0c57b024c9a95d2ff0` / `14de20d2c378ac9af91e26378bd2c488a9b54faa` | `/root/ticket_535_model_eval` | Sage `6a7cde839e55d283fa02a033e90fe8f708f34d7b`; eval `2e3db4ac53aae31f36350b72957c80a5ee46c7b4`; parent pointer/records in this closeout | Fresh standards/spec pass; real two-turn Sage replay; model-backed Compose eval scheduled for #539 | Sage 121 full; Sage check; fmt; eval 5/5 + py_compile/help |
| #536 | `e164e695a818566289e829760a2b4d89882b1446` / `6a7cde839e55d283fa02a033e90fe8f708f34d7b` | `/root/ticket_536` | parent `1f21c775f657628052c124e1542356caeb5b788c`; Sage `3733df23fd5cbae33cbc81c9e8f7ae5fe0151dea` | Fresh exact-SHA standards/spec pass; native structured-log capture; live stream and batch failure seams | Sage 124 full; check; fmt; diff; frontend 375 full + build |
| #537 | `5f3a0c64dc2d6e937d880ff16948c99e0ce2adbb` / `7bfcfc2911f4987235813e032ce95b4aea78d33e` | `/root/ticket_537` | parent `8d167d1677346f4a20ac372990c6c03bbf334a8a`; Sage `7bfcfc2911f4987235813e032ce95b4aea78d33e` | Independent exact-SHA spec/standards PASS; no findings | Sage 136 full; check; fmt; frontend 378 full + build/Prettier |
| #538 | `2a1efdc68e1a8e59a85defb04d405a52816d25a2` / `7bfcfc2911f4987235813e032ce95b4aea78d33e` | `/root/ticket_538` | parent `718e55a`; Sage `327ee9ad018c47f65124df38a16e399114fe1c93` | Two correction rounds; final independent exact-SHA spec/standards PASS with no findings | Sage 152 full + check/fmt/diff; frontend 382 full + build; focused frontend 50 |
| #539 | `ab0516b09179485f57f264d3a647e44c303454d8` / `327ee9ad018c47f65124df38a16e399114fe1c93` | `/root/ticket_539` | parent `b992b9f`; Sage issue fixed point `a82ac43761475a57a45ac18f8bcb9acedaf9e7bc`; post-feature CodeRabbit integration `3bad5dbf28d1c27098f9759bd7297fecd2d8b639` | Final independent exact-fixed-point specification/standards PASS; local CodeRabbit issue fixed | eval 35; backend 424; Sage 163 + check/fmt/diff; frontend 382 + build; current global Spanish 3/3; metadata inventory RED preserved then 2/2 GREEN; prior mixed provider evidence retained; all cleanup clean |

## Open Questions

- None.

## Escalations

- None.
