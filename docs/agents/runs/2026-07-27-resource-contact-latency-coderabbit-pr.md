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

## Corrected-commit confirmation

- CodeRabbit examined the replies on `d622040308d371ace8221a320fd7d3ef68940400`, explicitly confirmed all 3 actionable inline findings as addressed, and automatically resolved all 3 review threads.
- The provider-neutral split-argument safety fix and both accepted nits are included in the same corrected commit and regression suite.
- No new finding was produced for the corrected commit. The branch-level CodeRabbit status remains a successful skip because automatic reviews are disabled for the non-default `staging` base; the explicit full review and per-thread confirmations are the review evidence.
- Sage PR #29 is open, non-draft, mergeable, and `CLEAN` at the corrected commit.

## Required checks

- Parent: [backend security](https://github.com/enclave-free/enclave.free/actions/runs/30351768993/job/90250661657), [frontend security](https://github.com/enclave-free/enclave.free/actions/runs/30351768993/job/90250661605), [frontend production runtime](https://github.com/enclave-free/enclave.free/actions/runs/30351768993/job/90250661749), and [demo PDF drift](https://github.com/enclave-free/enclave.free/actions/runs/30351768993/job/90250661672) passed at `55c9e10f9a9f5248bfa00cdba8e3d324fc50be2c`.
- Parent [Dependency/SAST](https://github.com/enclave-free/enclave.free/actions/runs/30351768993/job/90250661580) failed only at `npm audit` on the current PostCSS and React Router advisories. The PR changes neither `frontend/package.json` nor `frontend/package-lock.json`, so this is recorded as an unrelated baseline dependency failure rather than expanding this feature into a dependency migration. A reviewer-facing explanation is on [PR #540](https://github.com/enclave-free/enclave.free/pull/540#issuecomment-5103107933).
- Sage: explicit full review completed, every actionable thread is resolved, and the corrected branch is mergeable.
