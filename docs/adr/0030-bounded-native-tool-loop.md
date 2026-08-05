# Bounded Native Tool Loop

Status: Accepted

Sage will run a small provider-native **Tool** loop for each **Conversation** turn. The configured **Model Provider** receives the same enabled, authorized Tool contracts on each model request and may answer directly or select a Tool batch. Sage executes no more than six model-selected Tool batches per turn. If the model requests a seventh batch, Sage stops before executing it and returns a clear bounded-runtime error.

This decision supersedes only the one-batch and Tool-free-final-request constraints in [ADR-0029](0029-native-tool-calling-with-one-tool-round.md). ADR-0029 remains authoritative for the native protocol hard cut, same-model operation, authorization and validation, removal of deterministic routing and answer filtering, bounded retries, result budgets, and privacy-safe observability.

## Context

The first GLM 5.2 deployment enforced one Tool batch by removing Tool definitions from the next request. After successful Retrieval and Tool execution, GLM could finish with provider reasoning but no answer content. Keeping the schemas while setting `tool_choice` to `none` avoided that empty response, but a 40-turn customer replay then produced literal textual `<tool_call>` markup instead of final answers in 29 turns.

The replay showed that the model was still trying to choose a useful follow-up Tool after seeing the first results. Converting that intent into prose by disabling native Tool selection was the wrong protocol boundary. A bounded native loop lets the frontier model use its supported protocol without restoring a separate planner, intent classifier, content scanner, or answer rewriter.

## Decision

- The first model request receives every enabled, authorized Tool definition. With no enabled Tools, the provider request explicitly disables Tool selection.
- A direct answer ends the turn immediately without a planning-only request.
- A native Tool-call response is validated and executed through the existing authorization, argument, batch-size, timeout, retry, result-budget, Activity, and Conversation Trace boundaries.
- Correlated Tool-result messages and the same enabled Tool definitions return to the same configured model.
- The model may continue selecting Tool batches after correlated results, within a six-batch safety ceiling.
- After six executed batches, Sage makes one more model request so the model can answer from the accumulated results. If that request selects another Tool batch, Sage rejects it before execution. No seventh Tool batch can run.
- The per-batch limit remains eight native Tool calls. The loop bound therefore does not weaken the existing batch bound.
- One generic same-model protocol retry remains scoped to an individual model request. It repeats the identical request and never replays a completed Tool batch.
- Tool selection remains model-driven. Sage does not add keyword routing, customer-specific query rules, textual Tool-markup parsing, Tool coercion, semantic answer filtering, or deterministic answer fallback.
- Tool-selection and timing observations identify each loop step without logging prompts, Tool arguments or results, contact data, hidden reasoning, or answer content.

## Consequences

Simple turns still complete in one model request, and turns satisfied by one Tool batch still complete after the next request. A turn that genuinely needs a follow-up lookup can complete through the provider's native protocol instead of leaking Tool syntax or failing with an empty answer.

The worst-case turn may now contain seven logical model requests and six Tool batches. Because each logical model request may receive one eligible same-model retry, the provider-request ceiling is fourteen attempts. With at most eight calls in each batch and one eligible retry for each safe read call, Tool execution is bounded at 48 logical calls and 96 attempts. These are independent per-request and per-execution bounds, not one turn-wide retry. This remains intentionally smaller than an open-ended agent loop. When the bound is reached, the user receives an explicit error and operators receive a content-free `native_tool_round_limit_reached` event.

The earlier four-batch ceiling was grounded in the first focused deployment: GLM 5.2 selected a third native batch in five of ten representative turns even though every preceding Tool execution succeeded. The earlier two-batch ceiling rejected those valid continuations and therefore failed its release regression. The authoritative 40-turn customer replay then showed GLM 5.2 select a fifth batch in three turns after four successful Tool batches. Six batches permit that observed refinement pattern with one bounded step of headroom.

The first deployment of this decision requires a focused GLM 5.2 regression across the known failure classes. Transport success alone is insufficient: inspected final answers must contain neither leaked Tool markup nor empty completions, and representative Tool-assisted and ordinary no-Tool turns must behave normally. The single authoritative four-persona, 40-turn customer replay follows the final integration gate in issue #580 so later Tool-contract migrations do not invalidate the evidence.
