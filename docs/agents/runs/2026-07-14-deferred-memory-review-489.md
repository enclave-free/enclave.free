# Deferred Session Memory Embeddings — Review #489

## Fixed Point

- Base: Sage `9664b38bbda23315cc3229f5a87740c9eab8af45`
- Reviewed commit: Sage `174aac68f3a0b77d69fd0a5e173b6996d711ad7c`
- Review axes: issue/spec contract and repository standards

## Findings and Resolution

1. P1: compaction coordination was initially local to each request-created `MemoryManager`.
   Resolution: use an agent-keyed weak registry so fresh managers in the process share a lock; recheck generation and threshold while holding it.
2. P1: a compaction error after durable insertion initially caused callers to lose the message UUID and skip assistant trace attachment.
   Resolution: make post-insert compaction best-effort and preserve the UUID/trace path; add a direct regression.
3. P2: the initial deletion fake could not recreate a row and therefore did not prove production behavior.
   Resolution: remove the misleading fake test and retain explicit update-only database behavior with zero-row logging.

## Final Result

- Spec review: clean
- Standards re-review: clean
- Remaining P0–P2 findings: none
- Full Sage library suite: 143 passed
- Runtime build check, formatting, changed-code Clippy, and diff hygiene: passed
