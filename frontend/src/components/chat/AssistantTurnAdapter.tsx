import type { ReactNode } from 'react';
import type { AppendMessage, ThreadMessage } from '@assistant-ui/react';
import type { ConversationSurfaceTurn } from './ConversationSurfaceModel';
import {
  getConversationMessageActions,
  type LocalizedConversationMessageAction,
  type ConversationTransportCapabilities,
} from './ConversationMessageActions';

export interface AssistantTurnAccessoryRegistry {
  [turnId: string]: ReactNode;
}

export interface AssistantConversationState {
  messages: ThreadMessage[];
  turnItems: Array<{
    turn: ConversationSurfaceTurn;
    accessory: ReactNode | null;
    actions: LocalizedConversationMessageAction[];
  }>;
  isRunning: boolean;
  isDisabled: boolean;
  unsupportedActions: {
    attachments: true;
    edit: true;
    regenerate: true;
    stop: true;
  };
}

export function buildAssistantConversationState({
  turns,
  isRunning = false,
  disabled = false,
  turnAccessories,
  transportCapabilities = {},
  hasPendingApproval = false,
  hasPersistedSession = false,
  runtimeMessageIdPrefix = '',
  translate,
}: {
  turns: ConversationSurfaceTurn[];
  isRunning?: boolean;
  disabled?: boolean;
  turnAccessories?: AssistantTurnAccessoryRegistry;
  transportCapabilities?: ConversationTransportCapabilities;
  hasPendingApproval?: boolean;
  hasPersistedSession?: boolean;
  runtimeMessageIdPrefix?: string;
  translate?: (key: string, defaultValue: string) => string;
}): AssistantConversationState {
  return {
    messages: turns.map((turn) =>
      convertTurnToAssistantMessage(turn, runtimeMessageIdPrefix)
    ),
    turnItems: turns.map((turn) => ({
      turn,
      accessory: turnAccessories?.[turn.id] ?? null,
      actions: getConversationMessageActions({
        role: turn.role,
        isRunning,
        hasSession: hasPersistedSession,
        transportCapabilities,
        hasPendingApproval,
      }).map((action) => ({
        id: action.id,
        label: translate
          ? translate(action.labelKey, action.labelDefault)
          : action.labelDefault,
        disabled: action.disabled,
        disabledReason:
          action.disabledReasonKey && action.disabledReasonDefault
            ? translate
              ? translate(
                  action.disabledReasonKey,
                  action.disabledReasonDefault
                )
              : action.disabledReasonDefault
            : undefined,
      })),
    })),
    isRunning,
    isDisabled: disabled,
    unsupportedActions: {
      attachments: true,
      edit: true,
      regenerate: true,
      stop: true,
    },
  };
}

function convertTurnToAssistantMessage(
  turn: ConversationSurfaceTurn,
  runtimeMessageIdPrefix: string
): ThreadMessage {
  const common = {
    id: `${runtimeMessageIdPrefix}${turn.id}`,
    createdAt: new Date(),
    content: [{ type: 'text' as const, text: turn.content }],
    metadata: {
      custom: {
        activitySteps: turn.activitySteps,
        traceDeltas: turn.traceDeltas,
        trace: turn.trace,
        traceStatus: turn.traceStatus,
      },
    },
  };

  if (turn.role === 'user') {
    return {
      ...common,
      role: 'user',
      attachments: [],
    };
  }

  return {
    ...common,
    role: turn.role,
    status: turn.traceStatus
      ? { type: 'running' }
      : { type: 'complete', reason: 'stop' },
    metadata: {
      ...common.metadata,
      unstable_state: null,
      unstable_annotations: [],
      unstable_data: [],
      steps: [],
    },
  };
}

export function extractAppendMessageText(message: AppendMessage): string {
  return message.content
    .map((part) =>
      'text' in part && typeof part.text === 'string' ? part.text : ''
    )
    .join('');
}
