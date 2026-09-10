# GLM-5.3 Flash migration

The Enclave conversation model is `glm-5-3-flash`, served through the existing
verified Tinfoil proxy. The default reasoning effort is `low`.

This replaces the GLM-5.2 configuration at the operator's request because that
model is being deprecated. Tests and benchmarks were run before changing source
defaults, then repeated with the new configuration. The work started from
Enclave staging `37082ef` and Sage `f41321e` on September 9, 2026.

## Provider compatibility

The [Tinfoil model catalog](https://inference.tinfoil.sh/v1/models), retrieved
through the verified proxy, lists `glm-5-3-flash` with tool calling and reasoning
support. GLM-5.2 was absent from that catalog but still accepted completion
requests during the baseline run.

Keep the model and reasoning settings together. A direct preflight with
`glm-5-3-flash` and the former `reasoning_effort=none` setting returned reasoning
text in the answer's `content` field. The same request with `low` returned the
requested answer in `content` and reasoning separately. Sage already handles
the separate provider reasoning fields without publishing them as answer text.
The [model publisher's instructions](https://github.com/zai-org/GLM-5/blob/main/README.md)
describe `low`, `high`, and `max` thinking budgets for GLM-5.3 Flash.

The migration updates Compose, Python's diagnostic provider, frontend model
examples in every locale, benchmark/smoke defaults, and the pinned Sage runtime's
own defaults and launch instructions. Explicit operator model overrides remain
supported. The Tinfoil endpoint and proxy configuration are unchanged.

## Apply to an existing deployment

In Admin Deployment Settings, save the Model Provider model (`LLM_MODEL`) as
`glm-5-3-flash`. This saved setting takes precedence over the container's
`LLM_MODEL` environment for Python diagnostics and is the source of generated
runtime env exports. Restarting with a new environment does not overwrite an
existing saved value. The local migration used the normal audited admin update
endpoint, `PUT /admin/deployment/config/LLM_MODEL`.

Update both values in the deployment's `.env`:

```dotenv
TINFOIL_MODEL=glm-5-3-flash
TINFOIL_REASONING_EFFORT=low
```

Existing `.env` values override the new repository defaults. If the deployment
also loads exported files from `runtime/generated`, update or regenerate their
model values: `TINFOIL_MODEL` in `sage.env` and `LLM_MODEL` in
`core-backend.env`. A later env file can otherwise restore the old model. Carry
`TINFOIL_REASONING_EFFORT=low` into any operator override that sets reasoning.

After fetching the updated Sage submodule, rebuild and recreate the app services
using the deployment's normal Compose arguments. For the base local profile:

```bash
git submodule update --init runtime/sage
docker compose -f docker-compose.infra.yml -f docker-compose.app.yml up -d --build core-backend sage frontend
docker compose -f docker-compose.infra.yml -f docker-compose.app.yml exec -T sage printenv TINFOIL_MODEL TINFOIL_REASONING_EFFORT
docker compose -f docker-compose.infra.yml -f docker-compose.app.yml exec -T core-backend printenv LLM_MODEL
```

Expected outputs are `glm-5-3-flash`, `low`, and `glm-5-3-flash`, respectively.
Reapply the appropriate `--env-file` arguments when using generated deployment
files. Verify a fresh conversation as well as the runtime configuration; a
successful model-list health check alone does not exercise inference. Check that
`GET /llm/test` also reports `model: "glm-5-3-flash"`; this catches an old saved
diagnostic-model override that environment inspection alone misses.

## Verification results

The candidate pins Sage `0f24926` ([Sage PR #55](https://github.com/enclave-free/sage/pull/55)).
The local stack was rebuilt and its Sage environment, backend environment, and
`GET /llm/test` all verified as `glm-5-3-flash`; Sage uses `low` reasoning.
Raw local command logs are in `/tmp/enclave-glm53-results`.

| Check                                             | Before                                                         | After                                          |
| ------------------------------------------------- | -------------------------------------------------------------- | ---------------------------------------------- |
| Backend, fresh image                              | 435 passed, 1 error, 1 skipped                                 | 435 passed, same error, 1 skipped              |
| Frontend                                          | 487 passed, 1 timeout; affected file's 6 tests passed on rerun | 488 passed                                     |
| Frontend production build                         | Passed                                                         | Passed                                         |
| Sage host workspace                               | 256 passed                                                     | 256 passed                                     |
| Sage host Clippy and formatting                   | Passed                                                         | Passed                                         |
| Benchmark unit tests                              | 67 passed                                                      | 67 passed                                      |
| Script unit tests                                 | 53 passed                                                      | 53 passed                                      |
| Compose contracts                                 | 3 passed                                                       | 3 passed                                       |
| Frontend HTTP contracts                           | 5 passed                                                       | 5 passed                                       |
| Integration runner with local harness adjustments | 14/18 scripts passed                                           | 14/18 scripts passed; same failure categories  |
| Direct chunk retrieval                            | Functional checks passed; cleanup failed                       | Functional checks passed; same cleanup failure |
| Standalone Sage Linux smoke                       | Endpoint-retry unit test failed                                | Same test failed                               |

### Live model comparison

| Measurement                             | GLM-5.2 / `none` | GLM-5.3 Flash / `low` |
| --------------------------------------- | ---------------: | --------------------: |
| Conversation benchmark completed turns  |            12/12 |                 12/12 |
| Automated conversation scenarios passed |             9/10 |                  8/10 |
| Median first visible answer             |          2.767 s |               2.126 s |
| Median completed turn                   |          3.567 s |               3.307 s |
| Conversation warning checks             |               13 |                     8 |
| Contact-refresh cases completed         |            41/41 |                 41/41 |
| Contact-refresh cases passed            |             7/41 |                  4/41 |
| Contact-refresh cleanup failures        |                0 |                     0 |
| Legacy benchmark completed turns        |            25/25 |                 25/25 |
| Legacy summed response time             |          254.5 s |               162.4 s |
| Legacy median response time             |            6.8 s |                 5.4 s |

The GLM-5.2 conversation failure was failure to surface the seeded vetted
resource. GLM-5.3 Flash passed that scenario, but failed the exact-wording checks
in the knowledge-only and combined knowledge/resource scenarios. Inspection of
those two answers shows safe-place and trusted-people guidance expressed with
different wording. Their automated failure scores are retained, without changing
the benchmark checks. Both consent-boundary answers explicitly refused covert
documentation, although the benchmark's lexical warning still fired for both.

The contact-refresh evaluation is a substantive unresolved issue: both models
often repeated stale contact data instead of refreshing it through the resource
tool. The new model's 4/41 score is worse than the baseline's 7/41 in this run.
This migration therefore demonstrates lower observed latency, not an overall
quality improvement or a clean release gate. The requested deprecation migration
proceeds with these results disclosed.

All five separate admin timing scenarios completed:

| Admin scenario                  | Before: first visible / done | After: first visible / done |
| ------------------------------- | ---------------------------: | --------------------------: |
| No tools                        |              0.919 / 1.160 s |             0.485 / 0.638 s |
| Setup summary                   |              3.603 / 3.628 s |             2.429 / 2.455 s |
| Config only                     |              2.262 / 2.285 s |             2.059 / 2.087 s |
| Natural-language database query |              6.069 / 6.148 s |             4.285 / 4.362 s |
| Direct database select          |              1.848 / 1.875 s |             1.004 / 1.026 s |

### Evidence and commands

- [Machine-readable comparison](agents/runs/artifacts/glm-5-3-flash/comparison.json)
- Conversation artifacts: [before](agents/runs/artifacts/glm-5-3-flash/baseline-conversation.json), [after](agents/runs/artifacts/glm-5-3-flash/candidate-conversation.json)
- Contact artifacts: [before](agents/runs/artifacts/glm-5-3-flash/baseline-contact-eval.json), [after](agents/runs/artifacts/glm-5-3-flash/candidate-contact-eval.json)
- Admin timing: [before](agents/runs/artifacts/glm-5-3-flash/baseline-admin-timing.json), [after](agents/runs/artifacts/glm-5-3-flash/candidate-admin-timing.json)
- [Verified provider preflight](agents/runs/artifacts/glm-5-3-flash/provider-preflight.json) and [model catalog snapshot](agents/runs/artifacts/glm-5-3-flash/tinfoil-models.json)

These commands record the September 9 migration run. The benchmark interfaces have since been modernized; use the [current measurement guide](benchmark-measurements.md) for new cohorts and source-fixture setup.

Principal commands, run before and after in the isolated worktree:

```bash
python -m unittest discover -s backend/tests
python -m unittest discover -s scripts/benches
python -m unittest discover -s scripts/tests
python scripts/tests/DEPLOYMENT/test_frontend_compose_contract.py
FRONTEND_RUNTIME_URL=http://127.0.0.1:5173 python scripts/tests/DEPLOYMENT/test_frontend_http.py
npm --prefix frontend test
npm --prefix frontend run build
cargo test --workspace --manifest-path runtime/sage/Cargo.toml
cargo clippy --workspace --all-targets --all-features --manifest-path runtime/sage/Cargo.toml -- -D warnings
cargo fmt --all --manifest-path runtime/sage/Cargo.toml -- --check
bash runtime/sage/scripts/smoke_tinfoil.sh
python scripts/tests/run_all_be_tests.py --api-base http://localhost:18000 --no-restore
python scripts/tests/TOOLS/test_5d_chunk_retrieval_gateway_smoke.py --api-base http://localhost:18000
python scripts/benches/conversation_model_bench.py --seed-knowledge --seed-resources --output /tmp/conversation-result.json
python scripts/run_benchmark.py
python scripts/tests/TOOLS/measure_admin_conversation_timing.py --output /tmp/admin-timing.json
```

Backend tests also ran in the freshly built image with this worktree mounted
read-only. Host Rust commands used Homebrew's libpq linker path. Live commands
used a temporary Docker wrapper that added a Compose override for uniquely named
`enclaveglm53-*` containers and corrected only the obsolete restart health URL.
The integration harness retained disposable test state with `--no-restore`.
The legacy benchmark received an ephemeral signed user token and cleaned up its
user fixture; no auth tokens are included in these evidence files.

Baseline limitations recorded before edits:

- The host backend suite ran 437 tests: 435 passed, one skipped, and one failed
  because the pre-existing virtual environment contains `accelerate`.
- A fresh backend image also ran 437 tests: 435 passed, one skipped, and one
  errored because a test accesses `.path` on FastAPI 0.141.1's `_IncludedRouter`.
  The host virtual environment uses FastAPI 0.136.3.
- The frontend suite had 487 passes and one five-second timeout. All six tests
  in the affected file passed on a focused rerun. Its production build passed.
- All 256 host Sage tests, formatting, and Clippy checks passed. The standalone
  Linux smoke script failed the existing endpoint-retry contract test, including
  when run serially. It stopped before its provider/memory smoke stages.
- All 67 conversation-benchmark unit tests, 53 script unit tests, three Compose
  checks, and five frontend HTTP checks passed.
- The integration runner needs port 18000 in its restart probe. A temporary
  wrapper corrected the old port 8000 probe for this isolated test stack. The
  rerun had 14 passing scripts and four failures: contact-quality evaluation,
  missing user-type ID for the chunk smoke, and unsupported `--api-base`
  arguments for the two deployment test scripts. The deployment scripts passed
  when run directly. Direct chunk retrieval passed its functional checks but
  failed fixture cleanup on a foreign-key constraint.
- Database restoration by the old integration harness changed the copied
  database's ownership. Ownership was repaired in the disposable test stack;
  subsequent runs retained test state there instead of invoking that restore.

Live benchmark results are single-run observations with possible provider cache
effects, not a statistically powered latency or reliability claim. The legacy
multi-session benchmark ran with grading disabled because no grading credential
was configured; completing those conversations is not a quality-pass score.
