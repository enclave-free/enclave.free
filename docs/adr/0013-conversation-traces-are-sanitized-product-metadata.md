# Conversation Traces Are Sanitized Product Metadata

The Enclave Free Prototype will expose Conversation Traces as structured, sanitized product metadata attached to assistant turns, not as raw model reasoning, provider trace blobs, full prompts, or full tool outputs. This gives Admins and Users operator-configured transparency into how Sage produced a response while preserving privacy boundaries, keeping trace visibility actor-specific through Agent Settings, and making persisted traces subject to Session Memory Deletion.

## Considered Options

- Expose raw chain-of-thought or provider reasoning traces. Rejected because it is unsafe, provider-specific, hard to redact reliably, and conflicts with the product boundary between safe Reasoning Summary and hidden model reasoning.
- Treat traces as admin-only debug logs. Rejected because Users may need operator-approved transparency in ordinary User Conversations, and chat exports should remain coherent after refresh.
- Compute traces only live and avoid persistence. Rejected because trace-backed conversations, exports, and admin troubleshooting would become lossy once the page reloads.

## Consequences

Conversation transports should return a structured `trace` object when Trace Visibility Policy permits it, and the chat UI should prefer streaming trace and answer updates when the streaming conversation transport is available. Existing route names such as `/llm/chat` and `/query` may remain API shapes, but they should share the same trace semantics. Sage should persist only the final sanitized Conversation Trace with the assistant turn it describes, should not persist traces when visibility is `off`, and should delete persisted traces through Session Memory Deletion. Streamed trace events must obey the same redaction rules as persisted traces. Trace generation is conversation metadata rather than Audit Log evidence, but Trace Visibility Policy changes and trace redaction failures should create Audit Log events.
