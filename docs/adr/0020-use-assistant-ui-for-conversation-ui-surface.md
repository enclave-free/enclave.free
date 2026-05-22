# Use assistant-ui for the Conversation UI Surface

The Enclave Free Prototype will use assistant-ui as the shared Conversation UI Surface for Admin Conversations and User Conversations, starting with a thin adapter around Sage-owned Conversation Streaming Transport. The first slice should replace the custom message thread and prompt input, render Sage-emitted Conversation Activity Steps as a progressive turn timeline before the final answer is complete, and preserve Enclave-specific controls such as tool selection, document scope, reachout, export, final Conversation Trace rendering, and Admin Change Confirmation. Because this is still a prototype, the live activity timeline should bias toward an inspectable agent-loop/debug experience while relying on Sage to sanitize what is safe to show. This favors a configurable open-source chat UI layer without moving Agent Runtime ownership, streaming semantics, tool behavior, memory, or inference boundaries out of Sage.

## Considered Options

- Continue custom chat UI components. Rejected because the product is spending effort on generic chat interface mechanics instead of Enclave-specific conversation behavior.
- Use Vercel AI Elements. Deferred because it is strongest when the app aligns with the Vercel AI SDK message and transport model, while this prototype already has a Sage-owned streaming contract.
- Use CopilotKit. Rejected for this slice because it is a broader agent application framework, and the current decision is only about the Conversation UI Surface.
