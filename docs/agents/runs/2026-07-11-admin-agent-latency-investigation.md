# Admin agent latency investigation

Date: 2026-07-11  
Repository commit: `2e161ee` (working tree already dirty before this investigation)  
Runtime model: `glm-5-2` through Tinfoil  
Scope: investigation only; no product latency fixes were made

## Executive conclusion

The Admin Config, Database Query, Knowledge Search, and Curated Resources implementations are **not the source of the observed 30–60 second waits**. In the measured turns, actual tool execution took **0–443 ms per tool**, while model inference plus structured-response correction consumed **98.9%–99.6% of the slow multi-tool turns**.

The latency is concentrated in three places:

1. **GLM/Tinfoil inference tail latency.** The worst reproduced turn took 108.1 seconds. Its first GLM call alone took 95.249 seconds; Knowledge Search took 398 ms.
2. **The model-driven tool loop serializes inference.** A tool-assisted answer normally requires one model call to choose the tool, the tool itself, and a second model call to answer. Those calls cannot overlap.
3. **GLM frequently fails Sage's typed `AgentResponse` format.** Each parse failure launches another full model call to repair the response. Several representative turns therefore made four serial model calls: two normal calls plus two correction calls.

There are two smaller contributors:

- Conversation memory performs synchronous remote embeddings before the model and after the answer. Direct embeddings had a 293 ms median, so the normal pair adds roughly 0.6 seconds to a turn.
- The SSE endpoint emits status and trace events early, but emits the user-visible answer as one complete `answer_delta` only after the entire agent loop finishes. This does not create the underlying compute delay, but it makes the full delay become time-to-first-answer.

There is also a **separate local deployment defect**: the Compose stack uses the deprecated `tinfoil-cli` proxy image. Its non-streaming responses had a `Content-Length` exactly 20 bytes larger than the body, causing Sage decoding failures and retry exhaustion. I used a temporary Compose override with the current standalone `tinfoil-proxy` to make the investigation valid. This defect can cause failures/retries, but it is separate from the successfully reproduced 30–108 second latency.

## Environment and setup

The supported local reset script was used to create a fresh disposable instance. The stack is left running at:

- Frontend: `http://127.0.0.1:5173`
- API gateway: `http://127.0.0.1:18000`
- Admin fixture: the benchmark's disposable `bench-admin-pubkey` identity
- Instance state: initialized, not setup-complete, not ready for users

The local ignored `.env` now selects `TINFOIL_MODEL=glm-5-2`. No application source was modified for setup or testing.

The temporary proxy override is `/tmp/enclave-tinfoil-proxy-override.yml`. The running proxy image is `ghcr.io/tinfoilsh/tinfoil-proxy:latest`; the repository still specifies `ghcr.io/tinfoilsh/tinfoil-cli:latest` in `docker-compose.infra.yml`.

## Measurements

All times below are wall-clock times through the real `POST /llm/chat/stream` path. The detailed agent trace records exact durations for model calls, correction calls, and tools.

| Scenario | Tools active | First visible answer | Done | Agent-loop breakdown |
|---|---|---:|---:|---|
| No-tool admin control (`Reply exactly: hello`) | none | 1.481 s | 1.709 s | 1 model call: 933 ms; no correction |
| Admin Config bootstrap proposal | Admin Config | 3.859 s | 4.141 s | 1 model call: 3.160 s; deterministic proposal ended the loop |
| Admin DB direct `SELECT` | Database Query | 7.126 s | 7.668 s | model 6.454 s; DB tool 5 ms; no correction |
| Admin DB natural-language guardrail | Database Query | 12.950 s | 13.178 s | model 8.789 s; correction 3.753 s; guarded tool 0 ms |
| Admin deployment readiness | Admin Config | 13.365 s | 13.652 s | model 8.179 s; correction 4.337 s; tool 30 ms |
| Admin Knowledge audit, all four families active | Admin Config, DB, Knowledge, Resources | 14.591 s | 14.996 s | model 6.233 s; corrections 7.303 s; Knowledge 443 ms |
| User Knowledge + Resources | Knowledge, Resources | 19.100 s | 19.409 s | model 9.404 s; corrections 9.120 s; 3 tools 202 ms |
| User Knowledge worst-case reproduction | Knowledge | 107.807 s | 108.073 s | model 100.284 s; corrections 6.600 s; tool 398 ms |

The Knowledge-only case was repeated to check whether the 108-second result was deterministic. The repeat completed in 9.972 seconds:

- Model step 1: 1.483 s
- Knowledge Search: 191 ms
- Model step 2: 4.338 s, but its response failed parsing
- Structured correction call: 3.216 s
- Total traced agent loop: 9.232 s

This high variance is evidence that the 95-second outlier is upstream/model-call tail latency, not a deterministic Knowledge Search problem.

### Direct provider controls

Eight sequential simple, non-streaming GLM calls through the corrected proxy measured:

- Minimum: 1.628 s
- Median: 1.716 s
- Mean: 3.473 s
- Maximum: 15.618 s

The first of eight calls was the 15.6-second outlier; the remaining calls clustered around 1.6–2.0 seconds. Five calls with an approximately 4,823-token prompt had a 2.579-second median and a 3.157-second maximum. Prompt size adds some cost, but it does not explain the 95-second real-turn call.

Eight direct embedding calls measured a 293 ms median, 298.6 ms mean, and 415 ms maximum.

## Slowest trace: exact attribution

The 108.073-second Knowledge turn (`session_id=708c7461-b709-4dee-9330-f328531fc329`) recorded:

| Operation | Duration |
|---|---:|
| Model step 1, response failed typed parsing | 95,249 ms |
| Structured response correction 1 | 2,907 ms |
| Knowledge Search | 398 ms |
| Model step 2, response failed typed parsing | 5,035 ms |
| Structured response correction 2 | 3,693 ms |
| Total traced agent loop | 107,288 ms |

Model and correction calls consumed **106,884 ms (99.62%)**. Knowledge Search consumed **398 ms (0.37%)**. The remaining traced overhead was approximately 6 ms.

For the 18.730-second Knowledge + Resources agent loop, model and correction calls consumed **18,524 ms (98.9%)**, while three tool calls consumed **202 ms (1.08%)**.

## Root-cause ranking

### 1. Model/provider tail latency — primary cause of the worst cases

Confidence: high.

The exact 95.249-second span is a single traced GLM request. Direct provider calls also showed meaningful variance (1.6–15.6 seconds), while the identical Knowledge tool path varied only between 191 and 398 ms. The tool layer is not active during that 95-second span.

### 2. Serial model calls in the tool loop — primary repeatable multiplier

Confidence: high.

The agent's model-driven loop calls the model once to select tools and again after tool results are injected. A successful direct DB turn needed two model calls even though SQLite took 5 ms. A no-tool admin response needed one 933 ms model call and completed in 1.7 seconds.

The loop is implemented in `runtime/sage/crates/sage-core/src/web_runtime.rs` (`run_agent_steps` and `run_conversation_tool_loop`). This orchestration is part of the tool-enabled path, but the latency is in the serial inference calls around the tool, not the tool implementation.

### 3. Structured-output correction calls — large and frequent avoidable multiplier

Confidence: high.

GLM often returned useful prose and/or a tool call but omitted or malformed fields required by Sage's typed `AgentResponse`. Sage then called the model again to transform the response into the schema. The measured correction cost was:

- 3.753 s for the guarded DB turn
- 4.337 s for Admin Config readiness
- 6.600 s across the worst Knowledge turn
- 7.303 s across the admin all-tools Knowledge turn
- 9.120 s across Knowledge + Resources

The behavior is in `runtime/sage/crates/sage-core/src/sage_agent.rs`: `MAX_LLM_RETRIES`, typed prediction, and `attempt_correction`. The runtime permits up to three attempts. In these traces, correction succeeded before retry exhaustion.

### 4. Synchronous conversation-memory embeddings — small fixed floor

Confidence: high.

The stream handler stores the user message with an embedding before entering the tool loop, then stores the assistant answer with another embedding before emitting `done`. `store_message_with_compaction_check` reaches `RecallManager::add_message`, which awaits the remote embedding request. At the measured 293 ms median, the ordinary pair adds approximately 0.6 seconds. Successful Admin Config tool persistence can create additional embedded tool-memory writes.

The repository already contains a store-without-embedding path and a later embedding-update path, but the chat stream currently uses the synchronous path.

### 5. Batched answer emission — perceived latency amplifier

Confidence: high.

Initial SSE events arrived in 72–379 ms and trace/tool feedback in 357–662 ms. However, the handler waits for the complete agent loop and then emits the assembled answer as a single `answer_delta`. Therefore provider output cannot become visible incrementally, and time-to-first-visible-answer approximately equals the entire model/tool/correction loop.

### 6. Actual control-plane, SQLite, Qdrant, and resource tools — not a major contributor

Confidence: high; hypothesis falsified.

Measured durations were:

- Admin setup summary: 30 ms
- Direct SQLite query: 5 ms
- Guarded DB request: effectively 0 ms
- Knowledge Search: 183–443 ms
- Curated resource lookups: 6–13 ms each

Even the slowest tool represented less than 1% of the slowest turn.

## Separate proxy compatibility finding

Before valid latency testing, every Sage call failed after retries when using the repository's deprecated Tinfoil CLI proxy. Strict non-streaming responses consistently declared a `Content-Length` 20 bytes longer than the received body. The JSON body itself was complete, but HTTP clients reported an incomplete response and Sage logged `error decoding response body`.

Streaming a direct GLM request worked, which initially made the proxy appear healthy, but Sage's typed predictor uses the affected non-streaming response path. Switching only the local test container to the current standalone proxy made body length and `Content-Length` agree and restored chats. The current standalone image and flags are documented by the [official Tinfoil proxy package](https://pkg.go.dev/github.com/tinfoilsh/tinfoil-proxy%40v0.0.10).

This should be fixed independently because it can add retry delays or prevent responses entirely. It is not included in the successful-turn latency percentages above.

## Hypotheses and verdicts

| Hypothesis | Verdict | Evidence |
|---|---|---|
| GLM/Tinfoil tail variability dominates the worst outliers | Supported | One traced GLM call took 95.249 s; direct calls ranged 1.628–15.618 s |
| Tool-enabled turns serialize multiple model calls | Supported | No-tool: one 933 ms call; direct DB: two model calls and a 5 ms tool |
| Structured parse recovery adds full model calls | Supported | Corrections added 3.216–9.120 s in representative turns |
| Synchronous memory embeddings add a smaller fixed floor | Supported | Two awaited embeddings per normal turn; 293 ms direct median |
| Python/SQLite/Qdrant/resource tool execution is the 30–60 s bottleneck | Falsified | Tools measured 0–443 ms and about 0.4%–1.1% of slow turns |

## Recommended fix order for the next phase

No fixes were made in this phase. Based on expected impact, the next phase should evaluate:

1. Remove or sharply reduce repair-model calls for GLM responses—especially final prose responses—and test native/tool-call parsing options.
2. Reduce the number of serial inference steps for deterministic/guarded operations and common single-tool reads.
3. Add provider-call instrumentation with request IDs, prompt/completion token counts, time to headers, and time to first token so Tinfoil/model tails can be separated from client decoding.
4. Stream usable model output instead of emitting the whole answer after the loop, where the response protocol permits it.
5. Move recall embeddings off the critical path or use the existing deferred-embedding flow.
6. Replace the deprecated Compose proxy image and add a non-streaming integrity smoke test.

## Reproduction artifacts and commands

Benchmark artifacts are intentionally outside the repository:

- `/tmp/enclave-admin-baseline-2.json`
- `/tmp/enclave-tool-baseline-1.json`
- `/tmp/enclave-tinfoil-proxy-override.yml`

Representative benchmark commands:

```bash
python3 scripts/benches/conversation_model_bench.py \
  --api-base http://127.0.0.1:18000 \
  --scenario admin_deployment_readiness \
  --scenario admin_database_direct_select \
  --scenario admin_database_natural_language_guardrail \
  --timeout 180 \
  --output /tmp/enclave-admin-baseline-2.json \
  --verbose

python3 scripts/benches/conversation_model_bench.py \
  --api-base http://127.0.0.1:18000 \
  --scenario admin_config_bootstrap \
  --scenario user_knowledge_assistance \
  --scenario user_knowledge_and_resource_assistance \
  --seed-knowledge \
  --seed-resources \
  --timeout 180 \
  --output /tmp/enclave-tool-baseline-1.json \
  --verbose
```

## Limitations

- This is a targeted local investigation, not a statistically powered provider benchmark.
- The Knowledge and Resources fixtures are deliberately tiny and synthetic, making tool execution easy to isolate. A production-scale corpus may increase retrieval time, but it would need to grow by two orders of magnitude to resemble the observed model delays.
- Provider conditions vary over time. The exact outlier distribution should be re-measured over a larger sample before setting an SLO.
- The benchmark admin uses a synthetic public key. Post-answer encrypted session-log persistence warns for that invalid key, but the warning occurs after response generation and was not part of the measured agent-loop latency.

