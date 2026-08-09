# Migrate Test User Sessions onto the shared User Conversation module

Parent spec: #612

Blocked by: #613

Type: AFK tracer bullet

## Outcome

Replace the standalone Admin Test-as-User chat client with a thin Test User Session adapter over the shared User Conversation module while preserving persona selection, synthetic-user isolation, encrypted transcript capture, and Feedback review.

## Required behavior

- Delete the Admin test harness's custom message state machine, stream-event switch, plain-text message renderer, composer, and bespoke running/error behavior.
- Render the Test User Session through the same assistant-ui Conversation UI Surface used by ordinary logged-in Users.
- Preserve the selected User Type, scoped synthetic User bearer, server-authoritative User Tool Sets and Document Access, persona label, Reset, Exit, and End & Save Trial controls.
- Display live Activity Steps, Trace Deltas, final Conversation Trace, markdown, copy affordances, auto-scroll, and stable running state exactly through the shared module.
- Preserve useful partial assistant output on failure and use the ordinary User Conversation's existing pre-output fallback behavior.
- Capture only terminally completed canonical turns for encrypted save, including final Conversation Trace and Tool metadata, without reconstructing state from the DOM or maintaining a second conversation state machine.
- Keep Test User Sessions out of ordinary User Conversation history and real User Reachout side effects.

## Testing

- Add red-first Admin adapter coverage for shared-surface rendering, live Activity and Trace Deltas after an early answer fragment, markdown, synthetic bearer requests, persona controls, reset to a new Sage session, partial-output failure, pre-output fallback, and completed-turn transcript serialization.
- Preserve FeedbackView encrypted review coverage.
- Run the complete frontend test suite and production build.
- Perform agent-driven browser verification comparing one prompt in a logged-in User Conversation and a Test User Session of the same User Type, then verify encrypted save and Feedback navigation.

## Blocking edges

- Blocked by #613, the shared User Conversation module ticket.
- No HITL validation or human-granted access is required; the user will perform an additional manual staging smoke test after the PR is ready.

## Done when

- `TestAsUserView` is a thin identity-and-feedback wrapper over the shared User Conversation module.
- The independent test chat implementation is gone.
- Targeted, full, build, and browser checks pass.
- Standards and spec review findings are addressed or recorded.
- The completed slice is committed on `feature/shared-test-user-conversation` and its SHA is recorded in the feature ledger.
