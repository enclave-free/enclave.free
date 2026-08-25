import { describe, expect, it } from 'vitest';
import type {
  ConversationActivityStep,
  ConversationTrace,
  ConversationTraceDelta,
} from './ChatMessage';
import { presentConversationActivity } from './conversationActivityPresentation';

const operationalSteps: ConversationActivityStep[] = [
  {
    id: 'provider-wait',
    kind: 'timing',
    title: 'Provider first-event wait',
    status: 'timed_out',
    summary: 'Provider produced no event before the deadline.',
  },
  {
    id: 'model-request',
    kind: 'model_step',
    title: 'Model request',
    status: 'succeeded',
    summary: 'Model request: 842 ms.',
  },
  {
    id: 'tool-selection',
    kind: 'tool_selection_observation',
    title: 'Tool Selection',
    status: 'succeeded',
    summary: 'No Tools were selected.',
  },
  {
    id: 'model-usage',
    kind: 'model_usage_observation',
    title: 'Model usage',
    status: 'succeeded',
    summary: 'Input tokens: 120; output tokens: 40.',
  },
];

const productSteps: ConversationActivityStep[] = [
  {
    id: 'search',
    kind: 'tool',
    title: 'Web Search',
    status: 'succeeded',
    summary: 'Found three results after the search provider retried.',
  },
  {
    id: 'retrieval',
    kind: 'retrieval',
    title: 'Knowledge Search',
    status: 'succeeded',
    summary: 'Found the tenant guide.',
  },
  {
    id: 'future-product-work',
    kind: 'workflow',
    title: 'Preparing referral options',
    status: 'running',
  },
];

const operationalDeltas: ConversationTraceDelta[] = [
  {
    id: 'retry',
    kind: 'retry',
    title: 'Retry delay',
    content: 'Retrying model request after 500 ms.',
  },
  {
    id: 'tool-retry',
    kind: 'tool_retry',
    title: 'Curated Resources',
    content: 'Retrying Curated Resources after attempt 1.',
  },
  {
    id: 'timeout',
    kind: 'timeout',
    title: 'Knowledge Search',
    content: 'Knowledge Search timed out.',
  },
  {
    id: 'correction',
    kind: 'correction',
    title: 'Corrected provider event order',
  },
];

const productDeltas: ConversationTraceDelta[] = [
  {
    id: 'tool-call',
    kind: 'tool_call',
    title: 'Curated Resources',
    content: 'Finding relevant organizations.',
  },
  {
    id: 'tool-result',
    kind: 'tool_result',
    title: 'Curated Resources',
    content: 'Found two organizations with their retry guidance.',
  },
  {
    id: 'retrieval',
    kind: 'retrieval',
    title: 'Tenant guide',
  },
  {
    id: 'future-product-work',
    kind: 'workflow' as ConversationTraceDelta['kind'],
    title: 'Preparing referral options',
  },
  {
    id: 'product-row-with-diagnostic-title',
    kind: 'tool_result',
    title: 'Model request',
    content: 'Loaded a guide whose title matches an operational label.',
  },
];

describe('presentConversationActivity', () => {
  it('removes operational rows for Users while preserving product work and raw input', () => {
    const trace: ConversationTrace = {
      visibility: 'detailed',
      tools: [{ id: 'web-search', name: 'Web Search' }],
      retrieval: [{ title: 'Tenant guide' }],
      activity_steps: [...operationalSteps, ...productSteps],
      trace_deltas: [...operationalDeltas, ...productDeltas],
    };
    const activitySteps = [...operationalSteps, ...productSteps];
    const traceDeltas = [...operationalDeltas, ...productDeltas];

    const presented = presentConversationActivity({
      audience: 'user',
      trace,
      activitySteps,
      traceDeltas,
      liveStatus: 'Running enabled tools...',
    });

    expect(presented.activitySteps.map((step) => step.id)).toEqual([
      'search',
      'retrieval',
      'future-product-work',
    ]);
    expect(presented.traceDeltas.map((delta) => delta.id)).toEqual([
      'tool-call',
      'tool-result',
      'retrieval',
      'future-product-work',
      'product-row-with-diagnostic-title',
    ]);
    expect(presented.trace?.activity_steps).toEqual(presented.activitySteps);
    expect(presented.trace?.trace_deltas).toEqual(presented.traceDeltas);
    expect(presented.trace?.tools).toEqual(trace.tools);
    expect(presented.trace?.retrieval).toEqual(trace.retrieval);
    expect(presented.liveStatus).toBe('Running enabled tools...');
    expect(trace.activity_steps).toEqual([
      ...operationalSteps,
      ...productSteps,
    ]);
    expect(trace.trace_deltas).toEqual([
      ...operationalDeltas,
      ...productDeltas,
    ]);
  });

  it('returns Admin diagnostics unchanged', () => {
    const trace: ConversationTrace = {
      visibility: 'detailed',
      activity_steps: operationalSteps,
      trace_deltas: operationalDeltas,
    };
    const input = {
      audience: 'admin' as const,
      trace,
      activitySteps: operationalSteps,
      traceDeltas: operationalDeltas,
      liveStatus: 'Provider first-event wait: 30001 ms.',
    };

    const presented = presentConversationActivity(input);

    expect(presented.trace).toBe(trace);
    expect(presented.activitySteps).toBe(operationalSteps);
    expect(presented.traceDeltas).toBe(operationalDeltas);
    expect(presented.liveStatus).toBe(input.liveStatus);
  });

  it('suppresses only diagnostic User statuses and keeps friendly progress', () => {
    const presentStatus = (liveStatus: string) =>
      presentConversationActivity({
        audience: 'user',
        trace: null,
        activitySteps: [],
        traceDeltas: [],
        liveStatus,
      }).liveStatus;

    expect(presentStatus('Preparing selected tools...')).toBe(
      'Preparing selected tools...'
    );
    expect(presentStatus('Running enabled tools...')).toBe(
      'Running enabled tools...'
    );
    expect(presentStatus('Writing answer...')).toBe('Writing answer...');
    expect(presentStatus('Provider first-event wait: 30001 ms.')).toBeNull();
    expect(presentStatus('TIMED_OUT')).toBeNull();
    expect(presentStatus('Knowledge Search timed out.')).toBeNull();
    expect(presentStatus('Retrying model request after attempt 1.')).toBeNull();
    expect(
      presentStatus('Retrying Curated Resources after attempt 1.')
    ).toBeNull();
  });

  it('recognizes diagnostic titles even when an older payload used a generic kind', () => {
    const presented = presentConversationActivity({
      audience: 'user',
      trace: null,
      activitySteps: [
        {
          id: 'legacy-model-request',
          kind: 'status',
          title: 'Model request',
          status: 'succeeded',
        },
        {
          id: 'legacy-tool-selection',
          kind: 'status',
          title: 'Tool Selection',
          status: 'succeeded',
        },
        {
          id: 'legacy-provider-request',
          kind: 'status',
          title: 'Provider request',
          status: 'succeeded',
        },
        {
          id: 'legacy-provider-timing',
          kind: 'status',
          title: 'Provider timing',
          status: 'succeeded',
        },
        {
          id: 'unknown-product-work',
          kind: 'status',
          title: 'Preparing referral options',
          status: 'running',
        },
      ],
      traceDeltas: [],
      liveStatus: null,
    });

    expect(presented.activitySteps.map((step) => step.id)).toEqual([
      'unknown-product-work',
    ]);
  });
});
