import { ReactNode, useCallback, useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { MessageCircle, Sparkles } from 'lucide-react'
import {
  AssistantRuntimeProvider,
  useExternalStoreRuntime,
  type AppendMessage,
  type ThreadMessage,
} from '@assistant-ui/react'
import { ChatInput } from './ChatInput'
import { ChatMessage } from './ChatMessage'
import type { ConversationSurfaceTurn } from './ConversationSurfaceModel'

interface ConversationSurfaceProps {
  turns: ConversationSurfaceTurn[]
  onSend: (message: string) => void
  isRunning?: boolean
  disabled?: boolean
  placeholder?: string
  toolbar?: ReactNode
}

export function ConversationSurface({
  turns,
  onSend,
  isRunning = false,
  disabled = false,
  placeholder,
  toolbar,
}: ConversationSurfaceProps) {
  const { t } = useTranslation()
  const runtimeMessages = useMemo(
    () => turns.map(convertTurnToAssistantMessage),
    [turns]
  )
  const handleNew = useCallback(async (message: AppendMessage) => {
    const text = extractAppendMessageText(message).trim()
    if (text) onSend(text)
  }, [onSend])
  const runtime = useExternalStoreRuntime({
    messages: runtimeMessages,
    isRunning,
    isDisabled: disabled,
    onNew: handleNew,
  })

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <div className="flex min-h-0 flex-1 flex-col">
        <div className="flex-1 overflow-y-auto px-3 py-6 sm:px-4">
          <div className="mx-auto w-full max-w-3xl">
            {turns.length === 0 && !isRunning ? (
              <ConversationEmptyState />
            ) : (
              <>
                {turns.map((turn) => (
                  <div key={turn.id}>
                    {turn.role === 'assistant' && turn.activitySteps.length > 0 && (
                      <div className="mb-3 ml-10 space-y-2" aria-label="Conversation activity">
                        {turn.activitySteps.map((step) => (
                          <div
                            key={step.id}
                            className="rounded-lg border border-border bg-surface-raised px-3 py-2 text-sm shadow-sm"
                          >
                            <div className="flex items-center justify-between gap-3">
                              <span className="font-medium text-text">{step.title}</span>
                              <span className="label text-[10px]">{step.status}</span>
                            </div>
                            {step.summary && (
                              <p className="mt-1 text-xs leading-relaxed text-text-secondary">
                                {step.summary}
                              </p>
                            )}
                            {step.warnings && step.warnings.length > 0 && (
                              <div className="mt-1 flex flex-wrap gap-1">
                                {step.warnings.map((warning) => (
                                  <span
                                    key={warning}
                                    className="rounded border border-warning/30 bg-warning/10 px-1.5 py-0.5 text-[10px] text-warning"
                                  >
                                    {warning}
                                  </span>
                                ))}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
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
                  </div>
                ))}
                {isRunning && <ConversationRunningIndicator label={t('chat.typing')} />}
              </>
            )}
          </div>
        </div>
        <ChatInput
          onSend={onSend}
          disabled={disabled || isRunning}
          placeholder={placeholder}
          toolbar={toolbar}
        />
      </div>
    </AssistantRuntimeProvider>
  )
}

function ConversationEmptyState() {
  const { t } = useTranslation()

  return (
    <div className="flex min-h-[24rem] items-center justify-center p-4">
      <div className="w-full max-w-lg min-w-0 animate-fade-in text-center">
        <div className="relative mx-auto mb-8 h-20 w-20">
          <div className="absolute inset-0 rotate-6 rounded-2xl bg-gradient-to-br from-accent/20 to-accent/5 scale-95" />
          <div className="absolute inset-0 flex items-center justify-center rounded-2xl bg-gradient-to-br from-accent to-accent-hover shadow-xl ring-1 ring-white/10">
            <MessageCircle className="h-10 w-10 text-white" strokeWidth={1.75} />
          </div>
        </div>
        <h2 className="heading-xl mb-2 text-balance">{t('chat.emptyState.title')}</h2>
        <p className="mx-auto mb-0 max-w-xs text-pretty text-sm text-text-secondary sm:max-w-prose">
          {t('chat.emptyState.description')}
        </p>
      </div>
    </div>
  )
}

function ConversationRunningIndicator({ label }: { label: string }) {
  return (
    <div className="mb-4 animate-fade-in-up">
      <div className="flex gap-3">
        <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-accent to-accent-hover shadow-md ring-1 ring-white/10">
          <Sparkles className="h-4 w-4 text-white" aria-hidden="true" />
        </div>
        <div className="flex items-center gap-2 rounded-2xl rounded-bl-md border border-border bg-surface-raised px-4 py-3">
          <div className="flex items-center gap-1">
            <span className="typing-dot h-2 w-2 rounded-full bg-accent/60" />
            <span className="typing-dot h-2 w-2 rounded-full bg-accent/60" />
            <span className="typing-dot h-2 w-2 rounded-full bg-accent/60" />
          </div>
          <span className="animate-pulse-subtle text-sm text-text-secondary">{label}</span>
        </div>
      </div>
    </div>
  )
}

function convertTurnToAssistantMessage(turn: ConversationSurfaceTurn): ThreadMessage {
  const common = {
    id: turn.id,
    createdAt: new Date(),
    content: [{ type: 'text' as const, text: turn.content }],
    metadata: {
      custom: {
        activitySteps: turn.activitySteps,
        trace: turn.trace,
        traceStatus: turn.traceStatus,
      },
    },
  }

  if (turn.role === 'user') {
    return {
      ...common,
      role: 'user',
      attachments: [],
    }
  }

  return {
    ...common,
    role: turn.role,
    status: turn.traceStatus ? { type: 'running' } : { type: 'complete', reason: 'stop' },
    metadata: {
      ...common.metadata,
      unstable_state: null,
      unstable_annotations: [],
      unstable_data: [],
      steps: [],
    },
  }
}

function extractAppendMessageText(message: AppendMessage): string {
  return message.content
    .map((part) => ('text' in part && typeof part.text === 'string' ? part.text : ''))
    .join('')
}
