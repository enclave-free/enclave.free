import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark, oneLight } from 'react-syntax-highlighter/dist/esm/styles/prism'
import type { CSSProperties } from 'react'
import { useTranslation } from 'react-i18next'
import { Check, Copy } from 'lucide-react'
import { useTheme } from '../../theme'
import { useInstanceConfig } from '../../context/InstanceConfigContext'
import { DynamicIcon } from '../shared/DynamicIcon'
import { Button } from '../ui'

export interface ConversationTrace {
  visibility: 'off' | 'minimal' | 'summary' | 'detailed'
  reasoning?: {
    summary?: string
  }
  tools?: Array<{
    id: string
    name: string
    status?: string
    execution?: string
    input_summary?: string | null
    output_summary?: string | null
    warnings?: string[]
    metadata?: Record<string, unknown>
  }>
  retrieval?: Array<{
    source_type?: string
    title?: string | null
    summary?: string | null
    score?: number | null
  }>
  suppressed?: boolean
}

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp?: Date
  trace?: ConversationTrace | null
  traceStatus?: string | null
}

interface ChatMessageProps {
  message: Message
}

function UserIcon({ iconName }: { iconName: string }) {
  return (
    <div className="w-7 h-7 rounded-full bg-accent/10 flex items-center justify-center shrink-0 ring-1 ring-accent/20">
      <DynamicIcon name={iconName} size={16} className="text-accent" />
    </div>
  )
}

function AssistantIcon({ iconName }: { iconName: string }) {
  return (
    <div className="w-7 h-7 rounded-full bg-gradient-to-br from-accent to-accent-hover flex items-center justify-center shrink-0 shadow-md ring-1 ring-white/10">
      <DynamicIcon name={iconName} size={16} className="text-white" />
    </div>
  )
}

interface CodeBlockProps {
  language: string | null
  children: string
  resolvedTheme: 'light' | 'dark'
}

function CodeBlock({ language, children, resolvedTheme }: CodeBlockProps) {
  const [copied, setCopied] = useState(false)
  const { t } = useTranslation()

  const handleCopy = async () => {
    await navigator.clipboard.writeText(children)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const codeStyle = resolvedTheme === 'dark' ? oneDark : oneLight

  return (
    <div className="my-4 rounded-xl overflow-hidden border border-border shadow-md group">
      <div className="flex items-center justify-between px-4 py-2.5 bg-surface-raised border-b border-border">
        <div className="flex items-center gap-2">
          <span className="label">
            {language || 'code'}
          </span>
        </div>
        <Button
          onClick={handleCopy}
          variant="ghost"
          size="sm"
          leadingIcon={
            copied ? (
              <Check className="h-3.5 w-3.5 text-success" aria-hidden="true" />
            ) : (
              <Copy className="h-3.5 w-3.5" aria-hidden="true" />
            )
          }
          className="text-xs"
          aria-label={copied ? t('chat.code.copied') : t('chat.code.copyCode')}
        >
          {copied ? t('chat.code.copied') : t('chat.code.copy')}
        </Button>
      </div>
      <SyntaxHighlighter
        style={codeStyle as { [key: string]: CSSProperties }}
        language={language || 'text'}
        PreTag="div"
        showLineNumbers={false}
        customStyle={{
          margin: 0,
          padding: '1rem 1.25rem',
          fontSize: '0.8125rem',
          lineHeight: '1.7',
        }}
      >
        {children}
      </SyntaxHighlighter>
    </div>
  )
}

function ConversationTracePanel({ trace }: { trace: ConversationTrace }) {
  const tools = trace.tools ?? []
  const retrieval = trace.retrieval ?? []
  const summary = trace.reasoning?.summary

  if (trace.visibility === 'off') return null

  if (trace.visibility === 'minimal') {
    if (tools.length === 0 && retrieval.length === 0) return null

    return (
      <div className="mt-3 flex flex-wrap gap-2 border-t border-border/70 pt-3 text-xs text-text-muted">
        {tools.map((tool) => (
          <div key={tool.id} className="rounded-md border border-border bg-surface px-2 py-1">
            <span className="font-medium text-text">{tool.name}</span>
          </div>
        ))}
        {retrieval.map((item, index) => (
          <div key={`${item.title ?? item.source_type ?? 'retrieval'}-${index}`} className="rounded-md border border-border bg-surface px-2 py-1">
            <span className="font-medium text-text">{item.title || item.source_type || 'Retrieved source'}</span>
          </div>
        ))}
      </div>
    )
  }

  return (
    <details className="mt-3 border-t border-border/70 pt-3 text-xs text-text-muted">
      <summary className="mb-2 cursor-pointer select-none font-medium text-text">Conversation Trace</summary>
      {summary && <p className="mb-2 leading-relaxed">{summary}</p>}
      {tools.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {tools.map((tool, index) => (
            <div key={`${tool.id}-${tool.input_summary ?? ''}-${index}`} className="rounded-md border border-border bg-surface px-2 py-1">
              <span className="font-medium text-text">{tool.name}</span>
              {tool.output_summary && <span className="ml-1">{tool.output_summary}</span>}
            </div>
          ))}
        </div>
      )}
      {retrieval.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-2">
          {retrieval.map((item, index) => (
            <div key={`${item.title ?? item.source_type ?? 'retrieval'}-${index}`} className="rounded-md border border-border bg-surface px-2 py-1">
              <span className="font-medium text-text">{item.title || item.source_type || 'Retrieved source'}</span>
              {item.summary && <span className="ml-1">{item.summary}</span>}
            </div>
          ))}
        </div>
      )}
    </details>
  )
}

export function ChatMessage({ message }: ChatMessageProps) {
  const { resolvedTheme } = useTheme()
  const { t } = useTranslation()
  const { config } = useInstanceConfig()
  const [copiedMessage, setCopiedMessage] = useState(false)
  const isUser = message.role === 'user'
  const label = isUser ? config.userLabel : config.assistantName

  const handleCopyMessage = async () => {
    await navigator.clipboard.writeText(message.content)
    setCopiedMessage(true)
    setTimeout(() => setCopiedMessage(false), 2000)
  }

  const bubbleStyles = {
    soft: {
      user: 'rounded-2xl rounded-tr-md',
      assistant: 'rounded-2xl rounded-tl-md',
    },
    round: {
      user: 'rounded-3xl',
      assistant: 'rounded-3xl',
    },
    square: {
      user: 'rounded-lg',
      assistant: 'rounded-lg',
    },
    pill: {
      user: 'rounded-3xl',
      assistant: 'rounded-3xl',
    },
  } as const

  const bubbleRadius = bubbleStyles[config.chatBubbleStyle] || bubbleStyles.soft
  const bubbleShadow = config.chatBubbleShadow ? 'shadow-md' : ''
  const userBubbleClass = `group/message relative inline-block max-w-72 sm:max-w-[min(85%,42rem)] bg-accent text-accent-text px-4 py-2.5 pr-11 ${bubbleRadius.user} ${bubbleShadow} ${config.chatBubbleShadow ? 'glow-accent' : ''}`
  const assistantBubbleClass = `group/message relative inline-block max-w-72 sm:max-w-[min(100%,48rem)] bg-surface-raised border border-border px-4 py-3 pr-11 ${bubbleRadius.assistant} ${bubbleShadow}`
  const copyButtonClass = isUser
    ? 'absolute right-2 top-2 inline-flex h-7 w-7 items-center justify-center rounded-full text-accent-text/75 opacity-70 transition hover:bg-white/15 hover:text-accent-text hover:opacity-100 focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/70'
    : 'absolute right-2 top-2 inline-flex h-7 w-7 items-center justify-center rounded-full text-text-muted opacity-70 transition hover:bg-surface-overlay hover:text-text focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40'
  const copyIcon = copiedMessage ? (
    <Check className="h-3.5 w-3.5" aria-hidden="true" />
  ) : (
    <Copy className="h-3.5 w-3.5" aria-hidden="true" />
  )
  const copyAction = (
    <button
      type="button"
      onClick={handleCopyMessage}
      className={copyButtonClass}
      aria-label={copiedMessage ? t('chat.messages.copied') : t('chat.messages.copy')}
      title={copiedMessage ? t('chat.messages.copied') : t('chat.messages.copy')}
    >
      {copyIcon}
    </button>
  )

  return (
    <div className="animate-fade-in-up mb-4 last:mb-0">
      <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : ''}`}>
        {/* Avatar */}
        {isUser ? (
          <UserIcon iconName={config.userIcon} />
        ) : (
          <AssistantIcon iconName={config.assistantIcon} />
        )}

        {/* Content */}
        <div className={`flex-1 min-w-0 ${isUser ? 'flex flex-col items-end' : 'flex flex-col items-start'}`}>
          {label?.trim() && (
            <div className="text-xs text-text-muted mb-1">{label}</div>
          )}
          {isUser ? (
            <div className={userBubbleClass}>
              {copyAction}
              <p className="whitespace-pre-wrap break-words text-[15px] leading-relaxed">{message.content}</p>
            </div>
          ) : (
            <div className={assistantBubbleClass}>
              {copyAction}
              <div className="text-text break-words [&_*]:text-inherit [&_a]:text-accent [&_code]:text-text">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                  code({ node, className, children, ...props }) {
                    const match = /language-(\w+)/.exec(className || '')
                    const isInline = !match && !className

                    if (isInline) {
                      return (
                        <code
                          className="bg-surface-overlay px-1.5 py-0.5 rounded text-[0.875em] font-mono text-text"
                          {...props}
                        >
                          {children}
                        </code>
                      )
                    }

                    return (
                      <CodeBlock
                        language={match ? match[1] : null}
                        resolvedTheme={resolvedTheme}
                      >
                        {String(children).replace(/\n$/, '')}
                      </CodeBlock>
                    )
                  },
                  p({ children }) {
                    return <p className="mb-3 last:mb-0 text-[15px] leading-relaxed">{children}</p>
                  },
                  a({ href, children }) {
                    return (
                      <a
                        href={href}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-accent hover:text-accent-hover underline underline-offset-2 decoration-accent/30 hover:decoration-accent transition-colors"
                      >
                        {children}
                      </a>
                    )
                  },
                  ul({ children }) {
                    return <ul className="mb-3 last:mb-0 list-disc space-y-1.5 pl-5 text-[15px]">{children}</ul>
                  },
                  ol({ children }) {
                    return <ol className="mb-3 last:mb-0 list-decimal space-y-1.5 pl-5 text-[15px]">{children}</ol>
                  },
                  li({ children }) {
                    return (
                      <li className="pl-1 leading-relaxed marker:text-accent">{children}</li>
                    )
                  },
                  blockquote({ children }) {
                    return (
                      <blockquote className="my-4 border-l-4 border-border pl-4 text-text-secondary text-[15px] leading-relaxed [&>p]:mb-0">
                        {children}
                      </blockquote>
                    )
                  },
                  em({ children }) {
                    return <em className="italic text-inherit">{children}</em>
                  },
                  h1({ children }) {
                    return <h1 className="text-xl font-semibold mb-3 mt-4 first:mt-0 text-text tracking-tight">{children}</h1>
                  },
                  h2({ children }) {
                    return <h2 className="text-lg font-semibold mb-2 mt-4 first:mt-0 text-text tracking-tight">{children}</h2>
                  },
                  h3({ children }) {
                    return <h3 className="text-base font-semibold mb-2 mt-3 first:mt-0 text-text tracking-tight">{children}</h3>
                  },
                  hr() {
                    return <hr className="my-4 border-border" />
                  },
                  strong({ children }) {
                    return <strong className="font-semibold text-text">{children}</strong>
                  },
                  table({ children }) {
                    return (
                      <div className="my-4 overflow-x-auto rounded-xl border border-border shadow-sm">
                        <table className="min-w-full text-sm divide-y divide-border">
                          {children}
                        </table>
                      </div>
                    )
                  },
                  thead({ children }) {
                    return (
                      <thead className="bg-surface-raised">
                        {children}
                      </thead>
                    )
                  },
                  tbody({ children }) {
                    return (
                      <tbody className="divide-y divide-border bg-surface">
                        {children}
                      </tbody>
                    )
                  },
                  tr({ children }) {
                    return (
                      <tr className="hover:bg-surface-overlay transition-colors duration-150 even:bg-surface-raised/50">
                        {children}
                      </tr>
                    )
                  },
                  th({ children }) {
                    return (
                      <th className="px-4 py-3 text-left text-xs font-semibold text-text uppercase tracking-wider">
                        {children}
                      </th>
                    )
                  },
                  td({ children }) {
                    return (
                      <td className="px-4 py-3 text-text-secondary">
                        {children}
                      </td>
                    )
                  },
                  }}
                >
                  {message.content}
                </ReactMarkdown>
                {message.traceStatus && (
                  <div className="mt-3 border-t border-border/70 pt-3 text-xs text-text-muted">
                    {message.traceStatus}
                  </div>
                )}
                {message.trace && <ConversationTracePanel trace={message.trace} />}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
