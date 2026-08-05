# PRD: Recover Silent Model Provider Stalls and Preserve Tool-Loop Continuity

Status: Implemented, merged, deployed to `demo.enclave.free`, and release
verified. The complete four-persona replay recovered one real silent provider
stall. It also recorded two separate 180-second failures after provider progress
and two answer-quality concerns; see the verification record for the exact
release evidence and residuals.

Decision anchors: [ADR-0024](https://github.com/enclave-free/enclave.free/blob/staging/docs/adr/0024-transparent-reasoning-and-tool-trace-posture.md) and [ADR-0030](https://github.com/enclave-free/enclave.free/blob/staging/docs/adr/0030-bounded-native-tool-loop.md)

Delivery issues: [#600](https://github.com/enclave-free/enclave.free/issues/600),
[#601](https://github.com/enclave-free/enclave.free/issues/601),
[#602](https://github.com/enclave-free/enclave.free/issues/602), and
[#603](https://github.com/enclave-free/enclave.free/issues/603).

Verification record:
[2026-08-05 provider-stall, continuity, and latency verification](2026-08-05-provider-stall-continuity-latency-verification.md).

## Problem Statement

Users can still experience an extremely slow Conversation even when Retrieval and
Tool execution are fast. Recent demo evidence showed ordinary provider responses
arriving in roughly one to three seconds while an equivalent request occasionally
remained silent for more than a minute. Sage currently waits for the broad
180-second model-request timeout before a completely silent response body becomes
retryable, so one unhealthy Model Provider attempt can dominate the entire turn.

Tool-assisted turns also lose model continuity. GLM supplies hidden
`reasoning_content` while deciding and refining native Tool calls, but the active
adapter discards that value before returning correlated Tool results. The next
model request therefore contains the assistant Tool call and Tool result without
the Provider Continuity State that led to that call. This is inconsistent with
the preserved-thinking pattern used by current reasoning-model Tool protocols and
can cause unnecessary follow-up Tool rounds, incoherent continuation, or an empty
or degraded final answer.

Existing timing already shows that the long tail is usually outside Resource
Directory lookup, Retrieval, and Tool execution, but it cannot distinguish an
oversized prompt or response from a silent provider-side stall because per-request
usage is not captured. Operators need aggregate token counts without creating a
second store of prompts, answers, Tool data, or hidden reasoning.

The correction must remain surgical. It must trust the configured frontier model,
preserve the current six-batch Bounded Native Tool Loop, keep the same-model and
one-retry limits, and avoid model-specific routing, reasoning prompts, degraded
cluster simulation, failover architecture, new dashboards, or new configuration
surfaces.

## Solution

Treat complete pre-response silence as one additional transient failure at the
existing native Model Provider boundary. If a logical model request produces no
answer, reasoning, Tool-call, or other provider stream event within 20 seconds,
Sage abandons that attempt and repeats the identical request once against the same
configured model. This recovery shares the model request's existing one-retry
budget and never replays an executed Tool. Once any provider event arrives, that
attempt is no longer eligible for model-request retry; the existing 180-second
attempt timeout still bounds a stream that has begun responding.

Preserve any Provider Continuity State supplied with an assistant Tool-call
message, return it unchanged to the same model with correlated Tool results during
the current Bounded Native Tool Loop, and destroy it when the turn ends. Treat the
state as opaque protocol material: Sage does not inspect it, derive routing or
authority from it, expose it, log it, persist it, export it, or carry it into a
later Conversation turn. The runtime does not force or disable thinking, tune
reasoning effort, add GLM-specific instructions, or manufacture continuity state.

Request aggregate usage on each streaming model request when the provider
supports it. Add the returned prompt, completion, total, cached, and reasoning
counts to the existing sanitized per-request timing trace as a Model Usage
Observation. Record only fields actually returned. These counts follow the
Conversation Trace retention and deletion lifecycle, stay out of normal answer
content, and do not create a billing or analytics subsystem.

Verify the transport behavior deterministically at the existing native provider
adapter and public Conversation Streaming Transport seams. Then replay the
customer prompt/persona suite once against the real GLM deployment as release
evidence. Live provider behavior remains outside required CI.

## User Stories

1. As a User, I want Sage to recover from a completely silent Model Provider attempt, so that I do not wait a minute or more for an unhealthy request.
2. As a User, I want recovery to use the same configured model, so that response quality and privacy posture do not silently change.
3. As a User, I want a normally progressing response left alone, so that long but active reasoning is not mistaken for a stall.
4. As a User, I want the first visible answer delta streamed normally, so that stall detection does not add answer buffering.
5. As a User, I want native Tool calls to continue coherently after Tool results arrive, so that the model does not lose the reasoning context behind its own call.
6. As a User, I want fewer unnecessary follow-up Tool rounds caused by lost model state, so that Tool-assisted answers finish efficiently.
7. As a User, I want direct no-Tool answers to retain the existing one-request fast path, so that the correction does not add a planning step.
8. As a User, I want ordinary Tool-assisted answers to retain the same authorized Tools and results, so that latency recovery does not change grounding behavior.
9. As a User, I want a clear temporary failure after the single retry is exhausted, so that Sage does not hang indefinitely or fabricate an answer.
10. As a User, I want Conversation history and exports to omit hidden model reasoning, so that private continuity material does not become product content.
11. As an Admin, I want Document Access, Tool Set, and actor authorization boundaries preserved during retries, so that recovery does not broaden consent.
12. As an Admin, I want Admin Config writes and other Tool executions never replayed by model-request recovery, so that an inference retry cannot duplicate a mutation.
13. As an Admin, I want Activity to show a content-free stall and retry outcome, so that an unusually slow turn can be diagnosed without exposing its content.
14. As an Admin, I want aggregate model usage available in expandable diagnostic trace details, so that context-size and generation-size problems can be distinguished from silence.
15. As an Admin, I want normal answer content free of token-accounting details, so that operational metadata does not clutter Sage's response.
16. As an Operator, I want a silent attempt bounded at 20 seconds, so that the demonstrated 60-to-75-second dead period is shortened.
17. As an Operator, I want any provider stream event to close the stall window, so that genuine model progress is not cancelled speculatively.
18. As an Operator, I want the existing 180-second attempt timeout retained after progress begins, so that long active generations remain possible.
19. As an Operator, I want the stall retry to consume the existing one-retry budget, so that recovery cannot multiply requests beyond the accepted ceiling.
20. As an Operator, I want the retry to repeat the identical request, so that recovery does not contain customer-, language-, contact-, or Tool-specific correction logic.
21. As an Operator, I want a content-free record of the abandoned attempt and retry result, so that deployment incidents can be correlated safely.
22. As an Operator, I want prompt, completion, total, cached, and reasoning counts recorded only when returned, so that the trace never invents provider facts.
23. As an Operator, I want usage reporting to avoid a second model call, so that observability adds no separate inference operation.
24. As an Operator, I want usage counts to follow Conversation deletion and retention, so that diagnostics do not outlive their associated product record unexpectedly.
25. As an Operator, I want unsupported usage reporting to degrade gracefully, so that provider compatibility does not become a Conversation availability requirement.
26. As an Operator, I want possible duplicate billing from a cancelled silent attempt visible where the provider reports it, so that the retry trade-off is inspectable.
27. As an Operator, I want provider first-event timing described as a combined transport/provider proxy, so that Enclave does not claim direct cluster-scheduler visibility.
28. As a Sage maintainer, I want Provider Continuity State represented separately from answer content and Tool calls, so that each provider channel retains its protocol meaning.
29. As a Sage maintainer, I want continuity state round-tripped unchanged, so that Sage does not become a reasoning interpreter or rewriter.
30. As a Sage maintainer, I want continuity state limited to the same model and current turn, so that provider-private state cannot leak across model identities or future Conversations.
31. As a Sage maintainer, I want no synthesized fallback continuity value, so that providers without this feature continue through their documented contract.
32. As a Sage maintainer, I want no change to thinking mode or reasoning effort, so that protocol correctness does not become a model-behavior experiment.
33. As a Sage maintainer, I want the existing six-batch Tool ceiling preserved, so that continuity does not create an unbounded agent loop.
34. As a Sage maintainer, I want the existing per-request retry path extended instead of adding a second retry subsystem, so that request ceilings remain understandable.
35. As a Sage maintainer, I want deterministic tests to control provider silence and stream events, so that CI does not depend on real network timing.
36. As a Sage maintainer, I want tests to prove no Tool replay, so that the most consequential retry invariant remains protected.
37. As a privacy reviewer, I want tests proving continuity state is absent from answer streams, Activity, Conversation Trace, persistence, exports, and logs, so that the ephemeral boundary is enforceable.
38. As a privacy reviewer, I want Model Usage Observations to contain counts only, so that observability cannot become covert Conversation Content capture.
39. As a customer evaluator, I want the affected four-persona prompts replayed once on the real demo path, so that the correction is assessed through actual product behavior.
40. As a customer evaluator, I want live replay judged on Tool selection, grounding, continuity, latency, and answer usefulness rather than exact wording, so that a frontier model is evaluated appropriately.
41. As a release owner, I want deterministic protocol tests to be the merge gate and live replay to be release evidence, so that CI remains reliable while deployment behavior is still inspected.
42. As a release owner, I want the change delivered without a degraded-cluster simulator, provider failover, analytics dashboard, or new runtime setting, so that the fix stays small and reversible.

## Implementation Decisions

- Extend the existing provider-native streaming adapter and Bounded Native Tool Loop rather than introducing a new orchestration path. The public Conversation transports continue to share this runtime behavior.
- Define a provider event as any valid stream event carrying answer content, reasoning or equivalent continuity material, Tool-call data, or another provider delta. HTTP response headers alone do not prove model progress.
- Start the first-event deadline when each provider request attempt begins. If no provider event arrives within 20 seconds, cancel the attempt and classify it as a Pre-Response Provider Stall.
- A Pre-Response Provider Stall is eligible for the same generic same-model retry already used for transient connection, response-stream, timeout, retryable upstream, and native protocol failures.
- Each logical model request may receive at most one retry total. A stall followed by another failure exhausts that request; failure categories do not stack independent retry allowances.
- Repeat the exact logical request on retry: same model, messages, Tool definitions, Tool choice, generation parameters, and accumulated correlated Tool results.
- Do not replay any Tool. Recovery occurs at the model-request boundary and reuses previously accumulated Tool-result messages.
- The first provider event ends all model-request retry eligibility for that attempt. Do not apply the 20-second silent-stall rule between later deltas or retry a later stream failure after progress has begun.
- Keep the existing 180-second HTTP attempt timeout for an attempt that has begun responding. This work does not add an inter-delta timeout.
- Keep 20 seconds as an internal named runtime policy. Do not expose it through Agent Settings, Deployment Settings, environment configuration, or the Admin UI in this slice.
- Emit the existing content-free retry and timing evidence for the abandoned attempt, scheduled retry, recovered or exhausted result, model step, attempt number, threshold, and elapsed duration.
- Do not include prompt text, answer text, Tool arguments or results, contact values, credentials, secrets, or Provider Continuity State in stall or retry evidence.
- Extend the provider adapter's assistant-turn representation with optional opaque Provider Continuity State associated with the assistant message that selected native Tools.
- Accumulate the complete provider-supplied continuity value across streamed deltas and serialize it back unchanged with the corresponding assistant Tool-call message before correlated Tool-result messages.
- Preserve Provider Continuity State only inside the in-memory request history for the current Bounded Native Tool Loop and only while continuing with the same configured model.
- Destroy continuity state when the turn ends, fails, or changes model identity. Do not add it to Session Memory, Conversation Content, persisted messages, Conversation Trace, Activity, exports, Audit Log, or structured runtime logs.
- Treat Provider Continuity State as opaque. Sage must not parse it for intent, summarize it, use it to authorize or route Tools, inspect it for answer policy, rewrite it, or truncate it independently.
- Apply a fixed aggregate protocol-size ceiling to Provider Continuity State and reject an oversized value without inspecting, logging, or partially forwarding it.
- Do not force thinking on or off, set a reasoning-effort parameter, add provider-specific reasoning prompts, or create placeholder continuity state when no state is returned.
- Keep provider field mapping inside the provider adapter. The active OpenAI-compatible GLM transport may map `reasoning_content`; future adapters may map a signed, encrypted, or otherwise opaque equivalent without changing the Tool-loop domain contract.
- Add optional streaming usage reporting to the existing model request when supported by the current OpenAI-compatible provider contract.
- If a provider explicitly rejects the optional usage request extension before inference, repeat that request once without the extension and retain the negotiated capability for later requests; this adapter-level negotiation does not consume the model-recovery retry budget.
- Parse a terminal usage-bearing stream chunk even when it contains no answer choice. It must not be mistaken for malformed completion data or a second answer.
- Create one Model Usage Observation for each provider request attempt that returns usage. Associate it with the same model step and attempt as the existing timing observation.
- Preserve provider-reported prompt, completion, total, cached, and reasoning counts when present. Do not derive missing subcounts or treat absence as zero.
- Add usage counts to sanitized per-request timing trace metadata. Keep normal answer content unchanged and require no new top-level response or database schema solely for usage.
- Persist Model Usage Observations only through the existing Conversation Trace persistence path and remove them through the existing Conversation deletion lifecycle.
- Treat usage as diagnostic metadata, not authoritative invoicing. No new billing calculator, price table, cost estimator, analytics service, dashboard, sampling pipeline, or long-term telemetry store is introduced.
- Preserve the configured model, Verifiable Inference checks, six executed Tool-batch ceiling, eight-call batch ceiling, Tool authorization, result budgets, Tool retry policy, and final Tool-disabled budget-exhaustion request.
- The correction is a hard behavioral update at the active provider adapter. Do not add a feature flag, parallel legacy adapter, GLM-only orchestration branch, customer-specific router, or content-specific retry prompt.

## Testing Decisions

- The highest deterministic acceptance seam is the existing public Conversation Streaming Transport backed by the native provider adapter and Bounded Native Tool Loop. Script the provider response and observe answer deltas, Activity, Trace Deltas, Tool executions, and terminal response behavior.
- Reuse the current in-process scripted HTTP provider patterns that already test native streaming, same-model retry, timeout, response-stream failure, and Tool non-replay. Do not introduce a second provider-test framework.
- Add a silent-body test using a short injected test deadline. Verify the first attempt is cancelled, the identical request is issued once, the retry succeeds, and content-free stall/retry evidence is emitted in order.
- Add an exhausted silent-body test. Verify exactly two attempts, a bounded temporary failure, and no third request.
- Add first-event boundary tests for answer content, reasoning/continuity data, and Tool-call data. Each event must prevent the pre-response stall timer from cancelling that attempt and prevent a later model-request retry if the stream fails.
- Add a test proving the overall attempt timeout still bounds a stream that begins responding and then never completes, without introducing an additional silent-stall retry after the first event.
- Add a Tool-assisted retry test proving prior Tool results are reused and the Tool implementation executes exactly once.
- Add a request-ceiling test proving a logical request cannot receive one stall retry and then another retry for a different failure category.
- Add provider-adapter tests that assemble continuity data from multiple deltas and return it unchanged on the next request with the matching assistant Tool call.
- Add multi-batch tests proving each assistant Tool-call message retains its own continuity state while the same model continues the turn.
- Add absence tests proving a provider that returns no continuity state produces no synthetic field and still completes normally.
- Add privacy tests proving sentinel continuity content never appears in answer deltas, Activity, Trace Deltas, persisted assistant content, conversation reads, exports, Audit Log, or captured structured logs.
- Add lifecycle tests proving continuity state is not present after successful completion or failure and is never carried into the next User turn.
- Add request-shape tests proving thinking mode, reasoning effort, system instructions, and Tool definitions are unchanged by continuity preservation.
- Add streaming usage tests with a final usage-only chunk. Verify the response completes normally and one Model Usage Observation is correlated to the correct step and attempt.
- Add partial-usage tests for providers that omit cached or reasoning counts. Verify absent fields remain absent and the turn does not fail.
- Add unsupported-usage tests proving an otherwise valid provider stream without usage remains successful.
- Add capability-negotiation coverage proving a provider that rejects the optional usage request extension is retried before inference without the extension and does not receive it on later requests.
- Add trace and persistence tests proving usage contains numeric counts only, follows the assistant turn, survives ordinary refresh/export with the trace, and disappears through Conversation deletion.
- Keep timing assertions external: verify event order, attempt counts, bounded completion, trace shape, and Tool execution count rather than private timer implementation.
- Run the full Sage Rust tests and the existing Enclave contract, backend, frontend, and production-build checks after the targeted provider tests.
- Run the existing customer Conversation prompt suite across all four personas once against the deployed GLM demo path. Capture model steps, Tool rounds, first-event and total latency, Model Usage Observations, final answer quality, and sanitized trace outcomes.
- Treat the live GLM replay as release evidence, not a required CI check. Do not require exact prose or a statistically powered latency claim from one replay.

## Out of Scope

- Changing GLM's thinking mode, reasoning effort, temperature, prompt, or model identity.
- Exposing, summarizing, inspecting, persisting, exporting, or analyzing hidden provider reasoning.
- Carrying Provider Continuity State across Conversation turns or between models.
- Adding customer-, WLC-, contact-, language-, organization-, or retrieval-specific Tool routing.
- Changing Resource Directory ranking, Knowledge Search retrieval, Curated Resource pagination, Tool descriptions, or customer-owned Documents.
- Adding more Tool batches, changing the Tool-call batch size, or creating an unbounded agent loop.
- Adding independent retry allowances for each failure category, replaying Tools, or retrying after provider progress.
- Adding an inter-delta timeout for a response that has already begun streaming.
- Provider or cluster failover, traffic shifting, cross-model fallback, or degraded-run detection.
- A normal-versus-degraded cluster simulator, controlled overload experiment, recurring provider benchmark, or networked CI test.
- A usage analytics product, billing subsystem, price calculation, cost dashboard, long-term telemetry service, or new database solely for token counts.
- A new Admin setting, Deployment Setting, environment variable, feature flag, or UI control for the 20-second threshold.
- Claiming direct measurement of internal provider queueing, cluster scheduling, or inference-only latency.
- Production or demo deployment. Deployment follows implementation, review, staging verification, and release approval.

## Further Notes

- This spec follows the simplified native Conversation runtime shipped through issues #580-#582. It does not restore the typed planner, content-specific Tool coercion, answer quarantine, or cross-model fallback removed by that work.
- It deliberately revisits the earlier PRD decision not to add a model deadline. Post-simplification evidence now isolates occasional 60-to-75-second complete provider silence while Tool work remains sub-second or low-single-second, making a narrow pre-first-event deadline evidence-backed.
- The Model Provider does not expose internal queue or scheduler timing. Pre-response silence remains an operational symptom and recovery boundary, not proof of a particular upstream cluster cause.
- Current [GLM](https://docs.z.ai/guides/capabilities/thinking-mode), [DeepSeek](https://api-docs.deepseek.com/guides/thinking_mode), [Claude](https://platform.claude.com/docs/en/about-claude/models/extended-thinking-models), and [OpenAI](https://platform.openai.com/docs/api-reference/responses-streaming/response/refusal/delta) reasoning/Tool protocols use provider-supplied reasoning or opaque signed state to preserve continuation across Tool results. The Enclave domain term Provider Continuity State keeps that behavior provider-neutral while preserving the strict non-disclosure boundary.
- [Tinfoil usage reporting](https://docs.tinfoil.sh/guides/web-search) is part of the existing provider request and does not create a second inference request. A cancelled silent attempt may nevertheless have consumed upstream work before cancellation; that rare duplicate-attempt trade-off is accepted for bounded user latency and should be visible through returned usage when available.
- Release evidence was captured on Enclave revision `898e0f1`, Sage revision
  `a7d0972`, and effective model `glm-5-2`. The live suite completed all 20 turns,
  recovered one exact 20-second silent stall, and cleaned up all four synthetic
  Conversations. Two active generations later reached the existing 180-second
  limit and failed safely without retry. Those active-generation failures remain
  outside this PRD's narrow silent-stall boundary.
