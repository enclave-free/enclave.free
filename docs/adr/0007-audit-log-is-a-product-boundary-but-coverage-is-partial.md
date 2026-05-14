# Audit Log Is A Product Boundary But Coverage Is Partial

Enclave Free treats the Audit Log as part of Operator-Controlled Privacy: the Operator should be able to review security-relevant and state-changing actions within an Instance.

The approved posture is:

- Confirmed Admin Conversation writes that change Instance or Agent Runtime state must emit tamper-evident Audit Log events in the same event family the equivalent admin API path would use.
- Confirmed Admin Conversation User Memory creates, supersedes, and deletes are Agent Runtime writes and must audit under `user_memories` with actor, target, action, and privacy-preserving content hashes rather than raw memory text.
- Document governance, User Approval, User Type governance, Data Deletion workflows, Deployment Settings, Agent Settings, and Document Access/default changes are operator-visible product events and must remain filterable through the Audit Log API.
- Direct database mutation is not a supported product path. The admin `db-query` tool is a read-only inspection tool; mutation statements such as `INSERT`, `UPDATE`, and `DELETE` are constrained rather than audited as valid product writes.
- Startup environment sync is an internal reconciliation path without a live operator actor. It may write configuration rows without an Audit Log event, but it must not be used as an operator-facing mutation path.
- SMTP test status writes (`SMTP_LAST_TEST_*`) are derived health/status metadata from an admin-triggered test. They are not treated as configuration authority changes; the underlying SMTP configuration updates remain the auditable product events.

Coverage is still partial. Future work should not assume a path is audited merely because it writes SQLite; each supported product mutation path must explicitly write an Audit Log event or be documented as constrained/internal.
