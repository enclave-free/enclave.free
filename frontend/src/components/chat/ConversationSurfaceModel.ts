import type {
  ConversationActivityStep,
  ConversationTrace,
  Message,
} from './ChatMessage'

export type { ConversationActivityStep }

export interface ConversationSurfaceTurn {
  id: string
  role: 'user' | 'assistant'
  content: string
  activitySteps: ConversationActivityStep[]
  trace: ConversationTrace | null
  traceStatus: string | null
}

export function buildConversationSurfaceTurns(messages: Message[]): ConversationSurfaceTurn[] {
  return messages.map((message) => ({
    id: message.id,
    role: message.role,
    content: message.content,
    activitySteps: mergeActivitySteps(message.activitySteps ?? [], message.trace?.activity_steps ?? []),
    trace: message.trace ?? null,
    traceStatus: message.traceStatus ?? null,
  }))
}

function mergeActivitySteps(
  liveSteps: ConversationActivityStep[],
  settledSteps: ConversationActivityStep[]
): ConversationActivityStep[] {
  const merged = new Map<string, ConversationActivityStep>()

  for (const step of liveSteps) {
    merged.set(step.id, step)
  }
  for (const step of settledSteps) {
    merged.set(step.id, step)
  }

  return Array.from(merged.values())
}
