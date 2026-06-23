# Admin Configuration Assistant

This document describes the admin configuration assistant workflow used by:

- the admin-only configuration assistant sidebar on authenticated admin pages, and
- the full chat page (`/chat`) when the caller is an authenticated admin.

## Goals

- Provide an in-product, admin-only AI assistant for configuration questions.
- Give Sage real configuration Tools it can call eagerly when the Admin asks about current Instance state.
- Allow the assistant to propose and apply changes (with explicit confirmation).
- Keep tool behavior unified with the full chat page (`/chat`) so admins get the same tool pipeline from either entry point.
- Keep secret environment variables opt-in:
  - By default, secrets are not included in the assistant context.
  - An admin can explicitly toggle secret sharing per session.
- Preserve guided onboarding while using the same underlying Admin Config Tool Set as normal Admin Conversations.

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
  - `tools` / Tool Sets (same admin-visible Tool Set IDs as full chat: `knowledge-search`, `curated-resources`, `web-search`, `admin-config`, `db-query`)
  - `admin-config` admin-only Tool Set
  - optional Tool constraints such as Knowledge Search document scope
  - no `client_executed_tools`
  - no admin configuration `tool_context` prefetch

Tool defaults:

- Applies Sage-owned session defaults from the Gateway/Sage runtime path (same default source as full chat).
- `admin-config` is default-on for admin configuration conversations, while `web-search` and `db-query` remain explicit unless enabled by defaults.
- `knowledge-search` is a visible Tool Set. When an admin configuration request refers to uploaded materials, theming, copy, or content, Sage should call Knowledge Search when enabled and relevant.
- `curated-resources` is a visible Tool Set for the admin-curated Resource Directory. It is separate from Knowledge Search and should be used for vetted referral/resource suggestions, not uploaded document retrieval.
- Admin `/chat`, the sidebar, and guided onboarding use the same Sage model-driven Tool loop.
- The browser does not assemble or inject admin configuration snapshots for chat turns.

Sidebar behavior:

- On desktop admin pages, the assistant appears as a right sidebar by default.
- Desktop supports open and collapsed states; collapse is a layout action only, so the current assistant conversation and session-local secret sharing persist.
- Mobile/tablet dismissal closes the drawer and clears session-local secret sharing.
- On smaller screens, the assistant is closed by default and opens as a right-side drawer.

### Admin Config Tool Set

`admin-config` is one visible Tool Set for admins. It exposes concrete model-callable Tools, rather than a single scoped prompt blob chosen by deterministic classification.

Initial Tools:

- `read_instance_settings`
- `read_deployment_settings`
- `read_deployment_readiness`
- `read_agent_settings`
- `read_user_types`
- `read_document_access`
- `read_onboarding_status`
- `propose_admin_config_bootstrap`
- `propose_config_change_set`

Tool descriptions should encourage Sage to inspect current Instance reality when it can answer the Admin's question. If the Admin asks what is configured, missing, ready, stale, stored, available, or still needing setup, Sage should call the relevant read Tool instead of asking the Admin to check manually.

There is no `overview` fallback scope and no keyword category classifier. If one Tool result is not enough, Sage may call another enabled Tool in the same model-driven loop until it has enough evidence or hits deterministic limits.

Admin write intent is represented through non-mutating proposal Tools. Primary guided bootstrap/setup should use `propose_admin_config_bootstrap`, whose arguments describe setup intent in product terms: instance identity, assistant identity, public copy, visual defaults, language, access policy, user types, onboarding questions, and supported behavior-rule intent. Deterministic Sage code builds the canonical request paths and bodies, validates the resulting change set, and stages it for the same Admin Change Confirmation flow.

`propose_config_change_set` remains available as a lower-level compatibility and escape-hatch Tool for supported Admin Config writes that do not yet have a typed proposal Tool. The UI validates every staged change set and still requires Admin Change Confirmation before applying ordinary admin endpoints.

Canonical Admin Config proposal shapes:

- Instance settings: `PUT /admin/settings` with a patch body using stored setting keys such as `instance_name`, `assistant_name`, `header_tagline`, `description`, `primary_color`, `default_theme`, `default_language`, and `auto_approve_users`.
- Agent Settings: `PUT /admin/ai-config/{key}` with `{ "value": "..." }`. Behavior rules and forbidden topics use `PUT /admin/ai-config/prompt_rules` and `PUT /admin/ai-config/prompt_forbidden` with `value` set to a JSON string array, such as `{ "value": "[\"Ask users where they are from before giving location-specific guidance.\"]" }`.
- User types: `POST /admin/user-types` with `{ "name", "description"?, "icon"?, "display_order"? }`.
- User fields/onboarding questions: `POST /admin/user-fields` with `{ "field_name", "field_type", "required"?, "display_order"?, "user_type_id"?, "placeholder"?, "options"?, "encryption_enabled"?, "include_in_chat"? }`. A bootstrap change set may reference newly proposed user types with `@type:<slug>` placeholders so Apply can resolve the created IDs.
- Guided onboarding bootstrap should propose the eight baseline settings plus any supplied visual defaults, user types, onboarding questions, and behavior rules in one change set when the admin has supplied them.

For Admin Conversations, theme requests mean Instance visual identity settings:

- `default_theme`
- `primary_color`
- `chat_bubble_style`
- `chat_bubble_shadow`
- `surface_style`
- `status_icon_set`
- `typography_preset`

They mean Instance Settings, not frontend CSS token or source-code theme edits. Developer-facing theme implementation remains outside the Admin Configuration Assistant.

Instance visual identity changes should be proposed through `propose_config_change_set` using a partial `PUT /admin/settings` request body. They still require Admin Change Confirmation before any write is applied.

The sidebar assistant, full chat page, and onboarding surface all use the same Tool Set. Onboarding may shape the guided prompt and proposed bootstrap setup, but it must not call a separate onboarding scope or inject an admin configuration snapshot.

### Model Provider Resilience

Long Admin Configuration Assistant conversations can hit Model Provider context or session limits. The product handles this with bounded context assembly, explicit recovery, direct confirmed apply, and sanitized observability.

Resilience layering on admin sends (sidebar assistant):

1. **Session Memory compaction** — older turns are summarized before the provider call (`frontend/src/utils/sessionMemoryCompaction.ts`).
2. **Tool output budgeting** — Sage caps Tool results and summarizes or truncates oversized outputs before they re-enter the model loop.
3. **Transport trim** — `llmChat` still bounds recent history as a final guard.

Admin `/chat` with **Config** selected runs the same model-driven Tool loop as
the sidebar assistant: Session Memory compaction, explicit Tool contracts,
Tool result budgeting, change-set review, and confirmed apply. Both surfaces
have identical Tool behavior and reduced-context notices.

Operator-facing notices (no raw prompts):

- **Session Memory compaction** — shown when older turns were summarized to stay within limits.
- **Reduced context** — shown when prompt budgeting trimmed admin, document, or conversation sections.

**Model Provider errors** are classified into safe categories (context limit, quota, timeout, unavailable, and others). Context-limit failures offer **Start new assistant conversation**, which clears the assistant session id and session-local secret sharing without deleting Instance, Deployment, Agent Settings, or Documents.

**Direct apply:** When a valid pending change set is in review, **Apply** executes authorized admin endpoints without another Model Provider turn. Conversational shortcuts such as “do it” or “apply them” route to the existing confirmation flow only when intent is unambiguous; they never auto-apply and never start another Model Provider turn while a proposal is pending.

**Sanitized instrumentation** (`frontend/src/utils/adminResilienceInstrumentation.ts`): maintainers can register listeners for structured metadata after compaction, prompt budgeting, and classified provider failures. Payloads include section names, estimated sizes, included/reduced/omitted scopes, provider category, and recovery action — never raw prompts, secrets, or provider traces.

### Tool Read Resilience

Admin Config Tool reads are best-effort. A slow or failing supporting endpoint should not block the admin assistant turn unless the failure means the admin is not authorized.

Blocking failures:

- `401 Unauthorized`
- `403 Forbidden`

Non-blocking failures:

- Timeout
- Network failure
- `5xx`
- `404` for optional supporting read endpoints

When a non-blocking read fails, the Tool should still return available structured data and include a warning:

```text
TOOL WARNINGS
- deployment_readiness failed: timed out after 2500ms
```

If every relevant read fails, Sage should explain which Tool could not inspect reality and ask a focused follow-up only if no other enabled Tool can answer.

Timeout budget:

- Each individual Tool execution gets a bounded timeout.
- The full model-driven Tool loop gets a bounded step/time budget.
- Fan-out reads, such as per-user-type Agent Settings or document access, should stop once the Tool budget is exhausted.

The chat request should proceed once the Tool budget is spent.

### Tool Result Cache

Status: planned. Tool result caching is a latency optimization, not a context
assembly contract.

Sage may cache successful read Tool results briefly during an admin assistant conversation:

- Cache successful read Tool results for 30 seconds.
- Do not cache failed Tool results.
- Invalidate affected Tool results after a change set apply succeeds or partially succeeds.
- Invalidate affected Tool results after ordinary admin UI changes when the page knows which config area changed.
- Keep revealed secret values session-local; do not store them in a Tool result cache.

This cache must not replace server-side authorization or validation.

### Change Application (Propose-Then-Confirm-Then-Apply)

For guided setup/bootstrap, the assistant proposes changes by calling
`propose_admin_config_bootstrap`. Its arguments are typed product setup fields:
instance identity, assistant identity, public copy, visual defaults, access
policy, user types, onboarding questions, and behavior-rule intent. Sage then
builds canonical Admin request paths and bodies deterministically.

For supported Admin Config writes that do not yet have a typed proposal Tool,
the assistant may use the lower-level `propose_config_change_set` escape hatch.
The tool arguments are:

- `summary`: one sentence summary of what will change.
- `requests_json`: a JSON array of request objects `{ "method", "path", "body"? }`.

Example `requests_json`:

```json
[
  {
    "method": "PUT",
    "path": "/admin/deployment/config/LLM_PROVIDER",
    "body": { "value": "sage" }
  }
]
```

Behavior-rule and forbidden-topic examples:

```json
[
  {
    "method": "PUT",
    "path": "/admin/ai-config/prompt_rules",
    "body": {
      "value": "[\"Ask users where they are from before giving location-specific guidance.\"]"
    }
  },
  {
    "method": "PUT",
    "path": "/admin/ai-config/prompt_forbidden",
    "body": {
      "value": "[\"Do not provide legal advice.\"]"
    }
  }
]
```

Sage validates the proposal against the backend's canonical allowlist and validation rules, emits the staged payload, and records Activity/Trace metadata without leaking secret values, blocklisted credentials, or hidden authority-bearing internals. The frontend mirrors those backend rules only for preview display and secret masking, then applies the changes only if the admin clicks **Apply**.

If a proposal is rejected by validation but the admin request is supported, Sage should correct the proposal and call `propose_config_change_set` again. It should not claim that supported Admin Config writes are unavailable.

Additional safety rules:

- The proposal Tool is non-mutating; it never calls admin write endpoints.
- Confirmed Apply is an explicit admin UI action, not a model-callable Tool.
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

Before allowlist validation, Sage and the frontend normalize only narrow, observed LLM output drift:

- Coalesces `PUT /admin/settings/{key}` with body `{ "value": ... }` into a single `PUT /admin/settings` patch object.
- Normalizes `/admin/user_types` to `/admin/user-types`.
- Normalizes instance setting key `tagline` to `header_tagline`.
- Normalizes supported language labels such as `English` to stored language codes such as `en`.
- Normalizes `POST /admin/user-types` bodies using canonical keys only (`name`, `description`, `icon`, `display_order`).
- Normalizes `POST /admin/user-fields` bodies using canonical keys only (`field_name`, `field_type`, `display_order`, `include_in_chat`, `user_type_id`, and related backend fields).
- For `POST /admin/user-fields`, `options` must be a native JSON array (`["A","B"]`), not a JSON-encoded string (`"[\"A\",\"B\"]"`).
- Parses boolean-like values (`true/false`, `1/0`, `yes/no`) and integer-like values where supported.

After normalization, staged `admin_change_set` payloads must contain only canonical paths and keys. Unknown instance setting keys, unsupported language values, malformed user type bodies, unsafe paths, or any other unrecognized drift are rejected before staging and before Apply.

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

Call `propose_config_change_set` with summary `Add a new user type and attach one onboarding field` and this `requests_json`:

```json
[
  {
    "method": "POST",
    "path": "/admin/user-types",
    "body": {
      "name": "Bitcoin Designer",
      "description": "Design-focused users"
    }
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

Tool-loop verification should prove the sidebar assistant, full admin chat, and onboarding surface all send the same `admin-config` Tool Set and do not prefetch `/admin/scoped-config-context` or inject admin configuration snapshots:

```bash
rg -n "scoped-config-context|requestedScopes|baseToolContext" frontend/src/components/admin frontend/src/pages/ChatPage.tsx frontend/src/utils/llmChat.ts
```

Proposal verification should prove both assistant surfaces stage pending review from structured `admin_change_set` payloads, with prose JSON extraction retained only as a temporary fallback:

```bash
rg -n "admin_change_set|extractAdminAssistantChangeSetStrict" frontend/src/components/admin frontend/src/pages/ChatPage.tsx
```
