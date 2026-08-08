# Provider first-event recovery window — feature ledger

Status: In progress

Spec issue: #607  
Implementation ticket: #608

## Goal

Reduce first-turn failures caused by a completely silent model-provider attempt without changing model behavior, prompts, Tool selection, routing, or reasoning configuration.

## Scope

- Increase the internal pre-response provider-stall boundary from 20 to 30 seconds.
- Allow at most two same-model retries for each logical model request (three identical attempts total).
- Preserve the existing rule that any provider event ends retry eligibility.
- Preserve Tool results across model-request recovery and never replay an executed Tool batch.
- Add deterministic regression coverage and repeat Jim's Admin Test-as-User first-turn flow after deployment.

## Non-goals

- Provider or cluster failover.
- Prompt, reasoning-effort, model, Tool, or routing changes.
- A new Instance Setting, Deployment Setting, Agent Setting, or Admin control.
- Retrying after answer, reasoning, or Tool-call data has begun streaming.

## Verification ledger

- [x] Tests fail against the previous 20-second / two-attempt policy.
- [x] Unit and public transport tests prove two silent attempts can recover on the third identical request.
- [x] Exhaustion remains bounded at three attempts across mixed eligible failure categories.
- [x] Executed Tools run once while their results are reused by model retries.
- [x] Sage formatting, lint, tests, and build checks pass.
- [x] Parent checks pass with the updated Sage revision.
- [x] Standards and specification review complete.
- [x] Staging PRs merge with green required checks.
- [x] Complete staging state is promoted to main.
- [ ] Demo runs the exact main parent revision and Sage pin.
- [ ] Jim's first-turn Test-as-User prompt succeeds in repeated fresh sessions.

## Release evidence

Record PRs, revisions, deployed fingerprints, and live verification results here before closeout.

- Sage implementation commits: `d9f6be1`, `6b02e6d`, and `0a06059`; staging PR `enclave-free/sage#48` merged as `ab4cdb8`. Documentation follow-up `enclave-free/sage#49` merged as `fba014c`.
- Sage checks: `cargo fmt --all -- --check`; `cargo test --workspace --all-features` (235 unit tests across targets plus doc tests); `cargo clippy --workspace --all-targets --all-features -- -D warnings`; `cargo check --bin enclave_web`.
- Independent standards review: pass, zero findings.
- Independent specification review: pass, zero Sage-scope findings.
- Parent review terminology and provider-event wording findings were fixed before publication; live deployment acceptance remains in the release checklist below.
- Parent checks: 65 benchmark/harness tests and 3 production Compose-contract tests passed.
- Local CodeRabbit: one minor suggestion rejected because suppressing `exhausted` after a scheduled retry would remove the terminal retry outcome required by the accepted trace contract.
- PR CodeRabbit: one documentation clarification fixed in `0a06059`; incremental review requested.
- Parent CI exposed newly published high-severity advisories on the unchanged staging lockfile. The lockfile was refreshed within existing compatible ranges to `nanoid` 3.3.18/5.1.16 and React Router 7.18.2; `npm audit`, all 389 frontend tests, and the production frontend build passed.
- Parent staging PR `#609` merged as `7b29172` after all required checks passed. Complete staging promotion PR `#610` merged to main as `c29ab83` after both staging-push and promotion CI suites passed.
