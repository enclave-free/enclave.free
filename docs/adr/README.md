# Architecture Decision Records

This directory records accepted product and architecture decisions for the Enclave Free Prototype. ADR-0023 is the current anchor for Conversation tool orchestration.

## Review Ledger

Reviewed on 2026-06-15 for the unified model-driven Tool loop hard cut:

| ADR                                                                     | Impact                                                                                                            |
| ----------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| 0001 Sage owns Agent Runtime while Python retains Enclave Control Plane | Still valid; tool choice language is reinforced by ADR-0023.                                                      |
| 0002 Privacy means operator control, not offline-only operation         | No change required.                                                                                               |
| 0003 Model Providers must support encrypted verifiable inference        | No change required; ADR-0023 stays provider-portable and avoids provider-native tool coupling.                    |
| 0004 Admin Conversations can apply confirmed control-plane changes      | Still valid; ADR-0023 keeps writes proposal-based through the non-mutating proposal Tool and Change Confirmation. |
| 0005 User Reachout is outside Conversations                             | No change required.                                                                                               |
| 0006 Retention and deletion are operator-controlled but incomplete      | No change required.                                                                                               |
| 0007 Audit Log is a product boundary but coverage is partial            | Still valid; `db-query` remains read-only and confirmed writes remain auditable.                                  |
| 0008 Replace Documents only after successful ingestion                  | No change required.                                                                                               |
| 0009 User Memory is low-sensitivity Sage context                        | No change required.                                                                                               |
| 0010 Session Memory Deletion uses retryable tombstones                  | No change required; route names remain API compatibility details.                                                 |
| 0011 Minimize Retrieval Index and encrypt chunk text                    | Still valid; ADR-0023 changes how Retrieval enters Conversations, not the storage boundary.                       |
| 0012 Conversations require current Verifiable Inference                 | No change required.                                                                                               |
| 0013 Conversation Traces are sanitized product metadata                 | Updated to route-agnostic Conversation wording.                                                                   |
| 0014 Sage owns tool-aware Conversation Streaming Transport              | Superseded for future tool-loop work by ADR-0023.                                                                 |
| 0015 External Retention Scheduler with product-owned run records        | No change required.                                                                                               |
| 0016 User Memory retention depends on retention class, not age alone    | No change required.                                                                                               |
| 0017 Remove Prototype Compatibility Debt after Sage hard cut            | Updated to name Scoped Config Context removal as part of the no-compatibility posture.                            |
| 0018 Shared rate limiting uses self-hosted Valkey                       | No change required.                                                                                               |
| 0019 Deployment Settings generate runtime env                           | No change required.                                                                                               |
| 0020 Use assistant-ui for the Conversation UI Surface                   | Updated so Knowledge is an explicit Tool control and Documents are Knowledge constraints.                         |
| 0021 Signal is a Conversation Channel                                   | No change required.                                                                                               |
| 0022 Bound Admin Database Streaming and Turn Timing                     | Superseded for future tool-loop work by ADR-0023.                                                                 |
| 0023 Unified Model-Driven Tool Loop                                     | New anchor decision.                                                                                              |
