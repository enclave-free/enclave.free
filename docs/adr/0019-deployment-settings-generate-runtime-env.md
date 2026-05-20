# Deployment Settings Generate Runtime Env

Deployment Settings are the product source of truth for operator-controlled desired runtime configuration, but running services may remain stale until the Deployment applies that desired state. The first unification slice generates an auditable runtime env artifact from Deployment Settings for operator-facing integration and origin settings; the Operator or Deployment Automation applies that artifact by restarting affected services. This avoids live process mutation, avoids giving the product host/container restart authority, and keeps root bootstrap environment files separate from product-managed desired configuration.

Sage may expose an internal runtime-config fingerprint endpoint so the Enclave Control Plane can compare desired Deployment Settings with running Sage configuration without exposing raw secrets.

Operator-run Compose apply is the supported prototype path. The product may
generate, audit, export, and compare generated runtime env artifacts, but the
product must not apply generated artifacts to live services, must not rewrite
root bootstrap env files, must not restart containers, and must not require
Docker socket or host-control authority.

The product must not apply generated artifacts to live services.

Product-managed apply/restart is rejected for this prototype. An external
Deployment Automation remains a future option only behind a separate auth,
audit, and evidence contract. That future contract must identify the actor,
record artifact fingerprint evidence, record service restart or recreate
evidence, and verify post-apply runtime fingerprints where safe fingerprint
endpoints exist.

Considered options:

- Let Sage pull runtime configuration from the Enclave Control Plane at startup. Rejected for the first slice because it makes Sage boot depend more tightly on Python availability and creates a larger startup contract.
- Rewrite the root `.env` file from the admin UI. Rejected because root `.env` is operator-authored bootstrap material and app-managed rewrites would make local operations and diffs surprising.
- Let the product write env files and restart containers. Rejected for now because it crosses into host control and Docker socket authority, which is a larger security boundary than Deployment Settings need.
