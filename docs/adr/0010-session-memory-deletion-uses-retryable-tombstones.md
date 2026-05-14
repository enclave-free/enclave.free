# Session Memory Deletion Uses Retryable Tombstones

Enclave Free treats Session Memory Deletion as a coordinated lifecycle workflow across the Enclave Control Plane and Sage, not as a distributed transaction. Deletion must report per-target Lifecycle Deletion Results using sanitized Lifecycle Error Categories rather than raw backend errors, and incomplete deletion must leave a metadata-only Deletion Tombstone that remains visible to the Operator and can be retried without retaining Conversation Content. Successful Session Memory Deletion should leave lifecycle and audit metadata only, not Conversation Content.

Session Memory Deletion is logical active-storage deletion in the first version, not a Secure Erase guarantee across WAL, backups, snapshots, logs, or other Deployment Surfaces.

Deletion Tombstones are owned by the Enclave Control Plane as operator-visible lifecycle evidence and are visible to the Admin as the Operator's control identity, not to ordinary Users in the first version. Sage owns the Session Memory deletion target and reports target results back to the Enclave Control Plane.

User deletion may still remove active User Profile and access state when some Conversation or Session Memory targets fail, but those failures must produce retryable Deletion Tombstones and an incomplete lifecycle result rather than silently orphaning Agent Runtime data. Tombstones for deleted Users should use a minimal former-subject reference rather than retaining deleted User Profile data such as name or email.

Session Memory Deletion should use a formal internal lifecycle contract between the Enclave Control Plane and Sage rather than overloading public query-session deletion semantics.

Operator-invoked Session Memory Deletion and Retention Execution should emit Audit Log events even when no data changes or one target fails. This favors truthful lifecycle evidence and repairability over pretending that cross-runtime deletion can be atomic.
