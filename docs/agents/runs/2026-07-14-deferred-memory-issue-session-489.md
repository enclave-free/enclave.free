# Deferred Session Memory Embeddings — Issue Session #489

## Issue

- Issue: [#489](https://github.com/enclave-free/enclave.free/issues/489)
- Fixed point before session: Sage `9664b38`
- Worker session: `/root/ticket_489`
- Sage commit: `174aac68f3a0b77d69fd0a5e173b6996d711ad7c`
- Status: complete

## Inputs

- Spec issue: [#486](https://github.com/enclave-free/enclave.free/issues/486)
- Ticket: persist Session Memory rows immediately and move remote embedding work off the response critical path
- Relevant glossary terms: Session Memory, Conversation Trace, Admin Config Tool
- Relevant ADR: `docs/adr/0027-separate-tool-decisions-from-final-answer-delivery.md`

## Implementation

- `/llm/chat`, `/llm/chat/stream`, `/query`, and persisted Admin Config Tool messages insert durable rows before scheduling remote embedding work.
- Background embedding updates target the returned durable UUID; failure leaves a discoverable `NULL` embedding and does not fail the conversation.
- Assistant trace metadata attaches to the already-persisted assistant row.
- Late embedding completion uses update-only database behavior and cannot recreate a deleted history row.
- Fresh request-local memory managers share a process-local, agent-keyed weak compaction coordinator.
- Threshold compaction rechecks both summary generation and current threshold under the retained lock.
- A post-insert compaction maintenance failure preserves the durable UUID and trace-attachment path.
- `tdd` used: yes; durable-ID timing, asynchronous failure, out-of-order completion, shared-manager compaction, compaction failure, and trace-ID regressions were exercised before acceptance.

## Verification

- Targeted deferred-memory tests: 5 passed
- `cargo test -p sage-core --lib`: 143 passed
- `cargo check -p sage-core --bin enclave_web`: passed
- `cargo fmt --all -- --check`: passed
- Changed-code Clippy: passed with six unrelated base warnings explicitly allowed
- `git diff --check`: passed

## Review

- The first standards review found two P1 defects: a request-local compaction lock and trace loss after post-insert compaction failure.
- Both P1 defects were fixed and covered by regression tests.
- A misleading fake-only deletion test was removed; production deletion safety rests on update-only database semantics.
- Final spec and standards reviews were clean with no remaining P0–P2 findings.

## Risks

- Compaction coordination is process-local, matching the current single-process `enclave_web` topology. Horizontal Sage replicas would require database-level or advisory serialization.
- This ticket leaves failed embeddings repairable as `NULL`; it does not introduce a new retry worker.
