# enclave.free-prototype Docs

Start with the current-state docs below. They are the files that describe the active Sage hard-cut topology in this repo.

## Start Here

- [../README.md](../README.md): operator/bootstrap overview for the prototype stack.
- [dumb-gateway-foundation.md](dumb-gateway-foundation.md): current branch goal, ownership split, and what "boring gateway" means in practice.
- [prototype-sage-cutover.md](prototype-sage-cutover.md): shortest explanation of the Sage cutover, route ownership, and the Sage-to-Python contract.
- [../ARCHITECTURE_CURRENT.md](../ARCHITECTURE_CURRENT.md): current service topology, request flow, and data ownership reference.
- [tools.md](tools.md): current `/llm/chat` and `/query` tool semantics.
- [sessions.md](sessions.md): current auth, CSRF, and Sage-backed query session behavior.
- [admin-deployment-config.md](admin-deployment-config.md): current deployment config split across gateway, Python, Sage, and Tinfoil.
- [internal-agent-contract.md](internal-agent-contract.md): private Sage-to-Python contract used by the prototype.

## Core Product Docs

- [authentication.md](authentication.md): admin Nostr auth and user magic-link auth.
- [instance-initiation.md](instance-initiation.md): first-admin bootstrap and guarded public routes.
- [security.md](security.md): security overview and production hardening guidance.
- [security-data-protection-checklist.md](security-data-protection-checklist.md): engineering-facing security checklist.
- [integration-tests.md](integration-tests.md): backend and runtime parity checks.

## Admin And Ops

- [admin-config-assistant.md](admin-config-assistant.md): admin config assistant bubble and change-apply flow.
- [admin-key-recovery-runbook.md](admin-key-recovery-runbook.md): admin key recovery procedures.
- [sqlite-encryption.md](sqlite-encryption.md): SQLite encryption model and migration notes.
- [upstream-sync.md](upstream-sync.md): notes for syncing from upstream `enclave.free`.

## Additional Product Docs

- [upload-documents.md](upload-documents.md): document ingest workflow.
- [user-reachout.md](user-reachout.md): authenticated user email reachout flow.
- [data-protection-notice-template.md](data-protection-notice-template.md): adaptable user-facing privacy notice template.

Some older docs still use legacy `Sanctum` naming because that is how parts of the product and database were originally labeled. Use the docs in the `Start Here` section as the current architecture source of truth.
