# Issue #626 Session — Bounded Pre-Output Provider Rate-Limit Recovery

## Fixed Point

- Parent repository: `50f0157d04d145e3d5419a87d3392e66e51c82a7`
- Sage: `e072834d849a1f5363c7fb22027f56150ef0b9d7`
- Issue: [#626](https://github.com/enclave-free/enclave.free/issues/626)
- Sage implementation: `df70528cf4c5baf1dc4bdf4e4f066db5b4924f56`

## Public Seam

The existing native Model Provider adapter and same-model request recovery loop
are authoritative. No provider, model, prompt, Tool-routing, failover, or
operator configuration surface was added.

## TDD and Corrections

Deterministic local HTTP-provider tests cover:

- `429 -> success` with identical request reuse;
- `stall -> 429 -> success` on the third shared attempt;
- `stall -> 429 -> 429` and `429 -> 429 -> 429` exhaustion with no fourth call;
- Retry-After seconds, HTTP-date, malformed, and capped-delay behavior;
- provider-event cutoff and private response-body redaction;
- post-Tool result reuse without Tool replay; and
- one stable retry Activity row through multiple schedules and recovered or
  exhausted terminal state.

The review loop added the mixed stall/rate-limit exhaustion regression and
replaced an initial ID-prefix policy inference with typed
`TraceDeltaSnapshotWrite::{Append, ReplaceById}` semantics.

## Behavior

- A pre-output HTTP 429 shares the existing three-attempt same-model budget.
- A valid short Retry-After value guides the delay; otherwise a short capped
  exponential delay with jitter applies.
- Any provider event still ends recovery eligibility for that attempt.
- A completed Tool batch is never replayed.
- Retry delay and outcome remain content-free.
- Scheduled retry Activity is replaced by recovered/succeeded or
  exhausted/failed evidence under one logical identity; ordinary trace deltas
  still append.

## Verification

```text
cargo fmt --all -- --check — passed
cargo clippy --all-targets --all-features -- -D warnings — passed
cargo test --all-features --quiet — 188 library + 66 main tests passed
cargo check -p sage-core --bin enclave_web — passed
git diff --check — passed
Sage worktree — clean
```
