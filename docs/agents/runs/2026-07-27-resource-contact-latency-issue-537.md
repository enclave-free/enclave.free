# Issue

- Issue: #537 — Bound and retry read-only lookup failures
- Fixed point before session: parent `5f3a0c64dc2d6e937d880ff16948c99e0ce2adbb`; Sage `3733df23fd5cbae33cbc81c9e8f7ae5fe0151dea`
- Worker session: `/root/ticket_537`
- Status: implementation complete; independent spec and standards reviews pass

## Inputs

- Spec issue: GitHub `enclave-free/enclave.free#537`, parent #533, blocked by #536
- Relevant ADRs: 0023 (model-driven Tool selection), 0024 (transparent Trace/Activity), 0027 (separate Tool decisions from final answer delivery)
- Public seams: Sage `Tool`/`SageAgent` execution and Trace hook; typed read-only internal backend calls; Conversation Trace/Activity and stream adapter

## Implementation

- Added an explicit `ToolRetryPolicy` interface with a no-retry default and read-only-only bounded policy constructors. Curated Resources uses 5s per attempt, 2 attempts, 8s total; Knowledge Search uses 35s total, at most one retry, with a useful remaining-budget guard and bounded 100ms backoff.
- Added typed `ToolExecutionError` classification for connection, timeout, HTTP 502/503/504, HTTP 4xx, malformed contracts, and non-retryable failures. Only document/resource read adapters use the typed request path; legacy internal client behavior remains unchanged.
- Centralized Tool execution preserves the #536 call ID across attempts, emits one privacy-safe attempted event per attempt, `tool_retry` and timeout evidence, and exactly one terminal event. Failed timeout/exhaustion results remain `success = false`; valid empty responses remain successful and are not retried. State-changing Tools inherit no retry.
- Added structured-log allowlisting and Trace Delta/Activity mappings for `tool_retry` and `timeout`; the existing model `retry` mapping remains unchanged.
- `tdd` used: yes. RED was the focused policy test failing to compile before the typed boundary; GREEN covered scripted and controlled local endpoint seams before broader checks.

## Verification

- Sage focused: `LIBRARY_PATH="$(brew --prefix libpq)/lib:${LIBRARY_PATH:-}" cargo test -p sage-core --lib retry_ --no-default-features`; 5 passed.
- Sage endpoint matrix: `... cargo test -p sage-core --lib endpoint_retry_contract --no-default-features`; 1 passed, covering transient recovery, exhausted 503/504, timeout budget, 4xx, malformed response, valid empty, success.
- Sage production adapters: `... cargo test -p sage-core --lib production_read_tools_use_typed_retry_path_and_preserve_valid_empty_success --no-default-features`; 1 passed, covering real Find Resources retry/empty and Knowledge Search retry.
- Sage typed timeout: `... cargo test -p sage-core --lib typed_timeout_emits_one_timeout_event_before_retry --no-default-features`; 1 passed, proving reqwest timeout and outer timeout paths each emit exactly one timeout event.
- Sage full library: `... cargo test -p sage-core --lib --no-default-features`; 136 passed after the final retry trace, timeout-scope, and truncated-body tests.
- Sage checks: `cargo check -p sage-core --bin enclave_web`, `cargo fmt --all -- --check`, `git diff --check` passed.
- Frontend focused: `npm test -- --run src/components/chat/SageStreamEventAdapter.test.ts --reporter=dot`; 3 passed; `npm test -- --run src/components/chat/ChatMessage.test.tsx --reporter=dot`; 17 passed.
- Frontend full: `CI=1 npm test -- --run --reporter=dot`; 75 files / 378 tests passed, including the reducer merge test. `npm run build` and touched-file Prettier checks passed.

## Commits

- Sage issue commit: `7bfcfc2911f4987235813e032ce95b4aea78d33e`.
- Parent issue commit: supplied in the final handoff message.

## Risks

- Retry policy is deliberately limited to the two read-only lookup Tools; provider failover and broad phase timings remain out of scope. The timeout trace status is `timed_out`, while the Tool result is failed and cannot be mistaken for an empty success.
