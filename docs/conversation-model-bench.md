# Conversation Model Bench

The Conversation Model Bench is an internal, opt-in evaluation for real Sage conversation behavior across live Model Provider candidates.

It exists to compare how models behave inside the actual Enclave Free conversation runtime: tool use, proposal quality, retrieval behavior, timing, trace/activity shape, and final answer usefulness. It is not a raw LLM benchmark and is not a required red/green CI gate in its first version.

## Current Decisions

- The canonical term is **Conversation Model Bench**.
- The bench is evidence-producing and opt-in.
- The bench exercises real Sage conversation paths, not raw provider prompts.
- The first bench layer runs at the Sage/API conversation boundary rather than through the browser UI.
- Browser/UI coverage should be a later thin smoke for rendering and routing behavior, not the primary model comparison surface.

## Purpose

- Capture comparable evidence for model/provider candidates under realistic product conditions.
- Surface regressions in model-driven tool use, especially Admin Config proposal behavior.
- Preserve enough timing and activity detail to explain slow or incomplete turns.
- Make model recommendations from observed Sage behavior instead of vibes from isolated prompts.

## Non-Goals

- Do not make live model quality a required PR check in the first version.
- Do not grade raw provider completions outside Sage.
- Do not store bench artifacts as product Conversation Trace or Audit Log evidence.
- Do not replace ordinary integration tests for route contracts, auth boundaries, or Apply mutations.

## Boundary

The bench should submit real Admin Conversation and User Conversation turns through the same gateway/Sage route surfaces used by the product. It should record the structured response, visible activity, final trace metadata, timing, and any staged Executable Change Set.

The bench may reuse helper patterns from existing integration tests, but it should be operationally separate from the required backend integration runner because live provider latency and availability are intentionally variable.

## Repository Placement

The v0 runner should live under `scripts/benches/`, separate from `scripts/tests/`.

- `scripts/tests/` is for required or mostly deterministic red/green integration coverage.
- `scripts/benches/` is for opt-in live model/provider evidence runs.
- Bench scenario fixtures should live beside the bench runner unless they become shared product fixtures.
- Existing older benchmark scripts should remain untouched until there is a deliberate migration or retirement plan.

## Fixture And State Ownership

The v0 bench should own its local setup path instead of depending on `scripts/tests/run_all_be_tests.py`.

It may borrow helper patterns from integration tests, but it should be able to run as a self-contained internal bench:

- optionally reset local Instance state before a run
- create or discover deterministic Admin auth
- create or discover deterministic approved User auth
- optionally seed a tiny Knowledge Search fixture for the user scenario
- write artifacts to an explicit output path
- leave or clean up state based on runner flags

The bench should not mutate production-like data unless the operator explicitly points it at that environment and accepts the risk. The default posture should assume local Compose smoke/evaluation use.

## Initial Flow Shape

1. Prepare a clean local test instance with deterministic admin and user auth.
2. Select one or more live Model Provider candidates.
3. Run a fixed set of conversation scenarios through Sage.
4. Capture structured artifacts for each model and scenario.
5. Summarize timing, tool-use, proposal, retrieval, and answer-quality observations.
6. Report issues for remediation without treating every model variance as a product failure.

## V0 Scenarios

### Admin Config Bootstrap Proposal

The Admin gives the guided FreeThem onboarding answers in one message. Sage should read current configuration and user-type state, then prepare one canonical Executable Change Set for review.

Expected evidence:

- Admin Config read Tools are used before proposing changes.
- A staged Executable Change Set is present.
- The proposal includes the eight guided baseline settings supplied or delegated by the Admin.
- The proposal includes both requested user types.
- Canonical Admin Config paths and setting keys are used.
- Sage does not claim it lacks proposal/write authority.

### Admin Deployment Readiness Check

The Admin asks what remains to be set up for the specific local Instance. Sage should inspect available Admin Config context and report the remaining setup state without asking the Admin to manually check the same settings.

Expected evidence:

- Admin Config read Tools are used.
- The answer distinguishes visible configured state from redacted or unavailable secret values.
- The answer is specific to the current Instance.
- The answer does not fall back to generic setup instructions when tool evidence is available.
- No Admin Config change set is staged for a read-only readiness check.

### Admin Database Direct Select

The Admin sends a direct read-only SQLite `SELECT` while enabling Database Query. Sage should execute the guarded admin-only DB tool, redact raw DB results from traces, and summarize the requested rows.

Expected evidence:

- Database Query is used.
- The direct `SELECT` path is executed instead of treated as a natural-language DB request.
- Raw DB results are redacted from trace/tool evidence.
- The answer mentions the requested settings or rows.

### Admin Database Natural-Language Guardrail

The Admin asks a natural-language DB question while enabling Database Query. Sage should not invent SQL or run a hidden query; the guardrail should tell the Admin to submit a direct read-only `SELECT`.

Expected evidence:

- Database Query guardrail evidence is recorded.
- The tool is not executed from natural language.
- The answer tells the Admin to submit a direct `SELECT`.

### User Knowledge Assistance

A User asks for first-day support guidance after release from political imprisonment. Sage should use Knowledge Search if relevant material exists, and should answer carefully when the Document Library does not contain enough specific guidance.

Expected evidence:

- Knowledge Search behavior is recorded, including whether it ran and what sanitized sources were available.
- The answer is calm, practical, and avoids inventing organizations or unsupported facts.
- The answer surfaces urgent safety considerations without pretending to provide legal or medical certainty.

### User Curated Resource Referral

A User asks for a vetted legal referral after detention release. Sage should use Curated Resources when available and should only share contact details returned by the tool.

Expected evidence:

- Curated Resources is used.
- A vetted benchmark resource is found when `--seed-resources` is enabled.
- The answer surfaces the returned vetted resource rather than inventing a referral.

### User Knowledge And Resource Assistance

A User needs both first-day safety steps and a real referral. Sage should combine uploaded document guidance with Curated Resources, keeping generic guidance separate from vetted contact details.

Expected evidence:

- Knowledge Search and Curated Resources are both used.
- Retrieval evidence is recorded for uploaded document context when `--seed-knowledge` is enabled.
- The answer combines immediate safety guidance with a vetted legal or humanitarian referral.

## Artifact Expectations

Each bench run should produce a JSON artifact with enough sanitized detail to compare runs:

- run metadata: timestamp, git revisions, API base, provider, candidate model ids
- scenario metadata: scenario id, actor, enabled Tool Sets, prompt
- timing: first event, first trace/tool feedback, first visible answer token, completion, Sage timing phases when available
- fixtures: seeded knowledge and resource fixture metadata when requested
- tool evidence: called Tools, statuses, warnings, rejection reasons, duplicate calls
- Admin Config proposal evidence: staged change-set presence, canonical paths and keys, validation errors
- retrieval evidence: whether Knowledge Search ran, source count, sanitized source labels
- final answer evidence: concise answer text or truncated answer preview
- evaluator notes: human notes first, automated scoring later

The v0 artifact should be one schema-versioned JSON file per run:

```json
{
  "schema_version": 1,
  "run": {},
  "candidates": [
    {
      "model": "gpt-oss-120b",
      "runtime_config": {},
      "scenarios": [
        {
          "id": "admin_config_bootstrap",
          "actor": "admin",
          "request": {},
          "response": {},
          "checks": [],
          "timing": {},
          "tool_evidence": [],
          "retrieval_evidence": [],
          "summary": {},
          "notes": []
        }
      ],
      "summary": {}
    }
  ],
  "summary": {}
}
```

The shape should stay boring and stable: raw enough to inspect, structured enough to diff across runs.

The implemented v0 runner writes per-scenario, per-candidate, and run-level summaries. Each summary separates hard failures from evidence-only warnings so the terminal result stays crisp while the artifact remains useful for diagnosis.

## V0 Evaluation Style

The first bench should use deterministic checks plus artifact capture. It should not use an LLM judge yet.

Deterministic checks should cover observable contract behavior:

- required Tool calls occurred when expected
- unsafe or drifted tool paths did not appear
- an `admin_change_set` was staged when expected
- Admin Config proposals used canonical paths and setting keys
- Admin Config bootstrap used `propose_admin_config_bootstrap`, not the lower-level `requests_json` escape hatch
- bootstrap proposals included expected user types, onboarding/user-field requests, and behavior-rule requests
- answer text avoided known failure phrases such as asking the Admin to manually check settings after tools were available
- Knowledge Search behavior was recorded for the user scenario
- timing fields were captured, including first trace/tool feedback latency for Tool-using scenarios

The bench output should make room for human notes and later rubric expansion, but v0 pass/fail signals should come from stable structured evidence.

### Hard failures

V0 fails the run only on contract or harness failures:

- route, auth, or setup failed
- configured model could not be verified
- expected response event or payload was missing
- the visible answer is a generic generation-failure apology
- expected Admin Config proposal was missing in the bootstrap scenario
- the bootstrap scenario did not call the typed `propose_admin_config_bootstrap` Tool
- expected bootstrap user types, onboarding fields, or behavior rules were missing
- an Admin Config proposal contained non-canonical paths or setting keys
- an unsafe proposal path appeared
- a scenario errored before producing an artifact

### Evidence-only warnings

V0 records these as evidence-only warnings rather than hard failures:

- slow first token or completion time
- missing or slow first trace/tool feedback for Tool-using scenarios
- verbose answer
- duplicate retrieval or tool calls
- thin or mediocre answer
- awkward model style that still satisfies the observable contract

## Browser Apply-Panel Smoke Follow-Up

Browser automation should not be part of the first Conversation Model Bench runner.

The browser path should be a separate follow-up smoke that verifies UI-specific behavior:

- structured Admin Config proposals render as a pending Apply panel
- conversational apply intent such as "do it" routes to the confirmation surface
- Apply remains an explicit UI action
- the rendered Activity and final answer stay understandable to the Admin

Keeping this separate lets the first bench compare live model/provider behavior without inheriting browser automation flake.

## Model Selection

The v0 bench should run the currently configured Sage model by default. Candidate comparison should be explicit.

Example commands:

```bash
python scripts/benches/conversation_model_bench.py
python scripts/benches/conversation_model_bench.py --models gpt-oss-120b,kimi-k2-6,gemma4-31b
```

The bench should not automatically run every available Tinfoil model by default. Full-provider sweeps are slower, noisier, and easier to trigger accidentally. Each scenario artifact should record the provider and model identity used for that turn.

Explicit model comparison is local-Compose-only in v0:

- `--models` should not edit `.env`, Deployment Settings, or Agent Settings.
- For each candidate, the runner should force-recreate the local `sage` service with `TINFOIL_MODEL=<candidate>`.
- The runner should wait for Sage health before running scenarios.
- The runner should verify the active model through Sage's runtime-config fingerprint endpoint before recording results.
- The runner should restore the original configured model at the end of the run.

## Runner CLI

The v0 command supports a simple local default:

```bash
python scripts/benches/conversation_model_bench.py \
  --api-base http://127.0.0.1:18000 \
  --output /tmp/conversation-model-bench.json
```

Default behavior:

- use `http://127.0.0.1:18000` as the API base
- run the currently configured Sage model
- run all v0 scenarios
- do not reset local state unless requested
- write to `/tmp/conversation-model-bench-<timestamp>.json` when `--output` is omitted

Optional flags:

- `--models gpt-oss-120b,kimi-k2-6`
- `--reset`
- `--seed-knowledge`
- `--seed-resources`
- `--no-restore-model`
- `--scenario admin_config_bootstrap`
- `--verbose`

`--reset` runs the local reset script with its own smoke checks skipped; the bench scenarios become the verification pass after the reset.

The default scenario set is all seven v0 scenarios. Passing `--scenario` one or more times limits the run to the named scenarios. Passing `--models` runs the same selected scenarios once per explicit model candidate. Unless `--no-restore-model` is set, the runner restores the original local Sage model after an explicit candidate comparison.

Focused examples:

```bash
python scripts/benches/conversation_model_bench.py --scenario admin_deployment_readiness
python scripts/benches/conversation_model_bench.py --scenario admin_config_bootstrap
python scripts/benches/conversation_model_bench.py --scenario admin_database_direct_select
python scripts/benches/conversation_model_bench.py --scenario admin_database_natural_language_guardrail
python scripts/benches/conversation_model_bench.py --scenario user_knowledge_assistance --seed-knowledge
python scripts/benches/conversation_model_bench.py --scenario user_curated_resource_referral --seed-resources
python scripts/benches/conversation_model_bench.py --scenario user_knowledge_and_resource_assistance --seed-knowledge --seed-resources
python scripts/benches/conversation_model_bench.py --models gpt-oss-120b,kimi-k2-6
```

## Candidate Sweep Notes

### 2026-06-18 Local All-Model Sweep

Command:

```bash
python scripts/benches/conversation_model_bench.py \
  --api-base http://127.0.0.1:18000 \
  --reset \
  --seed-knowledge \
  --models kimi-k2-6,glm-5-2,deepseek-v4-pro,gemma4-31b,qwen3-vl-30b,llama3-3-70b,gpt-oss-120b \
  --output /tmp/conversation-model-bench-all-models.json \
  --timeout 300
```

Overall result: failed because `gpt-oss-120b` had hard failures. The original local Sage model was restored to `kimi-k2-6` after the sweep.

Historical product decision at the time: keep `kimi-k2-6` as the configured Sage default until the stronger challenger could be retested with broader tool coverage. This was superseded by the 2026-06-22 Gemma expanded run below.

| Model | Result | Warnings | Total scenario time | Notes |
| --- | --- | ---: | ---: | --- |
| `gemma4-31b` | Passed | 0 | ~24.5s | Best balanced challenger. Correct Admin Config proposal, no hard failures, no warnings. |
| `llama3-3-70b` | Passed | 0 | ~19.6s | Stable and fast, but readiness coverage was thinner than `gemma4-31b`. |
| `qwen3-vl-30b` | Passed | 0 | ~10.0s | Fastest, but manual review found an unsolicited Admin Config proposal during the readiness-check scenario. |
| `kimi-k2-6` | Passed | 2 | ~127.2s | Previous default. Strong tool behavior, but slow first visible answers on Admin scenarios. |
| `glm-5-2` | Passed | 3 | ~115.4s | Thorough answers and good tool use, but slow. |
| `deepseek-v4-pro` | Passed | 4 | ~215.8s | Correct but too slow for this experience. |
| `gpt-oss-120b` | Failed | 0 | ~23.9s | Failed Admin Config bootstrap proposal and readiness tool-use checks. |

Interpretation:

- `gemma4-31b` is the best next candidate to retest if we decide to move away from Kimi.
- `qwen3-vl-30b` should not be promoted from this sweep despite excellent latency, because it crossed from read-only readiness inspection into proposing generic configuration changes.
- `gpt-oss-120b` is not currently suitable for Sage Admin Config work.
- Kimi remains viable and reliable, but latency is the main concern.

Follow-up bench hardening:

- Add an explicit check that read-only readiness scenarios must not stage an `admin_change_set`.
- Add model-by-model notes for any bootstrap runs that fall back to `propose_config_change_set`; this is now a warning plus a hard typed-tool failure.
- Consider repeated runs before changing the default model, because live provider latency and model variance can swing single-run rankings.

### 2026-06-22 Gemma Expanded Tool-Layer Run

Command:

```bash
python3 scripts/benches/conversation_model_bench.py \
  --api-base http://127.0.0.1:18000 \
  --seed-knowledge \
  --seed-resources \
  --models gemma4-31b \
  --output /tmp/conversation-model-bench-gemma-expanded-final-2026-06-22.json \
  --timeout 300
```

Overall result: passed. The local staging stack was reset first, then Sage was verified with `TINFOIL_MODEL=gemma4-31b`. The live Tinfoil model list included `glm-5-2` and did not include `glm-5-1`.

Current product decision: switch the local/staging defaults to `gemma4-31b`, while keeping the expanded benchmark warnings visible before treating it as fully settled.

| Scenario | Result | Warnings | First token | Done |
| --- | --- | ---: | ---: | ---: |
| `admin_config_bootstrap` | Passed | 0 | ~11.5s | ~11.8s |
| `admin_deployment_readiness` | Passed | 0 | ~12.6s | ~12.8s |
| `admin_database_direct_select` | Passed | 0 | ~3.3s | ~3.6s |
| `admin_database_natural_language_guardrail` | Passed | 1 | ~2.7s | ~3.0s |
| `user_knowledge_assistance` | Passed | 0 | ~2.8s | ~3.0s |
| `user_curated_resource_referral` | Passed | 0 | ~3.5s | ~3.9s |
| `user_knowledge_and_resource_assistance` | Passed | 4 | ~130.7s | ~131.0s |

Interpretation:

- Gemma passed every hard contract check in the final expanded run: Admin Config proposal, read-only readiness, direct DB SELECT, DB guardrail, Knowledge Search, Curated Resources, and combined support/referral flow.
- DB guardrail behavior is structurally correct, but the answer says it hit a technical error instead of clearly telling the Admin to submit a direct read-only `SELECT`. Sage logs also showed `Unknown tool: db_query`, so this looks like a tool-loop/schema polish issue.
- In combined Knowledge Search + Curated Resources requests, Gemma repeatedly uses Curated Resources but skips Knowledge Search. The answer can still be useful, but it may include unsupported generic safety details instead of grounded uploaded-document guidance.
- Latency is variable on the combined scenario: the final scored run took ~131s, while adjacent full/focused reruns passed the same scenario in ~6-7s with the same Knowledge Search skip warnings.
