import { describe, expect, it } from 'vitest';
import { getConversationMessageActions } from './ConversationMessageActions';

describe('Conversation message actions', () => {
  it('hides unsupported ChatGPT-style controls instead of exposing fake actions', () => {
    const actions = getConversationMessageActions({
      role: 'assistant',
      isRunning: false,
      hasSession: true,
      transportCapabilities: {},
      hasPendingApproval: false,
    });

    expect(actions).toEqual([]);
  });

  it('gates supported actions by role, session, active turn, and approval state', () => {
    expect(
      getConversationMessageActions({
        role: 'assistant',
        isRunning: true,
        hasSession: true,
        transportCapabilities: { stop: true, regenerate: true },
        hasPendingApproval: false,
      })
    ).toEqual([
      expect.objectContaining({
        id: 'stop',
        disabled: false,
      }),
      expect.objectContaining({
        id: 'regenerate',
        disabled: true,
        disabledReason: 'Wait for the current response to finish first.',
      }),
    ]);

    expect(
      getConversationMessageActions({
        role: 'user',
        isRunning: false,
        hasSession: true,
        transportCapabilities: { edit: true, regenerate: true },
        hasPendingApproval: true,
      })
    ).toEqual([
      expect.objectContaining({
        id: 'edit',
        disabled: true,
        disabledReason:
          'Resolve the pending Change Confirmation before changing history.',
      }),
    ]);
  });
});
