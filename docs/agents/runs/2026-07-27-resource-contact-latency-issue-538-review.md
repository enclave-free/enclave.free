# Review Packet

## Issue

- Issue: #538 — Attribute Conversation latency to its real phases
- Slice type: typed Sage phase timing, provider-wait proxy attribution, privacy-safe Trace/Activity/log surfacing, and streaming ordering
- Acceptance criteria: all requested phase durations; provider proxy labels; stable correlation; content-free logs; accessible live/final timing; stream/non-stream terminal parity; no Audit Log changes
- Baseline: parent `2a1efdc68e1a8e59a85defb04d405a52816d25a2`; Sage `7bfcfc2911f4987235813e032ce95b4aea78d33e`

## Implementation Evidence

- `implement` session: `/root/ticket_538`; `tdd` used with a compile-failing RED timing seam before implementation.
- Sage pointer commit: `327ee9ad018c47f65124df38a16e399114fe1c93`.
- Public evidence: one typed phase event maps to Trace Delta, Activity, and allowlisted structured logs; phase-instance IDs include planning round/attempt and Tool call correlation; provider header/first-event waits use request-start timing and proxy labels; actual retry sleeps are measured; final timing events precede `trace_final`/`done`.

## Standards Review

- Scope checked against `AGENTS.md`, `runtime/sage/AGENTS.md`, ADR-0023/24/27, and existing #536/#537 lifecycle contracts.
- No generated artifacts, Audit Log writes, provider failover, or state-changing retry behavior were introduced.
- Final independent standards review: PASS with no actionable findings at Sage `327ee9ad018c47f65124df38a16e399114fe1c93` and the held parent frontend surface.

## Spec Review

- Phase coverage: Tool-planning model, final-answer model, response-header wait, first-provider-event wait, per-Tool execution, Resource Directory, Retrieval, retry delay, and total turn.
- Privacy: no prompt/conversation/contact/tool args/output/secret/raw reasoning in timing metadata or structured logs.
- Stream ordering: selection → Tool/retry → provider timing → answer deltas → final trace → completion; late timing rows are emitted to Activity while preserving order.
- Correction review: answer deltas are staged behind validated first-provider timing; unknown Tools have typed failed timing; guarded database rejection status is typed at the Tool boundary rather than inferred from prose; malformed choice/content/reasoning events are rejected exactly once while role-only events are accepted deliberately.
- Full lifecycle evidence uses a real replay's signal stream and the production terminal-emission helper, not manually appended lifecycle names; the test asserts real `trace_final` and `done` payloads and timing placement.
- Final independent specification review: PASS with no actionable findings at the same exact fixed point.

## Verification

- Sage: 152/152 library tests; isolated endpoint retry contract pass plus full-suite rerun; `cargo check -p sage-core --bin enclave_web --no-default-features`; `cargo fmt --all -- --check`; `git diff --check`.
- Frontend focused timing/transport seam: 50 tests passed across adapter, reducer, renderer, and stream transport. Full frontend suite `npx vitest run --maxWorkers=2`: 75 files / 382 tests passed (84.09s; `/tmp/frontend-vitest2.log`). `npm run build` passed. Changed files pass Prettier; repository-wide format check remains red on pre-existing generated/dist and unrelated files. No lint script is defined.

## Residual Risk

- Provider-wait values are product-visible proxies and may include network, provider queueing, or model startup; they do not measure internal cluster scheduling. Production/provider replay is intentionally not performed.
- Audit boundary proof: timing is transported only through `/api/llm/chat/stream`; the browser timing seam test asserts the sole fetch URL is that endpoint and no audit URL is opened. Sage's timing implementation has no Audit Log client or audit persistence call; existing audit tests cover separate admin configuration flows.
