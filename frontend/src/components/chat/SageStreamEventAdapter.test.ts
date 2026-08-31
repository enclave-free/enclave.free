import { describe, expect, it } from 'vitest';
import { adaptSageStreamEvent } from './SageStreamEventAdapter';

describe('Sage Stream Event Adapter', () => {
  it('accepts content-free Tool Selection Observations', () => {
    expect(
      adaptSageStreamEvent(
        'trace_delta',
        {
          trace_delta: {
            id: 'tool-selection-1',
            kind: 'tool_selection_observation',
            title: 'Tool Selection',
            content: 'No Tools were selected.',
            status: 'succeeded',
            metadata: {
              step: 0,
              enabled_tools: ['find_resources'],
              selected_tools: [],
              selection_count: 0,
              outcome: 'none',
            },
          },
        },
        'assistant-1'
      )
    ).toMatchObject({
      type: 'assistantTraceDeltaReceived',
      traceDelta: {
        kind: 'tool_selection_observation',
        status: 'succeeded',
        metadata: {
          selection_count: 0,
          outcome: 'none',
        },
      },
    });
  });

  it('preserves Tool retry and timeout trace deltas for streaming consumers', () => {
    expect(
      adaptSageStreamEvent(
        'trace_delta',
        {
          trace_delta: {
            id: 'tool-retry-1',
            kind: 'tool_retry',
            title: 'Curated Resources',
            content: 'Retrying Curated Resources after attempt 1.',
            tool_name: 'find_resources',
            status: 'running',
            metadata: { phase: 'retry', call_id: 'call-1', attempt: 1 },
          },
        },
        'assistant-1'
      )
    ).toMatchObject({
      type: 'assistantTraceDeltaReceived',
      traceDelta: {
        id: 'tool-retry-1',
        kind: 'tool_retry',
        tool_name: 'find_resources',
      },
    });
    expect(
      adaptSageStreamEvent(
        'trace_delta',
        {
          trace_delta: {
            id: 'tool-timeout-1',
            kind: 'timeout',
            title: 'Knowledge Search',
            content: 'Knowledge Search timed out.',
            tool_name: 'knowledge_search',
            status: 'timed_out',
            metadata: { phase: 'timeout', call_id: 'call-2', attempt: 2 },
          },
        },
        'assistant-1'
      )
    ).toMatchObject({
      type: 'assistantTraceDeltaReceived',
      traceDelta: {
        id: 'tool-timeout-1',
        kind: 'timeout',
        status: 'timed_out',
      },
    });
  });

  it('adapts the backend timing payload without changing its phase or outcome', () => {
    expect(
      adaptSageStreamEvent(
        'trace_delta',
        {
          message_id: 'msg-timing-1',
          trace_delta: {
            id: 'timing-final-provider-1',
            kind: 'timing',
            title: 'Provider first-event wait',
            content:
              'Provider first-event wait: 184 ms (combined provider wait).',
            status: 'succeeded',
            metadata: {
              phase: 'provider_first_event_wait',
              step: 1,
              attempt: 1,
              outcome: 'succeeded',
              duration_ms: 184,
              provider_wait_proxy: true,
              wait_origin: 'request_start',
            },
            created_at: '2026-07-28T12:00:00Z',
          },
        },
        'assistant-1'
      )
    ).toEqual({
      type: 'assistantTraceDeltaReceived',
      assistantTurnId: 'assistant-1',
      traceDelta: {
        id: 'timing-final-provider-1',
        kind: 'timing',
        title: 'Provider first-event wait',
        content: 'Provider first-event wait: 184 ms (combined provider wait).',
        status: 'succeeded',
        metadata: {
          phase: 'provider_first_event_wait',
          step: 1,
          attempt: 1,
          outcome: 'succeeded',
          duration_ms: 184,
          provider_wait_proxy: true,
          wait_origin: 'request_start',
        },
        created_at: '2026-07-28T12:00:00Z',
      },
    });
  });

  it('maps transport events into Conversation UI State actions', () => {
    expect(
      adaptSageStreamEvent('assistant_message_started', {
        message_id: 'assistant-1',
        session_id: 'session-1',
      })
    ).toEqual({
      type: 'assistantTurnStarted',
      id: 'assistant-1',
      sessionId: 'session-1',
    });

    expect(
      adaptSageStreamEvent(
        'trace_status',
        {
          status: 'Checking configuration...',
          timing: {
            phase: 'preparing_tools',
            elapsed_ms: 1234,
          },
        },
        'assistant-1'
      )
    ).toEqual({
      type: 'assistantTraceStatusChanged',
      assistantTurnId: 'assistant-1',
      traceStatus: 'Checking configuration... · 1.2s',
    });

    expect(
      adaptSageStreamEvent(
        'activity_step',
        {
          activity_step: {
            id: 'tool-db-query',
            kind: 'tool',
            title: 'Database Query',
            title_key: 'chat.activity.tool.databaseQuery.title',
            title_values: { toolId: 'db-query' },
            status: 'succeeded',
            status_key: 'chat.activity.status.succeeded',
            status_values: {},
            summary: 'Database results were redacted from the trace.',
            summary_key: 'chat.activity.databaseResultsRedacted',
            summary_values: { toolId: 'db-query' },
            warnings: ['raw_results_redacted', 123],
          },
        },
        'assistant-1'
      )
    ).toEqual({
      type: 'assistantActivityStepReceived',
      assistantTurnId: 'assistant-1',
      step: {
        id: 'tool-db-query',
        kind: 'tool',
        title: 'Database Query',
        titleKey: 'chat.activity.tool.databaseQuery.title',
        titleValues: { toolId: 'db-query' },
        status: 'succeeded',
        statusKey: 'chat.activity.status.succeeded',
        statusValues: {},
        summary: 'Database results were redacted from the trace.',
        summaryKey: 'chat.activity.databaseResultsRedacted',
        summaryValues: { toolId: 'db-query' },
        warnings: ['raw_results_redacted'],
      },
    });

    expect(
      adaptSageStreamEvent(
        'activity_step',
        {
          activity_step: { id: 'tool-db-query' },
        },
        'assistant-1'
      )
    ).toBeNull();

    expect(
      adaptSageStreamEvent(
        'trace_delta',
        {
          trace_delta: {
            id: 'trace-admin-config-call',
            kind: 'tool_call',
            title: 'Admin Config',
            content: 'Calling read_instance_settings.',
            tool_name: 'read_instance_settings',
            status: 'running',
            metadata: { phase: 'tool_loop' },
            created_at: '2026-06-18T12:00:00Z',
          },
        },
        'assistant-1'
      )
    ).toEqual({
      type: 'assistantTraceDeltaReceived',
      assistantTurnId: 'assistant-1',
      traceDelta: {
        id: 'trace-admin-config-call',
        kind: 'tool_call',
        title: 'Admin Config',
        content: 'Calling read_instance_settings.',
        tool_name: 'read_instance_settings',
        status: 'running',
        metadata: { phase: 'tool_loop' },
        created_at: '2026-06-18T12:00:00Z',
      },
    });

    expect(
      adaptSageStreamEvent(
        'trace_delta',
        {
          trace_delta: {
            id: '   ',
            kind: 'tool_call',
          },
        },
        'assistant-1'
      )
    ).toBeNull();

    expect(
      adaptSageStreamEvent(
        'trace_delta',
        {
          trace_delta: {
            id: 'trace-unknown-kind',
            kind: 'unknown_kind',
          },
        },
        'assistant-1'
      )
    ).toBeNull();

    expect(
      adaptSageStreamEvent(
        'answer_delta',
        {
          delta: 'Hello',
        },
        'assistant-1'
      )
    ).toEqual({
      type: 'assistantContentDeltaReceived',
      assistantTurnId: 'assistant-1',
      delta: 'Hello',
    });

    const trace = { visibility: 'summary', tools: [], retrieval: [] };
    expect(
      adaptSageStreamEvent('trace_final', { trace }, 'assistant-1')
    ).toEqual({
      type: 'assistantTraceSettled',
      assistantTurnId: 'assistant-1',
      trace,
    });

    expect(
      adaptSageStreamEvent(
        'trace_final',
        {
          trace: { visibility: 'summary', tools: {} },
        },
        'assistant-1'
      )
    ).toBeNull();

    expect(adaptSageStreamEvent('done', { session_id: 'session-1' })).toEqual({
      type: 'assistantTurnFinished',
      sessionId: 'session-1',
    });

    expect(adaptSageStreamEvent('error', { detail: 'Stream failed' })).toEqual({
      type: 'requestFailed',
      message: 'Stream failed',
    });
  });

  it('normalizes keyed Activity steps in final traces while preserving legacy traces', () => {
    expect(
      adaptSageStreamEvent(
        'trace_final',
        {
          trace: {
            visibility: 'detailed',
            tools: [],
            retrieval: [],
            activity_steps: [
              {
                id: 'tool-db-query',
                kind: 'tool',
                title: 'Database Query',
                title_key: 'chat.activity.tool.databaseQuery.title',
                title_values: { toolId: 'db-query' },
                status: 'succeeded',
                status_key: 'chat.activity.status.succeeded',
                status_values: {},
                summary: 'Database results were redacted from the trace.',
                summary_key: 'chat.activity.databaseResultsRedacted',
                summary_values: { toolId: 'db-query' },
              },
            ],
          },
        },
        'assistant-1'
      )
    ).toMatchObject({
      type: 'assistantTraceSettled',
      trace: {
        activity_steps: [
          {
            id: 'tool-db-query',
            titleKey: 'chat.activity.tool.databaseQuery.title',
            titleValues: { toolId: 'db-query' },
            statusKey: 'chat.activity.status.succeeded',
            summaryKey: 'chat.activity.databaseResultsRedacted',
            summaryValues: { toolId: 'db-query' },
          },
        ],
      },
    });

    const legacyTrace = { visibility: 'summary', tools: [], retrieval: [] };
    expect(
      adaptSageStreamEvent('trace_final', { trace: legacyTrace }, 'assistant-1')
    ).toEqual({
      type: 'assistantTraceSettled',
      assistantTurnId: 'assistant-1',
      trace: legacyTrace,
    });
  });
});
