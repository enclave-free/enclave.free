# Sessions

This prototype has three related session and memory concepts:

- auth sessions: browser or API authentication for admins and users
- public query-session records: Sage-owned `web_sessions` records for `/query` continuity
- Session Memory: Sage-owned Conversation history and derived memory state

## Auth Sessions

The public auth model is still Enclave's Python auth system for issuing tokens and cookies.

On this branch, Sage independently verifies the same contract for Sage-owned public routes. The gateway does not transform auth anymore.

### Token Format

Session tokens are signed with `itsdangerous.URLSafeTimedSerializer` using `SECRET_KEY`:

- user salt: `session`
- admin salt: `admin-session`
- default lifetime: 7 days

They are signed but not encrypted, so treat them as secrets.

### How Requests Authenticate

Two modes are supported:

1. cookie auth for browser clients
2. bearer auth for CLI or non-browser clients

Bearer requests are not subject to cookie CSRF checks.

### Cookie Names

- `USER_SESSION_COOKIE_NAME` default: `sanctum_session`
- `ADMIN_SESSION_COOKIE_NAME` default: `sanctum_admin_session`
- `CSRF_COOKIE_NAME` default: `sanctum_csrf`

Those names must stay aligned across Python, Sage, and the frontend.

The same is true for `SECRET_KEY`, because Sage verifies the same `itsdangerous` session format Python issues.

## CSRF Model

Both Python and Sage enforce the same high-level rules for unsafe cookie-authenticated requests:

- trusted `Origin` or `Referer` required
- `X-CSRF-Token` must match the CSRF cookie
- bearer-authenticated requests skip this check

The gateway simply forwards cookies, `Authorization`, and `X-CSRF-Token` to Sage. It does not synthesize auth or participate in CSRF decisions.

## Sage Public Query-Session Records

### What A Public Query-Session Record Is

`/query` uses a public `session_id` for Conversation continuity. On this prototype, the public session record and the underlying Session Memory are owned by Sage, not by the legacy Python in-memory session store.

Current Sage persistence model:

- `web_sessions` stores the public query-session record and ownership
- Sage Session Memory tables store the actual Conversation history and derived Session Memory state
- `external_identities` keeps a durable mapping between Enclave identities and Sage-side session ownership metadata

### Persistence Guarantees

Public query-session records and Sage Session Memory persist as long as Sage Postgres persists.

That means:

- sessions survive Sage process restarts
- sessions can be resumed across requests
- durability is no longer tied to one Python process memory map

### Ownership Rules

- admins can inspect or delete any public query-session record
- non-admin users can only access their own sessions

Sage verifies the session token itself, hydrates the user/admin record from Python's private control-plane endpoints, and then applies session ownership checks against `web_sessions`.

### API Behavior

- `POST /query` creates or resumes a session and returns `session_id`
- `GET /query/session/{session_id}` returns the stored conversation view for that session
- `DELETE /query/session/{session_id}` deletes the public query-session record and coordinates Session Memory Deletion for the associated Sage-owned Conversation memory

Current nuance:

- active Conversation deletion removes the public `web_sessions` row and associated Sage Session Memory for that Conversation
- scheduled retention for every historical Session Memory or log surface is still not implemented

## Debugging

Useful checks:

```bash
curl http://localhost:8000/auth/me \
  -H "Authorization: Bearer <user-session-token>"

curl http://localhost:8000/admin/session \
  -H "Authorization: Bearer <admin-session-token>"

curl http://localhost:8000/query/session/<session-id> \
  -H "Authorization: Bearer <session-token>"
```

If `/query` continuity looks wrong, check:

1. the user really received the same `session_id`
2. the request is still reaching Sage through the gateway
3. Sage Postgres state was not reset
