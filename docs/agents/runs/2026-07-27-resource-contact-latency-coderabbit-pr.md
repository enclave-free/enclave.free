# CodeRabbit PR Rounds: Resource Contact and Latency

## Pull Requests

- Parent: https://github.com/enclave-free/enclave.free/pull/540
- Sage: https://github.com/enclave-free/sage/pull/29
- Base branch: `staging`
- Head branch: `feature/resource-contact-latency`

## Round 1

- Requested: `@coderabbit full review` on both PRs.
- Parent request: https://github.com/enclave-free/enclave.free/pull/540#issuecomment-5102927078
- Sage request: https://github.com/enclave-free/sage/pull/29#issuecomment-5102927099
- Parent status: CodeRabbit check passed by skipping because reviews are disabled for the `staging` base branch; no PR review findings were produced. Local parent Round 2 had reported no product-code issue.
- Sage status: completed against `3bad5dbf28d1c27098f9759bd7297fecd2d8b639` with 3 actionable inline comments, 1 outside-diff safety comment, and 3 low-value nits.

### Sage findings addressed in `d622040308d371ace8221a320fd7d3ef68940400`

- Load the final-answer attempt once for each paired Model Step/Timing trace.
- Accept usage-bearing `choices: []` provider events as metadata-only rather than failing a valid stream; the adapter still does not request or persist usage.
- Increase the retry test-server join budget from 1 to 10 seconds.
- Hold incomplete snake-case provider-neutral Tool labels until a line boundary so split `Args` cannot be exposed; ordinary explanatory Tool prose still streams immediately.
- Use backend-returned Resource offset/limit values in model-visible page narration.
- Reuse `ConversationTimingOutcome::as_str()` instead of a duplicate status match.

### Sage findings not changed

- The paused-Tokio-time suggestion would add a Cargo feature solely for one already-fast deterministic test; the full suite completes in about 4.5 seconds and the test remains stable with explicit bounded timeouts.
- The 80% docstring warning is repository-wide baseline coverage, not a regression introduced by this PR.

### Verification

- Three new focused regressions passed: usage-only provider event, split provider-neutral Tool arguments, and backend-reported Resource pagination.
- Existing benign Tool-prose same-/cross-delta regressions passed.
- Full Sage suite: 165/165 passed.
- `cargo fmt --all -- --check`, `cargo check -p sage-core --bin enclave_web --no-default-features`, and `git diff --check` passed.

## Required checks

- Parent: backend security, frontend security, frontend production runtime, and demo PDF drift passed.
- Parent Dependency/SAST failed only at `npm audit` on PostCSS/React Router advisories; the PR changes neither `frontend/package.json` nor `frontend/package-lock.json`, so this is recorded as an unrelated baseline dependency failure rather than expanding this feature into a dependency migration.
- Sage: CodeRabbit Round 1 completed; corrected-commit refresh pending.
