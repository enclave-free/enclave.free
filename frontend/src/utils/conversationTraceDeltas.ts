import type { ConversationTraceDelta } from '../components/chat/ChatMessage';

export const CONVERSATION_TRACE_DELTA_KINDS = [
  'reasoning',
  'model_step',
  'tool_call',
  'tool_result',
  'tool_selection_observation',
  'retry',
  'tool_retry',
  'timeout',
  'correction',
  'retrieval',
  'timing',
] as const satisfies readonly ConversationTraceDelta['kind'][];

export function isConversationTraceDeltaKind(
  value: string
): value is ConversationTraceDelta['kind'] {
  return CONVERSATION_TRACE_DELTA_KINDS.includes(
    value as ConversationTraceDelta['kind']
  );
}

export function mergeTraceDeltas(
  existing: ConversationTraceDelta[] = [],
  incoming: ConversationTraceDelta[] = []
): ConversationTraceDelta[] {
  const merged = new Map<string, ConversationTraceDelta>();
  for (const delta of existing) merged.set(delta.id, delta);
  for (const delta of incoming) {
    const previous = merged.get(delta.id);
    merged.set(delta.id, previous ? { ...previous, ...delta } : delta);
  }
  return Array.from(merged.values());
}
