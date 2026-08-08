# Provider Stall, Continuity, and Latency Verification

Date: 2026-08-05

Scope: implementation verification for PRD #599 and delivery issues #600-#603.

## Outcome

The implementation is merged, deployed to `demo.enclave.free`, and release
verified. Deterministic verification remains green. The release:

- preserves provider continuity state privately within the current bounded Tool
  loop;
- abandons and retries a completely silent provider request once after 20
  seconds, using the same model and identical logical request;
- never retries after a provider event and never replays an executed Tool;
- records optional numeric usage counts in the existing sanitized Conversation
  Trace lifecycle; and
- bounds private continuity state to 1 MiB per response and in aggregate for the
  turn; and
- recovered a real 20-second completely silent GLM request during the deployed
  customer-suite replay.

The replay also showed that this surgical correction is not a general latency
cure. Two later turns made provider progress and then exceeded the existing
180-second active-stream limit. They failed safely and were not retried. One
successful turn waited 160.2 seconds for its first visible answer. Retrieval and
Resource Directory lookup remained fast throughout.

## Deterministic implementation evidence

Sage verification on revision `fb080ea`:

- `cargo fmt --all -- --check`: passed.
- strict all-target/all-feature Clippy with warnings denied: passed.
- `cargo test --workspace --no-fail-fast`: passed (173 Sage core library tests,
  62 Sage binary tests, plus Tool and documentation tests).
- scripted provider coverage proves silent recovery, exhausted recovery, the
  shared one-retry ceiling, no retry after progress, exact request reuse, no Tool
  replay, optional usage negotiation, malformed/partial usage tolerance,
  per-response and aggregate continuity bounds, and multi-batch continuity.
- privacy coverage proves continuity sentinels are absent from answers, stream
  trace, trace metadata, and the next User turn.
- one combined public-stream acceptance test carries an actual silent recovery,
  two provider-selected Tool batches, private continuity, usage, answer deltas,
  trace deltas, and terminal events through the same transport flow.

Enclave integration verification:

- backend suite: 423 tests passed.
- focused Session Log coverage proves numeric usage observations persist through
  the encrypted trace, survive authorized export, and disappear with Conversation
  deletion.
- frontend suite: 75 files and 389 tests passed.
- production frontend build: passed.
- Compose contract checks: 3 passed; rendered Compose configuration is valid.

Two independent implementation reviews were completed. The final review found no
remaining actionable correctness issue after capability negotiation, continuity
bounds, trace evidence, and lifecycle coverage were hardened.

## Live pre-change baseline

Per-turn timing lines for 14 turns of the existing four-persona customer suite
were captured against the healthy demo. Service history confirms that the harness
subsequently advanced into the fourth persona before its long-running SSH command
session was lost, but it did not produce its final aggregate artifact. No response
error occurred in the 14 captured turns, so this is deliberately recorded as
partial evidence rather than reconstructing missing measurements.

Completed-turn timing:

- first visible answer: 2.6 seconds minimum, 29.5 seconds median, 239.8 seconds
  maximum;
- total turn time: 38.1 seconds minimum, 106.0 seconds median, 309.2 seconds
  maximum;
- 12 of 14 turns used at least one Tool; two no-Tool turns still took 56.3 and
  210.9 seconds total; and
- one direct no-Tool turn waited 78.2 seconds for its first visible answer.

These observations reproduce the customer's severe long-tail latency. They also
show that retrieval is not the universal bottleneck: very slow turns occur even
when Sage selects no Tool. Tool-assisted turns sometimes use several Resource
Directory calls, but direct provider progress can dominate elapsed time by
minutes. The old runtime emits no Model Usage Observation, as expected.

The interrupted harness's remaining test Conversation was identified and deleted
through the normal Conversation lifecycle endpoint. The deletion reported eight
successful targets, including four messages, two memory blocks, the session
record, and the agent record; no failed or skipped cleanup target remained.

## Deployed release evidence

The release was merged through
[Sage PR #46](https://github.com/enclave-free/sage/pull/46) and
[Enclave PR #604](https://github.com/enclave-free/enclave.free/pull/604). All five
Enclave CI jobs passed. The demo was then updated surgically by rebuilding and
replacing Sage only.

Effective deployed state after the replay:

- Enclave parent revision: `898e0f1`;
- Sage revision: `a7d0972`;
- Sage image: `sha256:6f68ee392c0d11d1efaaa25a71b893c1456f318c767253e02608dcf297488aa8`;
- effective Conversation model: `glm-5-2`; and
- all nine Compose services healthy.

The exact four-persona suite in `scripts/benchmark_sessions.json` ran from
19:43:41 through 20:18:32 UTC on 2026-08-05. It completed all five conversational
turns for each persona. Eighteen turns reached the normal terminal event; two
returned the intended temporary-unavailable error after an active model request
hit 180 seconds. Every synthetic Conversation was deleted through the normal
lifecycle with zero failed or skipped cleanup targets.

Post-change timing across all 20 turns:

- first visible answer: 2.9 seconds minimum, 26.2 seconds median, 32.4 seconds
  mean, 70.2 seconds p95, and 160.2 seconds maximum;
- total turn time: 33.8 seconds minimum, 92.9 seconds median, 104.4 seconds mean,
  200.3 seconds p95, and 208.7 seconds maximum; and
- provider first-event wait: 0.6 seconds minimum, 1.1 seconds median, 8.4 seconds
  p95, and 20.001 seconds maximum across 84 request attempts.

The pre-change and post-change samples are small and not paired, so their
comparison is directional rather than a performance claim:

| Measure | Pre-change partial replay (14 turns) | Post-change complete replay (20 turns) |
| --- | ---: | ---: |
| Median first visible answer | 29.5 s | 26.2 s |
| Maximum first visible answer | 239.8 s | 160.2 s |
| Median total turn | 106.0 s | 92.9 s |
| Maximum total turn | 309.2 s | 208.7 s |

Completed-turn trace contained 127 successful Knowledge Search timings with a
220 ms median and 401 ms maximum, plus 43 successful Resource Directory timings
with a 12 ms median and 28 ms maximum. Seventeen of the 18 normally completed
turns used Knowledge Search, 12 used Curated Resources, and one context-complete
follow-up correctly used the direct no-Tool path. This evidence rules out
Retrieval or Resource Directory execution as the dominant latency source in this
run.

Usage reporting was present on all 20 turns and produced 83 provider-reported
observations. The provider returned prompt and total counts but reported
completion count as zero and omitted cached/reasoning counts. Sage correctly
preserved those explicit provider values without inventing missing data, but the
provider's response means this replay cannot use completion usage to explain the
long generations.

## Live recovery proof

Solidarity Networks turn 1 produced no provider event for 20.001 seconds on model
step 0, attempt 1. Sage emitted a content-free `pre_response_stall` observation,
scheduled attempt 2 against the same `glm-5-2` model, and recorded the retry as
recovered. The retry produced its first event in 640 ms, the model selected
Knowledge Search and Curated Resources, and the turn completed with a full answer.
No Tool existed before the stalled request, so no Tool was replayed.

This is direct live evidence that the deployed recovery boundary is active and
that it can rescue the exact provider behavior it was designed for.

## Residual findings

### Active-generation latency

Two turns began responding normally and later had one model request run for
180.001 seconds. Both returned the configured temporary-unavailable error. They
were correctly not retried after progress. Successful individual model requests
also took as long as 126.5 seconds, while the associated Retrieval and Resource
Directory work stayed below half a second.

The root residual is therefore active GLM reasoning/generation, sometimes across
several model-directed Tool rounds. The new telemetry distinguishes this from
complete provider silence. Addressing it would require a separate product choice
about active-stream limits, response length, reasoning behavior, or provider
capacity; none should be smuggled into the silent-stall retry.

### Answer and Tool quality

The replay validated several intended behaviors:

- no answer exposed a literal native Tool-call payload;
- specific Curated Resource contacts appeared in grounded recommendations;
- a truncated Curated Resource lookup explicitly reported 10 of 15 results with
  `has_more=true`; the answer selected a few relevant organizations and did not
  claim to list every result; and
- context-dependent follow-ups could answer directly when another lookup was not
  needed.

The replay was not uniformly good enough to treat as a clean customer acceptance
pass:

- answers were very long: 442 to 1,364 words, with a 958-word median, which is a
  visible contributor to generation time and demo usability;
- one El Chipote/Nicaragua turn searched with Venezuela-oriented resource
  context and recommended Venezuelan organizations before later turns returned
  to Nicaragua-specific resources; and
- one answer advised a family member to create, photograph, and submit a record
  about a released torture survivor without his knowledge after he had said he
  did not want the experience publicized. Distinguishing the family member's own
  observations was reasonable, but recommending covert collection and sharing
  was too permissive for Enclave's tight-consent posture.

These are model judgment/relevance findings, not evidence that the stall,
continuity, or usage implementation malfunctioned. They should remain visible as
separate follow-up quality work rather than being hidden by a broad success claim.

## Release boundary

PRD #599's implementation and release-evidence boundary is complete: the changes
are reviewed, merged, deployed to the approved demo target, running on the
effective configured model, and exercised through the complete four-persona
suite. The real silent-stall recovery succeeded and all test data was cleaned up.

Release verification is therefore **complete with observed residuals**. The two
active-stream failures and the two answer-quality concerns above are not reasons
to roll back this narrow correction, but they are reasons not to characterize
overall demo latency or answer quality as solved.
