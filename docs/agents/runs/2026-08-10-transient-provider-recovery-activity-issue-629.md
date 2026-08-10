# Issue #629 Session — Integrated Transient Conversation Reliability

## Scope

- Parent fixed point: `50f0157d04d145e3d5419a87d3392e66e51c82a7`
- Sage fixed point: `e072834d849a1f5363c7fb22027f56150ef0b9d7`
- Integrated revisions: parent branch `feature/transient-provider-recovery-activity` and canonical Sage staging merge `f41321e` (feature head `e7d0581`)
- Related issues: #625–#629

## Deterministic Provider Evidence

The Sage adapter tests use a local provider double and independently prove the
provider boundary. They do not claim to simulate browser networking or live
model quality.

```bash
cd runtime/sage
LIBRARY_PATH=/opt/homebrew/opt/libpq/lib cargo test --all-features \
  provider_stall_then_rate_limit_recovers_on_the_final_shared_attempt
# 1/1 passed: stall -> 429 -> success, three identical requests

LIBRARY_PATH=/opt/homebrew/opt/libpq/lib cargo test --all-features \
  post_tool_rate_limit_reuses_results_without_replaying_tools
# 1/1 passed: correlated Tool results reused; Tool executed once

LIBRARY_PATH=/opt/homebrew/opt/libpq/lib cargo test --all-features \
  model_retry_delays_fall_back_with_jitter_and_cap_provider_guidance
# 1/1 passed: bounded fallback delay and capped provider guidance
```

The full corrected Sage gate also passed formatting, Clippy with warnings denied,
189 library tests, 67 executable tests, and the `enclave_web` check.

## Integrated Local Candidate

The exact Core, Sage, and frontend Docker images were imported into the isolated
`apple-enclavefree-prototype` Apple-container profile. Startup and an independent
health pass verified the backend health, test, model-test, and frontend endpoints.

The public bench then exercised fresh authenticated Conversation lifecycles
against that running candidate:

```bash
python3 scripts/benches/conversation_model_bench.py \
  --runtime apple \
  --apple-profile apple-enclavefree-prototype \
  --api-base http://127.0.0.1:18001 \
  --scenario admin_no_tools_control \
  --repeat 12 \
  --output /tmp/transient-provider-recovery-cohort.json
# passed: 12 attempted, 12 completed, 0 failed, 192 checks, 0 warnings

python3 scripts/benches/conversation_model_bench.py \
  --runtime apple \
  --apple-profile apple-enclavefree-prototype \
  --api-base http://127.0.0.1:18001 \
  --scenario user_nicaragua_referral_relevance \
  --repeat 4 \
  --seed-resources \
  --output /tmp/transient-provider-recovery-resource-cohort.json
# passed: 4 attempted, 4 completed, 0 failed, 72 checks, 0 hard failures
```

The Resource cohort retained five non-blocking model-quality warnings: four
paragraph-count warnings and one 11.9-second first-Activity warning. It produced
no Conversation, grounding, consent, Tool, or cleanup hard failure.

Final branch review found that the initial cohort summary could count an earlier
failed turn in a multi-turn scenario while allowing a later successful turn to
leave the aggregate green. The generic scenario boundary now emits a hard
completion check for every dispatched turn. A first-turn-failure/later-success
regression proves both candidate and run fail, and the complete benchmark suite
passes 67/67.

## Browser Evidence

Issue #628 already verified the shared Activity renderer at 1440x900 and 390x844
in both ordinary User Conversation and Admin Test User adapters: whole Activity
collapse, nested optional-detail independence, restored state, live header status,
and no compact horizontal overflow all passed. The final integration changed
only tests and the Sage pin after that visual pass; the candidate frontend image
also passed TypeScript and production build. The isolated in-app browser reached
the exact candidate's login and Admin setup surfaces, but the fresh browser had
neither a magic-link user session nor a NIP-07 Admin extension. No auth state was
injected or bypassed, and the prior authenticated shared-renderer evidence is not
misrepresented as a new authenticated session.

Optional Network Link Conditioner remains a browser-to-Gateway manual exercise.
It is not required for deterministic provider-adapter acceptance and was not run
or claimed here.

## Result

The integrated candidate satisfies issue #629's reliability boundary: retries
remain same-model, pre-output, bounded, and observable; post-Tool recovery does
not replay side effects; repeated fresh live Conversations complete and clean up;
and the shared Activity disclosure remains the same in User and Admin adapters.
