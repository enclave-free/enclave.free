# Recover Transient Provider Rejections and Clarify User Activity

Status: Accepted for implementation

## Problem Statement

Users can still lose a complete Conversation turn when the configured Model Provider returns HTTP 429 before producing model output. The existing three-attempt same-model recovery correctly handles complete provider silence and several temporary upstream failures, but it treats 429 as terminal. In Jim's August 10 evaluation, one turn stalled for 30 seconds and then stopped on a 429 before its third attempt, while another stopped on a first-attempt 429. Two of fifteen User turns therefore failed even though the model, Retrieval, and Curated Resources behavior was otherwise materially improved.

The current release evidence also makes this intermittent problem easy to miss. The Conversation Model Bench uses fresh Conversation identifiers, but it runs a small sequential sample against an already-running provider path and does not exercise a scripted 429 or mixed stall/rate-limit sequence. Browser network degradation is a different seam and needs an explicit manual protocol rather than being treated as a substitute for provider fault coverage.

Finally, Activity is intentionally visible to both Admins and Users under the prototype's transparent Trace Visibility Posture, but the current `Hide activity details` control hides only optional summaries. It leaves the complete timeline and operational Trace visible, so the control reads like a full collapse while behaving like a narrow detail toggle.

## Solution

Sage will treat a pre-output HTTP 429 as a Transient Provider Rejection within the existing same-model three-attempt budget. The identical request will wait through a small bounded delay before retrying. A short provider `Retry-After` value will guide that delay; all delays remain internally capped and observable through content-free Retry Delay timing. The existing provider-event cutoff, request identity, Tool-result reuse, no-Tool-replay rule, model choice, reasoning configuration, and attempt ceiling remain unchanged.

The Conversation Model Bench will gain a reliability-cohort mode that repeats selected scenarios as fresh Conversations, records each iteration and aggregate completion/failure evidence, and fails normally when any repeated turn fails a hard Conversation check. Deterministic native-provider tests will supply the authoritative 429/stall fault matrix. Release guidance will distinguish provider-side fault injection from optional Network Link Conditioner testing of the browser-to-Gateway stream.

The shared Conversation UI Surface will keep Activity visible by default for Admins and Users, while giving each assistant turn a real whole-Activity disclosure at the header. Optional reasoning, Tool, and Retrieval summaries will remain a separate nested detail disclosure. The same behavior will automatically apply to ordinary User Conversations and Admin Test User Sessions through their shared module.

## User Stories

1. As a User, I want a temporary provider rate limit to recover automatically before any answer begins, so that a brief upstream capacity event does not discard my turn.
2. As a User, I want Sage to use the same configured model during recovery, so that reliability does not silently change answer provenance.
3. As a User, I want a recovered request to preserve the exact Conversation and Tool evidence, so that the answer remains grounded in the same context.
4. As a User, I want retry attempts bounded, so that a degraded provider cannot hold my turn indefinitely.
5. As a User, I want a request that has started producing answer, reasoning, or Tool output not to be replayed, so that I do not receive duplicated or conflicting output.
6. As an Admin, I want HTTP 429 to share the existing model-request recovery budget, so that failure categories cannot multiply retries independently.
7. As an Admin, I want non-transient provider rejections to remain terminal, so that invalid credentials or invalid requests are not repeatedly submitted.
8. As an Admin, I want Sage to respect short provider retry guidance, so that it does not immediately repeat a request during a known rate-limit window.
9. As an Admin, I want provider retry waits capped, so that an excessive Retry-After value cannot create an unbounded Conversation delay.
10. As an Admin, I want retry delay and outcome visible as sanitized Activity and Conversation Trace evidence, so that I can distinguish recovery from Tool or Retrieval latency.
11. As an Admin, I want provider response bodies excluded from user-facing errors, Activity, logs, and exports, so that transient recovery does not weaken secret handling.
12. As an Operator, I want completed Tool batches executed only once during model-request recovery, so that retries do not duplicate external work or cost.
13. As an Operator, I want the retry policy to stay internal rather than becoming another configuration surface, so that Instances share one tested reliability contract.
14. As a release owner, I want selected scenarios repeated through fresh Conversations, so that a single healthy sample cannot stand in for reliability evidence.
15. As a release owner, I want every cohort iteration recorded independently, so that early clustered failures remain visible instead of disappearing inside aggregate timing.
16. As a release owner, I want a cohort with any hard Conversation failure to fail the benchmark result, so that a partial success rate is not reported as ship-ready.
17. As a release owner, I want benchmark artifacts to record requested repetition and completed turn counts, so that sample size is explicit.
18. As a release owner, I want fresh Conversation identity and cleanup verified for every iteration, so that Conversation Memory cannot make later iterations appear healthier.
19. As a release owner, I want provider-reported cached-token observations retained when available, so that warm-provider evidence is not mislabeled as cache-neutral.
20. As a developer, I want scripted native-provider tests for `429 → success`, `stall → 429 → success`, and bounded 429 exhaustion, so that Jim's exact failure classes are deterministic regressions.
21. As a developer, I want Retry-After parsing and capping tested independently, so that provider guidance cannot create accidental long sleeps.
22. As a developer, I want retry-delay tests to avoid real production-duration sleeps, so that the deterministic suite remains fast.
23. As a tester, I want browser network conditioning documented separately from provider fault injection, so that each test is interpreted at the seam it actually exercises.
24. As a tester, I want poor-signal browser checks to cover pre-answer disconnect, post-partial-answer disconnect, and delayed streaming, so that field connectivity failures preserve the established fallback and partial-output behavior.
25. As a User, I want Activity available when I need to understand what Sage did, so that the transparent prototype remains inspectable.
26. As a User, I want to collapse the complete Activity body for an assistant turn, so that operational rows do not dominate the Conversation.
27. As a User, I want the Activity header and current live status to remain visible when collapsed, so that hiding detail does not look like the work disappeared.
28. As a User, I want optional summaries controlled separately from whole-Activity visibility, so that `Show details` has one clear meaning.
29. As an Admin, I want ordinary User Conversations and Test User Sessions to expose identical Activity behavior, so that customer testing remains representative.
30. As an accessibility user, I want the whole-Activity and optional-detail disclosures to expose accurate expanded state and controlled regions, so that assistive technology can operate them reliably.
31. As an Operator, I want Activity presentation changes not to alter trace streaming, persistence, export, retention, or deletion, so that UI polish does not change the data lifecycle.
32. As a maintainer, I want these corrections at the existing provider, benchmark, and shared Conversation seams, so that the change adds no planner, classifier, response rewrite, provider failover, or duplicate chat path.

## Implementation Decisions

- Extend the native Model Provider error interface so an HTTP rejection can carry a sanitized optional retry delay derived from the response headers before the response body is consumed.
- Classify only HTTP 429 alongside the existing temporary upstream statuses. Authentication, authorization, validation, and other non-transient 4xx responses remain non-retryable.
- Keep one three-attempt budget per logical model request. A stall followed by a 429 has only the attempts remaining in that same budget.
- Preserve byte-for-byte request identity across attempts, including model, messages, Tools, parameters, and reasoning configuration.
- Apply a small internal exponential delay with jitter before eligible retries. Prefer a valid short Retry-After delay, cap all delays at a small internal maximum, and expose only elapsed Retry Delay timing.
- Keep the 30-second first-event boundary and 180-second active request timeout unchanged in this slice.
- Continue making any answer, hidden provider reasoning event, Tool call, or other provider stream event the hard cutoff for model-request recovery.
- Do not replay a completed Tool batch. A post-Tool model retry receives the already-correlated Tool results in the identical logical request.
- Extend the Conversation Model Bench through its existing public CLI with a positive repetition count that defaults to one. Each repetition produces an independently identified scenario result and a fresh Conversation lifecycle.
- Preserve normal hard checks for every repetition. Aggregate run status fails when any repeated scenario has a hard failure; latency and prose variance retain their existing warning severity.
- Report repetition, attempted turn count, completed turn count, and failed turn count without claiming statistically powered provider reliability from a small sample.
- Keep deterministic provider fault behavior in Sage's native-provider test adapter rather than adding a production fault switch or a browser-only simulation.
- Document Network Link Conditioner as an optional manual release check of the browser-to-Gateway Conversation Streaming Transport. It is not evidence for Gateway-to-Model-Provider behavior.
- Keep the Trace Visibility Posture shared and detailed for both Admins and Users during the prototype phase.
- Add a whole-Activity disclosure at the existing shared Activity module. Default it open, retain the Activity header and live status when closed, and keep optional summaries behind a distinct nested disclosure.
- Do not change Conversation Trace payloads, Activity Step payloads, streaming event order, persistence, exports, session deletion, Test User identity, feedback capture, or Conversation state.

## Testing Decisions

- The native provider seam is authoritative for retry classification, request identity, Retry-After parsing/capping, bounded delay, provider-event cutoff, attempt exhaustion, and post-Tool result reuse. Scripted local HTTP responses will test behavior without a live provider.
- The Conversation Model Bench public interface is authoritative for reliability-cohort behavior. Unit tests will use the existing fake environment/client adapters and assert fresh scenario execution, independent results, cleanup, aggregate counts, and hard-failure propagation.
- The shared Conversation Activity module is authoritative for UI behavior. Component tests will use accessible names and expanded/controlled relationships to prove that the complete timeline/Trace body collapses while the header remains, and that optional summaries remain independently controlled.
- Ordinary logged-in and Admin Test User adapters need only focused parity assertions because ADR-0032 already makes the shared User Conversation module their common implementation.
- Existing frontend transport tests remain authoritative for pre-output fallback and partial-output preservation. Manual Network Link Conditioner checks validate those behaviors over a real remote stream; they do not replace deterministic tests.
- Run focused tests during each slice, then the complete Sage workspace tests, parent benchmark tests, frontend test suite, frontend production build, Sage formatting, Clippy, and `enclave_web` check before publication.
- Perform browser verification at desktop and compact viewport sizes for both ordinary User Conversation and Admin Test User Session Activity.

## Out of Scope

- Switching Model Provider, model, cluster, reasoning effort, prompt, Tool selection, or routing.
- Provider or cluster failover.
- Retrying after any model stream event or replaying partial answer content.
- Increasing the three-attempt ceiling or changing the 30-second first-event boundary.
- Retrying arbitrary 4xx responses.
- A production fault-injection switch, deployment setting, or Admin retry control.
- Claiming that a small live cohort is a statistically powered provider availability measurement.
- Automating macOS Network Link Conditioner in CI or using it as provider-side failure evidence.
- Hiding Activity by actor type, adding User Type trace policies, or removing Activity from persisted Conversations and exports.
- Changing retrieval, Curated Resources, answer style, or model-led Tool autonomy.
- Production deployment or customer-impacting release actions in the Feature Dev loop.

## Further Notes

The exact upstream reason for the observed 429 remains outside sanitized application logs. It may represent account rate limiting, provider router throttling, or temporary model capacity. This work does not infer that cause; it handles the status conservatively at the only safe recovery point before model output.

The deployed August 10 evidence showed two upstream 429 responses among forty-two model-provider HTTP calls during the customer window, but those two responses caused two complete User turn failures because 429 was terminal. The first fresh investigation probe later needed two silent retries and recovered on its third attempt after roughly 74 seconds, while eleven following fresh Conversations completed in roughly 7–10 seconds. This supports deterministic mixed-failure coverage and repeated release evidence without treating application Conversation caching as the established cause.
