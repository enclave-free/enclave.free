# Agent Runtime Tool Semantics

This document describes the accepted Tool behavior for the Sage hard-cut prototype after [ADR-0023](adr/0023-unified-model-driven-tool-loop.md).

## Core Rule

Sage owns one model-driven Tool loop for Conversations. The browser sends the user message, selected Tool Sets, and optional Tool constraints. Sage expands those selected Tool Sets into concrete Tool contracts, gives the contracts to the model, executes authorized model-chosen Tool calls, injects Tool results, emits Activity and Conversation Trace metadata, and continues until the model can answer or produce an Executable Change Set.

Python no longer owns or exposes public Agent Runtime routes. Direct Python calls are unsupported because public Agent Runtime routes are absent from the Enclave Control Plane; public callers use the Gateway path so nginx dispatches requests to Sage. Python remains the Enclave Control Plane behind private/internal contracts for authorized facts and actions such as safe database reads, document search, user profile context, lifecycle operations, and admin configuration reads.

## Public Route Shape

The product mental model is one Conversation runtime. Existing public route names may remain while the hard cut is implemented:

| Gateway route      | Role                                                  |
| ------------------ | ----------------------------------------------------- |
| `/llm/chat`        | non-streaming Conversation transport                  |
| `/llm/chat/stream` | streaming Conversation transport                      |
| `/query`           | stateful Conversation API compatibility shape         |
| `/query/session/*` | Conversation session inspection, rename, and deletion |

Route names do not define separate tool systems. Document-grounded chat is Conversation plus the `knowledge-search` Tool Set. Curated referral/resource lookup is Conversation plus the `curated-resources` Tool Set. Admin chat is Conversation plus admin-authorized Tool Sets. Guided onboarding is Conversation plus guided UI prompts and the same `admin-config` Tool Set.

## Browser To Sage Request Contract

The browser sends Tool Set IDs to Sage in the Conversation request. Admin Conversations send the Admin's visible selections and normal Admin Conversation surfaces start with no Tool Sets selected. User Conversations use the operator-configured session defaults returned by Sage-owned `/session-defaults`; the default user composer does not expose Tool Set controls or a Knowledge document selector. Sage is responsible for expanding those IDs into concrete Tool contracts and enforcing the effective non-admin default policy server-side.

For `/llm/chat` and `/llm/chat/stream`, the request shape is:

```json
{
  "message": "What does the handbook say?",
  "session_id": "optional-session-id",
  "tools": ["knowledge-search", "curated-resources", "web-search"],
  "job_ids": ["doc-handbook", "doc-faq"],
  "conversation_history": [
    { "role": "user", "content": "Earlier user turn" },
    { "role": "assistant", "content": "Earlier assistant turn" }
  ]
}
```

- `tools` is a list of Tool Set IDs selected by an Admin or resolved by Sage from User Conversation defaults.
- Sage drops or rejects Tool Sets the actor is not authorized to use. For non-admin users, Sage ignores the client-submitted `tools` list for effective resolution and computes the Tool Set list from server-side `/session-defaults`, including the empty or omitted case where configured defaults still apply.
- `job_ids` is an optional Knowledge Search constraint: it is a list of selected Document Library `job_id` values, not an arbitrary prompt blob.
- Additional Knowledge filters must be added as explicit request fields before the browser can send them.
- `conversation_history` is optional recent client context; Sage-owned session memory remains authoritative when a `session_id` is present.
- `client_decrypted_context` is optional **Admin Signer-Decrypted Context**, shaped like `{ "source": "admin-signer-user-roster", "users": [...] }`. The browser may attach it only for authenticated Admin turns with the `db-query` Tool Set enabled, and Sage treats it as signer-delegated plaintext for the current encrypted inference turn rather than Tool output or trace metadata.

## Tool Sets

Tool Sets are conversation controls and permission bundles. They are visible controls for Admin Conversations only, and normal Admin Conversations do not enable any Tool Set by default. User Conversations always consume the server-resolved defaults without showing Tool controls by default.

| Tool Set ID         | Access                                        | Exposes                                                                                                 |
| ------------------- | --------------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| `knowledge-search`  | users and admins, filtered by Document Access | `knowledge_search` over the Document Library                                                            |
| `curated-resources` | users and admins                              | `find_resources` over the admin-curated Resource Directory                                              |
| `web-search`        | users and admins when enabled                 | `web_search` through the configured SearXNG service                                                     |
| `admin-config`      | admins only                                   | admin configuration read Tools, typed bootstrap proposal Tool, and lower-level change-set proposal Tool |
| `db-query`          | admins only                                   | read-only database inspection Tools                                                                     |

Enabled does not mean forced. Enabled means the model is allowed and encouraged to call the Tool when it improves the answer. If an enabled Tool can answer a factual, configuration, data, availability, setup, or freshness question better than guessing, Sage should call it instead of asking the user to check manually.

## Knowledge Search

`knowledge-search` is a first-class visible Tool Set, not a hidden retrieval mode. Selected Documents are constraints on `knowledge_search`, not silent Required Context for ordinary chat.

Sage passes allowed document constraints to the Knowledge Tool. Python enforces Document Access and hydrates retrieved chunks from product-owned storage after vector search. Retrieved chunks enter the Conversation as Tool results and Activity/Trace metadata under the transparent trace posture in ADR-0024.

Required Context remains a separate product-policy term for future mandatory context that must be included outside ordinary model discretion. It is not the default document-chat path.

## Curated Resources

`curated-resources` is a first-class visible Tool Set for the admin-curated Resource Directory. It is separate from `knowledge-search`: Resources are structured, priority referrals stored in SQLite by admins; Knowledge is uploaded document retrieval through embeddings and document access policy.

Sage exposes this Tool Set as `find_resources`. The Tool calls Python's private `/internal/agent/resources/search` contract and returns vetted organizations, contacts, coverage, help types, and languages. Operators may enable it as a User Conversation default when they want Sage to recommend known priority resources before guessing, searching the web, or asking the user to check manually. When this Tool Set is enabled and a user asks what resources are available or asks to list resources, Sage should call `find_resources` without a `help_type` so it lists ready curated resources from the live Resource Directory instead of describing the tool catalog.

## Admin Config

`admin-config` is an admin-only Tool Set. It should expose concrete model-callable Tools rather than a prompt-ready scoped prompt blob. Initial Tools should include:

- `read_instance_settings`
- `read_admin_setup_summary`
- `read_deployment_settings`
- `read_deployment_readiness`
- `read_agent_settings`
- `read_user_types`
- `read_document_access`
- `read_onboarding_status`
- `propose_admin_config_bootstrap`
- `propose_config_change_set`

Reads may happen directly within Admin Conversation authority. Broad setup, status, and readiness questions should use `read_admin_setup_summary` first because it compacts readiness, missing setup, and next actions. Guided setup/bootstrap write intent should use `propose_admin_config_bootstrap`, whose typed arguments describe instance identity, assistant identity, public copy, visual defaults, language, access policy, user types, onboarding questions, and behavior rules. Other supported Admin Config writes may use `propose_config_change_set` as the lower-level escape hatch. Applying either proposal still requires Change Confirmation in the Conversation UI Surface.

Each proposal Tool is a model-callable, non-mutating Tool. They validate and stage a change set for review, but they never call admin mutation endpoints. Confirmed **Apply** remains a UI/admin action, not a model-authorized Tool call.

Admin Config proposals must stage canonical write shapes. Typed bootstrap builds these shapes deterministically; the generic escape hatch must provide them directly. Instance settings use
`PUT /admin/settings` with stored setting keys such as `header_tagline`,
`default_language`, `default_theme`, and `auto_approve_users`. Agent Settings use
`PUT /admin/ai-config/{key}` with `{ "value": "..." }`; behavior rules and
forbidden topics use `PUT /admin/ai-config/prompt_rules` and
`PUT /admin/ai-config/prompt_forbidden` with `value` set to a JSON string array,
such as `{ "value": "[\"Ask users where they are from before giving location-specific guidance.\"]" }`.
User types use `POST /admin/user-types` with `{ "name", "description"?, "icon"?,
"display_order"? }`. User fields/onboarding questions use `POST /admin/user-fields`
with `{ "field_name", "field_type", "required"?, "display_order"?, "user_type_id"?,
"placeholder"?, "options"?, "encryption_enabled"?, "include_in_chat"? }`.
Deployment config uses `PUT /admin/deployment/config/{key}`. Document-default
assignments use the `PUT/DELETE /ingest/admin/documents/...` defaults paths.
The proposal boundary may normalize only known small drift
(`/admin/user_types`, legacy `tagline` into canonical `header_tagline`, and supported language labels such as
`English`); staged `admin_change_set` payloads must contain canonical paths and
keys after that. Unknown keys and unsupported values reject the proposal before
review.

Admin Config Tools may return non-secret configuration and secret status metadata by default. Raw Deployment Setting secret values require explicit Admin sharing and remain inside the trace blocklist unless they are intentionally shared by the Admin for the current turn; secret previews must stay masked in Change Confirmation.

Theme requests in Admin Conversations mean Instance visual identity settings, such as default theme and `primary_color`. They should become Instance Settings change-set proposals, not frontend CSS or source-code theme edits.

## Database

`db-query` is an admin-only Tool Set for read-only inspection. When an approved Admin enables it, Sage exposes the executable Database Query Tool to the model for the turn. Sage may translate natural-language database questions into a single read-only SQLite `SELECT` when live database facts would improve the answer. Python remains the safe SQL executor and must enforce read-only validation, blocked keywords, allowed tables, authorization, truncation, and redaction. Direct database mutation is not a supported product path.

Admin Database turns may also include **Admin Signer-Decrypted Context** built by the browser from admin-authorized encrypted User values. This context lets Sage combine safe query results with plaintext identity/profile values under encrypted inference. It must not be accepted for non-Admin turns, non-Database turns, Python database execution, Activity, or Conversation Trace.

## Web Search

`web-search` uses the internal SearXNG service at `http://searxng:8080/search?format=json`. It is intended for current or external information and should not replace Enclave Document Library Retrieval.

## Frontend Duties

The frontend chooses visible Admin Tool Sets and Tool constraints. For non-admin User Conversations, it consumes `/session-defaults` and sends the configured default Tool Set IDs and Knowledge Source scope without showing Tool controls by default. It must not prefetch admin configuration context for chat, run hidden document retrieval outside configured defaults, or send `client_executed_tools` as a compatibility path. It may build Admin Signer-Decrypted Context only after an authenticated Admin submits a Database-enabled turn.

Normal Admin Conversation composers should make Knowledge, Resources, Web, Config, and Database explicit opt-in controls with none selected by default. Admin configuration conversations are the exception: `admin-config` is default-active and visible there, while all other Tool Sets remain opt-in. Knowledge document scope belongs under the Knowledge Tool Set control. User composers show no Tool Set controls by default; Config and Database must only render for server-validated admins.

## Sage Duties

Sage decides Tool planning through model instructions and Tool descriptions, not deterministic intent classifiers. Deterministic Sage code still decides:

- which Tool Sets and Tools are available for the actor
- max Tool-loop steps, timeouts, and output budgets
- Tool result injection
- Activity, Trace Delta, and Conversation Trace assembly
- Change Confirmation handoff for Executable Change Sets

## Python Duties

Python serves authorized Enclave Control Plane facts/actions through private `/internal/agent/*` contracts protected by `INTERNAL_AGENT_TOKEN`. It enforces data ownership, authorization, redaction, read-only validation, and lifecycle boundaries for the data it owns. It must not classify a Conversation turn into a scoped prompt context before the model sees available Tools.
