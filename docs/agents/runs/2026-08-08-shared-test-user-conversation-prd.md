# Shared Test User Conversation

Status: Accepted for implementation.

## Problem

Admin Test & Feedback currently reaches the correct Sage User Conversation endpoint as a synthetic User, but it implements its own Conversation UI State, stream-event switch, message renderer, composer, and failure handling. The fork ignores live `activity_step` and `trace_delta` events, renders assistant answers as plain pre-wrapped text, can hide the running state after an early answer fragment, deletes partial assistant output on failure, and lacks the ordinary User Conversation's fallback behavior. This makes Test User Sessions look slower, less capable, and less reliable than the User Conversation they are intended to evaluate.

The request policy is already substantially correct. The synthetic bearer resolves a non-admin actor, Sage applies the selected User Type's authoritative Conversation defaults, and the same model and Bounded Native Tool Loop execute the turn. The root correction is therefore frontend ownership, not a new model, prompt, routing, Retrieval, or Tool policy.

## Decision

Create one shared User Conversation module that owns ordinary User Conversation execution and presentation. Both the logged-in User page and the Admin Test User Session adapter use that module. Keep only test-specific identity and feedback controls in the Admin wrapper.

The shared module owns:

- canonical Conversation UI State and assistant-turn lifecycle;
- Sage stream-event adaptation, including Activity Steps, Trace Deltas, final Conversation Trace, answer deltas, and terminal state;
- ordinary User Conversation streaming, bounded non-streaming fallback, partial-output preservation, error presentation, Sage session continuation, and reset;
- the assistant-ui Conversation UI Surface, including markdown rendering, copy affordances, automatic scrolling, the composer, and stable running state.

The Admin test adapter owns:

- User Type selection and synthetic User provisioning;
- the scoped synthetic User bearer token;
- the `Testing as ...` toolbar, Reset, Exit, and End & Save Trial controls;
- serialization of terminally completed canonical turns and Tool metadata into the existing encrypted Test User Session log;
- navigation into the existing Feedback view after save.

## Acceptance criteria

1. Ordinary logged-in User Conversations and Test User Sessions render through the same Conversation UI Surface and use the same canonical Conversation UI State and stream adaptation.
2. A Test User Session continues to authenticate every Sage request as the provisioned synthetic User and never exposes Admin-only Tool Sets.
3. Sage remains authoritative for effective User Tool Sets and Document Access; no client-side routing or forced Tool policy is added.
4. Test User Sessions display live Activity Steps and Trace Deltas, final Conversation Trace, and the stable running indicator even when answer text arrives before Tool work finishes.
5. Assistant answers in Test User Sessions support the same markdown, links, lists, tables, code rendering, message copy behavior, and configured assistant identity as ordinary User Conversations.
6. Stream failures follow the same ordinary User Conversation rules: useful partial assistant output remains visible, a failure before useful output may use the existing non-streaming fallback, and errors do not leave the composer permanently disabled.
7. Reset retains the selected synthetic User identity but starts a new Sage Conversation; Exit returns to the User Type picker.
8. End & Save Trial persists only terminally completed turns, including the final Conversation Trace and Tool metadata, through the existing encrypted feedback-log contract.
9. Test User Sessions remain excluded from ordinary User Conversation history and real User Reachout side effects.
10. Existing ordinary User Conversation behavior, Admin Conversation behavior, configurable Conversation defaults, and encrypted Feedback review remain regression-covered.

## Testing seams

- Test the shared User Conversation execution module through its public interface with controlled streaming and non-streaming transport adapters. Cover Activity/Trace event ordering, session continuation, terminal completion metadata, early failure fallback, and partial-output failure.
- Test Conversation UI State through reducer-visible outcomes rather than internal implementation details.
- Test the shared Conversation UI Surface through observable thread, Activity, markdown, running-state, and composer behavior.
- Test the logged-in adapter for ordinary User request identity, defaults, history refresh, and reset behavior.
- Test the Admin adapter for synthetic bearer identity, User Type defaults, persona controls, canonical transcript serialization, encrypted save, and Feedback navigation.
- Run the complete frontend test suite and production build, then visually compare the same prompt in a logged-in User Conversation and an Admin Test User Session using a synthetic User with the same User Type and blank-profile expectations.

The user explicitly approved these seams and authorized autonomous completion of the specification, ticketing, implementation, review, and staging PR pipeline on 2026-08-08.

## Out of scope

- Cloning or editing a real User Profile for the synthetic User.
- Model, reasoning-effort, prompt, Tool-selection, Retrieval, routing, provider, or retry-policy changes.
- Persisting Test User Sessions in ordinary User Conversation history.
- Sending real User Reachout messages from the Admin test harness.
- Production release or demo deployment.
