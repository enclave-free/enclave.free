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
            content: 'Curated Resources was expected but not selected.',
            status: 'failed',
            metadata: {
              round: 1,
              enabled_tools: ['find_resources'],
              selected_tools: [],
              selection_count: 0,
              expected_curated_resources: true,
              missed_expected_curated_resources: true,
            },
          },
        },
        'assistant-1'
      )
    ).toMatchObject({
      type: 'assistantTraceDeltaReceived',
      traceDelta: {
        kind: 'tool_selection_observation',
        status: 'failed',
        metadata: {
          selection_count: 0,
          missed_expected_curated_resources: true,
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
            status: 'succeeded',
            summary: 'Database results were redacted from the trace.',
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
        status: 'succeeded',
        summary: 'Database results were redacted from the trace.',
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
});
