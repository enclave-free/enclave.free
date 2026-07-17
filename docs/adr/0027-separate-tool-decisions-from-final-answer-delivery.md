# Separate Tool decisions from final answer delivery

Status: Still authoritative for Tool planning and natural final-answer delivery. Its Admin Config proposal and confirmation references are superseded by [ADR-0028](0028-sage-owns-direct-admin-config-writes.md).

Sage will keep provider-portable typed responses for deciding and executing enabled **Tools**, but it will not require final user-visible prose to round-trip through the typed `AgentResponse` schema or a repair-model call. After the model-selected Tool round completes, **Conversation Streaming Transport** should generate the final answer through a plain completion path and forward real provider chunks as answer deltas; deterministic terminal Tool results may finish without another model call. This accepts a bounded Tool-planning phase in exchange for removing correction calls and fake streaming from the answer critical path while preserving Sage ownership, Tool authorization, trace visibility, and provider portability.

## Considered Options

- Keep every step typed and batch the final response. Rejected because malformed final prose triggers expensive correction calls and prevents real answer streaming.
- Depend on provider-native function calling for the whole loop. Rejected because ADR-0023 requires provider-portable, Sage-owned Tool orchestration.
- Stream structured predictor output directly. Rejected because schema markers and incomplete Tool decisions must not leak into user-visible answer content.

## Consequences

The model should select every immediately useful enabled Tool in the bounded planning response. Sage may still finish deterministic proposal Tools without another inference call. Tool execution, authorization, redaction, trace events, and Change Confirmation remain unchanged; only terminal answer generation leaves the typed response contract.
