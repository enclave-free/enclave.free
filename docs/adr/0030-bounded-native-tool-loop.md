# Bounded Native Tool Loop

Status: Accepted

Sage will run a small provider-native **Tool** loop for each **Conversation** turn. The configured **Model Provider** receives the same enabled, authorized Tool contracts on each ordinary model request and may answer directly or select a Tool batch. Sage executes no more than six model-selected Tool batches per turn. If the model requests a seventh batch, Sage rejects it before execution, returns correlated bounded Tool failures, and gives the same model one final Tool-disabled request to answer from the accumulated evidence.

This decision supersedes only the one-batch and Tool-free-final-request constraints in [ADR-0029](0029-native-tool-calling-with-one-tool-round.md). ADR-0029 remains authoritative for the native protocol hard cut, same-model operation, authorization and validation, removal of deterministic routing and answer filtering, bounded retries, result budgets, and privacy-safe observability.

## Context

The first GLM 5.2 deployment enforced one Tool batch by removing Tool definitions from the next request. After successful Retrieval and Tool execution, GLM could finish with provider reasoning but no answer content. Keeping the schemas while setting `tool_choice` to `none` avoided that empty response, but a 40-turn customer replay then produced literal textual `<tool_call>` markup instead of final answers in 29 turns.

The replay showed that the model was still trying to choose a useful follow-up Tool after seeing the first results. Converting that intent into prose by disabling native Tool selection was the wrong protocol boundary. A bounded native loop lets the frontier model use its supported protocol without restoring a separate planner, intent classifier, content scanner, or answer rewriter.

## Decision

- The first model request receives every enabled, authorized Tool definition. With no enabled Tools, the provider request explicitly disables Tool selection.
- A direct answer ends the turn immediately without a planning-only request.
- A native Tool-call response is validated and executed through the existing authorization, argument, batch-size, timeout, retry, result-budget, Activity, and Conversation Trace boundaries.
- Correlated Tool-result messages, the same enabled Tool definitions, and any provider-supplied Provider Continuity State from the corresponding assistant Tool-call message return unchanged to the same configured model. Provider Continuity State exists only for the current turn and is never interpreted, streamed, logged, persisted, exported, or carried into a later Conversation turn.
- The model may continue selecting Tool batches after correlated results, within a six-batch safety ceiling.
- After six executed batches, Sage makes one more ordinary model request with the Tool contracts still available. If that request selects another Tool batch, Sage rejects it before execution and injects one correlated `tool_budget_exhausted` result for each unexecuted call.
- After the correlated rejection results, Sage makes exactly one final request to the same model with Tools disabled. That request may answer only from the accumulated Conversation and Tool evidence. No seventh Tool batch can run.
- The per-batch limit remains eight native Tool calls. The loop bound therefore does not weaken the existing batch bound.
- One generic same-model retry budget remains scoped to each logical model request. In addition to existing eligible transport, upstream, and protocol failures, a request that produces no provider event within 20 seconds is a Pre-Response Provider Stall: Sage abandons that attempt and repeats the identical request once. The first answer, reasoning, Tool-call, or other provider stream event makes that attempt ineligible for any model-request retry. A retry never replays a completed Tool batch, and the existing 180-second overall attempt timeout remains for requests that have begun responding.
- The 20-second stall threshold is an internal runtime policy, not a new Agent Setting, Deployment Setting, or Admin control.
- Sage preserves provider-supplied continuity state but does not force thinking on or off, set reasoning effort, add model-specific reasoning prompts, or manufacture continuity state when the provider supplies none.
- Provider Continuity State remains subject to a fixed aggregate protocol-size bound. Sage rejects an oversized value without inspecting, logging, or independently truncating it.
- Each request asks for aggregate provider usage when the protocol supports it. If the provider explicitly rejects that optional request extension before inference, the adapter retries once without the extension and remembers the capability for later requests. Returned counts become Model Usage Observations under ADR-0024; unsupported, malformed, or omitted usage metadata does not fail the turn.
- Tool selection remains model-driven. Sage does not add keyword routing, customer-specific query rules, textual Tool-markup parsing, Tool coercion, semantic answer filtering, or deterministic answer fallback.
- Tool-selection and timing observations identify each loop step without logging prompts, Tool arguments or results, contact data, hidden reasoning, or answer content.

## Consequences

Simple turns still complete in one model request, and turns satisfied by one Tool batch still complete after the next request. A turn that genuinely needs a follow-up lookup can complete through the provider's native protocol instead of leaking Tool syntax or failing with an empty answer.

The worst-case turn may now contain eight logical model requests and six executed Tool batches: six requests that select executable batches, a seventh request that selects the rejected batch, and one Tool-disabled final-answer request. Because each logical model request may receive one eligible same-model retry, including recovery from a Pre-Response Provider Stall, the turn-wide provider ceiling remains sixteen attempts. A silent first attempt may still incur provider usage before cancellation, so stall recovery trades a rare duplicate billed attempt for a bounded user wait; Model Usage Observations make that trade-off inspectable where the provider reports it. With at most eight calls in each executed batch and one eligible retry for each Tool call that satisfies the existing retry policy, the turn-wide Tool ceiling is 48 logical calls and 96 attempts. The rejected seventh batch may contain at most eight correlated calls, but none execute. The one-retry rules apply independently to each eligible model request and Tool execution within those turn-wide ceilings. This remains intentionally smaller than an open-ended agent loop. When the bound is reached, operators receive a content-free `native_tool_round_limit_reached` event plus terminal rejected Tool evidence, while the model receives the correlated failures and remains responsible for the final answer.

The earlier four-batch ceiling was grounded in the first focused deployment: GLM 5.2 selected a third native batch in five of ten representative turns even though every preceding Tool execution succeeded. The earlier two-batch ceiling rejected those valid continuations and therefore failed its release regression. The authoritative 40-turn customer replay then showed GLM 5.2 select a fifth batch in three turns after four successful Tool batches. Six batches permit that observed refinement pattern with one bounded step of headroom.

The first deployment of this decision requires a focused GLM 5.2 regression across the known failure classes. Transport success alone is insufficient: inspected final answers must contain neither leaked Tool markup nor empty completions, representative Tool-assisted and ordinary no-Tool turns must behave normally, and provider-continuity and silent-stall behavior must be proven deterministically at the existing native provider seam. The single authoritative four-persona customer replay remains release evidence rather than a network-dependent CI gate.
