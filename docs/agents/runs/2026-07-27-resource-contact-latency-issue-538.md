# Issue

- Issue: #538 — Attribute Conversation latency to its real phases
- Fixed point before session: parent `2a1efdc68e1a8e59a85defb04d405a52816d25a2`; Sage `7bfcfc2911f4987235813e032ce95b4aea78d33e`
- Worker session: `/root/ticket_538`
- Status: Complete; final independent specification and standards reviews passed

## Inputs

- Spec issue: GitHub `enclave-free/enclave.free#538`, parent #533, blocked by #536 and #537
- PRD: `docs/agents/runs/2026-07-27-curated-resource-contact-latency-prd.md`
- Relevant ADRs: 0023 (model-driven Tool loop), 0024 (transparent Trace/Activity), 0027 (separate Tool decisions from final-answer delivery)
- Public seams: Sage `SageAgent` planner/executor and provider stream adapter; Conversation Trace/Activity and stream event payloads

## Implementation

- Added one typed `ConversationTimingPhase` event boundary covering Tool-planning model duration, final-answer model duration, provider response-header and first-provider-event waits, generic per-Tool execution, Resource Directory lookup, Retrieval, retry delay, and total turn.
- Provider waits start at request start and are explicitly labeled as provider-wait proxies; metadata states that network, provider queue, or model startup may contribute and never claims internal cluster timing. First-event timing fires only after a complete non-empty provider SSE event; request/status/stream failures emit failed timing outcomes.
- Tool timing keeps stable planning round, attempt, tool name, and call ID correlation. Resource Directory and Retrieval timings are per attempt with true success/failure/timeout outcomes; generic Tool execution is emitted once at terminal with cumulative duration. Both Tool retry backoff and planner retry delay report measured actual sleep.
- Final-answer safety retries preserve the real provider attempt number. Planning and final-answer failures emit terminal phase timing without exposing raw errors. Total-turn success/failure timing is emitted before stream completion.
- Trace Delta metadata and Activity rows expose human-readable phase labels and durations while omitting arguments, contact values, output, secrets, and raw reasoning. Late final-answer/total timings also receive live Activity rows after answer streaming starts. Structured logs use an explicit allowlist and never enter Audit Log data.
- Added stable `message_id` correlation to every structured Tool/timing log event for chat, stream, and query turns; same-conversation turns are tested to retain distinct message IDs. Closed `ConversationTimingOutcome` preserves `succeeded`, `failed`, `timed_out`, and `guarded` end-to-end.
- First-provider-event success is gated on a validated, consumed Chat Completions SSE choice; malformed, semantically invalid, empty/DONE-only, stream, consume, and status failures emit exactly one failed first-event timing event.
- Second review corrections stage validated answer/reasoning deltas until the first-provider timing hook has fired, so live ordering is response-header timing → first-provider timing → answer. Role-only assistant SSE events remain valid; unusable choices and non-string content/reasoning fail exactly once.
- Unknown/unregistered Tools now emit one correlated failed `ToolExecution` timing before their terminal event. Guarded outcomes cross a typed `Tool` boundary (`AdminDbQueryTool` returns `Guarded` alongside the unchanged `ToolResult` API); guard status no longer parses backend error prose.
- A real Resource Directory replay now drains actual `ConversationStreamSignal`s through the production emission adapter and appends the production terminal helper, asserting selection/retry/result → provider waits → answer → final model/total timing → real `trace_final`/`done` payloads.
- Reused existing #536/#537 lifecycle, retry policy, stable IDs, and model-vs-tool retry kinds; no provider failover or cluster inference claims were added.

## TDD Evidence

- RED: before implementation, the focused timing seam tests failed to compile because `AgentTraceEvent::Timing` did not exist; the malformed provider payload test also failed because it was incorrectly marked as a successful first event.
- GREEN: typed phase delta/log/privacy tests, round/attempt ID tests, late Activity emission test, provider SSE timing hook coverage, stable message correlation, and public transport ordering/parity tests pass through public Sage/Conversation seams.

## Verification

- Sage full library: `LIBRARY_PATH="$(brew --prefix libpq)/lib:${LIBRARY_PATH:-}" cargo test -p sage-core --lib --no-default-features` — 152 passed.
- Endpoint retry contract isolated rerun passed (transient recovery, exhausted retry, timeout, and non-retryable 4xx/malformed cases); the subsequent full 152-test rerun also passed, so no retry flake was masked.
- Sage checks: `cargo check -p sage-core --bin enclave_web --no-default-features`, `cargo fmt --all -- --check`, and `git diff --check` passed.
- Sage commit: `327ee9ad018c47f65124df38a16e399114fe1c93`.
- Frontend focused timing/transport tests: `npx vitest run src/components/chat/SageStreamEventAdapter.test.ts src/components/chat/ConversationUiState.test.ts src/components/chat/ChatMessage.test.tsx src/utils/llmChat.test.ts` — 50 passed. Full frontend suite: `npx vitest run --maxWorkers=2` — 75 files and 382 tests passed (84.09s; log `/tmp/frontend-vitest2.log`). The expected stderr includes missing `LLM_API_KEY` interpolation and lazy-route test diagnostics; the suite exit was successful. `npm run build` passed. Changed frontend files pass `npx prettier --check`; repository-wide `npm run format:check` remains red on pre-existing generated/dist and unrelated files. No lint script is defined in `frontend/package.json`.

## Review / Risks

- Self-review: phase enum and correlation IDs are closed/allowlisted; provider wait labels are proxy-safe; stream timing precedes final trace and completion; Audit Log remains untouched.
- Final independent specification review: PASS with no actionable findings at Sage `327ee9ad018c47f65124df38a16e399114fe1c93`.
- Final independent standards review: PASS with no actionable findings at the same exact Sage fixed point.
- Residual risk: provider internals remain intentionally unobservable; production deployment, failover, and degraded-provider experiments are out of scope. Frontend tests prove the browser transport has only the chat stream write path for timing events; Sage has no Audit Log client or timing-to-audit persistence path, while existing Audit Log tests cover separate admin config writes.
