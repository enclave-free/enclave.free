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

The browser sends selected Tool Set IDs to Sage in the Conversation request. Sage is responsible for expanding those IDs into the concrete Tool contracts that the current actor is authorized to use.

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

- `tools` is a list of visible Tool Set IDs selected in the composer.
- Sage drops or rejects Tool Sets the actor is not authorized to use.
- `job_ids` is an optional Knowledge Search constraint: it is a list of selected Document Library `job_id` values, not an arbitrary prompt blob.
- Additional Knowledge filters must be added as explicit request fields before the browser can send them.
- `conversation_history` is optional recent client context; Sage-owned session memory remains authoritative when a `session_id` is present.

## Tool Sets

Visible Tool Sets are conversation controls and permission bundles:

| Tool Set ID         | Access                                        | Exposes                                                                                       |
| ------------------- | --------------------------------------------- | --------------------------------------------------------------------------------------------- |
| `knowledge-search`  | users and admins, filtered by Document Access | `knowledge_search` over the Document Library                                                  |
| `curated-resources` | users and admins                              | `find_resources` over the admin-curated Resource Directory                                    |
| `web-search`        | users and admins when enabled                 | `web_search` through the configured SearXNG service                                           |
| `admin-config`      | admins only                                   | admin configuration read Tools and the non-mutating `propose_config_change_set` proposal Tool |
| `db-query`          | admins only                                   | read-only database inspection Tools                                                           |

Enabled does not mean forced. Enabled means the model is allowed and encouraged to call the Tool when it improves the answer. If an enabled Tool can answer a factual, configuration, data, availability, setup, or freshness question better than guessing, Sage should call it instead of asking the user to check manually.

## Knowledge Search

`knowledge-search` is a first-class visible Tool Set, not a hidden retrieval mode. Selected Documents are constraints on `knowledge_search`, not silent Required Context for ordinary chat.

Sage passes allowed document constraints to the Knowledge Tool. Python enforces Document Access and hydrates retrieved chunks from product-owned storage after vector search. Retrieved chunks enter the Conversation as Tool results and sanitized Activity/Trace metadata.

Required Context remains a separate product-policy term for future mandatory context that must be included outside ordinary model discretion. It is not the default document-chat path.

## Curated Resources

`curated-resources` is a first-class visible Tool Set for the admin-curated Resource Directory. It is separate from `knowledge-search`: Resources are structured, priority referrals stored in SQLite by admins; Knowledge is uploaded document retrieval through embeddings and document access policy.

Sage exposes this Tool Set as `find_resources`. The Tool calls Python's private `/internal/agent/resources/search` contract and returns vetted organizations, contacts, coverage, help types, and languages. The Tool should be enabled by default for user chat so Sage can recommend known priority resources before guessing, searching the web, or asking the user to check manually.

## Admin Config

`admin-config` is an admin-only Tool Set. It should expose concrete model-callable Tools rather than a prompt-ready scoped prompt blob. Initial Tools should include:

- `read_instance_settings`
- `read_deployment_settings`
- `read_deployment_readiness`
- `read_agent_settings`
- `read_user_types`
- `read_document_access`
- `read_onboarding_status`
- `propose_config_change_set`

Reads may happen directly within Admin Conversation authority. Write intent must become an Executable Change Set proposal through `propose_config_change_set`. Applying that change set still requires Change Confirmation in the Conversation UI Surface.

`propose_config_change_set` is a model-callable, non-mutating Tool. It validates and stages a change set for review, but it never calls admin mutation endpoints. Confirmed **Apply** remains a UI/admin action, not a model-authorized Tool call.

Admin Config proposals must stage canonical write shapes. Instance settings use
`PUT /admin/settings` with stored setting keys such as `header_tagline`,
`default_language`, `default_theme`, and `auto_approve_users`. Agent Settings use
`PUT /admin/ai-config/{key}` with `{ "value": "..." }`; behavior rules and
forbidden topics use `PUT /admin/ai-config/prompt_rules` and
`PUT /admin/ai-config/prompt_forbidden` with `value` set to a JSON string array,
such as `{ "value": "[\"Ask users where they are from before giving location-specific guidance.\"]" }`.
User types use `POST /admin/user-types` with `{ "name", "description"?, "icon"?,
"display_order"? }`. The proposal boundary may normalize only known small drift
(`/admin/user_types`, `tagline`, and supported language labels such as
`English`); staged `admin_change_set` payloads must contain canonical paths and
keys after that. Unknown keys and unsupported values reject the proposal before
review.

Admin Config Tools may return non-secret configuration and secret status metadata by default. Raw Deployment Setting secret values require explicit Admin sharing and must remain redacted in messages, Activity, traces, and previews.

Theme requests in Admin Conversations mean Instance visual identity settings, such as theme, primary color, chat bubble style, surface style, icon set, and typography preset. They should become Instance Settings change-set proposals, not frontend CSS or source-code theme edits.

## Database

`db-query` is an admin-only Tool Set for read-only inspection. Sage may use the model-driven Tool loop for database questions, but Python remains the safe SQL executor and must enforce read-only validation, blocked keywords, authorization, truncation, and redaction. Direct database mutation is not a supported product path.

## Web Search

`web-search` uses the internal SearXNG service at `http://searxng:8080/search?format=json`. It is intended for current or external information and should not replace Enclave Document Library Retrieval.

## Frontend Duties

The frontend chooses visible Tool Sets and Tool constraints. It must not prefetch admin configuration context for chat, run hidden document retrieval for ordinary turns, or send `client_executed_tools` as a compatibility path.

The composer should make Knowledge, Resources, Web, Config, and Database explicit controls. Knowledge document scope belongs under the Knowledge Tool Set control. Resources is enabled by default for user chat; Config and Database must only render for server-validated admins.

## Sage Duties

Sage decides Tool planning through model instructions and Tool descriptions, not deterministic intent classifiers. Deterministic Sage code still decides:

- which Tool Sets and Tools are available for the actor
- max Tool-loop steps, timeouts, and output budgets
- Tool result injection
- Activity and Conversation Trace assembly
- Change Confirmation handoff for Executable Change Sets

## Python Duties

Python serves authorized Enclave Control Plane facts/actions through private `/internal/agent/*` contracts protected by `INTERNAL_AGENT_TOKEN`. It enforces data ownership, authorization, redaction, read-only validation, and lifecycle boundaries for the data it owns. It must not classify a Conversation turn into a scoped prompt context before the model sees available Tools.
