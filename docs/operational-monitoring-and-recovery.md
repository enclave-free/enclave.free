# Operational Monitoring and Recovery

This runbook covers operator-owned monitoring and recovery verification for production-like Enclave deployments. It complements `POST /admin/deployment/config/validate`, `GET /admin/deployment/operational-readiness`, `docs/admin-key-recovery-runbook.md`, and `docs/security-data-protection-checklist.md`.

## Runtime Alerting

Configure alerts outside the product runtime for:

- repeated auth failures from magic-link requests, session validation, and Admin authentication;
- unusual Admin actions such as off-hours configuration changes, lifecycle review changes, export activity, or database-inspection activity;
- destructive endpoint usage such as deletion, purge, migration, irreversible Audit Log detail compaction, and lifecycle execution endpoints.

Use Audit Log records, gateway access logs, and application logs as evidence sources. Alert rules should identify the actor where available, the route or action category, the affected object, timestamp, source IP or proxy identity where available, and the follow-up ticket or incident record.

## Backup and Restore Verification

Run a restore drill quarterly and before production upgrades or storage migrations. The drill must cover:

- SQLite: restore the database into an isolated environment, run migrations, and verify Admin login plus representative User Conversation and lifecycle status reads.
- deployment config: restore non-secret settings and secret references without copying raw secret values into evidence.
- uploads: restore the uploads directory and verify document listing, download, ingest metadata, and lifecycle deletion behavior.
- Retrieval Index: restore Qdrant from a snapshot or rebuild it from product storage, then verify retrieval hydrates chunk text from SQLite rather than vector payload text.

Record the restore drill date, operator, environment, backup source, targets covered, result, failures, and follow-up actions.

## Incident Response

For repeated auth failures, unusual Admin actions, or destructive endpoint usage:

1. Preserve Audit Log, gateway, and application log evidence.
2. Identify affected accounts, sessions, configuration keys, documents, exports, and lifecycle records.
3. Rotate affected secrets or sessions when compromise is plausible.
4. Review Deployment Surface retention for provider traces, runtime logs, backups, snapshots, copied exports, and browser-held copies.
5. Record the incident timeline, decision log, and recovery validation.

## Admin Key Recovery

Use `docs/admin-key-recovery-runbook.md` for admin key recovery. Include the recovery scenario, whether a tested backup exists, whether encrypted PII remains recoverable, and any irreversible access loss in the incident record.

## Drill Evidence

For each alert drill, restore drill, incident response drill, or admin key recovery drill, record drill evidence:

- date and operator;
- scenario;
- systems and data classes covered;
- expected signal or recovery result;
- actual result;
- follow-up action and owner;
- checklist evidence update.

Update `docs/security-data-protection-checklist.md` when a drill completes.
