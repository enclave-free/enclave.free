# Admin Conversations Can Apply Confirmed Control Plane Changes

Sage may directly apply state-changing actions during an Admin Conversation, but every write that changes Instance or Agent Runtime state requires Change Confirmation from the Admin first. This keeps the admin experience agentic and efficient while preserving an explicit control boundary for configuration, user, document, agent, and other operator-owned changes. Read actions may happen within the authority of the Admin Conversation without the same confirmation step.
