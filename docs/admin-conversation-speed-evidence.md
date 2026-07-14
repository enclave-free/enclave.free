# Admin Conversation Speed Evidence

Issue: [#278](https://github.com/enclave-free/enclave.free-prototype/issues/278)

This file is historical evidence for the bounded streaming/database investigation.
[ADR-0023](adr/0023-unified-model-driven-tool-loop.md) supersedes the guarded
natural-language database posture for future unified Tool-loop work.

Initial evidence was captured on 2026-05-24 from the supported local Docker
Compose topology. The PR evidence below was refreshed on 2026-06-13 from the
same Compose gateway topology.

```bash
docker compose -f docker-compose.infra.yml -f docker-compose.app.yml up --build -d
docker compose -f docker-compose.infra.yml -f docker-compose.app.yml ps --format 'table {{.Name}}\t{{.State}}\t{{.Ports}}'
python3 scripts/tests/TOOLS/measure_admin_conversation_timing.py --api-base http://127.0.0.1:18000 --output /tmp/admin-conversation-timing-after.json
```

The timing harness mints an admin bearer token inside `enclave-core-backend`, then streams through the gateway at `127.0.0.1:18000`. It records first SSE event, first visible `answer_delta`, final `done`, Sage-emitted Conversation Turn Timing phases, and visible tool statuses/warnings.

For the 2026-06-13 refresh, a local `omlx-server` process already owned
`127.0.0.1:8000`, so the gateway was published to host port `18000` with a
temporary Compose override while preserving the same in-container gateway path:

```bash
docker compose -f docker-compose.infra.yml -f docker-compose.app.yml -f /tmp/enclave-pr-compose-ports.yml up --build -d
python3 scripts/tests/TOOLS/measure_admin_conversation_timing.py --api-base http://127.0.0.1:18000 --output /tmp/admin-conversation-timing-after-current.json
```

## Before Rebuild Snapshot

Before rebuilding the local Compose app stack to the current commits, the already-running Sage container still reflected an older image. That run is useful as a same-machine, same-gateway snapshot of the prior runtime behavior, but it should not be treated as a controlled provider-latency benchmark.

| Scenario | First event | First visible assistant token | Done | Visible tool state | Conversation Turn Timing |
| --- | ---: | ---: | ---: | --- | --- |
| Config-only Admin Conversation | 86.5 ms | 2,704.5 ms | 3,328.0 ms | `admin-config` completed | not emitted by the stale image |
| Database selected, natural-language question | 66.4 ms | 33,169.1 ms | 34,104.4 ms | `db-query` completed, `raw_results_redacted` | not emitted by the stale image |
| Database selected, direct safe `SELECT` | 10.5 ms | 5,129.7 ms | 5,968.4 ms | `db-query` completed, `raw_results_redacted` | not emitted by the stale image |

## Current PR Refresh

Captured on 2026-06-13.

Sage commit: `7502a75`

Prototype branch: `codex/mega-conversation-tool-turn`

| Scenario | First event | First visible assistant token | Done | Visible tool state | Conversation Turn Timing |
| --- | ---: | ---: | ---: | --- | --- |
| Config-only Admin Conversation | 47.5 ms | 9,664.7 ms | 10,310.0 ms | `admin-config` completed | `preparing_tools`: 0 ms; `writing_answer`: 33 ms |
| Database selected, natural-language question | 59.4 ms | 8,037.0 ms | 9,026.6 ms | `db-query` guarded, `direct_select_required` | `preparing_tools`: 0 ms; `writing_answer`: 46 ms |
| Database selected, direct safe `SELECT` | 44.4 ms | 3,182.4 ms | 3,702.6 ms | `db-query` completed, `raw_results_redacted` | `preparing_tools`: 0 ms; `writing_answer`: 36 ms |

## Interpretation

The local pre-answer phases are not the dominant delay in the post-change runs. All three paths emitted the first stream event in under 60 ms, and Sage's admin-only timing metadata reported `preparing_tools` at 0 ms and `writing_answer` at roughly 33-46 ms before the request entered model streaming.

Remaining slow turns are dominated by Model Provider first-token latency after Sage has already emitted live status. The natural-language Database-selected path was visibly guarded quickly, did not execute database work, and spent the remaining time waiting for the model to write guidance for the admin. The direct safe `SELECT` path completes with redacted result metadata and avoids the slower natural-language database interpretation path entirely.

Because provider first-token latency varies substantially between runs, compare the before and after numbers mainly for behavioral evidence and local phase visibility rather than as a precise model latency benchmark. The in-repo script exists so future speed work can capture cleaner baseline and after runs before merging.

## 2026-07-14 GLM 5.2 Critical-Path Verification

Issue: [#490](https://github.com/enclave-free/enclave.free/issues/490)

The supported local gateway now runs at `127.0.0.1:18000`. A fresh reset/build used the standalone Tinfoil proxy, and every Compose service became healthy. The final timing command was:

```bash
python3 scripts/tests/TOOLS/measure_admin_conversation_timing.py \
  --api-base http://127.0.0.1:18000 \
  --output /tmp/admin-conversation-timing-final-2026-07-14.json
```

The harness now records first event, first Trace or Tool feedback, first provider answer delta, completion, answer-delta count, model calls, correction calls, retries, and Tool execution time. Session Memory persistence and embedding duration are not exposed by the public stream; Sage runtime tests verify that durable message creation happens before detached embedding work and that embedding failures remain repairable without failing the response.

| Scenario | First event | First feedback | First answer | Done | Model calls | Corrections | Tool time | Answer deltas |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| No Tool control | 445.6 ms | 448.7 ms | 1,078.9 ms | 1,428.3 ms | 1 | 0 | 0 ms | 9 |
| Deterministic Admin Config bootstrap proposal | 304.4 ms | 306.8 ms | 3,262.2 ms | 3,278.7 ms | 1 | 0 | 0 ms | 1 deterministic delta |
| Admin Config read | 197.0 ms | 200.0 ms | 3,249.4 ms | 4,174.0 ms | 2 | 0 | 30 ms | 23 |
| Database natural-language question with bounded guarded replans | 194.6 ms | 197.1 ms | 23,879.1 ms | 26,129.4 ms | 4 | 0 | 10 ms | 53 |
| Database direct safe `SELECT` | 262.5 ms | 264.4 ms | 4,039.0 ms | 4,504.3 ms | 2 | 0 | 3 ms | 12 |

The deterministic proposal used one planning call and no unnecessary final Model Provider call. Every terminal-prose scenario used zero correction calls. When GLM supplied multiple answer chunks, Sage exposed multiple real `answer_delta` events rather than buffering the completed answer.

The final clean nine-scenario Conversation Model Bench passed every hard acceptance gate across 174 checks for the no-Tool control, Admin Config, Database Query, Knowledge Search, and Curated Resources. The final run also required authenticated lifecycle deletion of every temporary conversation and verified fixture cleanup as a hard gate. One provider-latency observation remained as a bounded warning:

```bash
python3 scripts/benches/conversation_model_bench.py \
  --api-base http://127.0.0.1:18000 \
  --seed-knowledge \
  --seed-resources \
  --output /tmp/conversation-model-bench-glm-5-2-final-clean-2026-07-14.json
```

| Scenario | First feedback | First answer | Done | Model calls | Corrections | Tool time | Answer deltas |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| No Tool control | 290.8 ms | 1.2 s | 1.3 s | 1 | 0 | 0 ms | 2 |
| Deterministic Admin Config bootstrap | 135.6 ms | 18.8 s | 18.9 s | 1 | 0 | 0 ms | 1 deterministic delta |
| Live onboarding bootstrap | 134.4 ms | 6.6 s | 6.6 s | 1 | 0 | 0 ms | 1 deterministic delta |
| Deployment readiness | 141.9 ms | 38.4 s | 44.6 s | 3 | 0 | 20 ms | 89 |
| Database direct `SELECT` | 129.9 ms | 8.2 s | 9.8 s | 3 | 0 | 1 ms | 24 |
| Database natural-language count | 129.6 ms | 11.1 s | 11.5 s | 3 | 0 | 7 ms | 6 |
| Knowledge assistance | 148.5 ms | 9.1 s | 15.1 s | 3 | 0 | 216 ms | 102 |
| Curated Resource referral | 143.4 ms | 9.9 s | 13.4 s | 3 | 0 | 3 ms | 55 |
| Knowledge plus Resource | 173.8 ms | 11.1 s | 17.5 s | 3 | 0 | 219 ms | 107 |

All required Tool calls, exact seeded facts, exact database count, deterministic proposal behavior, zero-correction and zero-retry contracts, and incremental streaming contracts passed. The only bounded warning was the deployment-readiness first-answer outlier. Every dispatched scenario used a client-owned session ID and attempted authenticated lifecycle deletion even on transport failure. A post-run audit found zero benchmark Users, User Types, policies, document jobs, Qdrant points, uploads, Resources, Sage sessions, orphan agents, or external identities. Older fixtures from pre-cleanup benchmark runs were also removed from the local instance before this final verification.

### Attribution

Repository-controlled critical-path work completed in this slice:

- the deprecated proxy was replaced with the supported standalone Tinfoil proxy and strict response-integrity smoke coverage;
- Tool decisions remain typed, while final prose streams directly without structured-response correction calls;
- successful deterministic Admin Config proposals terminate without another model call;
- Session Memory rows receive durable IDs before detached embedding work, so embeddings no longer block response completion;
- server-authoritative User Tool and Required Context policy is reproduced correctly by the live benchmark fixtures.

The remaining long tail is predominantly Model Provider generation variance after Enclave has already emitted visible status. Across the final clean run, first feedback arrived in 0.13–0.29 seconds and measured Tool work took 0–219 ms, while first-answer latency ranged from 1.2 to 38.4 seconds. A natural-language DB question can still consume extra model steps when GLM first proposes rejected SQL; that bounded replan behavior is repository-controlled and remains a narrower future optimization, but the DB executor itself is not the source of the long wait.
