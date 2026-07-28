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
- Verification commands:
  - Sage focused retry policy: `LIBRARY_PATH="$(brew --prefix libpq)/lib:${LIBRARY_PATH:-}" cargo test -p sage-core --lib retry_ --no-default-features` (5 passed).
  - Sage endpoint contract: `LIBRARY_PATH="$(brew --prefix libpq)/lib:${LIBRARY_PATH:-}" cargo test -p sage-core --lib endpoint_retry_contract --no-default-features` (1 passed across transient, exhausted, timeout, 4xx, malformed, empty, and success cases).
  - Sage production adapters and timeout seams: the corresponding exact-name `cargo test -p sage-core --lib ... --no-default-features` invocations recorded in the issue record passed.
  - Sage full/checks: `LIBRARY_PATH="$(brew --prefix libpq)/lib:${LIBRARY_PATH:-}" cargo test -p sage-core --lib --no-default-features` (136 passed), `cargo check -p sage-core --bin enclave_web`, `cargo fmt --all -- --check`, and `git diff --check`.
  - Frontend focused: `npm test -- --run src/components/chat/SageStreamEventAdapter.test.ts --reporter=dot` (3 passed) and `npm test -- --run src/components/chat/ChatMessage.test.tsx --reporter=dot` (17 passed).
  - Frontend full/build: `CI=1 npm test -- --run --reporter=dot` (75 files / 378 tests) and `npm run build` passed; touched-file Prettier checks passed.
- The deterministic controlled-local-HTTP endpoint matrix above exercised the smoke seams for this runtime-only slice. No manual browser Test Dashboard steps were run or claimed; frontend transport and Activity behavior were verified through the focused and full automated suites.
