# Extract the shared User Conversation execution module

Parent spec: #612

Blocks: #614

Type: AFK tracer bullet

## Outcome

Create the deep frontend module that owns ordinary User Conversation execution and presentation, then migrate the logged-in User Conversation adapter onto it without changing observable behavior. The module's interface must be small enough that a second synthetic-user adapter can supply identity and capture terminal turn evidence without learning or reimplementing stream-event mechanics.

## Required behavior

- The shared module owns canonical Conversation UI State, Sage stream adaptation, assistant-turn lifecycle, ordinary streaming and bounded non-streaming fallback, partial-output preservation, error recovery, session continuation/reset, and rendering through the existing assistant-ui Conversation UI Surface.
- The logged-in User adapter supplies its current identity, effective conversation defaults, account shell/history callbacks, and User-only affordances without exposing those concerns through the shared conversation implementation.
- Admin Conversation-specific configuration, secret-redaction, and database behavior remain unchanged and outside the extracted User module.
- No model, prompt, Tool policy, Retrieval policy, routing, provider, retry, or Sage contract changes are introduced.
- Existing ordinary User markdown, Activity, Trace, running state, Conversation history refresh, reset, and error behavior remain observable.

## Testing

- Add red-first coverage at the shared module interface for stream event ordering, Activity and Trace accumulation, terminal metadata, session continuation, useful partial-output failure, and pre-output non-streaming fallback.
- Keep reducer tests focused on observable Conversation UI State outcomes.
- Preserve and run the relevant ChatPage and Conversation Surface regression tests.
- Run the complete frontend test suite and production build before closing the ticket.

## Blocking edges

- Blocks #614 because that Test User Session adapter must consume this stable interface.
- No HITL validation or human-granted access is required.

## Done when

- The logged-in User Conversation uses the shared module.
- The shared module has a stable public test seam and no test-only production interface.
- Targeted and full checks pass.
- Standards and spec review findings are addressed or recorded.
- The completed slice is committed on `feature/shared-test-user-conversation` and its SHA is recorded in the feature ledger.
