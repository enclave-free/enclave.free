import { describe, expect, it } from 'vitest';
import {
  buildConversationSurfaceTurns,
  type ConversationActivityStep,
  type ConversationTraceDelta,
} from './ConversationSurfaceModel';
import type { Message } from './ChatMessage';

describe('buildConversationSurfaceTurns', () => {
  it('keeps streamed activity steps before the assistant answer and reconciles final trace activity', () => {
    const activity: ConversationActivityStep = {
      id: 'tool-db-query',
      kind: 'tool',
      title: 'Database Query',
      status: 'succeeded',
      summary: 'Database results were redacted from the trace.',
      warnings: ['raw_results_redacted'],
    };
    const messages: Message[] = [
      {
        id: 'user-1',
        role: 'user',
        content: 'Check the settings table',
      },
      {
        id: 'assistant-1',
        role: 'assistant',
        content: 'The settings table is configured.',
        activitySteps: [activity],
        trace: {
          visibility: 'detailed',
          reasoning: {
            summary: 'Sage checked configuration before answering.',
          },
          tools: [],
          retrieval: [],
          activity_steps: [activity],
        },
      },
    ];

    const turns = buildConversationSurfaceTurns(messages);

    expect(turns).toEqual([
      {
        id: 'user-1',
        role: 'user',
        content: 'Check the settings table',
        activitySteps: [],
        traceDeltas: [],
        trace: null,
        traceStatus: null,
      },
      {
        id: 'assistant-1',
        role: 'assistant',
        content: 'The settings table is configured.',
        activitySteps: [activity],
        traceDeltas: [],
        trace: messages[1].trace,
        traceStatus: null,
      },
    ]);
  });

  it('propagates settled Conversation Trace Deltas onto surface turns', () => {
    const traceDelta: ConversationTraceDelta = {
      id: 'trace-admin-config-result',
      kind: 'tool_result',
      title: 'Admin Config',
      tool_name: 'read_instance_settings',
      status: 'succeeded',
      content: 'Tool completed.',
    };
    const messages: Message[] = [
      {
        id: 'assistant-1',
        role: 'assistant',
        content: 'Settings are ready.',
        trace: {
          visibility: 'detailed',
          tools: [],
          retrieval: [],
          trace_deltas: [traceDelta],
        },
      },
    ];

    const turns = buildConversationSurfaceTurns(messages);

    expect(turns[0].traceDeltas).toEqual([traceDelta]);
  });
});
