import { ReactNode, useCallback, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import {
  AssistantRuntimeProvider,
  useExternalStoreRuntime,
  type AppendMessage,
} from '@assistant-ui/react';
import { AssistantConversationThread } from './AssistantConversationThread';
import {
  buildAssistantConversationState,
  extractAppendMessageText,
} from './AssistantTurnAdapter';
import { ChatInput } from './ChatInput';
import type { ConversationSurfaceTurn } from './ConversationSurfaceModel';

interface ConversationSurfaceProps {
  turns: ConversationSurfaceTurn[];
  onSend: (message: string) => void;
  isRunning?: boolean;
  disabled?: boolean;
  placeholder?: string;
  toolbar?: ReactNode;
  turnAccessories?: Record<string, ReactNode>;
  notices?: ReactNode;
}

export function ConversationSurface({
  turns,
  onSend,
  isRunning = false,
  disabled = false,
  placeholder,
  toolbar,
  turnAccessories,
  notices,
}: ConversationSurfaceProps) {
  const { t } = useTranslation();
  const assistantState = useMemo(
    () =>
      buildAssistantConversationState({
        turns,
        isRunning,
        disabled,
        turnAccessories,
      }),
    [disabled, isRunning, turnAccessories, turns]
  );
  const handleNew = useCallback(
    async (message: AppendMessage) => {
      const text = extractAppendMessageText(message).trim();
      if (text) onSend(text);
    },
    [onSend]
  );
  const runtime = useExternalStoreRuntime({
    messages: assistantState.messages,
    isRunning: assistantState.isRunning,
    isDisabled: assistantState.isDisabled,
    onNew: handleNew,
  });

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <section
        aria-label="Conversation surface"
        className="flex min-h-0 flex-1 flex-col"
      >
        <AssistantConversationThread
          assistantState={assistantState}
          runningLabel={t('chat.typing')}
          notices={notices}
        />
        <ChatInput
          onSend={onSend}
          disabled={disabled || isRunning}
          placeholder={placeholder}
          toolbar={toolbar}
          assistantRuntime
        />
      </section>
    </AssistantRuntimeProvider>
  );
}
