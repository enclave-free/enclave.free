# Configurable Conversation Defaults

User Conversations will no longer show Tool Set controls by default. Instead, the Operator configures which User Conversation Tool Sets are default-active and what Knowledge Source scope applies to new sessions.

This refines ADR-0023. Tool Sets remain explicit product capabilities and Sage still owns the model-driven Tool loop, but the user-facing composer no longer needs to expose those controls by default. Admin Conversations continue to show admin Tool controls because Operators need direct inspection and override affordances.

## Decision

- User Conversation composer controls hide Tool Set buttons and Knowledge Source selectors by default.
- User Conversation default Tool Sets are configured through Agent Settings and returned by Sage-owned `/session-defaults`.
- Knowledge Source defaults use an explicit scope:
  - `none`: Knowledge Search is not default-active.
  - `selected`: Knowledge Search is default-active and constrained to default Document IDs.
  - `all`: Knowledge Search is default-active without `job_ids`, so all Documents available to the current User Type can be searched.
- Sage filters non-admin `/llm/chat` Tool Sets against the effective configured defaults for the current User Type.
- Admin-only Tool Sets remain server-gated by authenticated Admin authority.
- Admin configuration conversations keep `admin-config` default-active and visible.

## Why

Visible Tool controls were useful while the prototype was proving the model-driven Tool loop, but they are too operational for ordinary Users. The Operator should decide the Instance's default help posture: no tools, curated referrals, document retrieval, web search, or any safe combination. This preserves Operator-Controlled Privacy while giving Users a calmer Conversation UI Surface.

## Consequences

- Existing tests and docs that assume `curated-resources` is always default-on for User Conversations must change.
- Default document selection remains useful, but it only activates Knowledge Search when the Knowledge Source scope is `selected`.
- Selecting `all` must not send all document IDs from the browser; it should omit `job_ids` and let the Enclave Control Plane enforce Document Access.
- If `/session-defaults` cannot be loaded, the safe User fallback is no default Tool Sets.
- Existing explicit Tool Set semantics remain available for Admin Conversations and for any future advanced user controls.

## Considered Options

- Keep User Tool controls visible but default them off. Rejected because the request is for no tools shown in the user UI by default.
- Keep `curated-resources` always default-on. Rejected because Operators need complete control over which Tool Sets are default-active.
- Treat default documents as an implicit retrieval mode. Rejected because ADR-0023's explicit Tool loop remains the runtime model; Knowledge Search is still a Tool Set, only its default activation is configurable.
