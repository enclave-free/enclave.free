# Test User Sessions Reuse the User Conversation Module

Status: Accepted.

An Admin-created **Test User Session** is a **User Conversation**, not a second chat product. The frontend will use one shared User Conversation module for Conversation UI State, Sage Conversation Streaming Transport adaptation, request completion and failure semantics, and the assistant-ui Conversation UI Surface. The ordinary logged-in User page and the Admin Test & Feedback page are adapters at that module's seam.

The logged-in adapter supplies the current User identity and account-specific shell such as durable Conversation history and User Reachout. The Admin test adapter provisions a synthetic User for the selected User Type, supplies its scoped bearer token, labels the active persona, and captures completed turns for encrypted feedback. Those adapter responsibilities must not fork message rendering, Tool and Retrieval Activity, stream state, retry or fallback behavior, or error handling.

The Admin test adapter serializes feedback from the canonical shared Conversation UI State and terminal Tool metadata. It does not reconstruct the Conversation from the DOM or maintain a second message state machine. Reset starts a new Sage Conversation while retaining the selected synthetic User identity. Ending a trial saves only terminally completed turns through the existing encrypted Test User Session log path.

The synthetic User is intentionally a User Type fixture rather than a clone of a real User. It receives the selected User Type's effective Tool Sets, Document Access, Agent Personalization, and other server-resolved policy, but it has no real person's User Profile answers unless a separate, explicit fixture capability is designed later. User Profile fixture editing is outside this decision.

## Consequences

- A Conversation behavior or rendering fix made in the shared User Conversation module applies to both ordinary User Conversations and Test User Sessions.
- Test User Sessions render the same markdown, Activity, Trace Deltas, running states, and recoverable failures as ordinary User Conversations.
- The Admin test harness remains small and focused on persona selection, synthetic identity, reset and exit, encrypted save, and feedback navigation.
- Test User Sessions do not appear in an ordinary User's Conversation history and do not inherit account-only side effects such as sending a real User Reachout.
- Tests exercise behavior through the shared module's interface and use the two adapters only to verify their distinct identity and persistence responsibilities.

## Rejected alternatives

- Keep the standalone Test-as-User chat client and manually synchronize it. Rejected because stream events, Conversation UI State, rendering, and failure behavior already drifted despite request-level Tool parity.
- Embed the logged-in page in an iframe or mutate global authentication state. Rejected because it couples Admin controls to navigation and cookie state while weakening the synthetic User identity seam.
- Copy the logged-in User page into the Admin route. Rejected because another copy recreates the same locality and parity problem.
- Add a Test User Profile editor now. Rejected because the current requirement is User Type-level simulation, and a profile fixture system is a separate product decision.
