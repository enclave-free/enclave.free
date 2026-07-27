# PRD: Reliable Curated Resource Contact Lookup and Attributable Conversation Latency

## Problem Statement

Users can receive useful Curated Resource referrals in one turn and then lose
grounding on a direct follow-up asking for an email, phone number, website,
address, or other contact detail. Sage may answer from Conversation context
without calling `find_resources` again, even though contact details should come
only from the Admin-vetted Resource Directory. The current faceted Resource
Directory search also cannot target an organization name or exact contact value,
and its bounded response does not report whether more matching Curated Resources
exist. Sage can therefore imply that a short result set is complete when it is
only the first bounded page.

At the same time, slow User Conversations remain difficult to attribute. Existing
Conversation Trace metadata records total model-step, Tool, and turn duration,
but it does not clearly distinguish Tool planning, final-answer inference,
provider first-event wait, Resource Directory lookup, **Retrieval**, or the point
at which an expected Curated Resources call was omitted. Operators cannot tell
whether a slow turn omitted a Tool during model planning, attempted a Tool that
timed out, or simply waited on the Model Provider.

## Solution

Make contact-detail requests and follow-ups a required Curated Resources
Tool-planning behavior whenever that Tool Set is enabled. Extend
`find_resources` with exact and hybrid query matching over organization and
contact fields, and return complete bounded-result metadata so Sage knows when
results are partial. Format Tool results and planning instructions so final
answers never claim completeness unless the Tool proves it.

Add content-free Tool Selection Observations and attributable timing around the
existing Sage-owned Model-Driven Tool Loop. Show meaningful selection, omission,
Tool, retry, and timing events through Activity and Trace Deltas while emitting
privacy-safe structured runtime logs for operational correlation. Add bounded
timeouts and conservative retries to the read-only Curated Resources and
Knowledge Search calls without expanding provider failover or retrying
state-changing Tools.

## User Stories

1. As a User, I want Sage to look up contact details again when I ask for an email, so that the answer comes from the current Resource Directory rather than Conversation memory.
2. As a User, I want the same fresh lookup for phone numbers, websites, addresses, secure channels, and other contact methods, so that contact grounding is consistent.
3. As a User, I want a contact follow-up to retain the organization, jurisdiction, language, and help type already established in my Conversation, so that I do not need to repeat context.
4. As a User, I want Sage to search by an exact organization name, so that similarly named resources do not displace the organization I asked about.
5. As a User, I want Sage to search by an exact email address or phone number when I provide one, so that I can confirm which Curated Resource it belongs to.
6. As a User, I want reasonable partial-name and contact-value matching, so that punctuation, capitalization, spacing, or phone formatting do not prevent a useful lookup.
7. As a User, I want local and verified Curated Resources to retain their existing ranking priority after contact relevance is considered, so that precise matching does not erase geographic relevance.
8. As a User, I want Sage to say when no matching contact is present, so that it does not invent or reconstruct contact details.
9. As a User, I want Sage to distinguish all currently matching Curated Resources from the first page of matches, so that a short list is not presented as exhaustive.
10. As a User, I want Sage to offer or retrieve another page when more matching Curated Resources exist, so that I can continue exploring without starting over.
11. As a User, I want a complete result claim to remain scoped to currently ready Curated Resources matching my filters, so that it is not confused with every organization that exists.
12. As a User, I want pending or archived Resource Directory records to remain unavailable, so that search improvements do not bypass Admin curation.
13. As a User, I want contact lookup to respect the Curated Resources Tool Set boundary, so that a disabled Tool is never called without authorization.
14. As a User, I want Sage to explain honestly when Curated Resources are unavailable for my turn, so that it does not pretend a lookup happened.
15. As an Admin, I want the Resource Directory to remain the authority for Curated Resource contact details, so that corrections are reflected on the next lookup.
16. As an Admin, I want exact contact matching to work without adding a separate semantic index, so that the managed directory remains operationally simple.
17. As an Admin, I want existing scope, verification, language, and display-order behavior preserved within equivalent match quality, so that search precision does not silently rewrite curation policy.
18. As an Admin reviewing Test & Feedback, I want Activity to show that Curated Resources was selected and executed for a contact follow-up, so that I can judge grounding directly.
19. As an Admin reviewing a failed contact turn, I want Activity to show that a Curated Resources lookup was expected but not selected, so that the failure is not mistaken for an empty directory.
20. As an Operator, I want Tool planning, final-answer inference, Resource Directory lookup, Retrieval, Tool execution, provider first-event wait, retries, and total turn duration separated, so that slow turns can be attributed.
21. As an Operator, I want each Tool Selection Observation to distinguish enabled Tools from model-selected Tools, so that authorization and model choice are not conflated.
22. As an Operator, I want a selected Tool to produce an attempted, succeeded, timed-out, or failed outcome, so that Tool calls cannot disappear silently between planning and execution.
23. As an Operator, I want provider first-event wait labeled as a proxy rather than internal cluster queue time, so that the product does not claim visibility the Model Provider does not expose.
24. As an Operator, I want privacy-safe structured logs that correlate high provider wait with missed expected Resource Directory lookup, so that degradation hypotheses can be tested from real observations.
25. As an Operator, I want structured logs to omit Conversation Content, contact values, Tool output, credentials, and raw reasoning, so that diagnosis does not create a second content store.
26. As an Operator, I want slow or unavailable read-only Resource Directory lookup and Retrieval calls to terminate within bounded budgets, so that a Tool cannot hang a Conversation indefinitely.
27. As an Operator, I want a transient read-only lookup failure retried at most once, so that brief network failures can recover without multiplying latency unpredictably.
28. As an Operator, I want valid empty results and validation failures returned without retry, so that retries do not manufacture data or waste time.
29. As an Operator, I want state-changing Tools excluded from automatic retry, so that observability work cannot duplicate writes.
30. As a maintainer, I want the behavior tested through real Conversation and internal Resource Directory seams, so that tests cover user-visible outcomes instead of private helper names.
31. As a maintainer, I want the affected customer prompts replayed once after implementation, so that the original contact and incomplete-list failures are verified without building a degraded-cluster experiment.
32. As a maintainer, I want existing provider fallback and final-answer retry behavior left unchanged, so that this focused change does not introduce a new inference recovery architecture.

## Implementation Decisions

- Preserve ADR-0023 and ADR-0027. Sage continues to expose enabled Tool contracts
  to the model, the model returns typed Tool decisions, Sage executes authorized
  calls, and final user-visible prose uses the plain answer path.
- Do not add a hidden deterministic router or bypass the Model-Driven Tool Loop.
  The Curated Resources planning instruction and `find_resources` Tool contract
  must state that a current request or follow-up for contact details requires a
  fresh Tool call when the Tool Set is enabled. The policy must explicitly cover
  email, phone, URL/website, address, secure channel, and equivalent contact
  language in the Conversation's supported languages.
- If the model omits `find_resources` when a conservative content-free contact
  cue is present, record a missed Tool Selection Observation. The observation is
  diagnostic only: it must not authorize, synthesize, or execute a Tool call.
- A contact follow-up may use recent Conversation context to identify the
  organization, jurisdiction, language, or help type, but final contact details
  must come from the fresh Tool result. The plain-answer instruction must forbid
  contact details copied only from earlier assistant prose.
- Extend the `find_resources` arguments with an optional free-text query and a
  continuation offset. Keep help type, region, and language as independent
  filters. Inventory requests continue to omit help type.
- Extend the internal Resource Directory search request with `query`, `limit`,
  and `offset`. Extend its response with the normalized query, `total_count`,
  `returned_count`, `limit`, `offset`, `has_more`, and `next_offset` in addition
  to resources, resolved jurisdiction, and help type.
- Use offset pagination for this bounded SQLite directory. No opaque cursor or
  new pagination service is needed in this slice.
- Match exact normalized resource ID, organization name, email, phone, URL,
  secure-channel value, or address before partial matches. Normalize case and
  surrounding whitespace; compare phones by digits while retaining stored
  display formatting; treat punctuation and ordinary spacing differences in
  organization names as equivalent where practical.
- Hybrid fallback may match organization-name prefixes/substrings and contact
  value substrings, then description text. It must not introduce vector search,
  external web search, or a new Resource Directory index service.
- Rank contact/query relevance before the existing curation order, then preserve
  scope specificity, verification status, language preference, display order,
  and name within equivalent relevance. Do not add organization-specific boosts.
- Apply the same ready-status, jurisdiction, help-type, language, and query
  predicates to the count and page queries. `total_count` must describe the
  complete filtered set before `limit` and `offset`.
- Tool output must begin with bounded-result metadata such as “Showing 5 of 12
  matching ready Curated Resources.” When `has_more` is true, it must say that
  more results are available and provide the next offset to the model.
- The final-answer instruction must prohibit “all,” “every,” “complete list,” or
  equivalent claims when `has_more` is true or completeness is unknown. When
  `has_more` is false, completeness language must remain scoped to currently
  ready Curated Resources matching the supplied filters.
- Add a truncation warning to Tool Trace and Activity when `has_more` is true.
  Trace metadata may include counts, offsets, Tool names, statuses, and timing,
  but must not duplicate contact values or full Tool output.
- Add a Tool Selection Observation for each planning round. It records enabled
  Tool names, selected Tool names, selection count, whether Curated Resources
  was expected by the conservative contact cue, and whether that expectation
  was missed. It records no user text, model reasoning, or Tool arguments.
- Make Tool Selection Observations visible through a dedicated Trace Delta and
  Activity row. A selected call must be followed by an attempted Tool event and
  a terminal succeeded, timed-out, guarded, or failed event.
- Separate timing into Tool-planning model duration, final-answer model duration,
  final-answer provider response-header wait, final-answer first-provider-event
  wait, per-Tool execution duration, Resource Directory lookup and Retrieval
  duration, retry delay, and total Conversation turn duration. Existing stable
  Conversation and message IDs may
  correlate events, but logs must not include Conversation Content.
- Treat final-answer first-provider-event time as a provider-wait proxy that
  includes network, provider queueing, and model startup. Do not label it as
  measured internal cluster scheduling. Non-streaming Tool-planning calls expose
  total model-step duration only unless the provider later supplies a finer
  signal.
- Show meaningful Tool selection, omission, retry, timeout, and timing through
  Activity and live Trace Deltas. Fine-grained Conversation Turn Timing remains
  transient and must not become Audit Log evidence. Structured runtime logs are
  a Deployment Surface and must remain content-free.
- Emit one structured runtime event per phase and Tool decision with a stable
  event name, correlation identifiers, actor kind, enabled/selected Tool names,
  phase, attempt, outcome, duration, and missed-expected-resource-lookup boolean. Do
  not log prompts, answers, contact data, Tool results, auth headers, secrets, or
  raw Reasoning Trace content.
- Instrumentation must classify each expected contact-lookup turn as: not selected by
  the model, selected and attempted, attempted and timed out/failed, or completed.
  This distinguishes skipped Tool selection from Tool execution degradation.
- Introduce a reusable timeout/retry policy for read-only lookup Tools, but
  enable it only for Curated Resources and Knowledge Search in this slice.
- Curated Resources receives a five-second per-attempt timeout, at most two
  attempts, and an eight-second total budget. Knowledge Search receives a
  thirty-five-second total budget and at most one retry only when the first
  attempt fails quickly enough to remain within that budget.
- Retry only connection failures, timeouts with remaining budget, and HTTP 502,
  503, or 504 responses. Use a short bounded backoff. Do not retry HTTP 4xx,
  malformed contracts, valid empty results, successful calls, or any
  state-changing Tool.
- A timed-out or exhausted lookup Tool returns an ordinary failed Tool result,
  emits retry/timeout trace evidence, and lets the existing bounded replanning
  behavior continue. It must never be reported as a successful empty result.
- Do not add new Agent Settings for timeout values in this first slice. Keep the
  initial budgets as named runtime policy constants with focused tests so a later
  evidence-backed change remains small.
- No database schema migration is required. Exact and hybrid search use the
  existing structured Resource Directory records and contact JSON.
- No ADR is required. This spec implements the existing Model-Driven Tool Loop,
  transparent Conversation Trace, final-answer, and latency-attribution
  decisions rather than changing those boundaries.

## Testing Decisions

- The highest acceptance seam is a real User Conversation through the unified
  `/llm/chat` and `/llm/chat/stream` behavior with Curated Resources enabled.
  Tests should assert final answers, Tool use, Activity/Trace evidence, and
  timing/timeout outcomes rather than private helper calls.
- Add public Conversation tests for an initial organization request followed by
  email, phone, website, and address follow-ups. Cover English and Spanish,
  including the reported “me puedes dar el email…” shape.
- Verify each contact follow-up produces a fresh `find_resources` Tool call and
  uses returned contact data. Verify earlier assistant prose alone is never the
  authority for the final contact value.
- Add a Conversation test where the model omits Tools for a contact cue. The
  answer may continue under the existing model-driven contract, but Activity,
  Trace, and structured log capture must identify the missed expected lookup.
- Add a disabled-Tool-Set test proving the contact diagnostic does not authorize
  or execute Curated Resources.
- Extend the existing Resource Directory backend tests for exact organization,
  resource ID, email, normalized phone, URL, secure channel, and address matching;
  partial-name fallback; unchanged ready/scope/help-type/language filters; stable
  relevance and curation order; counts; offsets; final page; and empty results.
- Verify pending and archived Curated Resources are excluded from both results
  and `total_count`.
- Extend the existing Sage `find_resources` Tool tests to assert query and offset
  forwarding, count metadata, partial-result wording, next-offset instructions,
  truncation warnings, and completeness wording on the final page.
- Add timeout tests with a deliberately slow internal search endpoint. Verify the
  Tool emits a timed-out terminal event, remains within the total budget, and
  does not convert timeout into an empty successful result.
- Add retry tests for transient connection/502/503/504 failures followed by
  success, exhausted transient failure, HTTP 4xx, malformed response, and valid
  empty response. Assert at most one retry and bounded backoff.
- Add a guard test proving state-changing Admin Config Tools are not passed
  through the automatic retry policy.
- Add Agent Runtime tests for phase attribution and Tool Selection Observations:
  enabled versus selected Tools, no-Tool decisions, selected-but-not-attempted
  prevention, Tool timeout, retry, success, provider response headers, first
  provider event, final-answer completion, and total turn timing.
- Add streaming transport tests for event order: Tool selection, Tool call,
  optional retry, Tool result, final-answer provider timing, answer deltas, final
  trace, and completion.
- Add non-streaming tests proving the same final Tool decision and terminal
  outcomes are accumulated even though live answer deltas are unavailable.
- Add Conversation UI Surface tests proving the new Tool Selection Observation,
  missed-lookup state, timeout, retry, and phase timing render accessibly without
  exposing Tool arguments or contact values in summary rows.
- Verify fine-grained Conversation Turn Timing is not written to the Audit Log.
  Verify structured operational events contain only the allowlisted metadata.
- Replay the affected customer contact and inventory prompts once across the
  relevant User Types after implementation. This is a regression check, not a
  normal-versus-degraded cluster experiment.
- Run targeted Resource Directory backend tests, targeted Sage Agent Runtime
  tests, targeted frontend Conversation tests, then the full backend, Rust, and
  frontend suites plus the frontend production build.

## Out of Scope

- Uploading or inventing missing Bitcoin guidance.
- WLC-specific ranking, hard-coded organization boosts, or changing Resource
  Directory metadata to favor one organization.
- A deterministic intent classifier that directly forces Tool execution or
  bypasses the Model-Driven Tool Loop.
- Provider- or cluster-level failover, automatic degraded-run detection, routing
  traffic to another Model Provider, or changing the configured model chain.
- A controlled normal-versus-degraded cluster experiment or statistically
  powered provider latency benchmark.
- Claiming direct measurement of the Model Provider's internal queue or cluster
  scheduler when only response timing is available.
- New Resource Directory vector embeddings, external semantic search, or web
  search fallback for contact details.
- Retrying model calls as part of lookup recovery or changing existing
  final-answer retry semantics.
- Automatic retry for Admin Config writes, other state-changing Tools, or
  requests whose mutation outcome is unknown.
- A Resource Directory pagination UI. Continuation in this slice is model-driven
  through the Tool contract and ordinary Conversation follow-ups.
- Production deployment, production data mutation, or live failover testing.

## Further Notes

Published as GitHub issue #533 with the `ready-for-agent` label.

This work extends, rather than replaces, the latency direction in GitHub issues
#486 and #490. Those issues cover the broader Admin Conversation critical path
and end-to-end evidence. This spec focuses on User Conversation contact
grounding, bounded Resource Directory completeness, missed Tool-selection
visibility, and conservative read-only lookup resilience.

The Model Provider does not currently expose internal queue or cluster scheduler
timing. Provider response-header and first-event waits are therefore correlation
signals, not proof of a particular infrastructure cause. The new stage
classification can prove whether Sage omitted, attempted, failed, or completed a
Tool call; causal claims about upstream cluster degradation still require
provider-side evidence.

The exact customer prompt replay remains evidence outside the product's active
storage lifecycle as documented in the July 27 demo retrieval run. New runtime
logs and traces must not copy those prompts or their generated answers.
