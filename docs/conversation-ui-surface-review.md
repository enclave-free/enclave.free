# Conversation UI Surface Review

Status: ready for browser review before full end-to-end smoke

## Checkpoint: assistant-ui refactor slices

Date: 2026-05-24

The assistant-ui refactor is in a working checkpoint after nine TDD slices. The current implementation is intentionally more modern and calmer than the previous chat surface, but still prototype-transparent: Activity remains visible by default so operators can inspect what Sage did, while raw implementation labels and overly loud statuses are being softened.

Completed user-facing changes:

- Assistant messages now render as an unboxed, full-width assistant response surface while user messages keep compact right-aligned bubbles.
- Conversation Trace copy has been renamed to Activity across the visible chat UI and accessible labels.
- Tool trace sections inside Activity now read as Tool calls.
- Completed Activity rows rely on success iconography instead of showing a raw `completed` badge.
- Composer context now separates Tools and Documents, with compact controls suitable for a chat composer.
- Mobile chat sessions have an open/close drawer shell; selecting a drawer action such as New chat closes the drawer.
- Admin Change Confirmation cards are rendered inline with product-facing approval copy and UI buttons.
- Older pending Change Confirmations become visible, disabled, Superseded cards when a newer reviewable change set appears.
- Admin Session Memory compaction now shows a quiet notice instead of a long provider-budget warning.

Boundaries intentionally preserved:

- Sage still owns the Agent Runtime, streaming semantics, tool execution, trace sanitization, memory, and inference.
- Enclave-specific controls still live outside the shared ConversationSurface.
- Admin Change Confirmation remains separate from Activity and still requires explicit admin approval.
- Deployment secrets remain masked in Change Confirmation previews.

Verification at this checkpoint:

- `npm test -- ChatMessage.test.tsx ChatPage.test.tsx`
- `npm run build`
- `npm test` -> 52 files, 257 tests passed

Known follow-up:

- The production build still reports the existing Vite large chunk warning. This checkpoint does not address code splitting.

## Full End-To-End Smoke Gate

Do this review before the full Compose smoke so visual and workflow gaps are separated from runtime availability failures. If review finds polish or production-hardening gaps, file separate follow-up issues rather than expanding this review ticket.

## User Conversation browser flow

Verify message sending, streaming, activity steps, document scope, reachout, export, and fallback/error states in the product UI.

Expected boundaries:

- Sage owns Agent Runtime behavior, streaming semantics, tool execution, trace sanitization, memory, and inference.
- Enclave-specific controls stay outside the shared ConversationSurface, including Document scope, reachout, export, and role-specific page chrome.
- Conversation Activity Steps appear before the clean assistant response when Sage emits them.

## Admin Conversation browser flow

Verify selected tools, activity steps, Change Confirmation, secret redaction, final trace rendering, and fallback/error states in the product UI.

Expected boundaries:

- Admin-only tools remain admin-only.
- Admin Change Confirmation remains separate from live activity visibility and still requires explicit admin approval.
- Deployment secrets and raw tool/database payloads remain redacted in messages, activity, traces, and previews.

## Layout review

Run desktop and mobile layout checks for:

- readable user and assistant messages
- stable prompt input behavior while idle, sending, and disabled
- non-overlapping header actions, tool controls, document scope controls, reachout/export actions, and error notes
- activity timeline readability before and after the assistant answer settles

## Human review

A human reviewer confirms the activity timeline is inspectable enough for the prototype without feeling like the old dense trace blob. If the timeline is too noisy, too sparse, or visually hard to scan, file separate follow-up issues with screenshots or exact reproduction notes.
