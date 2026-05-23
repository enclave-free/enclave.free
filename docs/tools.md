# Agent Runtime Tool Semantics

This document describes the current tool behavior on the Sage hard-cut prototype. The important distinction is not just which tools exist, but which runtime owns the turn.

## Route-Level Behavior

Gateway routes public Agent Runtime requests to Sage. Public clients should call the Gateway-facing paths and let Gateway dispatch to Sage:

| Gateway route | Sage runtime mode | Tool behavior |
| --- | --- | --- |
| `/llm/chat` | assistant-style, stateful, memory-backed | optional `web_search`; admin-only `db_query`; admin-only `admin_config`; optional admin trusted context |
| `/llm/chat/stream` | assistant-style streaming | prepares explicitly selected tools/context first, then streams the final answer from the Model Provider |
| `/query` | retrieval-first, stateful, memory-backed | initial document context plus internal `knowledge_search`; may also run `web_search` and admin-only `db_query` |

Python no longer owns or exposes these public Agent Runtime routes. Direct Python calls are unsupported because the routes are absent from the Enclave Control Plane; public callers use the Gateway path so nginx dispatches the request to Sage. Python remains the Enclave Control Plane behind private/internal contracts for facts and actions such as safe database reads, document search, user profile context, and lifecycle operations.

Current rule of thumb:

- Call public Agent Runtime routes through Gateway, not directly against Python.
- Use `/llm/chat` or `/llm/chat/stream` for assistant-style admin/user turns.
- Use `/query` for document-grounded, session-continuous user conversations.
- Use private Python `/internal/agent/*` endpoints only from Sage with the internal token.

See [ADR-0014](adr/0014-sage-owns-tool-aware-conversation-streaming-transport.md) and [ADR-0017](adr/0017-remove-prototype-compatibility-debt-after-sage-hard-cut.md).

## Public Tool IDs

| Public tool ID | Sage runtime tool | Access | Notes |
| --- | --- | --- | --- |
| `web-search` | `web_search` | all users | hits SearXNG for current/external information |
| `db-query` | `db_query` | admins only | delegates to Python safe read-only admin DB query |
| `admin-config` | `admin_config` | admins only | reads Scoped Config Context for Admin Conversations, including an admin-visible Tool capability overview and Instance visual identity context when relevant |

`knowledge_search` is not a public frontend toggle. Sage registers it internally for retrieval-first turns so the agent can revisit Enclave document retrieval during the turn.

## Assistant-Style Turns

Assistant-style Sage turns cover admin chat, config-assistant flows, web-search-only conversations, and no-document user conversations.

Sage owns:

- Conversation/session creation and continuation
- Session Memory writes
- effective Agent Settings lookup
- public tool choice and Model Provider calls
- streamed answer and trace events

Python contributes Control Plane facts and actions over active contracts, such as `POST /admin/db/query` and active `/internal/agent/*` endpoints.

### Admin Trusted Context

Admins can send trusted context to help the model reason over explicitly prepared client-side material such as:

- other trusted precomputed context

Prototype clients no longer send `client_executed_tools`. Trusted context is just additional context; selected tools still belong to the Sage runtime for the turn.

Current frontend behavior is intentionally boring: `web-search`, `db-query`, and `admin-config` are sent as normal tool IDs. The frontend does not call `/admin/tools/execute` or pre-run `db-query`; Sage authorizes and orchestrates the tool turn, delegating safe read-only SQL execution to Python internally when needed.

## Streaming Events

`/llm/chat/stream` returns server-sent events from Sage:

- `assistant_message_started`: announces the stable assistant message ID and session ID
- `trace_status`: reports live preparation or answer-writing status
- `answer_delta`: appends user-visible answer text to the assistant turn
- `trace_final`: attaches the final sanitized Conversation Trace when Trace Visibility Policy allows it
- `done`: completes the turn and returns session/provider/tool metadata
- `error`: reports a safe stream error without exposing raw provider traces, prompts, secrets, or database rows

The turn is intentionally two-phase: Sage prepares explicitly selected tools and trusted context first, then streams the final answer directly from the configured Model Provider. This keeps `admin-config` and database-assisted Admin Conversations tool-aware without forcing token streaming through structured DSR/BAML parsing.

## Retrieval-First Turns

Retrieval-first Sage turns cover document-grounded, session-continuous conversations.

Sage owns:

- public auth and session continuity
- Session Memory writes
- initial retrieval orchestration
- `knowledge_search` availability during the turn
- optional `web_search` and admin-only `db_query`

Python contributes active retrieval facts through the private Sage-to-Python contract, including `POST /internal/agent/document-search`.

## Admin DB Query Safety

`db_query` eventually delegates to Python's safe admin DB query path. Current protections include:

- admin auth required
- `SELECT` only
- dangerous SQL keywords blocked
- Enclave-side validation still owns the trust decision

Use it as an admin troubleshooting/config tool, not as a generic data plane.

## SearXNG Notes

`web_search` uses the internal SearXNG service at `http://searxng:8080/search?format=json`. It is intended for current or external information, not as a replacement for Enclave document retrieval.
