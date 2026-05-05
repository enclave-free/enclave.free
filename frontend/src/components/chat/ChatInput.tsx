import { useState, useRef, useEffect, KeyboardEvent, ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Send } from 'lucide-react'
import { IconButton } from '../ui'

interface ChatInputProps {
  onSend: (message: string) => void
  disabled?: boolean
  placeholder?: string
  toolbar?: ReactNode
}

export function ChatInput({ onSend, disabled, placeholder, toolbar }: ChatInputProps) {
  const { t } = useTranslation()
  const defaultPlaceholder = t('chat.input.placeholder')
  const [input, setInput] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 160)}px`
    }
  }, [input])

  const handleSubmit = () => {
    if (input.trim() && !disabled) {
      onSend(input.trim())
      setInput('')
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto'
      }
    }
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  return (
    <div className="border-t border-border bg-surface px-3 py-3 sm:px-4 shadow-[0_-1px_3px_rgba(0,0,0,0.03)]">
      <div className="max-w-3xl mx-auto">
        <div className="input-container rounded-2xl overflow-hidden bg-surface-raised!">
          {/* Toolbar row */}
          {toolbar && (
            <div className="px-3 py-2.5 border-b border-border/50 flex items-center gap-2 bg-surface-overlay/30">
              {toolbar}
            </div>
          )}

          {/* Input row */}
          <div className="flex items-end gap-2 p-2">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              aria-label={placeholder || defaultPlaceholder}
              placeholder={placeholder || defaultPlaceholder}
              disabled={disabled}
              rows={1}
              className="flex-1 bg-transparent text-text placeholder:text-text-muted resize-none outline-none focus-visible:outline-none border-none px-2 py-2 max-h-40 text-[15px] leading-relaxed"
            />
            <IconButton
              label={t('chat.input.sendLabel')}
              onClick={handleSubmit}
              disabled={disabled || !input.trim()}
              title={t('chat.input.sendTitle')}
              variant="primary"
              className="rounded-xl shadow-sm hover:shadow-md hover:glow-accent disabled:shadow-none"
            >
              <Send className="h-5 w-5" aria-hidden="true" />
            </IconButton>
          </div>
        </div>
      </div>
    </div>
  )
}
