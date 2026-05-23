# Admin Configuration Assistant

This document describes the admin configuration assistant workflow used by:
- the admin-only configuration assistant sidebar on authenticated admin pages, and
- the full chat page (`/chat`) when the caller is an authenticated admin.

## Goals

- Provide an in-product, admin-only AI assistant for configuration questions.
- Give the assistant full awareness of current configuration state:
  - Always include the control contract needed to propose safe confirmed changes.
  - Include current configuration state by scoped read, rather than by always fetching every admin surface.
- Allow the assistant to propose and apply changes (with explicit confirmation).
- Keep tool behavior unified with the full chat page (`/chat`) so admins get the same tool pipeline from either entry point.
- Keep secret environment variables opt-in:
  - By default, secrets are not included in the assistant context.
  - An admin can explicitly toggle secret sharing per session.

## Security Model

### NIP-07 Admin Key

The admin's Nostr private key (`nsec`) is custodied by the browser extension via NIP-07 and is not accessible to the application or the assistant. The assistant should never request it.

### Secret Environment Variables

- Deployment config secrets are stored encrypted at rest in SQLite (`deployment_config`) and are masked in list endpoints.
- Secrets are not included by default.
- The admin UI can reveal a secret value with:
  - `GET /admin/deployment/config/{key}/reveal`
- The assistant bubble follows a strict rule:
  - Secrets are NOT fetched and NOT sent to the Agent Runtime unless the admin flips the "Share secret env vars" toggle.

Defense-in-depth:
- When secret sharing is enabled, the frontend keeps the revealed secret values locally and redacts any exact matches from rendered assistant messages (to prevent accidental echoing).

## Architecture

### Frontend

- Component: `frontend/src/components/admin/AdminConfigAssistant.tsx`
- Mounted for all admin pages in: `frontend/src/components/shared/AdminRoute.tsx`
- Full chat admin mode: `frontend/src/pages/ChatPage.tsx`
- Shares the same chat send runtime as `ChatPage`:
  - `frontend/src/utils/llmChat.ts` (`sendLlmChatWithUnifiedTools`)
- Transport: sends the normal public `POST /llm/chat` request to the Gateway-facing API base. Gateway routes this request to Sage; Python does not expose public `/llm/chat` or `/session-defaults` handlers in the hard-cut prototype.
  - `tools` (same admin-visible tool IDs as full chat: `web-search`, `db-query`, `admin-config`)
  - `admin-config` admin-only Sage runtime tool (enables scoped config context + change-set workflow)
  - `tool_context` only for trusted precomputed context supplied by the client
  - no `client_executed_tools`; selected tools still run in Sage when trusted context is present

Tool defaults:
- Applies Sage-owned session defaults from the Gateway/Sage runtime path (same default source as full chat).
- Config context is default-on for admin configuration conversations, while web search still follows Sage-owned session defaults.
- When an admin configuration request refers to uploaded materials, theming, copy, or content, Sage automatically uses Document Library Retrieval as first-party Instance context before answering.
- In current frontend behavior, admin `/chat` uses this assistant pipeline (runtime tools + changeset review/apply) and does not use document-scope Retrieval mode.

Sidebar behavior:
- On desktop admin pages, the assistant appears as a right sidebar by default.
- Desktop supports open and collapsed states; collapse is a layout action only, so the current assistant conversation and session-local secret sharing persist.
- Mobile/tablet dismissal closes the drawer and clears session-local secret sharing.
- On smaller screens, the assistant is closed by default and opens as a right-side drawer.

### Scoped Config Context

`admin-config` remains one visible tool toggle for admins. It is implemented as an admin-only Sage runtime tool that returns **Scoped Config Context**. This keeps admin turns responsive and prevents one slow or failing config area from blocking unrelated configuration questions.

Every scoped config context includes:

- `ADMIN-VISIBLE TOOL CAPABILITIES` for the public Tool IDs an authenticated admin can select
- Admin-assistant rules
- Change-set format and mutation constraints
- Secret-handling rules
- Generation timestamp

When scope selection is unsure, the tool should return `overview` only. The assistant should ask a focused follow-up or name the missing config area if the provided context is insufficient.

Available scopes:

- `overview`: small summary suitable for ambiguous configuration questions
- `instance-settings`: instance branding, public behavior, Instance visual identity settings, and other Instance Settings
- `deployment-settings`: Deployment Settings, grouped by config category, with secrets masked by default
- `agent-settings`: Agent Settings, including prompt sections, parameters, defaults, and per-user-type effective values when relevant
- `user-types`: user types and onboarding field definitions
- `document-defaults`: global and per-user-type document defaults
- `health`: deployment health, validation, and restart-related context

Scope selection starts as deterministic runtime-tool classification:

- Theme, appearance, branding, palette, color, typography, chat style, surface style, or status icon questions use `instance-settings`.
- Email, SMTP, domains, SSL, provider, model, SearXNG, env, or restart questions use `deployment-settings`.
- Prompt, temperature, max tokens, model behavior, user-type AI, or personalization questions use `agent-settings`.
- User type, onboarding question, or field questions use `user-types`.
- Document, default document, access, or ingestion-default questions use `document-defaults`.
- Broken, validate, health, restart, or service-status questions use `health` plus the relevant config scope.
- Ambiguous admin configuration questions use `overview`.

For Admin Conversations, theme requests mean Instance visual identity settings:

- `default_theme`
- `primary_color`
- `chat_bubble_style`
- `chat_bubble_shadow`
- `surface_style`
- `status_icon_set`
- `typography_preset`

They mean Instance Settings, not frontend CSS token or source-code theme edits. Developer-facing theme implementation remains outside the Admin Configuration Assistant.

Instance visual identity changes should be proposed as a confirmed change set using a partial `PUT /admin/settings` request body. They still require Admin Change Confirmation before any write is applied.

The former full snapshot behavior fetched:

- Instance settings:
  - `GET /admin/settings`
- Deployment config (masked secrets):
  - `GET /admin/deployment/config`
- Optional service health:
  - `GET /admin/deployment/health`
- Agent Settings:
  - `GET /admin/ai-config`
  - `GET /admin/ai-config/user-type/{user_type_id}` for each user type
- User types + fields:
  - `GET /admin/user-types`
  - `GET /admin/user-fields?user_type_id={user_type_id}` for each user type
- Document defaults:
  - `GET /ingest/admin/documents/defaults`
  - `GET /ingest/admin/documents/defaults/user-type/{user_type_id}` for each user type

If secret sharing is enabled, it additionally fetches:

- For every deployment config item with `is_secret=true`:
  - `GET /admin/deployment/config/{key}/reveal`

The former full snapshot behavior is retained only as a manual/debug behavior via **Refresh context** in the sidebar assistant. Normal admin turns use scoped reads assembled on the client for the sidebar assistant and via Sage for admin `/chat` when `admin-config` is selected.

### Model Provider Resilience

Long Admin Configuration Assistant conversations can hit Model Provider context or session limits. The product handles this with bounded context assembly, explicit recovery, direct confirmed apply, and sanitized observability.

Resilience layering on admin sends (sidebar assistant):

1. **Session Memory compaction** — older turns are summarized before the provider call (`frontend/src/utils/sessionMemoryCompaction.ts`).
2. **Prompt budget planning** — admin config, document, and recent-conversation sections are capped separately (`frontend/src/utils/promptBudget.ts`).
3. **Transport trim** — `llmChat` still bounds recent history as a final guard.

Admin `/chat` with **Config** selected runs client-side Session Memory compaction before Sage assembles the turn. Prompt budget planning and reduced-context notices are surfaced in both the sidebar assistant and the full chat admin-config path; Sage owns final prompt assembly for the full chat path.

Operator-facing notices (no raw prompts):

- **Session Memory compaction** — shown when older turns were summarized to stay within limits.
- **Reduced context** — shown when prompt budgeting trimmed admin, document, or conversation sections.

**Model Provider errors** are classified into safe categories (context limit, quota, timeout, unavailable, and others). Context-limit failures offer **Start new assistant conversation**, which clears the assistant session id and session-local secret sharing without deleting Instance, Deployment, Agent Settings, or Documents.

**Direct apply:** When a valid pending change set is in review, **Apply** executes authorized admin endpoints without another Model Provider turn. Conversational shortcuts such as “apply them” route to the existing confirmation flow only when intent is unambiguous.

**Sanitized instrumentation** (`frontend/src/utils/adminResilienceInstrumentation.ts`): maintainers can register listeners for structured metadata after compaction, prompt budgeting, and classified provider failures. Payloads include section names, estimated sizes, included/reduced/omitted scopes, provider category, and recovery action — never raw prompts, secrets, or provider traces.

### Scoped Read Resilience

Status: planned. The frontend admin assistant currently builds and refreshes
context in `frontend/src/components/admin/AdminConfigAssistant.tsx`; the Python
runtime tool only returns a small scoped context and warning field today.

Scoped config reads are best-effort. A slow or failing supporting endpoint should not block the admin assistant turn unless the failure means the admin is not authorized.

Blocking failures:

- `401 Unauthorized`
- `403 Forbidden`

Non-blocking failures:

- Timeout
- Network failure
- `5xx`
- `404` for optional scope endpoints

When a non-blocking read fails, the runtime tool should still return the available context and include a warning section:

```text
CONFIG CONTEXT WARNINGS
- health scope failed: timed out after 2500ms
```

If every requested scope fails, the runtime tool should still return the small control contract plus warnings. The assistant should ask a focused follow-up or explain which config area could not be inspected.

Timeout budget:

- Each individual scoped endpoint gets 2.5 seconds.
- The full config-context builder gets a 4-second total budget.
- Fan-out reads, such as per-user-type Agent Settings or document defaults, should stop once the total budget is exhausted.

The chat request should proceed once the context budget is spent.

### Scoped Read Cache

Status: planned. Cache invalidation and scoped-read budgets are design
requirements for the frontend/backend config-context builder, not guarantees
currently implemented by `backend/app/tools/admin_config.py`.

The runtime tool may cache successful scoped reads briefly during an admin assistant conversation:

- Cache successful scope reads for 30 seconds.
- Do not cache failed scope reads.
- Clear the cache when the admin manually refreshes assistant context.
- Invalidate all cached scopes after a change set apply succeeds or partially succeeds.
- Invalidate affected scopes after ordinary admin UI changes when the page knows which config area changed.
- Keep revealed secret values session-local; do not store them in the general scoped-config cache.

This cache is a latency optimization only. It must not replace server-side authorization or validation.

### Change Application (Confirm-Then-Apply)

The assistant can propose changes by including exactly one JSON code block with this shape:

```json
{
  "version": 1,
  "summary": "One sentence summary of what will change",
  "requests": [
    {
      "method": "PUT",
      "path": "/admin/deployment/config/LLM_PROVIDER",
      "body": { "value": "sage" }
    }
  ]
}
```

The frontend validates the change set with an allowlist (methods + path prefixes), displays a masked preview for secret deployment keys, and only applies the changes if the admin clicks **Apply**.

Additional safety rules:

- Exactly one valid change set must be present. If the assistant outputs multiple code blocks that look like change sets, the UI treats it as ambiguous and refuses to apply.
- A change set may contain at most 50 requests.
- Requests are applied sequentially, one HTTP call at a time (not as a single database transaction). Partial apply is possible.
- Certain high-risk endpoints are always blocked (even if they match a prefix), including:
  - `/admin/deployment/config/*/reveal`
  - `/admin/deployment/config/export`
  - `/prompts/preview`
  - `/admin/tools/execute`

Allowed mutation targets include:

- Deployment config: `PUT /admin/deployment/config/{key}`
- Instance settings: `PUT /admin/settings`
- Agent Settings: `PUT /admin/ai-config/{key}`, `PUT /admin/ai-config/user-type/{id}/{key}`
- User types: `POST/PUT/DELETE /admin/user-types...`
- User fields: `POST/PUT/DELETE /admin/user-fields...`
- Document defaults: `PUT/DELETE /ingest/admin/documents/...`

Note: Instance settings are updated via the single endpoint `PUT /admin/settings` (partial update supported). The backend does not expose per-key endpoints like `PUT /admin/settings/instance_name`.

### Normalization Rules (LLM Output Hardening)

Before allowlist validation, the frontend normalizes common LLM output drift:

- Coalesces `PUT /admin/settings/{key}` with body `{ "value": ... }` into a single `PUT /admin/settings` patch object.
- Normalizes `POST /admin/user-types` bodies using canonical keys only (`name`, `description`, `icon`, `display_order`).
- Normalizes `POST /admin/user-fields` bodies using canonical keys only (`field_name`, `field_type`, `display_order`, `include_in_chat`, `user_type_id`, and related backend fields).
- For `POST /admin/user-fields`, `options` must be a native JSON array (`["A","B"]`), not a JSON-encoded string (`"[\"A\",\"B\"]"`).
- Parses boolean-like values (`true/false`, `1/0`, `yes/no`) and integer-like values where supported.

### User Type Placeholders (Single Change Set)

Sometimes you want one change set to both create user types and then reference them (for fields, Agent Settings overrides, or document defaults overrides) without guessing numeric IDs.

The admin assistant UI supports a placeholder token in paths and request bodies:

- `@type:<slug>`

Where `<slug>` is the slugified user type name, computed as:
1. Convert to lowercase
2. Replace each run of one or more non-alphanumeric characters with a single `_`
3. Trim any leading/trailing `_`

Examples:
- `"Bitcoin Designer"` → `bitcoin_designer`
- `"A & B Project"` → `a_b_project`
- `"  Spaced  "` → `spaced`

This placeholder is resolved client-side at apply time by looking at existing user types and the responses from `POST /admin/user-types`.

The placeholder may appear in:

- request path segments that require a user type id
- request bodies as `"user_type_id": "@type:<slug>"`

Example:

```json
{
  "version": 1,
  "summary": "Add a new user type and attach one onboarding field",
  "requests": [
    {
      "method": "POST",
      "path": "/admin/user-types",
      "body": { "name": "Bitcoin Designer", "description": "Design-focused users" }
    },
    {
      "method": "POST",
      "path": "/admin/user-fields",
      "body": {
        "field_name": "Portfolio URL",
        "field_type": "url",
        "user_type_id": "@type:bitcoin_designer",
        "required": false
      }
    }
  ]
}
```

Explicitly blocked:
- Secret reveal endpoints (`/reveal`)
- Config export endpoints (`/export`)
- Prompt preview endpoints (`/prompts/preview`)
- Generic tool execution (`/admin/tools/execute`)

## Operational Notes

- Secret sharing is intentionally not persisted (it resets when the assistant is closed on mobile/tablet drawer dismiss, or when starting a new assistant conversation after a context-limit recovery).
- The assistant shows the same tool toggles as full chat and uses the same backend endpoint/tool semantics.
- If a deployment key change requires restart, the assistant should mention it. The backend already tracks restart-required keys via `/admin/deployment/restart-required`.
- After applying a change set, the UI runs:
  - `POST /admin/deployment/config/validate`
  - `GET /admin/deployment/restart-required`
  and appends a short summary to the chat.
- Pending change sets are preserved through Model Provider failures so reviewed configuration work is not lost.
- Streamed provider errors on the admin assistant path do not fall through to wasteful non-streaming retries when the failure category is known (for example context limit or quota exhaustion).

## Troubleshooting

### User-Field Create Reports `options ... list_type`

Error example:
- `POST /admin/user-fields: ... options Input should be a valid list [type=list_type, input_type=str]`

What to check:
- Ensure the request body uses a real JSON array for `options`, not a quoted JSON string.
- Confirm `field_type` is `select` when sending `options`.
- If the payload is already correct but the error persists, verify the backend is running a build that returns parsed field `options` arrays in create/update responses.

### Retry Then `Field name already exists for this type`

If a retry fails with duplicate field name after an earlier failure:
- Assume the earlier call may have persisted the row.
- Verify current state with `GET /admin/user-fields` (optionally filtered by `user_type_id`).
- Use `PUT /admin/user-fields/{field_id}` to correct metadata instead of re-POSTing the same field name.

## Quick Verification

Run the parity script to confirm full-chat and bubble payloads produce matching `tools_used` behavior:

```bash
python scripts/tests/TOOLS/test_4a_unified_chat_tools_parity.py --admin-token <ADMIN_TOKEN>
```
