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
python3 scripts/tests/TOOLS/measure_admin_conversation_timing.py --api-base http://127.0.0.1:8000 --output /tmp/admin-conversation-timing-after.json
```

The timing harness mints an admin bearer token inside `enclave-core-backend`, then streams through the gateway at `127.0.0.1:8000`. It records first SSE event, first visible `answer_delta`, final `done`, Sage-emitted Conversation Turn Timing phases, and visible tool statuses/warnings.

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
