# enclave.free-prototype Docs

Start with the current-state docs below. They are the files that describe the active Sage hard-cut topology in this repo.

## Start Here

- [../README.md](../README.md): operator/bootstrap overview for the prototype stack.
- [dumb-gateway-foundation.md](dumb-gateway-foundation.md): current branch goal, ownership split, and what "boring gateway" means in practice.
- [prototype-sage-cutover.md](prototype-sage-cutover.md): shortest explanation of the Sage cutover, route ownership, and the Sage-to-Python contract.
- [../ARCHITECTURE_CURRENT.md](../ARCHITECTURE_CURRENT.md): current service topology, request flow, and data ownership reference.
- [tools.md](tools.md): unified model-driven Tool loop semantics.
- [sessions.md](sessions.md): current auth, CSRF, Sage-backed public query-session records, and Session Memory behavior.
- [admin-deployment-config.md](admin-deployment-config.md): current deployment config split across gateway, Python, Sage, and Tinfoil.
- [internal-agent-contract.md](internal-agent-contract.md): private Sage-to-Python contract used by the prototype.
- [adr/README.md](adr/README.md): ADR review ledger and current decision index.
- [adr/0023-unified-model-driven-tool-loop.md](adr/0023-unified-model-driven-tool-loop.md): current anchor for Conversation Tool orchestration.

## Core Product Docs

- [authentication.md](authentication.md): admin Nostr auth and user magic-link auth.
- [instance-initiation.md](instance-initiation.md): first-admin bootstrap and guarded public routes.
- [security.md](security.md): security overview and production hardening guidance.
- [security-data-protection-checklist.md](security-data-protection-checklist.md): engineering-facing security checklist.
- [integration-tests.md](integration-tests.md): backend and runtime parity checks.
- [conversation-ui-surface-review.md](conversation-ui-surface-review.md): pre-smoke browser review for the shared Conversation UI Surface.

## Admin And Ops

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
