# PRD: Native Tool Calling Root Correction

Status: In implementation. Published as PRD issue #582 with implementation issues #574-#581 and #583-#589. The original one-batch constraint is superseded by the live-replay correction below.

Decision anchors: [ADR-0029](../../adr/0029-native-tool-calling-with-one-tool-round.md) and [ADR-0030](../../adr/0030-bounded-native-tool-loop.md)

ADR-0030 first raised the one-batch hard cut to four executed Tool batches. The authoritative 40-turn replay exposed that ceiling as too low, so the current revision raises it to six while preserving a hard bound.

## Problem Statement

Users are seeing inconsistent Knowledge Search and Curated Resources behavior even though the authoritative GLM 5.2 Conversation model is capable of selecting native Tools. Sage currently asks a separate typed planner to describe Tool calls in a custom response format, validates and rewrites those plans with contact- and inventory-specific rules, may plan again after Tool results, and filters final prose through a large answer quarantine. A valid model response can fail because an optional planner section is absent, and a simple no-Tool answer can pay for repeated planner calls before final generation. These layers increase latency, create new failure modes, and sometimes replace the model's judgment with brittle product code.

The same pattern appears in visible behavior. Contact follow-ups are detected through language-specific rules, incomplete Resource pages trigger prose policing and deterministic fallback, and clarifying questions are instructed to carry a literal `? ` transport marker that can leak into stored or displayed messages. Operators then receive timing categories that cannot actually separate provider inference from cluster scheduling, while the useful facts—whether the model selected a Tool, whether it ran, and where elapsed time was spent—are harder to see.

The Resource Directory itself is not the root problem. It already supports exact and partial organization/contact matching, ranks the strongest results first, and returns page counts and continuation metadata. The correction should preserve those generic search capabilities while removing orchestration that second-guesses a frontier model.

## Solution

Give each configured Conversation model the enabled Tool contracts through its provider-native Tool-calling API. On each ordinary request, the model either answers directly or selects a Tool batch. Sage validates and executes no more than six authorized batches and returns every successful, failed, or guarded result to the same model with the same enabled Tool contracts. A seventh selected batch is rejected before execution with correlated bounded failures, followed by exactly one final same-model request with Tools disabled. Final prose streams directly after basic protocol validation.

Tool descriptions remain short capability contracts. Knowledge Search explains that uploaded Documents can have different languages or titles and that multiple queries may be selected in the same Tool batch. Curated Resources explains that it searches curated services and contact information and returns relevance-ranked results with availability metadata. Sage does not encode WLC terms, contact-intent keywords, forced Tool calls, query rewriting, answer wording rules, or post-Tool replanning.

Keep generic resilience and observability at their natural boundaries. One unusable native model response may receive one content-neutral protocol retry. A safe-to-retry Tool call may retry once for a clearly transient infrastructure failure, but semantic outcomes and non-idempotent writes are never retried automatically. Record only measurable model-request, Tool execution, Retrieval or Resource Directory lookup, first-event, and total-turn timing together with content-free Tool-selection and outcome events.

## User Stories

1. As a User, I want Sage to answer an ordinary question directly when no Tool is useful, so that I do not wait for a separate planning model call.
2. As a User, I want the configured frontier model to decide whether Knowledge Search or Curated Resources can improve my answer, so that brittle keyword rules do not override the meaning of my request.
3. As a User, I want Knowledge Search available through the same Conversation flow as an ordinary answer, so that document grounding does not require a separate mode.
4. As a User, I want the model to know that a Document may have a different language or title than my question, so that it can search using an appropriate alternate query.
5. As a User, I want the model to select multiple Knowledge Search queries in one Tool batch when useful, so that cross-language or alternate-name retrieval can improve without another planning round.
6. As a User, I want exact organization names, email addresses, phone details, and other contact values to receive the Resource Directory's strongest matching behavior, so that precise requests return precise results.
7. As a User, I want the first Resource page to contain the highest-ranked matches, so that the default answer is useful without loading the entire directory.
8. As a User, I want Sage to know when more Resource matches exist, so that it can offer additional options naturally when useful.
9. As a User, I want Sage to speak about Resources naturally, so that I do not see Tool names, offsets, pagination jargon, or implementation details.
10. As a User, I want a later follow-up to use normal Conversation context and model judgment, so that I do not need to repeat the organization or help I was discussing.
11. As a User, I want valid empty results reported honestly, so that Sage does not repeatedly search or invent an answer merely because no match was found.
12. As a User, I want a failed or guarded Tool result reflected honestly in the answer, so that a Tool failure is not disguised as a successful empty result.
13. As a User, I want clarifying questions written as natural Markdown, so that literal parser markers do not appear in my Conversation.
14. As a User, I want answer text streamed as the model produces it, so that a prose scanner does not delay, reject, or replace a valid response.
15. As a User, I want Document Access, Tool Set, actor, and authorization boundaries preserved, so that simpler orchestration does not broaden what Sage can retrieve or change.
16. As an Admin, I want User Conversation defaults to determine which Tool Sets are enabled, so that model discretion remains inside the configuration I selected.
17. As an Admin, I want exact Resource matching and existing curation ranking retained, so that removing Sage rules does not weaken the managed Resource Directory.
18. As an Admin, I want Admin Config Tools to retain their typed arguments, validation, confirmation guidance, authorization, and Audit Log behavior, so that native Tool selection does not weaken write boundaries.
19. As an Admin, I want rejected Admin Config arguments reported accurately, so that I can correct them on a later turn without hidden same-turn replanning.
20. As an Admin reviewing Test & Feedback, I want to see which enabled Tools the model selected, so that I can distinguish model judgment from Tool availability.
21. As an Operator, I want every configured Conversation model to support the native Tool-call contract, so that runtime behavior does not silently fall back to an incompatible planner.
22. As an Operator, I want selected Tool calls to produce attempted and terminal outcome evidence, so that a Tool cannot disappear silently between model selection and execution.
23. As an Operator, I want model request, Tool execution, Retrieval or Resource Directory lookup, first-event, and total-turn timing separated, so that slow turns can be attributed to observable stages.
24. As an Operator, I want provider first-event timing described as a combined provider-wait signal, so that logs do not falsely claim direct visibility into cluster scheduling or inference-only time.
25. As an Operator, I want one low-level retry for eligible transient Tool failures, so that brief infrastructure faults can recover without model-specific patches.
26. As an Operator, I want empty results, weak relevance, invalid arguments, and non-idempotent writes excluded from automatic retry, so that retries remain safe and bounded.
27. As an Operator, I want diagnostic events to omit Conversation Content, Tool results, contact values, credentials, secrets, and hidden reasoning, so that observability does not create another sensitive-data store.
28. As a maintainer, I want one native Tool execution path, so that I do not have to reason about both a custom typed planner and a provider-native path.
29. As a maintainer, I want the old planner, `replan_after_results`, contact-intent rules, plan validators, sanitizers, and final-answer quarantine deleted, so that obsolete behavior cannot reappear behind a flag.
30. As a maintainer, I want one generic protocol retry rather than content-specific correction prompts, so that recovery behavior is small and provider-neutral.
31. As a maintainer, I want no more than six Tool batches executed per turn, so that GLM can refine retrieval without creating an unbounded agent loop.
32. As a maintainer, I want direct-answer and Tool-assisted turns tested through the public Conversation transport, so that tests assert product behavior rather than private helper structure.
33. As a maintainer, I want native Tool selection and same-model retry tested with GLM 5.2, so that the authoritative provider contract is explicit.
34. As a maintainer, I want the customer's prompt suite replayed across all four personas, so that the original retrieval and contact failures are checked after the root correction.
35. As a maintainer, I want WLC retrieval reevaluated after the model can issue multilingual and alternate-title queries, so that hybrid retrieval is added only if evidence still supports it.
36. As a maintainer, I want the Test Dashboard's unused clarifying-question panel and response field removed with the marker parser, so that dead transport behavior is not retained.
37. As a maintainer, I want existing Resource Directory pagination and ranking tests to remain authoritative, so that this orchestration change does not duplicate search logic in Sage.
38. As a maintainer, I want architecture, Tool semantics, and historical PRDs to identify which decisions were superseded, so that later tickets do not accidentally implement the removed design.

## Implementation Decisions

- Use the authoritative model's OpenAI-compatible native Tool-call request and response contract. GLM 5.2 must support that contract; incompatible configuration is rejected rather than routed through the legacy planner.
- Each model request includes the enabled, authorized Tool contracts. The model may return usable answer content or one batch of native Tool calls.
- A direct answer completes from the first model request. Sage does not make a planning request followed by a separate answer request when no Tool was selected.
- When the model selects Tools, Sage validates names, arguments, actor authority, Tool Set membership, batch bounds, and output budgets before execution. Provider selection never authorizes a Tool the actor could not use.
- Sage executes the validated calls as one batch. Multiple calls to the same read Tool are permitted in the batch, including alternate Knowledge Search queries. Existing concurrency and resource limits continue to bound execution.
- Successful, failed, rejected, and guarded Tool outcomes are returned as native Tool-result messages together with the same enabled Tool contracts. The model may select follow-up batches using the provider-native protocol within the six-batch ceiling.
- Sage executes at most six Tool batches per turn. If the next request selects another batch, Sage rejects it before execution, returns correlated `tool_budget_exhausted` failures for those calls, and makes exactly one final request to the same model with Tools disabled so it can answer from the accumulated results.
- Permit one generic retry for an unusable native model response before answer text is exposed. The retry may restate the protocol requirement but must not contain contact-, WLC-, language-, organization-, resource-, or intent-specific correction instructions.
- Remove the separate typed Tool-decision response, its parser dependency, `replan_after_results`, planner attempt loop, plan correction input, and every post-Tool replanning branch.
- Remove deterministic contact and inventory expectation detection, lookup-mode forcing, expected/missed contact fields, model-plan validation, Tool-call sanitization based on inferred intent, and continuation enforcement in Sage.
- Preserve generic Tool argument validation and authorization. A malformed or unauthorized call becomes a rejected or guarded Tool result; it is not silently rewritten into a different call.
- Keep Tool descriptions concise. Knowledge Search says it searches uploaded Documents, notes that language or title may differ from the question, and allows multiple queries in one batch. Curated Resources says it searches curated services and contact information and returns relevance-ranked results with availability metadata.
- Keep the Knowledge Search argument contract focused on one query plus existing constraints. Do not add a query-rewrite service or customer-specific synonym list; the model may select multiple calls instead.
- Preserve the Resource Directory's existing exact and partial matching, ready-status filters, jurisdiction behavior, language preference, verification priority, display order, first-page limit, total count, returned count, `has_more`, and continuation offset.
- Give the model structured Resource availability metadata. Do not automatically fetch another page, require the answer to mention additional pages, add a Resource pagination UI, or expose pagination mechanics to the user.
- Remove completeness-specific word scanning, answer rejection and retry, process-narration scanning, repetition quarantine, and deterministic Curated Resource answer fallback. Trust the final model to describe structured Tool results naturally.
- Preserve credential, secret, authorization, trace-redaction, output-size, and supported-protocol checks at the real security and transport boundaries. Removing prose quarantine does not permit secrets to enter Activity, Conversation Trace, logs, or Audit Log evidence.
- Stream final model prose directly after the protocol boundary. Do not hold initial prose to classify its wording or reconstruct a replacement answer.
- Remove the `? ` clarifying-question prefix instruction, marker extraction, unused response field, and Test Dashboard panel. Questions remain ordinary Markdown in the assistant answer.
- Keep one retry for a Tool execution only when the call is safe to retry and the failure is clearly transient. Read-only calls are eligible; state-changing calls require established idempotency and otherwise are not retried automatically. Do not retry valid empty results, weak relevance, HTTP validation failures, rejected arguments, or semantic dissatisfaction.
- Do not add a new model-request timeout in this correction. First measure latency after the known planner/retry/replan multiplier is removed; add a provider deadline only if a single model request still exhibits unacceptable stalls.
- Record content-free Tool Selection Observations containing enabled and selected Tool names and selection count. Remove contact-specific expectation, missed-lookup, and violation fields.
- Record only measurable stage timings: model request duration, per-Tool execution, Retrieval or Resource Directory lookup, time to first provider event where available, and total turn. Do not emit placeholder cluster-scheduling or inference-only phases when the provider does not expose them.
- Keep fine-grained turn timing as operational Conversation metadata rather than Audit Log evidence. Logs must not copy prompts, answers, Tool arguments or results, contact values, credentials, secrets, or raw reasoning.
- Make the change as a hard cut. Do not retain a feature flag, environment switch, compatibility adapter, or dormant tests for the old planner and quarantine path.
- No Python database schema migration or new Resource Directory index is required. The Enclave Control Plane search and document-access authority remain unchanged.

## Testing Decisions

- Use the public Conversation Streaming Transport as the primary deterministic acceptance seam. Script the provider at its native Tool-call boundary and stub only the existing private Enclave Control Plane contracts. Assert SSE answer, Activity, Trace, and terminal behavior rather than private helper calls.
- Reuse the existing chat-streaming transport and Sage web-runtime test patterns. Extend the non-streaming Conversation route only for parity cases that are not already exercised through the shared runtime.
- Verify a direct-answer turn exposes enabled Tools to the provider, returns usable content from one model request, executes no Tool, and emits a content-free selection observation.
- Verify a Tool-assisted turn accepts native Tool calls, executes an authorized batch, returns correlated native Tool-result messages with the same Tool definitions, and streams the model's answer.
- Verify multiple Knowledge Search calls can occur in the same batch and that successful, empty, failed, rejected, and guarded results all reach the next model request without Sage forcing a specific follow-up Tool round.
- Verify the model may select multiple follow-up Tool batches and answer after their results. Verify a seventh selected batch is rejected before execution, every call receives a correlated bounded failure, no seventh Tool executes, and one final Tool-disabled request to the same model produces the answer.
- Verify one malformed or unusable native model response receives at most one content-neutral protocol retry. Assert no contact-, organization-, WLC-, language-, or query-specific correction is added.
- Verify an eligible read-only Tool receives at most one retry for representative connection, timeout, and retryable server failures. Verify valid empty results, validation failures, weak results, and non-idempotent state-changing calls are not retried.
- Verify native Tool contracts and same-model retry are shaped correctly for GLM 5.2. Keep deterministic adapter tests in CI and use a live provider probe as release evidence rather than a required networked test.
- Verify Resource result metadata reaches the final model request unchanged, the first page remains backend-ranked, and Sage neither automatically requests another offset nor injects completeness wording.
- Preserve existing Resource Directory tests for exact organization/contact matching, partial fallback, ready-status filtering, ranking, counts, and pagination. Those tests remain the authority for search quality.
- Verify final answer deltas are forwarded without prose quarantine, completeness scanning, deterministic Resource fallback, or artificial `? ` markers while existing secret and trace-redaction checks continue to pass.
- Verify Tool-selection observations contain enabled and selected Tool names but no inferred contact expectation, prompt content, Tool arguments, contact values, results, or reasoning.
- Verify model request, Tool execution, Retrieval or Resource Directory lookup, first-event where available, and total-turn timings are present and non-negative. Verify unsupported cluster-scheduling and inference-only phases are absent rather than fabricated.
- Verify the normal Conversation UI renders natural clarifying questions from answer Markdown and the Test Dashboard no longer depends on a separate clarifying-question field.
- Run the full Rust, backend, frontend, contract, integration, and production-build suites after targeted tests. Documentation and ADR consistency checks must pass.
- After the bounded-loop deployment, run a focused live GLM 5.2 regression over the known empty-answer, textual Tool-markup, Tool-assisted, and ordinary no-Tool failure classes. Capture model identity, selected Tools, timings, answers, and sanitized trace evidence.
- After the final integration gate in issue #580, run the single authoritative replay of the exact customer examples across all four personas, including contact follow-ups, incomplete Resource lists, ordinary no-Tool questions, and English questions about Documents with non-English titles. Compare outcomes to the original feedback without requiring exact answer wording.
- Treat live prompt replay as evidence, not a deterministic CI gate. Evaluate whether Tool choice, grounding, truthful use of result metadata, latency, and overall answer usefulness improved.

## Out of Scope

- Adding or fabricating missing Bitcoin guidance or customer-owned Documents.
- WLC-specific ranking, hard-coded organization boosts, customer-specific synonyms, or deterministic query rewriting.
- A new Knowledge Search hybrid/keyword index in the initial correction. Reconsider it only if the post-cutover prompt replay still shows retrieval failure after model-selected multilingual queries.
- Automatically fetching a second Resource page, adding a pagination UI, or forcing Sage to mention that more results exist.
- Deterministic contact, language, inventory, or organization intent classification.
- Content-specific plan correction, answer rewriting, completeness policing, process-narration scanning, repetition quarantine, or deterministic final-answer fallback.
- More than six Tool batches, a separate post-result planner, textual Tool-markup parsing, or an unbounded agent loop.
- Model-provider or cluster failover, degraded-run detection, traffic shifting, or a controlled normal-versus-degraded cluster experiment.
- Claiming direct measurement of internal provider queueing, cluster scheduling, or inference-only latency without provider-supplied signals.
- Adding a model timeout before the simplified runtime is measured.
- Changing Resource Directory persistence, Admin curation policy, Document Access rules, or the private Enclave Control Plane endpoint shapes.
- Production or demo deployment. Deployment follows implementation, review, and staging verification in later work.

## Further Notes

- This spec supersedes the orchestration portions of GitHub issue #533 and the July 27 Curated Resource/contact/latency PRD. It intentionally retains the generic Resource Directory search, page metadata, measurable timing, and safe transient read-only retry work already delivered there.
- ADR-0029 supersedes ADR-0023 only for the typed-planning and provider-native rejection decisions. ADR-0030 supersedes ADR-0029 only for the one-batch constraint. ADR-0023 remains authoritative for Sage Tool ownership, Tool Set boundaries, actor authorization, and execution responsibility.
- ADR-0027 remains historical context; its separate typed Tool-planning phase and final-answer quarantine are not implementation guidance after this correction.
- Direct capability probes against GLM 5.2 returned valid OpenAI-style native Tool calls. The implementation tickets should still include deterministic adapter coverage and a repeatable live release probe.
- The initial WLC correction is deliberately model-led: disclose multilingual/title variation in the Knowledge Search Tool description, allow multiple same-batch queries, and rerun the evidence suite before adding retrieval infrastructure.
- The PRD and implementation slices are published in GitHub. Completion requires reviewed, merged code, exact-revision deployment, and the live customer replay evidence described above.

## Live-Replay Correction

The first deployed hard cut proved that GLM 5.2 sometimes needs native follow-up Tool calls after seeing initial Tool results. Omitting Tool definitions produced a provider `stop` with no answer content. Retaining definitions while disabling Tool selection completed transport but caused literal `<tool_call>` markup in 29 of 40 customer replay turns. A first two-batch correction then rejected a third native batch in five of ten focused turns even though all preceding Tool executions had succeeded. ADR-0030 initially replaced the one-batch request shape with a provider-native loop capped at four executed Tool batches. A later authoritative 40-turn replay showed GLM 5.2 select a fifth batch in three turns after four successful batches, so the current revision raises the hard ceiling to six. This correction is generic and does not restore the removed planner, customer-specific routing, semantic answer filtering, or answer rewriting.
