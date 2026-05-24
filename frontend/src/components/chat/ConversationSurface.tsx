import { ReactNode, useCallback, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { MessageCircle, Sparkles } from 'lucide-react';
import {
  AssistantRuntimeProvider,
  ThreadPrimitive,
  useExternalStoreRuntime,
  type AppendMessage,
  type ThreadMessage,
} from '@assistant-ui/react';
import { ChatInput } from './ChatInput';
import { ChatMessage } from './ChatMessage';
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
  const runtimeMessages = useMemo(
    () =>
      turns.map((turn, index) => convertTurnToAssistantMessage(turn, index)),
    [turns]
  );
  const handleNew = useCallback(
    async (message: AppendMessage) => {
      const text = extractAppendMessageText(message).trim();
      if (text) onSend(text);
    },
    [onSend]
  );
  const runtime = useExternalStoreRuntime({
    messages: runtimeMessages,
    isRunning,
    isDisabled: disabled,
    onNew: handleNew,
  });

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <section
        aria-label="Conversation surface"
        className="flex min-h-0 flex-1 flex-col"
      >
        <ThreadPrimitive.Root className="flex min-h-0 flex-1 flex-col">
          <ThreadPrimitive.Viewport
            autoScroll
            className="flex-1 overflow-y-auto px-3 py-6 sm:px-4"
          >
            <div className="mx-auto w-full max-w-3xl">
              {turns.length === 0 && !isRunning ? (
                <ConversationEmptyState />
              ) : (
                <>
                  {turns.map((turn) => (
                    <div key={turn.id}>
                      <ChatMessage
                        message={{
                          id: turn.id,
                          role: turn.role,
                          content: turn.content,
                          trace: turn.trace,
                          traceStatus: turn.traceStatus,
                          activitySteps: turn.activitySteps,
                        }}
                      />
                      {turnAccessories?.[turn.id]}
                    </div>
                  ))}
                  {notices}
                  {isRunning && (
                    <ConversationRunningIndicator label={t('chat.typing')} />
                  )}
                </>
              )}
            </div>
          </ThreadPrimitive.Viewport>
        </ThreadPrimitive.Root>
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

function ConversationEmptyState() {
  const { t } = useTranslation();

  return (
    <div className="flex min-h-[24rem] items-center justify-center p-4">
      <div className="w-full max-w-lg min-w-0 animate-fade-in text-center">
        <div className="mx-auto mb-6 flex h-14 w-14 items-center justify-center rounded-2xl border border-border bg-surface-raised text-accent">
          <MessageCircle className="h-7 w-7" strokeWidth={1.75} />
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
      <div className="flex gap-3">
        <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-border bg-surface-raised text-accent">
          <Sparkles className="h-4 w-4" aria-hidden="true" />
        </div>
        <div className="flex items-center gap-2 rounded-2xl rounded-bl-md border border-border bg-surface-raised px-4 py-3">
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

function extractAppendMessageText(message: AppendMessage): string {
  return message.content
    .map((part) =>
      'text' in part && typeof part.text === 'string' ? part.text : ''
    )
    .join('');
}
