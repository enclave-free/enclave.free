import type {
  ConversationActivityStep,
  ConversationTraceDelta,
  ConversationTrace,
} from './ChatMessage';
import type { ConversationUiAction } from './ConversationUiState';
import { isConversationTraceDeltaKind } from '../../utils/conversationTraceDeltas';

export function adaptSageStreamEvent(
  event: string,
  payload: Record<string, unknown>,
  assistantTurnId?: string | null
): ConversationUiAction | null {
  switch (event) {
    case 'assistant_message_started': {
      const id =
        typeof payload.message_id === 'string' ? payload.message_id : null;
      if (!id) return null;
      return {
        type: 'assistantTurnStarted',
        id,
        sessionId:
          typeof payload.session_id === 'string'
            ? payload.session_id
            : undefined,
      };
    }
    case 'trace_status': {
      if (!assistantTurnId || typeof payload.status !== 'string') return null;
      return {
        type: 'assistantTraceStatusChanged',
        assistantTurnId,
        traceStatus: formatTraceStatus(payload.status, payload.timing),
      };
    }
    case 'activity_step': {
      if (!assistantTurnId) return null;
      const step = readActivityStep(payload);
      if (!step) return null;
      return {
        type: 'assistantActivityStepReceived',
        assistantTurnId,
        step,
      };
    }
    case 'trace_delta': {
      if (!assistantTurnId) return null;
      const traceDelta = readTraceDelta(payload);
      if (!traceDelta) return null;
      return {
        type: 'assistantTraceDeltaReceived',
        assistantTurnId,
        traceDelta,
      };
    }
    case 'answer_delta': {
      if (!assistantTurnId) return null;
      return {
        type: 'assistantContentDeltaReceived',
        assistantTurnId,
        delta: typeof payload.delta === 'string' ? payload.delta : '',
      };
    }
    case 'trace_final': {
      const trace = readConversationTrace(payload.trace);
      if (!assistantTurnId || !trace) return null;
      return {
        type: 'assistantTraceSettled',
        assistantTurnId,
        trace,
      };
    }
    case 'done':
      return {
        type: 'assistantTurnFinished',
        sessionId:
          typeof payload.session_id === 'string'
            ? payload.session_id
            : undefined,
      };
    case 'error': {
      return {
        type: 'requestFailed',
        message:
          typeof payload.detail === 'string'
            ? payload.detail
            : 'Failed to send message',
      };
    }
    default:
      return null;
  }
}

export function readTraceDelta(
  payload: Record<string, unknown>
): ConversationTraceDelta | null {
  const raw = payload.trace_delta;
  if (!raw || typeof raw !== 'object') return null;
  const delta = raw as Record<string, unknown>;
  if (typeof delta.id !== 'string' || typeof delta.kind !== 'string') {
    return null;
  }
  const id = delta.id.trim();
  const kind = delta.kind.trim();
  if (!id || !isConversationTraceDeltaKind(kind)) {
    return null;
  }

  const result: ConversationTraceDelta = {
    id,
    kind,
  };
  if (typeof delta.title === 'string') result.title = delta.title;
  if (typeof delta.content === 'string') result.content = delta.content;
  if (typeof delta.tool_name === 'string') result.tool_name = delta.tool_name;
  if (typeof delta.status === 'string') result.status = delta.status;
  if (typeof delta.created_at === 'string')
    result.created_at = delta.created_at;
  if (
    delta.metadata &&
    typeof delta.metadata === 'object' &&
    !Array.isArray(delta.metadata)
  ) {
    result.metadata = delta.metadata as Record<string, unknown>;
  }
  return result;
}

function formatTraceStatus(status: string, timing: unknown): string {
  const turnTiming = readTurnTiming(timing);
  if (!turnTiming) return status;
  return `${status} · ${formatElapsedTime(turnTiming.elapsedMs)}`;
}

function readTurnTiming(
  value: unknown
): { phase: string; elapsedMs: number } | null {
  if (!value || typeof value !== 'object') return null;
  const timing = value as Record<string, unknown>;
  if (typeof timing.phase !== 'string' || typeof timing.elapsed_ms !== 'number')
    return null;
  return {
    phase: timing.phase,
    elapsedMs: timing.elapsed_ms,
  };
}

function formatElapsedTime(elapsedMs: number): string {
  if (!Number.isFinite(elapsedMs) || elapsedMs < 0) return '0.0s';
  return `${(elapsedMs / 1000).toFixed(1)}s`;
}

function isConversationTrace(value: unknown): value is ConversationTrace {
  if (!value || typeof value !== 'object') return false;
  const trace = value as unknown as Record<string, unknown>;
  if (
    !['off', 'minimal', 'summary', 'detailed'].includes(
      String(trace.visibility)
    )
  )
    return false;
  if (trace.tools !== undefined && !Array.isArray(trace.tools)) return false;
  if (trace.retrieval !== undefined && !Array.isArray(trace.retrieval))
    return false;
  if (
    trace.activity_steps !== undefined &&
    !Array.isArray(trace.activity_steps)
  )
    return false;
  if (trace.trace_deltas !== undefined && !Array.isArray(trace.trace_deltas))
    return false;
  if (
    trace.reasoning !== undefined &&
    (!trace.reasoning || typeof trace.reasoning !== 'object')
  )
    return false;
  return true;
}

function readConversationTrace(value: unknown): ConversationTrace | null {
  if (!isConversationTrace(value)) return null;
  const trace = value as unknown as Record<string, unknown>;
  const normalized = { ...trace } as Record<string, unknown>;
  if (Array.isArray(trace.activity_steps)) {
    normalized.activity_steps = trace.activity_steps
      .map(readActivityStepValue)
      .filter((step): step is ConversationActivityStep => Boolean(step));
  }
  if (Array.isArray(trace.trace_deltas)) {
    normalized.trace_deltas = trace.trace_deltas
      .map((delta) => readTraceDelta({ trace_delta: delta }))
      .filter((item): item is ConversationTraceDelta => Boolean(item));
  }
  return normalized as unknown as ConversationTrace;
}

function readActivityStep(
  payload: Record<string, unknown>
): ConversationActivityStep | null {
  return readActivityStepValue(payload.activity_step);
}

export function readActivityStepValue(
  raw: unknown
): ConversationActivityStep | null {
  if (!raw || typeof raw !== 'object') return null;
  const step = raw as Record<string, unknown>;
  if (
    typeof step.id !== 'string' ||
    typeof step.kind !== 'string' ||
    typeof step.title !== 'string' ||
    typeof step.status !== 'string'
  ) {
    return null;
  }
  return {
    id: step.id,
    kind: step.kind,
    title: step.title,
    titleKey: readOptionalString(step.title_key),
    titleValues: readOptionalObject(step.title_values),
    status: step.status,
    statusKey: readOptionalString(step.status_key),
    statusValues: readOptionalObject(step.status_values),
    summary: typeof step.summary === 'string' ? step.summary : undefined,
    summaryKey: readOptionalString(step.summary_key),
    summaryValues: readOptionalObject(step.summary_values),
    warnings: Array.isArray(step.warnings)
      ? step.warnings.filter(
          (warning): warning is string => typeof warning === 'string'
        )
      : undefined,
  };
}

function readOptionalString(value: unknown): string | undefined {
  return typeof value === 'string' && value.trim() ? value : undefined;
}

function readOptionalObject(
  value: unknown
): Record<string, unknown> | undefined {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : undefined;
}
