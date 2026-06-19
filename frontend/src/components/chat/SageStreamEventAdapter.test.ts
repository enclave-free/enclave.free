import { describe, expect, it } from 'vitest';
import { adaptSageStreamEvent } from './SageStreamEventAdapter';

describe('Sage Stream Event Adapter', () => {
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
