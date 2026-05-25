export type ConversationMessageActionId = 'stop' | 'regenerate' | 'edit';

export interface ConversationTransportCapabilities {
  stop?: boolean;
  regenerate?: boolean;
  edit?: boolean;
}

export interface ConversationMessageAction {
  id: ConversationMessageActionId;
  label: string;
  disabled: boolean;
  disabledReason?: string;
}

export interface ConversationMessageActionContext {
  role: 'user' | 'assistant';
  isRunning: boolean;
  hasSession: boolean;
  transportCapabilities: ConversationTransportCapabilities;
  hasPendingApproval: boolean;
}

export function getConversationMessageActions({
  role,
  isRunning,
  hasSession,
  transportCapabilities,
  hasPendingApproval,
}: ConversationMessageActionContext): ConversationMessageAction[] {
  const actions: ConversationMessageAction[] = [];

  if (role === 'assistant' && transportCapabilities.stop) {
    actions.push({
      id: 'stop',
      label: 'Stop response',
      disabled: !isRunning,
      disabledReason: !isRunning ? 'There is no response to stop.' : undefined,
    });
  }

  if (role === 'assistant' && transportCapabilities.regenerate) {
    actions.push({
      id: 'regenerate',
      label: 'Regenerate response',
      disabled: isRunning || !hasSession || hasPendingApproval,
      disabledReason: actionDisabledReason({
        isRunning,
        hasSession,
        hasPendingApproval,
      }),
    });
  }

  if (role === 'user' && transportCapabilities.edit) {
    actions.push({
      id: 'edit',
      label: 'Edit message',
      disabled: isRunning || !hasSession || hasPendingApproval,
      disabledReason: actionDisabledReason({
        isRunning,
        hasSession,
        hasPendingApproval,
      }),
    });
  }

  return actions;
}

function actionDisabledReason({
  isRunning,
  hasSession,
  hasPendingApproval,
}: Pick<
  ConversationMessageActionContext,
  'isRunning' | 'hasSession' | 'hasPendingApproval'
>): string | undefined {
  if (isRunning) return 'Wait for the current response to finish first.';
  if (!hasSession) return 'Start or resume a Conversation first.';
  if (hasPendingApproval) {
    return 'Resolve the pending Change Confirmation before changing history.';
  }
  return undefined;
}
