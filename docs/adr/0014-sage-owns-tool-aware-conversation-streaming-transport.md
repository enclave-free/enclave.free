# Sage Owns Tool-Aware Conversation Streaming Transport

The Enclave Free Prototype will implement assistant-style Conversation Streaming Transport in Sage's `enclave_web` runtime, using a two-phase turn: explicitly selected tools and trusted context are prepared first, then the final user-visible answer streams directly from the configured Model Provider. This preserves Sage ownership of public AI route behavior, keeps admin configuration and database-assisted conversations tool-aware, and avoids forcing token streaming through structured DSR/BAML parsing that only becomes useful after a full response is complete.

## Considered Options

- Add compatibility streaming in Python first. Rejected because public AI-route behavior is owned by Sage in this prototype, and Python should remain the Enclave Control Plane.
- Stream only no-tool turns first. Rejected because the latency problem is most visible in Admin Conversations where selected tools and admin context matter.
- Stream the final answer through DSR/BAML. Rejected because DSR/BAML is valuable for structured tool/context work, but the final answer phase should be plain user-visible prose that can be forwarded as Model Provider chunks arrive.

## Consequences

Sage should expose `/llm/chat/stream` for assistant-style Conversations before retrieval-first `/query/stream`. The first implementation should execute explicitly selected tools only, emit early assistant-turn and live trace-status events, wait for selected tools to finish, stream final answer deltas from the Model Provider, then emit the final sanitized Conversation Trace and completion event.
