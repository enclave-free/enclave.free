# Issue

- Issue: #536 — Show why Curated Resources was selected or missed
- Fixed point before session: parent `e164e695a818566289e829760a2b4d89882b1446`; Sage `6a7cde839e55d283fa02a033e90fe8f708f34d7b`
- Worker session: `/root/ticket_536`
- Status: implementation complete; final exact-SHA specification and standards reviews passed at Sage `3733df23fd5cbae33cbc81c9e8f7ae5fe0151dea`

## Inputs

- Spec issue: #536, parent #533, and PRD `docs/agents/runs/2026-07-27-curated-resource-contact-latency-prd.md`
- Relevant ADRs: 0023, 0024, 0027
- Public seams: Sage `SageAgent` Tool planner and Trace hook; web Conversation Trace/Activity payload; frontend stream adapter and ChatMessage Activity surface

## Implementation

- Added a typed `ToolSelectionObservation` Agent Trace event emitted by every successful Sage planning round. It records enabled and selected Tool names, selection count, conservative Curated Resources contact expectation, and missed expectation without content, reasoning, arguments, or output.
- Added conservative English/Spanish contact-cue detection that is diagnostic-only and gated by the enabled `find_resources` Tool.
- Serialized observations as dedicated `tool_selection_observation` Trace Deltas and accessible Activity rows for streaming and accumulated traces. Existing Tool call deltas now explicitly declare attempted semantics without serializing argument names; every selected Tool emits attempted and terminal lifecycle evidence, including failures and guard outcomes.
- Added allowlisted structured `sage.tool_selection` runtime events with conversation/actor correlation, round, call ID, attempt, outcome, duration, enabled/selected names, count, and expected/missed flags. Every selected Tool is owned by Sage execution and emits one attempted and one terminal lifecycle event.
- Stream replay now carries those typed Trace Deltas through the same Conversation stream channel and asserts selection evidence precedes answer chunks. Conversation transport tests cover exhausted planning (attempt 3), failed Tool terminal evidence, disabled streaming, and benign non-contact wording.
- Extended frontend Trace Delta parsing/rendering and added adapter/Activity tests.
- `tdd` used: yes — cue and public trace/Activity seam tests were added before the final implementation slice; real Sage planner replay now asserts selection observations for streaming and non-streaming paths and disabled Resources remains un-authorized.

## Verification

- Sage: `cargo test -p sage-core --lib` (124 tests), `cargo check -p sage-core --bin enclave_web`, `cargo fmt --all -- --check`, `git -C runtime/sage diff --check`
- Frontend: focused adapter/ChatMessage tests (18), full `CI=1 npm test -- --run --reporter=dot` (74 files / 375 tests), `npm run build`, and Prettier check on touched files

## Review

- Review fixed points: parent `e164e695a818566289e829760a2b4d89882b1446`; Sage final `3733df23fd5cbae33cbc81c9e8f7ae5fe0151dea`
- Standards review: pass at Sage `3733df23fd5cbae33cbc81c9e8f7ae5fe0151dea`, zero findings.
- Spec review: pass at Sage `3733df23fd5cbae33cbc81c9e8f7ae5fe0151dea`, zero findings.

## Risks

- Contact expectation remains conservative diagnostic metadata; model-driven planning and Tool authorization remain unchanged. Provider quality and full-stack model-backed replay remain outside #536.
