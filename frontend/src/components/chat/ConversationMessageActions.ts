export type ConversationMessageActionId = 'stop' | 'regenerate' | 'edit';

export interface ConversationTransportCapabilities {
  stop?: boolean;
  regenerate?: boolean;
  edit?: boolean;
}

export interface ConversationMessageAction {
  id: ConversationMessageActionId;
  labelKey: string;
  labelDefault: string;
  disabled: boolean;
  disabledReasonKey?: string;
  disabledReasonDefault?: string;
}

export interface LocalizedConversationMessageAction {
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
      labelKey: 'chat.actions.stop',
      labelDefault: 'Stop response',
      disabled: !isRunning,
      disabledReasonKey: !isRunning ? 'chat.actions.stopDisabled' : undefined,
      disabledReasonDefault: !isRunning
        ? 'There is no response to stop.'
        : undefined,
    });
  }

  if (role === 'assistant' && transportCapabilities.regenerate) {
    actions.push({
      id: 'regenerate',
      labelKey: 'chat.actions.regenerate',
      labelDefault: 'Regenerate response',
      disabled: isRunning || !hasSession || hasPendingApproval,
      ...actionDisabledReason({
        isRunning,
        hasSession,
        hasPendingApproval,
      }),
    });
  }

  if (role === 'user' && transportCapabilities.edit) {
    actions.push({
      id: 'edit',
      labelKey: 'chat.actions.edit',
      labelDefault: 'Edit message',
      disabled: isRunning || !hasSession || hasPendingApproval,
      ...actionDisabledReason({
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
>):
  | { disabledReasonKey: string; disabledReasonDefault: string }
  | { disabledReasonKey?: undefined; disabledReasonDefault?: undefined } {
  if (isRunning) {
    return {
      disabledReasonKey: 'chat.actions.waitForResponse',
      disabledReasonDefault: 'Wait for the current response to finish first.',
    };
  }
  if (!hasSession) {
    return {
      disabledReasonKey: 'chat.actions.startConversation',
      disabledReasonDefault: 'Start or resume a Conversation first.',
    };
  }
  if (hasPendingApproval) {
    return {
      disabledReasonKey: 'chat.actions.resolveConfirmation',
      disabledReasonDefault:
        'Resolve the pending Change Confirmation before changing history.',
    };
  }
  return {};
}
