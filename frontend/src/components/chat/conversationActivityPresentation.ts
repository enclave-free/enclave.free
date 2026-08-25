import type {
  ConversationActivityStep,
  ConversationTrace,
  ConversationTraceDelta,
} from './ChatMessage';

export type ConversationActivityAudience = 'user' | 'admin';

interface ConversationActivityPresentationInput {
  audience: ConversationActivityAudience;
  trace?: ConversationTrace | null;
  activitySteps: ConversationActivityStep[];
  traceDeltas: ConversationTraceDelta[];
  liveStatus?: string | null;
}

interface ConversationActivityPresentation {
  trace?: ConversationTrace | null;
  activitySteps: ConversationActivityStep[];
  traceDeltas: ConversationTraceDelta[];
  liveStatus: string | null;
}

const USER_HIDDEN_OPERATIONAL_KINDS = new Set([
  'correction',
  'model_request',
  'model_retry',
  'model_step',
  'model_usage',
  'model_usage_observation',
  'provider_retry',
  'provider_request',
  'provider_timing',
  'retry',
  'retry_delay',
  'timeout',
  'timing',
  'tool_retry',
  'tool_selection_observation',
  'usage',
  'usage_observation',
]);

const USER_HIDDEN_OPERATIONAL_TITLES = new Set([
  'model request',
  'model usage',
  'provider first-event wait',
  'provider request',
  'provider timing',
  'retry delay',
  'token usage',
  'tool selection',
  'tool retry',
]);

const USER_VISIBLE_PRODUCT_KINDS = new Set([
  'reasoning',
  'retrieval',
  'tool',
  'tool_call',
  'tool_result',
]);

const USER_FRIENDLY_LIVE_STATUSES = new Set([
  'finalizing response',
  'preparing selected tools',
  'running enabled tools',
  'writing answer',
]);

function normalizeCategory(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[\s-]+/g, '_');
}

function normalizeDisplayText(value: string): string {
  return value.trim().toLowerCase().replace(/\.+$/, '').trim();
}

function isUserVisibleRow(row: { kind: string; title?: string }): boolean {
  const kind = normalizeCategory(row.kind);
  if (USER_HIDDEN_OPERATIONAL_KINDS.has(kind)) {
    return false;
  }
  if (USER_VISIBLE_PRODUCT_KINDS.has(kind)) return true;

  return !(
    row.title &&
    USER_HIDDEN_OPERATIONAL_TITLES.has(normalizeDisplayText(row.title))
  );
}

function presentUserLiveStatus(status?: string | null): string | null {
  if (!status) return null;

  const normalized = normalizeDisplayText(status);
  if (USER_FRIENDLY_LIVE_STATUSES.has(normalized)) return status;

  if (
    normalized === 'timed_out' ||
    normalized === 'timeout' ||
    normalized.endsWith(' timed out') ||
    normalized.startsWith('provider first-event wait') ||
    normalized.startsWith('model request') ||
    normalized.startsWith('retry delay') ||
    normalized.startsWith('retrying model request') ||
    normalized.startsWith('retrying provider request') ||
    (normalized.startsWith('retrying ') &&
      normalized.includes(' after attempt')) ||
    normalized.startsWith('correcting provider') ||
    normalized.startsWith('model usage') ||
    normalized.startsWith('token usage')
  ) {
    return null;
  }

  return status;
}

/**
 * Adapts guarded Conversation Trace data for display without mutating the raw
 * message, persisted trace, or export payload. Unknown row kinds remain visible
 * so new product work does not silently disappear from User Activity.
 */
export function presentConversationActivity({
  audience,
  trace,
  activitySteps,
  traceDeltas,
  liveStatus,
}: ConversationActivityPresentationInput): ConversationActivityPresentation {
  if (audience === 'admin') {
    return {
      trace,
      activitySteps,
      traceDeltas,
      liveStatus: liveStatus ?? null,
    };
  }

  const presentedActivitySteps = activitySteps.filter(isUserVisibleRow);
  const presentedTraceDeltas = traceDeltas.filter(isUserVisibleRow);
  const presentedTrace = trace
    ? {
        ...trace,
        activity_steps: trace.activity_steps?.filter(isUserVisibleRow),
        trace_deltas: trace.trace_deltas?.filter(isUserVisibleRow),
      }
    : trace;

  return {
    trace: presentedTrace,
    activitySteps: presentedActivitySteps,
    traceDeltas: presentedTraceDeltas,
    liveStatus: presentUserLiveStatus(liveStatus),
  };
}
