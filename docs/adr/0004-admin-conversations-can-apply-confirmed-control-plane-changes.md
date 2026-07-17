# Admin Conversations Can Apply Confirmed Control Plane Changes

Status: Superseded for Admin Config writes by [ADR-0028](0028-sage-owns-direct-admin-config-writes.md).

Sage may prepare state-changing actions during an Admin Conversation, but every write that changes Instance or Agent Runtime state requires Change Confirmation from the Admin first. For Admin Config, Sage stages write intent through the non-mutating `propose_config_change_set` Tool; confirmed apply remains an explicit Admin UI action. Conversational apply language such as "do it" routes to the pending confirmation surface when a valid proposal exists, but it never gives Sage authority to mutate state directly. This keeps the admin experience agentic and efficient while preserving a clear control boundary for configuration, user, document, agent, and other operator-owned changes. Read actions may happen within the authority of the Admin Conversation without the same confirmation step.
