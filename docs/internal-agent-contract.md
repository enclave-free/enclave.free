# Internal Agent Contract v0

This document is the source of truth for the private `/internal/agent/*` and
`/internal/lifecycle/*` contracts between Sage and the Python control plane on
the current prototype.

These routes are not part of the public product API. Sage is the intended
caller, Python is the owner, and both sides must evolve request and response
schemas together. They are protected by the shared internal token even when
reachable through a local development gateway.

## Authentication

Every endpoint requires:

```http
X-Internal-Agent-Token: <INTERNAL_AGENT_TOKEN>
```

Clients should send `Accept: application/json`. `POST` endpoints require JSON
request bodies and should send `Content-Type: application/json`. Responses are
JSON, including FastAPI error payloads.

If `INTERNAL_AGENT_TOKEN` is unset in Python, protected routes return `503`.
If the header is missing or wrong, protected routes return `403`.

## Error Responses

The current implementation uses FastAPI's default error shape for auth,
validation, and explicit `HTTPException` failures:

```json
{
  "detail": "Invalid internal agent token"
}
```

Validation failures use FastAPI's structured `detail` array. Example:

```json
{
  "detail": [
    {
      "loc": ["body", "query"],
      "msg": "Field required",
      "type": "missing"
    }
  ]
}
```

Common statuses:

- `403`: missing or invalid `X-Internal-Agent-Token`
- `404`: missing user, admin, or user type records
- `422`: malformed JSON, missing required request fields, or invalid field types
- `503`: Python service has no `INTERNAL_AGENT_TOKEN` configured
- `5xx`: embedding, Qdrant, document-store, SQLite, or other infrastructure failure

## Active Endpoints

### `GET /internal/agent/health`

Returns internal-agent health.

Response:

```json
{
  "status": "healthy"
}
```

## Lifecycle Contract

Session Memory Deletion is now modeled as an operator-visible lifecycle
workflow under `/internal/lifecycle/*` rather than a bare public query-session
delete. The Enclave Control Plane owns deletion tombstones and Audit Log
evidence; Sage owns the Session Memory deletion target and must report
sanitized per-target lifecycle results.

### `POST /internal/lifecycle/session-memory/delete`

Deletes Sage-owned Session Memory for one Conversation. This endpoint is
internal-only and requires `X-Internal-Agent-Token`.

Request:

```json
{
  "conversation_id": "uuid"
}
```

Response:

```json
{
  "status": "deleted",
  "deletion": {
    "status": "succeeded",
    "retryable": false,
    "counts": {
      "succeeded": 1,
      "skipped": 0,
      "failed": 0
    },
    "results": []
  }
}
```

Field contract:

- `status`: outer endpoint outcome; currently `deleted` when Sage accepted the lifecycle delete request. Transport or auth failures use HTTP error status codes rather than this field.
- `deletion.status`: aggregate lifecycle result. Allowed values are `succeeded`, `partial_failure`, and `failed`.
- `deletion.retryable`: `true` when at least one failed target can be retried by the control plane; `false` when the result is complete or only contains non-retryable skips.
- `deletion.counts.succeeded`: number of lifecycle targets successfully deleted.
- `deletion.counts.skipped`: number of targets intentionally skipped, such as already-absent Session Memory or non-applicable targets.
- `deletion.counts.failed`: number of lifecycle targets that failed.
- `deletion.results`: per-target lifecycle evidence. It may be empty when Sage has no target-level detail to report. When populated, each result object includes `target_kind`, `target_id`, `action`, `status`, `retryable`, and `detail`. Failure details must use sanitized lifecycle error categories rather than raw backend errors or secrets.

The control plane sanitizes failed lifecycle details into stable categories
such as `target_unavailable`, `not_found`, `already_deleted`,
`unauthorized_internal_contract`, or `target_error` before storing tombstones or
Audit Log evidence. Tombstones must remain metadata-only: they may include a
Conversation id, Former Subject Reference, lifecycle class, source workflow,
retry count, status, and sanitized deletion result, but no Conversation Content
or deleted User PII.

Until secure erase and complete historical log/session retention are defined,
docs and UI must not imply secure erase or complete historical deletion.

### `GET /internal/agent/users/{user_id}`

Hydrates a user after Sage verifies a user session token.

Response:

```json
{
  "id": 123,
  "approved": true,
  "email": "user@example.com",
  "name": "User Name",
  "user_type_id": 1,
  "dev_mode": false
}
```

Missing users return `404`:

```json
{
  "detail": "User not found: 123"
}
```

### `GET /internal/agent/admins/by-pubkey/{pubkey}`

Hydrates an admin after Sage verifies an admin session token.

Response:

```json
{
  "id": 1,
  "pubkey": "<hex-pubkey>",
  "session_nonce": 0
}
```

Missing admins return `404`:

```json
{
  "detail": "Admin not found: <hex-pubkey>"
}
```

### `GET /internal/agent/user-types/{user_type_id}`

Returns user-type metadata for Sage config and admin responses.

Response:

```json
{
  "id": 1,
  "name": "Client",
  "description": "Optional description",
  "icon": "user",
  "display_order": 0,
  "created_at": "2026-04-12T00:00:00"
}
```

Missing user types return `404`:

```json
{
  "detail": "User type not found: 1"
}
```

### `GET /internal/agent/document-access`

Returns document IDs visible/defaulted for a user type.

Query:

- `user_type_id`: optional integer

Response:

```json
{
  "user_type_id": 1,
  "available_document_ids": ["job_123"],
  "default_document_ids": ["job_123"]
}
```

### `GET /internal/agent/user-profile-context/{user_id}`

Returns profile context that Sage may include in prompts.

Query:

- `user_type_id`: optional integer

Response:

```json
{
  "user_id": 123,
  "user_type_id": 1,
  "profile": {
    "Country": "Nicaragua"
  }
}
```

### `POST /internal/agent/document-search`

Runs Enclave document retrieval with Python-owned document access rules.

Request:

```json
{
  "query": "What documents apply?",
  "user": {
    "id": 123,
    "type": "user",
    "approved": true,
    "pubkey": null,
    "email": "user@example.com",
    "name": "User Name",
    "user_type_id": 1,
    "dev_mode": false
  },
  "top_k": 8,
  "job_ids": ["job_123"],
  "jurisdiction": "Nicaragua",
  "situation_details": "Optional context"
}
```

Response:

```json
{
  "sources": [],
  "context": "",
  "search_query": "What documents apply?",
  "top_k": 8
}
```

Qdrant, embedding, or document-store failures bubble as 5xx responses.
Malformed JSON, missing `query` or `user`, invalid field types, or invalid
`user` object shape return `422`. Validated request fields include `query`,
`user`, `top_k`, `job_ids`, `jurisdiction`, `situation_details`, and
`user.user_type_id`.

### `POST /internal/agent/admin-db-query`

Executes Python-owned safe read-only admin SQL.

Request:

```json
{
  "sql": "SELECT COUNT(*) AS count FROM users"
}
```

Response:

```json
{
  "success": true,
  "columns": ["count"],
  "rows": [{"count": 0}],
  "executionTimeMs": 1,
  "error": null
}
```

Invalid or unsafe SQL returns `success: false` with an `error` string rather
than throwing, unless an unexpected infrastructure failure occurs.

Example unsafe SQL response:

```json
{
  "success": false,
  "columns": [],
  "rows": [],
  "executionTimeMs": 0,
  "error": "Only SELECT queries are allowed. Use the CRUD endpoints for modifications."
}
```

## Compatibility-Only Endpoints

These endpoints may still exist in Python for older local paths, but Sage does
not depend on them in the current public route graph:

- `GET /internal/agent/session-defaults`
- `GET /internal/agent/ai-config/effective`
- any old `auth-context` endpoint references

Do not add new Sage dependencies on compatibility-only endpoints without
promoting them here as active contract endpoints.

## Change Rules

- Keep endpoint paths stable for this prototype branch.
- Additive response fields are allowed if Sage ignores unknown fields.
- Removing or renaming fields requires coordinated Sage and Python changes in
  the same pull request.
- Auth semantics and the internal token header name are not versioned; changing
  either requires a new contract version.
