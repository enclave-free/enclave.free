# Agent Runtime Tool Semantics

This document describes the current tool behavior on the Sage hard-cut prototype. The important distinction is not just which tools exist, but which route owns execution and whether the turn is assistant-style or retrieval-first.

## Route-Level Behavior

| Route | Runtime mode | Tool behavior |
| --- | --- | --- |
| `/llm/chat` | stateful and memory-backed | optional server-side `web-search`; optional admin-only `db-query`; optional admin-only `admin-config`; optional admin `tool_context` injection |
| `/llm/chat/stream` | stateful, memory-backed, assistant-style streaming | prepares explicitly selected tools/context first, then streams the final answer from the Model Provider |
| `/query` | stateful and memory-backed | always retrieval-first; always has internal `knowledge_search`; may also run `web_search` and admin-only `db_query` |

Current rule of thumb:

- use `/llm/chat` for assistant-style turns, admin chat, config-assistant flows, and no-document user conversations
- use `/llm/chat/stream` when the UI can consume assistant-style server-sent events and wants lower perceived latency
- use `/query` for document-grounded, session-continuous user conversations

`/llm/chat/stream` is owned by Sage for public AI-route behavior. Python remains the Enclave Control Plane behind private/internal contracts for facts and actions such as safe database reads. Retrieval-first `/query/stream` is a separate follow-up scope; the first streaming slice only covers assistant-style chat. See [ADR-0014](adr/0014-sage-owns-tool-aware-conversation-streaming-transport.md).

## Public Tool IDs

| Public tool ID | Sage runtime tool | Access | Notes |
| --- | --- | --- | --- |
| `web-search` | `web_search` | all users | hits SearXNG for current/external information |
| `db-query` | `db_query` | admins only | delegates to Python safe read-only admin DB query |
| `admin-config` | `admin_config` | admins only | reads Scoped Config Context for Admin Conversations |

`knowledge_search` is not a public frontend toggle. Sage registers it internally for `/query` so the agent can revisit Enclave document retrieval during the turn.

## `/llm/chat`

`/llm/chat` is the assistant-style session route:

- creates or resumes a `web_sessions` Conversation when `session_id` is provided
- stores user and assistant turns in Session Memory
- effective Agent Settings are loaded from Sage Postgres per request
- selected tools may execute server-side before or during the agent turn
- `tool_context` is accepted only for admins

### Admin `tool_context`

Admins can send extra context in `tool_context` to help the model reason over client-side material such as:

- decrypted DB rows
- other trusted precomputed context

When `tool_context` is present, clients should also send `client_executed_tools` so Sage does not re-run tools that have already been executed client-side.

Current frontend pattern for client-executed tools:

1. optional client-side call to `POST /admin/tools/execute`
2. decrypt or format the returned data in the browser
3. send the formatted text in `tool_context`
4. include `client_executed_tools`, usually `["db-query"]`

`admin-config` is not client-executed. Admin clients send it as a normal tool ID, and Sage executes the admin-only runtime tool server-side.

Non-admin use of `tool_context` is rejected with `403`.

## `/llm/chat/stream`

`/llm/chat/stream` is the streaming companion to `/llm/chat`. It keeps the same assistant-style route ownership and compatibility model, but returns server-sent events instead of a single JSON response.

Current event shape:

- `assistant_message_started`: announces the stable assistant message ID and session ID
- `trace_status`: reports live preparation or answer-writing status
- `answer_delta`: appends user-visible answer text to the assistant turn
- `trace_final`: attaches the final sanitized Conversation Trace when Trace Visibility Policy allows it
- `done`: completes the turn and returns session/provider/tool metadata
- `error`: reports a safe stream error without exposing raw provider traces, prompts, secrets, or database rows

The turn is intentionally two-phase: Sage prepares explicitly selected tools and trusted context first, then streams the final answer directly from the configured Model Provider. This keeps `admin-config` and database-assisted Admin Conversations tool-aware without forcing token streaming through structured DSR/BAML parsing.

### Example

```bash
curl -X POST http://localhost:8000/llm/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "message": "What changed in Bitcoin price today?",
    "tools": ["web-search"],
    "session_id": "existing-session-id-if-any"
  }'
```

## `/query`

`/query` is the retrieval-first route:

- Sage verifies auth natively and then hydrates Enclave Control Plane actor metadata from Python
- Sage loads or creates a durable public query-session record in `web_sessions`
- Sage fetches initial Document context from Python
- Sage stores user and assistant turns in Session Memory
- Sage always has internal `knowledge_search` available

If the request also enables `web-search`, Sage may run SearXNG during the turn. If an admin enables `db-query`, Sage may also call the Enclave Control Plane read-only DB tool during the turn.

### Example

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "question": "How do these uploaded docs relate to recent regulation changes?",
    "tools": ["web-search"],
    "job_ids": ["job_123"],
    "session_id": "existing-session-id-if-any"
  }'
```

### Response Notes

Current `/query` responses include:

- `session_id`
- `sources`
- `graph_context`
- `clarifying_questions`
- `context_used`
- `temperature`

`search_term` is still present in the response shape for compatibility, but on the current Sage path it is reserved and returned as `null`.

## Admin DB Query Safety

`db_query` eventually delegates to Python's safe admin DB query path. Current protections include:

- admin auth required
- `SELECT` only
- dangerous SQL keywords blocked
- Enclave-side validation still owns the trust decision

Use it as an admin troubleshooting/config tool, not as a generic data plane.

## SearXNG Notes

`web_search` uses the internal SearXNG service at `http://searxng:8080/search?format=json`. It is intended for current or external information, not as a replacement for Enclave document retrieval.
