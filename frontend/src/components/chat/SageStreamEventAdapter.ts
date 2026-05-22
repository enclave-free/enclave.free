import type { ConversationActivityStep, ConversationTrace } from './ChatMessage'
import type { ConversationUiAction } from './ConversationUiState'

export function adaptSageStreamEvent(
  event: string,
  payload: Record<string, unknown>,
  assistantTurnId?: string | null
): ConversationUiAction | null {
  switch (event) {
    case 'assistant_message_started': {
      const id = typeof payload.message_id === 'string' ? payload.message_id : null
      if (!id) return null
      return {
        type: 'assistantTurnStarted',
        id,
        sessionId: typeof payload.session_id === 'string' ? payload.session_id : undefined,
      }
    }
    case 'trace_status': {
      if (!assistantTurnId || typeof payload.status !== 'string') return null
      return {
        type: 'assistantTraceStatusChanged',
        assistantTurnId,
        traceStatus: payload.status,
      }
    }
    case 'activity_step': {
      if (!assistantTurnId) return null
      const step = readActivityStep(payload)
      if (!step) return null
      return {
        type: 'assistantActivityStepReceived',
        assistantTurnId,
        step,
      }
    }
    case 'answer_delta': {
      if (!assistantTurnId) return null
      return {
        type: 'assistantContentDeltaReceived',
        assistantTurnId,
        delta: typeof payload.delta === 'string' ? payload.delta : '',
      }
    }
    case 'trace_final': {
      if (!assistantTurnId || !isConversationTrace(payload.trace)) return null
      return {
        type: 'assistantTraceSettled',
        assistantTurnId,
        trace: payload.trace,
      }
    }
    case 'done':
      return {
        type: 'assistantTurnFinished',
        sessionId: typeof payload.session_id === 'string' ? payload.session_id : undefined,
      }
    case 'error': {
      return {
        type: 'requestFailed',
        message: typeof payload.detail === 'string' ? payload.detail : 'Failed to send message',
      }
    }
    default:
      return null
  }
}

function isConversationTrace(value: unknown): value is ConversationTrace {
  if (!value || typeof value !== 'object') return false
  const trace = value as Record<string, unknown>
  if (!['off', 'minimal', 'summary', 'detailed'].includes(String(trace.visibility))) return false
  if (trace.tools !== undefined && !Array.isArray(trace.tools)) return false
  if (trace.retrieval !== undefined && !Array.isArray(trace.retrieval)) return false
  if (trace.activity_steps !== undefined && !Array.isArray(trace.activity_steps)) return false
  if (trace.reasoning !== undefined && (!trace.reasoning || typeof trace.reasoning !== 'object')) return false
  return true
}

function readActivityStep(payload: Record<string, unknown>): ConversationActivityStep | null {
  const raw = payload.activity_step
  if (!raw || typeof raw !== 'object') return null
  const step = raw as Record<string, unknown>
  if (
    typeof step.id !== 'string' ||
    typeof step.kind !== 'string' ||
    typeof step.title !== 'string' ||
    typeof step.status !== 'string'
  ) {
    return null
  }
  return {
    id: step.id,
    kind: step.kind,
    title: step.title,
    status: step.status,
    summary: typeof step.summary === 'string' ? step.summary : undefined,
    warnings: Array.isArray(step.warnings)
      ? step.warnings.filter((warning): warning is string => typeof warning === 'string')
      : undefined,
  }
}
