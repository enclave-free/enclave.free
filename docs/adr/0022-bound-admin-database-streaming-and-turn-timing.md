# Bound Admin Database Streaming and Turn Timing

Status: Superseded for future Tool-loop work by [ADR-0023](0023-unified-model-driven-tool-loop.md). This ADR documents the earlier latency-bound streaming investigation.

Streaming **Admin Conversations** may execute the Database tool only when the submitted admin message is already a direct read-only `SELECT` query that passes the existing safe database validation. Natural-language database questions in the streaming path should not trigger text-to-SQL or automatic database execution; Sage may draft a suggested `SELECT` in the assistant answer, but the **Admin** must review and submit it before execution. **Conversation Turn Timing** is transient admin-facing status for the current turn and should not be persisted as **Conversation Trace** or **Audit Log** evidence in this latency investigation.

## Considered Options

- Allow natural-language database questions to run text-to-SQL during streaming. Rejected because it can add an opaque model call before the final answer stream and preserve the 30-60 second wait this investigation is trying to isolate.
- Fall back from streaming to the slower non-streaming database path. Rejected because silent fallback hides the latency boundary and makes Admin Conversations feel inconsistent.
- Persist timing diagnostics in Conversation Trace. Rejected for now because timing metadata changes the product meaning of Conversation Trace and can be revisited after real **Conversation Turn Timing** observations identify the bottleneck.

## Consequences

The streaming Admin Conversation path should make the database boundary visible as a guarded tool step with a warning when Database is selected but not executed. Direct safe `SELECT` queries can still run through the existing Enclave Control Plane validation. Natural-language database help remains available as assistant guidance, but not as automatic database execution in the streaming turn. Timing diagnostics can help diagnose slow turns without creating durable product evidence or expanding trace retention scope.
