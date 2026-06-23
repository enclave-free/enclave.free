# Use assistant-ui for the Conversation UI Surface

The Enclave Free Prototype will use assistant-ui as the shared Conversation UI Surface for Admin Conversations and User Conversations, starting with a thin adapter around Sage-owned Conversation Streaming Transport. The first slice should replace the custom message thread and prompt input, render Sage-emitted Conversation Activity Steps as a progressive turn timeline before the final answer is complete, and preserve Enclave-specific controls such as Tool Set selection, Knowledge Search document constraints, reachout, export, final Conversation Trace rendering, and Admin Change Confirmation. ADR-0024 updates the trace posture: the live activity experience should render reasoning and tool-call details transparently as assistant-ui-style message parts while Sage still protects the minimal credential and authority-bearing blocklist. This favors a configurable open-source chat UI layer without moving Agent Runtime ownership, streaming semantics, Tool behavior, memory, or inference boundaries out of Sage.

## Refined Product Direction

The Conversation UI Surface should move from a custom chat implementation that only wraps assistant-ui runtime primitives to a modern assistant-ui-led chat shell. Sage still owns the Agent Runtime, Conversation Streaming Transport, tool execution, trace sanitization, session memory, compaction, and inference boundaries. The frontend should use assistant-ui primitives and patterns for the ordinary chat experience, then add only thin Enclave-specific renderers for product behavior that assistant-ui cannot own safely. This refactor should prefer deleting or heavily rewriting bespoke chat components when assistant-ui provides a sensible default, rather than preserving the old chat surface behind an assistant-ui adapter.

The visual reference is a ChatGPT-like assistant interface with compact agentic affordances, not an agent console. Normal turns should feel calm, familiar, and message-first. Conversation Activity Steps and Conversation Trace metadata should remain visible by default when activity exists, because this prototype still needs strong feedback and transparency, but they should render as compact, expandable rows before the final assistant answer rather than as a dense debug blob.

The core message layout should follow modern assistant defaults: assistant responses are mostly unboxed text in a readable column, user turns use compact right-aligned bubbles, Activity renders as a visible structured timeline attached to assistant turns, and approval artifacts render as separate inline cards. Avatars and message actions should be subtle, with actions available through hover or compact controls instead of permanently loud chrome.

Admin Change Confirmation should become an inline approval card attached to the relevant assistant turn. The card should show a human-readable summary, affected settings, warnings, and masked secrets by default, with approve/reject actions and collapsed review details. Approvals should be non-blocking for normal conversation, with one clear pending admin-config approval at a time. Applying an approval should disable only that approval card, and historical cards should preserve their final state.

The chat layout should include a session-sidebar shell now, even before persistent session history is implemented. The shell may be static or local-only in this slice, but it should establish the future ChatGPT-style layout: sidebar for new chat and session navigation, light top bar for current chat context, composer toolbar for next-turn Tool Sets and Tool constraints, and thread content for assistant output, visible traces, compaction notices, errors, and approvals.

Tool Set selection should be represented as compact composer context rather than as separate dashboard-like controls. Knowledge Search document scope should live under the Knowledge Tool Set control as Tool constraints, not as a separate hidden document mode. True per-message file attachments, drag-and-drop upload, and assistant-ui attachment adapters are out of scope for this slice. Export should remain available but should move away from the primary path, such as into an overflow or secondary action area.

The chat should use Enclave theme tokens lightly for text, backgrounds, borders, accent, danger, and warning states, but should not preserve heavy legacy chat styling such as glow, strong gradients, oversized empty-state ornamentation, or bespoke bubble chrome. The Conversation UI Surface should become the best-designed part of the product and should be allowed to pull future theme work forward.

The current Sage stream contract emits `activity_step`, `trace_status`, and `trace_final` events rather than native assistant-ui tool-call lifecycle parts. After ADR-0024, Sage should also emit `trace_delta` events that the Conversation UI Surface adapts into assistant-ui-style reasoning and tool-call message parts. Conversation Activity Steps remain useful as summary or compatibility metadata, but the rich live experience should follow assistant-ui's grouped reasoning/tool-call presentation.

## Implementation Boundaries

- Use assistant-ui for the shared thread, composer, message layout, message actions, empty state, running state, and future-ready shell structure where practical.
- Keep Sage-owned Conversation Streaming Transport while moving route-specific tool behavior toward the unified model-driven Tool loop from ADR-0023.
- Keep Conversation Activity Steps and Conversation Trace as Sage-owned Conversation metadata, with raw reasoning/tool details exposed according to ADR-0024's transparent trace posture.
- Render traces before assistant answers when activity exists.
- Keep trace details expandable with local UI state only; do not persist open/closed state.
- Keep compaction notices as small system notices inside the thread rather than prominent warning blocks.
- Do not add message edit, regenerate, or full stop/cancel generation unless the existing Sage transport can support the behavior truthfully without corrupting **Conversation UI State**, **Session Memory**, or later turns.
- Preserve behavioral tests around stream adaptation, conversation state, transparent trace rendering, Admin Change Confirmation, Knowledge Search constraints, Tool Set selection, and export, while rewriting brittle DOM or style assertions as needed.

## Current Slice Status

The current implementation establishes the assistant-ui-backed Conversation Surface for Admin and User Conversations with a session-sidebar shell, shared composer, visible Conversation Activity Steps, expandable Conversation Trace details, composer-scoped Tool controls, secondary export placement, and inline Admin Change Confirmation approval cards.

Admin Change Confirmation cards are now UI-based rather than text-command-based. The assistant turn keeps human-readable prose, strips raw change-set JSON from the visible message after staging the approval, masks deployment secret values in review details, and preserves applied or rejected card state in the thread history. This keeps the prototype transparent without forcing operators to read or act on raw JSON.

The sidebar remains local-only. It shows the active conversation title and message count and supports starting a fresh chat, but durable session listing, resume, rename, delete, and cross-device persistence remain future work owned by the session-history slice.

Visual cleanup in this slice intentionally moves chat toward calm assistant defaults: lighter avatars, reduced glow/gradient treatment, smaller empty-state ornamentation, secondary export, and thread-contained notices. Broader product theming remains deferred.

## Next Refactor Direction

The next implementation slice should be one coherent modern assistant-ui chat-surface refactor rather than a set of disconnected polish tickets. It should convert the ordinary thread, composer, message layout, running states, and shell toward assistant-ui-led defaults while redesigning Activity, Change Confirmation, composer context controls, compaction notices, and the local-only Conversation Sidebar together.

## Considered Options

- Continue custom chat UI components. Rejected because the product is spending effort on generic chat interface mechanics instead of Enclave-specific conversation behavior.
- Use Vercel AI Elements. Deferred because it is strongest when the app aligns with the Vercel AI SDK message and transport model, while this prototype already has a Sage-owned streaming contract.
- Use CopilotKit. Rejected for this slice because it is a broader agent application framework, and the current decision is only about the Conversation UI Surface.
