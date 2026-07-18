# Unified Model-Driven Tool Loop

Status: Still authoritative for the shared model-driven Tool loop. Its Admin Config proposal and Change Confirmation details are superseded by [ADR-0028](0028-sage-owns-direct-admin-config-writes.md). Treat those historical proposal sections below as decision context, not implementation guidance.

The Enclave Free Prototype will hard-cut Conversation tool use to one Sage-owned, model-driven tool loop. Visible composer controls enable Tool Sets; each enabled Tool Set exposes concrete agent-callable Tools with explicit contracts. Sage gives those Tool contracts to the model, the model chooses which Tools to call, Sage executes authorized calls, injects Tool results, emits Activity and Conversation Trace metadata, and continues until the model can answer.

This replaces preselected context pipelines such as Scoped Config Context, route-specific retrieval magic, and deterministic intent classifiers that decide what configuration or knowledge the model is allowed to inspect before the model sees the available Tools. The model should be encouraged to call enabled Tools proactively when they can answer a factual, configuration, data, availability, or freshness question better than guessing. Deterministic code remains responsible for Tool availability, authorization, validation, persistence, output budgets, loop limits, and trace sanitization.

## Tool Sets And Tools

Visible Tool Sets are permission and product controls, not hidden routing modes:

- `knowledge-search` enables Document Library Retrieval Tools. Selected Documents are Tool constraints for `knowledge_search`, not silently injected Required Context for ordinary chat.
- `curated-resources` enables the admin-curated Resource Directory Tool, exposed as `find_resources`. It is separate from Knowledge Search because it searches structured SQLite resource records, not uploaded document embeddings.
- `web-search` enables current/external web search.
- `admin-config` enables admin configuration read Tools and direct write Tools. Sage asks for conversational confirmation before calling a write Tool, as defined by ADR-0028.
- `db-query` enables admin-only read-only database inspection Tools.

The Admin Config Tool Set exposes concrete read Tools such as `read_instance_settings`, `read_deployment_settings`, `read_deployment_readiness`, `read_agent_settings`, `read_user_types`, `read_document_access`, and `read_onboarding_status`, plus the direct write Tools defined by ADR-0028.

Historical note: before ADR-0028, this ADR required proposal Tools, Executable Change Sets, a browser-staged `admin_change_set`, and a separate Change Confirmation gate. ADR-0025 later preferred Typed Proposal Tools over `propose_config_change_set`. Those requirements are retained only as decision history and are not current implementation guidance.

## Route Direction

Product and runtime language should converge on one Conversation runtime. Existing public route names such as `/llm/chat`, `/llm/chat/stream`, `/query`, and `/query/session/*` may remain as transport/API compatibility shapes while the implementation is rewired, but they should not define separate assistant-style versus retrieval-first mental models. Document-grounded chat is Conversation plus the `knowledge-search` Tool Set and document constraints. Curated referral/resource lookup is Conversation plus the `curated-resources` Tool Set. Admin chat is Conversation plus admin-authorized Tool Sets. Guided onboarding is Conversation plus guided UI prompts and the same `admin-config` Tool Set.

## Considered Options

- Keep Scoped Config Context as a compatibility shim. Rejected because it preserves the hidden classifier that caused Sage to answer from an artificially narrowed view of configuration state.
- Convert only Admin Config first. Rejected because keeping Web, Database, and Knowledge Search on separate preparation paths would preserve route/tool complexity and hide retrieval behind special cases.
- Depend on provider-native function calling. Rejected because Tool orchestration should remain Sage-owned and provider-portable. Sage may render structured Tool contracts to the model and parse structured tool-call output without coupling the product to one provider's function-calling dialect.
- Keep selected Documents as Required Context for ordinary chat. Rejected for the unified tool loop because Document Library access should be explicit, inspectable, and represented as `knowledge_search` Tool results. Required Context remains available as a product-policy term for future mandatory context, not as the default document-chat mechanism.

## Consequences

Sage owns intent interpretation and Tool choice. Python remains the Enclave Control Plane: it serves private authorized facts/actions, enforces redaction and read-only rules where it owns the data, and never pre-classifies a Conversation into a prompt-ready context blob. The frontend sends the user message, selected Tool Sets, and Tool constraints; it does not prefetch admin configuration context for chat turns.

The UI should make Knowledge, Resources, Web, Config, and Database explicit Tool controls for Admin Conversations. ADR-0026 supersedes the earlier user-chat default-on posture: User Conversations consume operator-configured Tool Set and Knowledge Source defaults without showing Tool controls by default. Knowledge Search document scope belongs under the Knowledge Tool Set policy. Config and Database remain admin-only and must only render for server-validated admins. Enabled does not mean forced: it means Sage may call the Tool when useful. Tool calls and meaningful Tool results should be visible through Activity, Trace Deltas, and Conversation Trace according to ADR-0024's transparent trace posture.

ADR-0014 and ADR-0022 describe earlier bounded streaming slices and are superseded for future tool-loop work by this decision. ADR-0017's no-compatibility posture applies: obsolete Scoped Config Context routes, client helpers, cache invalidation hooks, and docs should be removed rather than preserved as fallback behavior.
