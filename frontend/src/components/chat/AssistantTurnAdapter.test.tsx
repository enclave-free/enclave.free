import { describe, expect, it } from 'vitest';
import {
  buildAssistantConversationState,
  extractAppendMessageText,
} from './AssistantTurnAdapter';
import type { ConversationSurfaceTurn } from './ConversationSurfaceModel';

describe('AssistantTurnAdapter', () => {
  it('maps Sage turns into assistant-ui messages with trace metadata and turn accessories', () => {
    const turns: ConversationSurfaceTurn[] = [
      {
        id: 'user-1',
        role: 'user',
        content: 'Show session memory',
        activitySteps: [],
        trace: null,
        traceStatus: null,
      },
      {
        id: 'assistant-1',
        role: 'assistant',
        content: 'Session memory is available.',
        activitySteps: [
          {
            id: 'tool-1',
            kind: 'tool',
            title: 'Memory Lookup',
            status: 'succeeded',
          },
        ],
        trace: {
          visibility: 'summary',
          tools: [
            {
              id: 'tool-trace-1',
              name: 'memory_lookup',
              status: 'succeeded',
              output_summary: 'Queried memory',
            },
          ],
        },
        traceStatus: 'Reading memory...',
      },
    ];

    const state = buildAssistantConversationState({
      turns,
      isRunning: true,
      disabled: true,
      turnAccessories: {
        'assistant-1': <div>Admin approval</div>,
      },
    });

    expect(state.messages).toHaveLength(2);
    expect(state.messages[0]).toMatchObject({
      id: 'user-1',
      role: 'user',
      content: [{ type: 'text', text: 'Show session memory' }],
    });
    expect(state.messages[1]).toMatchObject({
      id: 'assistant-1',
      role: 'assistant',
      content: [{ type: 'text', text: 'Session memory is available.' }],
      status: { type: 'running' },
    });
    expect(state.messages[1].metadata.custom).toMatchObject({
      traceStatus: 'Reading memory...',
      activitySteps: [{ title: 'Memory Lookup' }],
      trace: { tools: [{ output_summary: 'Queried memory' }] },
    });
    expect(state.turnItems).toHaveLength(2);
    expect(state.turnItems[0].accessory).toBeNull();
    expect(state.turnItems[1].accessory).toEqual(<div>Admin approval</div>);
    expect(state.turnItems[0].actions).toEqual([]);
    expect(state.turnItems[1].actions).toEqual([]);
    expect(state.isRunning).toBe(true);
    expect(state.isDisabled).toBe(true);
    expect(state.unsupportedActions).toMatchObject({
      attachments: true,
      edit: true,
      regenerate: true,
      stop: true,
    });
  });

  it('derives message actions only from explicit transport capabilities', () => {
    const turns: ConversationSurfaceTurn[] = [
      {
        id: 'assistant-1',
        role: 'assistant',
        content: 'Ready.',
        activitySteps: [],
        trace: null,
        traceStatus: null,
      },
    ];

    const state = buildAssistantConversationState({
      turns,
      isRunning: true,
      transportCapabilities: { stop: true },
    });

    expect(state.turnItems[0].actions).toEqual([
      expect.objectContaining({
        id: 'stop',
        disabled: false,
      }),
    ]);
  });

  it('does not treat local turns as a persisted session for history-mutating actions', () => {
    const turns: ConversationSurfaceTurn[] = [
      {
        id: 'user-1',
        role: 'user',
        content: 'Draft this again.',
        activitySteps: [],
        trace: null,
        traceStatus: null,
      },
    ];

    const withoutSession = buildAssistantConversationState({
      turns,
      transportCapabilities: { edit: true },
    });
    const withSession = buildAssistantConversationState({
      turns,
      transportCapabilities: { edit: true },
      hasPersistedSession: true,
    });

    expect(withoutSession.turnItems[0].actions).toEqual([
      expect.objectContaining({
        id: 'edit',
        disabled: true,
        disabledReason: 'Start or resume a Conversation first.',
      }),
    ]);
    expect(withSession.turnItems[0].actions).toEqual([
      expect.objectContaining({
        id: 'edit',
        disabled: false,
      }),
    ]);
  });

  it('extracts text from assistant-ui append messages', () => {
    expect(
      extractAppendMessageText({
        role: 'user',
        metadata: { custom: {} },
        createdAt: new Date(),
        parentId: null,
        sourceId: null,
        runConfig: undefined,
        content: [
          { type: 'text', text: 'Hello' },
          { type: 'text', text: ' world' },
        ],
      })
    ).toBe('Hello world');
  });
});
