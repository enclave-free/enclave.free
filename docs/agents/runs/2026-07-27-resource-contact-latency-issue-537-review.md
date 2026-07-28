# Review Packet

## Issue

- Issue: #537 — Bound and retry read-only lookup failures
- Slice type: typed read-only Tool retry/timeout execution, privacy-safe Trace/Activity evidence, and frontend stream parsing
- Acceptance criteria: bounded Curated Resources and Knowledge Search budgets; narrowly eligible retries; failed timeout/exhaustion; no state-changing retries; deterministic endpoint coverage; stable #536 correlation
- Baseline: parent `5f3a0c64dc2d6e937d880ff16948c99e0ce2adbb`; Sage `3733df23fd5cbae33cbc81c9e8f7ae5fe0151dea`

## Implementation Evidence

- `implement` session: `/root/ticket_537`.
- `tdd` used: yes.
- Red test: policy/executor tests initially failed to compile because `ToolRetryPolicy`, typed error classification, and lifecycle variants did not exist.
- Green implementation: central Sage execution boundary plus typed document/resource client path; focused tests pass through Sage and controlled local HTTP endpoints.
- Public evidence: each retry keeps the same call ID; terminal is emitted exactly once; `tool_retry`/timeout logs contain allowlisted correlation and timing fields only; frontend accepts `tool_retry` and `timeout` deltas while preserving the existing model `retry` kind.

## Review Instructions

Review only #537's Sage pointer, frontend parser, and run artifacts against the fixed points. Preserve ADR-0023 model-driven selection and #536 lifecycle semantics. Do not widen into #538 phase timings/provider failover.

## Reviewer Output

STANDARDS_STATUS: pass (independent review; final fixed point is parent `5f3a0c64dc2d6e937d880ff16948c99e0ce2adbb` and Sage `7bfcfc2911f4987235813e032ce95b4aea78d33e`)
STANDARDS_FINDINGS:
- None. The typed policy is explicit, default-no-retry, and localized to read-only lookup adapters; `tool_retry` keeps model `retry` semantics separate; generated build output was excluded.

SPEC_STATUS: pass (independent review against GitHub issue #537)
SPEC_FINDINGS:
- None. Exact issue budgets, eligible statuses, timeout/exhaustion failure semantics, stable call correlation, privacy-safe lifecycle evidence, stream/non-stream adapter coverage, and state-changing no-retry guard are covered.

## Residual Risk

- Full workspace checks and final CodeRabbit/independent review remain parent-orchestrated. Production/provider behavior is not exercised; no production deploy, migration, or failover work is included.

## Final Handoff

- Parent issue commit: supplied in the final handoff message.
- Sage pointer: `7bfcfc2911f4987235813e032ce95b4aea78d33e`.
- Verification: Sage 136/136 tests; frontend 75 files / 378 tests; Sage check/fmt and frontend build/Prettier pass.
