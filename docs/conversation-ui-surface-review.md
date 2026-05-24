# Conversation UI Surface Review

Status: ready for browser review before full end-to-end smoke

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
