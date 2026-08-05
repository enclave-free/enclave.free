# enclave.free-prototype Docs

Start with the current-state docs below. They are the files that describe the active Sage hard-cut topology in this repo.

## Start Here

- [../README.md](../README.md): operator/bootstrap overview for the prototype stack.
- [dumb-gateway-foundation.md](dumb-gateway-foundation.md): current branch goal, ownership split, and what "boring gateway" means in practice.
- [prototype-sage-cutover.md](prototype-sage-cutover.md): shortest explanation of the Sage cutover, route ownership, and the Sage-to-Python contract.
- [../ARCHITECTURE_CURRENT.md](../ARCHITECTURE_CURRENT.md): current service topology, request flow, and data ownership reference.
- [tools.md](tools.md): native model-driven Tool loop semantics.
- [sessions.md](sessions.md): current auth, CSRF, Sage-backed public query-session records, and Session Memory behavior.
- [admin-deployment-config.md](admin-deployment-config.md): current deployment config split across gateway, Python, Sage, and Tinfoil.
- [internal-agent-contract.md](internal-agent-contract.md): private Sage-to-Python contract used by the prototype.
- [adr/README.md](adr/README.md): ADR review ledger and current decision index.
- [adr/0023-unified-model-driven-tool-loop.md](adr/0023-unified-model-driven-tool-loop.md): current anchor for Tool ownership and Tool Set boundaries.
- [adr/0029-native-tool-calling-with-one-tool-round.md](adr/0029-native-tool-calling-with-one-tool-round.md): current anchor for the provider-native Tool hard cut and model trust boundary.
- [adr/0030-bounded-native-tool-loop.md](adr/0030-bounded-native-tool-loop.md): current anchor for the bounded six-batch native Tool loop and final-answer delivery.
- [adr/0024-transparent-reasoning-and-tool-trace-posture.md](adr/0024-transparent-reasoning-and-tool-trace-posture.md): current anchor for live and persisted content-free model, Tool, Retrieval, retry, and timing traces.

## Core Product Docs

- [authentication.md](authentication.md): admin Nostr auth and user magic-link auth.
- [instance-initiation.md](instance-initiation.md): first-admin bootstrap and guarded public routes.
- [security.md](security.md): security overview and production hardening guidance.
- [security-data-protection-checklist.md](security-data-protection-checklist.md): engineering-facing security checklist.
- [integration-tests.md](integration-tests.md): backend and runtime parity checks.
- [conversation-ui-surface-review.md](conversation-ui-surface-review.md): pre-smoke browser review for the shared Conversation UI Surface.

## Admin And Ops

- [demo-deployment-handoff.md](demo-deployment-handoff.md): simple recipient-facing walkthrough for an already-initialized demo instance. PDF: [enclave-demo-deployment-handoff.pdf](enclave-demo-deployment-handoff.pdf). Rebuild with `python3 scripts/build_demo_handoff_pdf.py`; CI rebuilds the PDF and fails on drift.
- [release-process.md](release-process.md): minimal tag-based process for publishing versioned GitHub releases.
- [admin-config-assistant.md](admin-config-assistant.md): admin config assistant bubble and change-apply flow.
- [admin-key-recovery-runbook.md](admin-key-recovery-runbook.md): admin key recovery procedures.
- [browser-storage-posture.md](browser-storage-posture.md): browser storage allowlist, logout clearing, and cache-minimizing response guidance.
- [lifecycle-confidentiality-runbook.md](lifecycle-confidentiality-runbook.md): Active Storage Lifecycle confidentiality regression and scheduled retention operations.
- [operational-monitoring-and-recovery.md](operational-monitoring-and-recovery.md): alerting, restore drills, incident response, and drill evidence.
- [sqlite-encryption.md](sqlite-encryption.md): SQLite encryption model and migration notes.
- [user-profile-plaintext-migration-plan.md](user-profile-plaintext-migration-plan.md): removal record for legacy plaintext User Profile fallback support.
- [upstream-sync.md](upstream-sync.md): notes for syncing from upstream `enclave.free`.

## Additional Product Docs

- [upload-documents.md](upload-documents.md): document ingest workflow.
- [user-reachout.md](user-reachout.md): authenticated user email reachout flow.
- [data-protection-notice-template.md](data-protection-notice-template.md): adaptable user-facing privacy notice template.

Some older docs may describe historical behavior from before the Sage hard-cut. The Sage hard-cut docs in `Start Here` are authoritative for current Agent Runtime route ownership, Gateway behavior, and the active Sage-to-Python contract.
