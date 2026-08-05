# Provider Stall, Continuity, and Latency Verification

Date: 2026-08-05

Scope: implementation verification for PRD #599 and delivery issues #600-#603.

## Outcome

The implementation is complete and deterministic verification is green. It:

- preserves provider continuity state privately within the current bounded Tool
  loop;
- abandons and retries a completely silent provider request once after 20
  seconds, using the same model and identical logical request;
- never retries after a provider event and never replays an executed Tool;
- records optional numeric usage counts in the existing sanitized Conversation
  Trace lifecycle; and
- bounds private continuity state to 1 MiB per response and in aggregate for the
  turn.

The live demo was intentionally not changed by this work. At verification time it
was healthy but still deployed parent revision `60aaa11` and Sage revision
`9873fac`, both preceding this implementation. Therefore the live observations
below are a pre-change baseline, not post-change release proof.

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

## Release boundary

The merge gate is satisfied by deterministic protocol and product tests. Release
verification still requires deploying the new parent and Sage revisions to an
approved staging/demo target, confirming the effective configured model, and
replaying the complete customer suite once there. That replay should capture
first-provider-event and total latency, Tool batches, usage observations when
returned, and content-free stall/recovery outcomes. It must be judged on Tool
selection, grounding, continuity, latency, and usefulness rather than exact prose.

Deployment itself remains outside PRD #599 and was not performed during this
implementation task.
