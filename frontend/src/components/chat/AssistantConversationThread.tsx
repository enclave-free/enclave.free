import { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { MessageCircle, Sparkles } from 'lucide-react';
import { ThreadPrimitive } from '@assistant-ui/react';
import { ChatMessage, type Message } from './ChatMessage';
import type { AssistantConversationState } from './AssistantTurnAdapter';
import type { ConversationMessageActionId } from './ConversationMessageActions';

interface AssistantConversationThreadProps {
  assistantState: AssistantConversationState;
  runningLabel: string;
  notices?: ReactNode;
  onMessageAction?: (
    actionId: ConversationMessageActionId,
    message: Message
  ) => void;
}

export function AssistantConversationThread({
  assistantState,
  runningLabel,
  notices,
  onMessageAction,
}: AssistantConversationThreadProps) {
  const { t } = useTranslation();

  return (
    <div
      role="region"
      aria-label="Conversation thread"
      className="flex min-h-0 flex-1 flex-col"
    >
      <ThreadPrimitive.Root className="flex min-h-0 flex-1 flex-col">
        <ThreadPrimitive.Viewport
          autoScroll
          role="group"
          aria-label={t(
            'chat.conversationMessagesAria',
            'Conversation messages'
          )}
          className="flex-1 overflow-y-auto px-2 py-5 sm:px-4 sm:py-6"
        >
          <div className="mx-auto w-full max-w-3xl">
            {assistantState.turnItems.length === 0 &&
            !assistantState.isRunning ? (
              <ConversationEmptyState />
            ) : (
              <>
                {assistantState.turnItems.map(
                  ({ turn, accessory, actions }) => (
                    <div key={turn.id}>
                      <ChatMessage
                        message={{
                          id: turn.id,
                          role: turn.role,
                          content: turn.content,
                          trace: turn.trace,
                          traceStatus: turn.traceStatus,
                          activitySteps: turn.activitySteps,
                          traceDeltas: turn.traceDeltas,
                          actions,
                        }}
                        onAction={onMessageAction}
                      />
                      {accessory}
                    </div>
                  )
                )}
                {notices}
                {assistantState.isRunning && (
                  <ConversationRunningIndicator label={runningLabel} />
                )}
              </>
            )}
          </div>
        </ThreadPrimitive.Viewport>
      </ThreadPrimitive.Root>
    </div>
  );
}

function ConversationEmptyState() {
  const { t } = useTranslation();

  return (
    <div className="flex min-h-[24rem] items-center justify-center p-4">
      <div className="w-full max-w-lg min-w-0 animate-fade-in text-center">
        <div className="mx-auto mb-5 flex h-12 w-12 items-center justify-center rounded-xl border border-border bg-surface-raised text-accent">
          <MessageCircle className="h-6 w-6" strokeWidth={1.75} />
        </div>
        <h2 className="heading-xl mb-2 text-balance">
          {t('chat.emptyState.title')}
        </h2>
        <p className="mx-auto mb-0 max-w-xs text-pretty text-sm text-text-secondary sm:max-w-prose">
          {t('chat.emptyState.description')}
        </p>
      </div>
    </div>
  );
}

function ConversationRunningIndicator({ label }: { label: string }) {
  return (
    <div className="mb-4 animate-fade-in-up">
      <div className="flex min-w-0 gap-3">
        <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-border bg-surface-raised text-accent">
          <Sparkles className="h-4 w-4" aria-hidden="true" />
        </div>
        <div className="flex min-w-0 max-w-full items-center gap-2 rounded-2xl rounded-bl-md border border-border bg-surface-raised px-4 py-3">
          <div className="flex items-center gap-1">
            <span className="typing-dot h-2 w-2 rounded-full bg-accent/60" />
            <span className="typing-dot h-2 w-2 rounded-full bg-accent/60" />
            <span className="typing-dot h-2 w-2 rounded-full bg-accent/60" />
          </div>
          <span className="animate-pulse-subtle text-sm text-text-secondary">
            {label}
          </span>
        </div>
      </div>
    </div>
  );
}
