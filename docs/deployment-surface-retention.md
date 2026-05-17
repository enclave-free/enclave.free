# Deployment Surface Retention Boundaries

Active Storage Lifecycle controls product-owned active records. Deployment Surfaces are different: they are created or retained by the operator's runtime, database, browser, provider, or export handling.

Acknowledging a Deployment Surface category records operator review only. It does not promote the category into a Lifecycle Data Class and does not make product Data Deletion or Retention controls apply to it.

## Operator-Owned Categories

| Category | Operator retention policy |
| --- | --- |
| Runtime logs | Set retention, redaction, access controls, export rules, and disposal in the container host, platform, or log sink. |
| Database internals | Manage SQLite/Postgres WAL, replication, checkpoint/vacuum behavior, and maintenance artifacts through database operations policy. |
| Backups and snapshots | Define encryption, expiry, restore testing, and destruction for host backups, volume snapshots, VM images, and database snapshots. |
| Browser-held copies | Use browser/device policy for downloads, cache, local storage, session storage, and profile data on operator or user devices. |
| Copied Exports | Treat downloaded exports as operator-held records with separate storage, sharing, retention, and disposal rules. |
| Provider traces | Review LLM, email, search, hosting, and infrastructure provider contracts; disable provider-side logging where required. |

## Secure Erase Boundary

Enclave does not claim Secure Erase in v1. Product workflows can delete supported active product records and report per-target status, but they cannot guarantee overwrite, crypto-erase, provider log deletion, backup deletion, WAL scrubbing, browser cache recall, or platform snapshot destruction.

## Historical Session and Log Retention

Active Session Memory deletion is separate from historical log/session retention. The product can coordinate supported Sage Session Memory deletion for active conversations, while historical platform logs, provider traces, backups, snapshots, and other Deployment Surfaces remain operator responsibilities until a separate retention process exists.

