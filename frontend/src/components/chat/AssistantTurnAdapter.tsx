import type { ReactNode } from 'react';
import type { AppendMessage, ThreadMessage } from '@assistant-ui/react';
import type { ConversationSurfaceTurn } from './ConversationSurfaceModel';
import {
  getConversationMessageActions,
  type ConversationMessageAction,
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
    actions: ConversationMessageAction[];
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
}: {
  turns: ConversationSurfaceTurn[];
  isRunning?: boolean;
  disabled?: boolean;
  turnAccessories?: AssistantTurnAccessoryRegistry;
  transportCapabilities?: ConversationTransportCapabilities;
  hasPendingApproval?: boolean;
  hasPersistedSession?: boolean;
}): AssistantConversationState {
  return {
    messages: turns.map((turn, index) =>
      convertTurnToAssistantMessage(turn, index)
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
      }),
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
  index: number
): ThreadMessage {
  const common = {
    id: `${turn.id}:${index}`,
    createdAt: new Date(),
    content: [{ type: 'text' as const, text: turn.content }],
    metadata: {
      custom: {
        activitySteps: turn.activitySteps,
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
