# Issue #627 Session — Repeatable Fresh Conversation Reliability Cohorts

## Fixed Point

- Parent repository: `cbdb74633cca18628a953e8bf78b400c75479d26`
- Issue: [#627](https://github.com/enclave-free/enclave.free/issues/627)
- Spec: [#625](https://github.com/enclave-free/enclave.free/issues/625)

## Public Seam

The existing Conversation Model Bench CLI and `run_bench` artifact are the
public seam. No second benchmark runner or production fault switch is added.

## TDD Evidence

RED coverage was added first for:

- positive `--repeat` parsing with a backwards-compatible default of one;
- independent fresh Conversation identifiers and cleanup for every repetition;
- preservation of an intermittent failed repetition as a hard run failure;
- aggregate requested/run/attempted/completed/failed counts; and
- the distinction between provider-reported zero cached tokens and no cached
  token observation.

The focused tests failed before the runner accepted repetitions and exposed the
new evidence, then passed after the implementation.

## Implementation

- Repeat every selected scenario through a fresh `run_scenario` lifecycle.
- Identify every result by scenario and repetition without changing existing
  scenario IDs.
- Record completion on every serialized turn and aggregate reliability counts
  at candidate and run scope.
- Preserve the existing hard-check summary so any failed repetition keeps the
  candidate and run failed.
- Record provider usage observation count and cached-token evidence without
  treating an absent field as zero.
- Document reliability-cohort interpretation and the separate browser network
  conditioning seam.

## Verification

```text
python3 -m unittest \
  scripts.benches.test_conversation_model_bench.ConversationModelBenchTest.test_bench_docs_match_direct_write_runner_contract \
  scripts.benches.test_conversation_model_bench.ConversationModelBenchTest.test_cli_defaults_to_one_repetition_and_rejects_non_positive_values \
  scripts.benches.test_conversation_model_bench.ConversationModelBenchTest.test_reliability_cohort_uses_fresh_conversations_and_reports_turn_counts \
  scripts.benches.test_conversation_model_bench.ConversationModelBenchTest.test_reliability_cohort_preserves_each_failed_iteration_as_a_hard_failure \
  scripts.benches.test_conversation_model_bench.ConversationModelBenchTest.test_stream_diagnostics_distinguish_observed_zero_cached_tokens_from_absence

Ran 5 tests — OK

python3 -m unittest scripts.benches.test_conversation_model_bench

Ran 66 tests — OK
```

## Boundaries Preserved

- Default execution remains one scenario run.
- No live-provider fault injection or production configuration surface exists.
- Network Link Conditioner remains optional and manual; it tests the
  browser-to-Gateway transport and is not provider-recovery evidence.
- A small sequential cohort is not described as a statistically powered
  availability measurement or as cache-neutral.
