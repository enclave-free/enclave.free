# Conversation UI Surface Review

Status: Historical review of the assistant-ui cutover. Admin Config approval-card findings are superseded by [ADR-0028](adr/0028-sage-owns-direct-admin-config-writes.md); the current surface sends confirmation language to Sage and renders direct Tool Activity.

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

Known follow-up from this checkpoint:

- The production build still reports the existing Vite large chunk warning. This checkpoint does not address code splitting.

## Checkpoint: assistant-ui cleanup and packaging slices

Date: 2026-05-24

Follow-up cleanup retired the unused bespoke `MessageList` thread path and split the assistant-ui composer into its own `AssistantComposerInput`, leaving the older textarea composer only for the separate Admin Configuration Assistant sidebar flow. `ConversationSurface` now owns the assistant-ui thread plus assistant-ui composer path directly.

Bundle evidence:

- Before route splitting: `index-tPKJYf8I.js` was 5,340.73 kB, 1,736.65 kB gzip, and Vite emitted the large chunk warning.
- Low-risk route splitting moved Chat, Admin, diagnostics, onboarding, and pending routes into lazy chunks. The Admin Configuration Assistant is also lazy-loaded from `AdminRoute`.
- After low-risk splitting: `ChatPage-BHlVCX0E.js` is 194.21 kB, `AdminConfigAssistant-DsHqjASd.js` is 36.11 kB, and the entry chunk is reduced to `index-BUY2u4PA.js` at 2,958.81 kB, 1,141.61 kB gzip.
- The Vite warning remains because shared vendor/config-icon chunks are still over 500 kB, including `DynamicIcon-BBm8YdBF.js` and `adminApplyIntent-DX-jX2yP.js`. A manual vendor split was tested but produced circular chunk warnings, so it was not kept. Further reduction should be a separate dependency/import audit rather than bundler machinery.

Visual polish evidence:

- Composer context controls now live in a named wrapping group so Tools, Documents, and adjacent controls can wrap on narrow viewports instead of forcing horizontal overflow.
- User message bubbles use a viewport-aware max width on mobile.
- Copy controls are quieter by default and become visible on hover or focus.
- Running feedback uses tighter min/max width constraints so it stays attached to the thread without resizing surrounding layout.

## Decision Checkpoint: remaining ChatGPT-style affordances

Date: 2026-05-24

Composer Knowledge semantics:

- Composer Knowledge controls mean selecting constraints for the `knowledge-search` Tool Set.
- Composer Resources controls mean enabling the admin-curated Resource Directory Tool Set; it is not document retrieval.
- The chat composer does not upload files, hold ephemeral browser-only file attachments, or expose assistant-ui attachment persistence as a product contract.
- Document persistence, Retrieval availability, deletion, export, Activity/Trace metadata, active-content handling, and authorization remain owned by the existing Document Library and Retrieval workflow.
- Unsupported file attachment affordances should stay absent so the composer does not imply hidden upload, multimodal, or one-turn file semantics.

Transport-backed chat commands:

- Stop, regenerate, and edit are not exposed until Sage publishes transport-backed command semantics for cancellation, turn supersession/branching, Session Memory mutation, Activity/Trace persistence, export, authorization, and Admin Change Confirmation invalidation.
- The frontend now has a capability-gated message action model that defaults to no actions and hides unsupported controls instead of rendering fake disabled ChatGPT-style buttons.
- No command mutates Conversation Content or Session Memory in this checkpoint.

Tool-call lifecycle:

- The Sage stream adapter now branches on `trace_delta` events, so Enclave can map Sage Trace Deltas into assistant-ui-style reasoning and tool-call parts as those surfaces mature.
- Sage remains the authority for Activity, Trace Deltas, Conversation Trace assembly, minimal blocklist protection, persistence, resume, and export boundaries.
- Raw reasoning, tool inputs/outputs, retrieval details, and timing should map into frontend trace parts when available, while credentials, hidden system/developer instructions, raw secret reveal results, infrastructure/runtime dumps, and other authority-bearing internals remain blocklisted.
- Admin Change Confirmation remains separate from Activity and still requires explicit approval.

## Full End-To-End Smoke Gate

Do this review before the full Compose smoke so visual and workflow gaps are separated from runtime availability failures. If review finds polish or production-hardening gaps, file separate follow-up issues rather than expanding this review ticket.

## User Conversation browser flow

Verify message sending, streaming, activity steps, Knowledge Search controls, reachout, export, and fallback/error states in the product UI.

Expected boundaries:

- Sage owns Agent Runtime behavior, streaming semantics, tool execution, trace assembly, minimal blocklist protection, memory, and inference.
- Enclave-specific controls stay outside the shared ConversationSurface, including Tool Set controls, Knowledge Search constraints, reachout, export, and role-specific page chrome.
- Conversation Activity Steps appear before the clean assistant response when Sage emits them.

## Admin Conversation browser flow

Verify selected Tool Sets, activity steps, Change Confirmation, secret redaction, final trace rendering, and fallback/error states in the product UI.

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
