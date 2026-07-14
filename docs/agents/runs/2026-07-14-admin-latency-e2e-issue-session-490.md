# Admin Agent Latency End-to-End Verification — Issue Session #490

## Issue

- Issue: [#490](https://github.com/enclave-free/enclave.free/issues/490)
- Fixed point before session: parent `05075a0`, Sage `174aac6`
- Worker session: `/root` with `/root/benchmark_hardening`
- Parent commit: `d1a4ae2`
- Sage commit: `5a1770c7d0ccc5badef2395385edda0a167336c1`
- Status: complete

## Inputs

- Spec issue: [#486](https://github.com/enclave-free/enclave.free/issues/486)
- Tickets verified together: [#487](https://github.com/enclave-free/enclave.free/issues/487), [#488](https://github.com/enclave-free/enclave.free/issues/488), [#489](https://github.com/enclave-free/enclave.free/issues/489)
- Relevant ADR: `docs/adr/0027-separate-tool-decisions-from-final-answer-delivery.md`
- Runtime: clean local Compose instance at `http://127.0.0.1:18000`, GLM 5.2 through the supported standalone Tinfoil proxy

## Implementation

- Expanded the Conversation Model Bench to nine scenarios spanning a no-Tool control, deterministic and live Admin Config, deployment readiness, direct and natural-language Database Query, Knowledge Search, Curated Resources, and combined Knowledge plus Resources.
- Captured first event, first Tool or Trace feedback, first answer delta, completion, answer-delta count, model-call count, correction-call count, retry count, Tool execution duration, and runtime timing phases.
- Added hard gates for Tool selection, exact seeded facts, exact database results, single-call deterministic proposals, zero correction calls with required telemetry, incremental answer streaming, authenticated conversation deletion, and complete fixture cleanup.
- Made Knowledge and Resource fixtures unique and cleanup-safe across SQLite, Sage Postgres, Qdrant, and uploads, including partial seed and interrupted-stream failures.
- Hardened the 5D retrieval smoke so external identities and pre-existing Core/Sage policy are preserved, temporary sessions use the product lifecycle deletion route, and upload or Qdrant cleanup failures fail the smoke.
- Removed the legacy unstructured terminal-prose recovery escape from Sage Tool turns. Actionable turns now remain on the typed planner path, and the runtime defensively rejects any recovered prose paired with actionable Tool calls.
- Updated integration, security, confidentiality, timing, and benchmark documentation to the supported gateway and current lifecycle behavior.

## Live Evidence

- Final benchmark artifact: `/tmp/conversation-model-bench-glm-5-2-final-clean-2026-07-14.json`
- Result: 174 checks passed, zero hard failures, one bounded latency warning.
- First Tool or Trace feedback: 130–291 ms across all nine scenarios.
- Measured Tool work: 0–219 ms.
- First answer: 1.2–38.4 seconds, with the only warning on deployment readiness at 38.4 seconds despite 142 ms feedback and 20 ms Tool work.
- All ordinary prose scenarios recorded zero correction calls and multiple real answer deltas. Deterministic Admin Config proposals used one model call and no final-answer model call.
- Post-run audit: zero benchmark Users, User Types, document jobs, Resources, uploads, Qdrant points, Sage sessions, orphan agents, external identities, or benchmark-created policy rows.
- Browser Admin Config: visible status in about 2.6 seconds and a correct answer in about 21.5 seconds.
- Browser Database Query: visible status in about 2.7 seconds and a correct redacted-trace answer in about 19.8 seconds.

## Verification

- Fresh local reset/build: all Compose services healthy.
- Strict provider response-integrity smoke on GLM 5.2: passed.
- Gateway smokes 5B–5G and full/bubble Tool parity: passed.
- 5D retrieval smoke, self-owned mode: passed with session lifecycle cleanup.
- 5D retrieval smoke, external-token mode: passed with identity and Core/Sage policy preservation.
- Backend suite: 382 passed.
- Frontend suite: 384 passed; production build passed.
- Sage library suite at final commit: 142 passed; Rust formatting passed.
- Benchmark and documentation unit tests: 87 passed.
- Reset-script tests: 6 passed; changed frontend formatting passed.
- Browser verification: login, Admin Config, and Database Query passed with no page or console errors.
- Python compile, shell syntax, changed-file formatting, and `git diff --check`: passed.

## Result

The repository-controlled latency contributors were removed or bounded without weakening Tool contracts. The remaining observed long tail begins after fast local feedback and negligible Tool execution, and is predominantly GLM 5.2/provider generation variance. Natural-language Database Query can still add bounded model replans when proposed SQL is rejected; that is the remaining repository-controlled optimization seam.
