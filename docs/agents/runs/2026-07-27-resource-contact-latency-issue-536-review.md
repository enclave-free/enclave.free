# Review Packet

## Issue

- Issue: #536 — Show why Curated Resources was selected or missed
- Slice type: Sage planner evidence, Conversation Trace transport, and frontend Activity rendering
- Baseline: parent `e164e695a818566289e829760a2b4d89882b1446`; Sage `6a7cde839e55d283fa02a033e90fe8f708f34d7b`
- Current Sage commit: `3733df23fd5cbae33cbc81c9e8f7ae5fe0151dea`

## Implementation Evidence

- Typed `ToolSelectionObservation` records enabled/selected Tools, selection count, expected/missed Curated Resources, planning round, real planner attempt, and outcome.
- Every selected Tool emits correlated attempted and terminal evidence from Sage execution, including failed and guarded outcomes; no wrapper emits duplicate lifecycle events.
- Production `sage.tool_selection` logging and privacy tests share one allowlisted field builder with exact key-set assertions for selection, attempted, and terminal phases.
- Real Conversation replay covers English/Spanish contact cues, mixed benign/physical-address wording, enabled/disabled batch and stream paths, live Trace transport ordering before answer chunks, exhausted planner failure at attempt 3, and failed Tool terminal transport.
- Frontend adapter and accessible Activity rows expose selection observations and missed state without raw prompt, arguments, or output.

## Verification

- Sage: `cargo test -p sage-core --lib` — 124 passed; `cargo check -p sage-core --bin enclave_web`; `cargo fmt --all -- --check`; `git -C runtime/sage diff --check`.
- Frontend: focused adapter/Activity tests (18), full `CI=1 npm test -- --run --reporter=dot` (74 files / 375 tests), `npm run build`, and Prettier check on touched files.

## Review Status

- Standards review: pass against `3733df23fd5cbae33cbc81c9e8f7ae5fe0151dea`; zero findings.
- Spec review: pass against `3733df23fd5cbae33cbc81c9e8f7ae5fe0151dea`; zero findings.

## Accepted Boundary

- Contact expectation is diagnostic metadata only; model-driven authorization remains unchanged. Deterministic replay providers validate public Conversation seams; live provider quality remains outside #536.
