# Issue #627 Review — Repeatable Fresh Conversation Reliability Cohorts

## Review Range

- Fixed point: `cbdb74633cca18628a953e8bf78b400c75479d26`
- Implementation: `6d63f3d7ea0ca4a0658b9af9af04f3f52147a70f`
- Diff: `git diff cbdb746...6d63f3d`
- Commit: `6d63f3d test: add fresh conversation reliability cohorts (#627)`

## Standards

PASS — no documented repository-standard violations and no actionable Fowler
baseline smells.

- Python naming, typing, documentation, and tests follow repository
  conventions.
- Candidate- and run-level reliability summaries share one implementation and
  are different scopes, not duplicated logic.
- The small test clients remain scenario-specific; extracting them would add
  speculative abstraction.

## Spec

PASS — no missing or partial requirement, scope creep, or incorrectly
implemented requirement.

- `--repeat` is positive and defaults to one.
- Every iteration runs a fresh authenticated Conversation lifecycle and cleanup.
- Artifacts identify repetitions and expose attempted/completed/failed counts.
- Existing hard checks preserve aggregate failure semantics.
- Cached-token evidence distinguishes observed zero from absence.
- Guidance keeps native provider fault coverage separate from manual
  browser-to-Gateway Network Link Conditioner checks.

## Independent Verification

```text
python3 -m unittest scripts.benches.test_conversation_model_bench

Ran 66 tests — OK
```

## Disposition

Accepted for integration into issue #629 without corrections. The public bench
contract and deterministic client evidence are the leaf-ticket gate. Compose
health, live fresh-Conversation cohorts, Test Dashboard checks, and their exact
endpoints belong to #629's combined verification record. Network Link
Conditioner remains an optional browser-to-Gateway manual check by design; it
does not prove native Gateway-to-Provider recovery and is not a prerequisite for
accepting this bench-harness slice.
