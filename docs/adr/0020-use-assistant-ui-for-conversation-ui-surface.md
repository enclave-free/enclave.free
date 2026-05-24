# Use assistant-ui for the Conversation UI Surface

The Enclave Free Prototype will use assistant-ui as the shared Conversation UI Surface for Admin Conversations and User Conversations, starting with a thin adapter around Sage-owned Conversation Streaming Transport. The first slice should replace the custom message thread and prompt input, render Sage-emitted Conversation Activity Steps as a progressive turn timeline before the final answer is complete, and preserve Enclave-specific controls such as tool selection, document scope, reachout, export, final Conversation Trace rendering, and Admin Change Confirmation. Because this is still a prototype, the live activity timeline should bias toward an inspectable agent-loop/debug experience while relying on Sage to sanitize what is safe to show. This favors a configurable open-source chat UI layer without moving Agent Runtime ownership, streaming semantics, tool behavior, memory, or inference boundaries out of Sage.

## Refined Product Direction

The Conversation UI Surface should move from a custom chat implementation that only wraps assistant-ui runtime primitives to a modern assistant-ui-led chat shell. Sage still owns the Agent Runtime, Conversation Streaming Transport, tool execution, trace sanitization, session memory, compaction, and inference boundaries. The frontend should use assistant-ui primitives and patterns for the ordinary chat experience, then add only thin Enclave-specific renderers for product behavior that assistant-ui cannot own safely.

The visual reference is a ChatGPT-like assistant interface with compact agentic affordances, not an agent console. Normal turns should feel calm, familiar, and message-first. Conversation Activity Steps and Conversation Trace metadata should remain visible by default when activity exists, because this prototype still needs strong feedback and transparency, but they should render as compact, expandable rows before the final assistant answer rather than as a dense debug blob.

Admin Change Confirmation should become an inline approval card attached to the relevant assistant turn. The card should show a human-readable summary, affected settings, warnings, and masked secrets by default, with approve/reject actions and collapsed review details. Approvals should be non-blocking for normal conversation, with one clear pending admin-config approval at a time. Applying an approval should disable only that approval card, and historical cards should preserve their final state.

The chat layout should include a session-sidebar shell now, even before persistent session history is implemented. The shell may be static or local-only in this slice, but it should establish the future ChatGPT-style layout: sidebar for new chat and session navigation, light top bar for current chat context, composer toolbar for next-turn tools and document context, and thread content for assistant output, visible traces, compaction notices, errors, and approvals.

Document scope should be represented as composer context rather than as a separate dashboard-like control. True per-message file attachments, drag-and-drop upload, and assistant-ui attachment adapters are out of scope for this slice. Export should remain available but should move away from the primary path, such as into an overflow or secondary action area.

The chat should use Enclave theme tokens lightly for text, backgrounds, borders, accent, danger, and warning states, but should not preserve heavy legacy chat styling such as glow, strong gradients, oversized empty-state ornamentation, or bespoke bubble chrome. The Conversation UI Surface should become the best-designed part of the product and should be allowed to pull future theme work forward.

The current Sage stream contract emits safe, sanitized activity and trace events rather than native assistant-ui tool-call lifecycle parts. This slice should render those existing events directly as Enclave trace metadata. Native assistant-ui tool-call parts should only be adopted later if Sage's stream contract changes to provide a compatible, sanitized tool-call protocol.

## Implementation Boundaries

- Use assistant-ui for the shared thread, composer, message layout, message actions, empty state, running state, and future-ready shell structure where practical.
- Keep Sage-owned Conversation Streaming Transport and existing `/llm/chat/stream` and `/query/stream` contracts.
- Keep Conversation Activity Steps and Conversation Trace as sanitized product metadata from Sage.
- Render traces before assistant answers when activity exists.
- Keep trace details expandable with local UI state only; do not persist open/closed state.
- Keep compaction notices as small system notices inside the thread rather than prominent warning blocks.
- Do not add message edit, regenerate, or full stop/cancel generation unless the existing transport can support the behavior cleanly.
- Preserve behavioral tests around stream adaptation, conversation state, trace visibility, Admin Change Confirmation, document context, and export, while rewriting brittle DOM or style assertions as needed.

## Current Slice Status

The current implementation establishes the assistant-ui-backed Conversation Surface for Admin and User Conversations with a session-sidebar shell, shared composer, visible Conversation Activity Steps, expandable Conversation Trace details, composer-scoped tools and Documents, secondary export placement, and inline Admin Change Confirmation approval cards.

Admin Change Confirmation cards are now UI-based rather than text-command based. The assistant turn keeps human-readable prose, strips raw change-set JSON from the visible message after staging the approval, masks deployment secret values in review details, and preserves applied or rejected card state in the thread history. This keeps the prototype transparent without forcing operators to read or act on raw JSON.

The sidebar remains local-only. It shows the active conversation title and message count and supports starting a fresh chat, but durable session listing, resume, rename, delete, and cross-device persistence remain future work owned by the session-history slice.

Visual cleanup in this slice intentionally moves chat toward calm assistant defaults: lighter avatars, reduced glow/gradient treatment, smaller empty-state ornamentation, secondary export, and thread-contained notices. Broader product theming remains deferred.

## Considered Options

- Continue custom chat UI components. Rejected because the product is spending effort on generic chat interface mechanics instead of Enclave-specific conversation behavior.
- Use Vercel AI Elements. Deferred because it is strongest when the app aligns with the Vercel AI SDK message and transport model, while this prototype already has a Sage-owned streaming contract.
- Use CopilotKit. Rejected for this slice because it is a broader agent application framework, and the current decision is only about the Conversation UI Surface.
