import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { X } from 'lucide-react'
import { API_BASE } from '../../types/onboarding'
import { Button, Callout, IconButton, Textarea } from '../ui'
import type { ReachoutMode } from '../../i18n/dynamicTranslationFamilies'

export type { ReachoutMode } from '../../i18n/dynamicTranslationFamilies'

interface ReachoutOverrides {
  title?: string
  description?: string
  buttonLabel?: string
  successMessage?: string
}

interface ReachoutModalProps {
  open: boolean
  mode: ReachoutMode
  overrides?: ReachoutOverrides
  onClose: () => void
}

function nonEmpty(value: unknown): string | undefined {
  if (typeof value !== 'string') return undefined
  const trimmed = value.trim()
  return trimmed ? trimmed : undefined
}

export function ReachoutModal({ open, mode, overrides, onClose }: ReachoutModalProps) {
  const { t } = useTranslation()
  const modalRef = useRef<HTMLDivElement | null>(null)
  const [message, setMessage] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  const title =
    nonEmpty(overrides?.title) ??
    t(`reachout.mode.${mode}.title`, mode === 'feedback' ? 'Feedback' : mode === 'help' ? 'Help' : 'Support')
  const description =
    nonEmpty(overrides?.description) ??
    t(
      `reachout.mode.${mode}.description`,
      mode === 'feedback'
        ? 'Send feedback or suggestions to the team.'
        : mode === 'help'
          ? 'Ask for help using this instance.'
          : 'Contact support about an issue or request.'
    )
  const sendLabel = nonEmpty(overrides?.buttonLabel) ?? t('reachout.form.send', 'Send')
  const successMessage = nonEmpty(overrides?.successMessage) ?? t('reachout.status.success', 'Thanks. Your message was sent.')

  useEffect(() => {
    if (!open) return
    setError(null)
    setSuccess(false)
    setMessage('')
    // Focus trap minimal: focus the dialog container so Escape works consistently.
    setTimeout(() => modalRef.current?.focus(), 0)
  }, [open])

  const handleSubmit = async () => {
    const trimmed = message.trim()
    if (!trimmed) {
      setError(t('reachout.errors.required', 'Message is required.'))
      return
    }

    setSubmitting(true)
    setError(null)

    try {
      const res = await fetch(`${API_BASE}/reachout`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({ message: trimmed }),
      })

      if (res.status === 429) {
        setError(t('reachout.errors.rateLimited', 'Too many messages. Please try again later.'))
        return
      }
      if (res.status === 404) {
        setError(t('reachout.errors.unavailable', 'Reachout is unavailable.'))
        return
      }
      if (res.status === 503) {
        setError(t('reachout.errors.notConfigured', 'This feature is not configured.'))
        return
      }
      if (!res.ok) {
        setError(t('reachout.errors.failed', 'Failed to send message. Please try again.'))
        return
      }

      setSuccess(true)
    } catch (e) {
      setError(t('reachout.errors.failed', 'Failed to send message. Please try again.'))
    } finally {
      setSubmitting(false)
    }
  }

  if (!open) return null

  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
      onClick={(e) => e.target === e.currentTarget && onClose()}
      role="dialog"
      aria-modal="true"
      aria-labelledby="reachout-modal-title"
    >
      <div
        ref={modalRef}
        tabIndex={-1}
        onKeyDown={(e) => e.key === 'Escape' && onClose()}
        className="bg-surface border border-border rounded-xl max-w-lg w-full shadow-xl overflow-hidden"
      >
        <div className="flex items-start justify-between gap-4 p-4 border-b border-border">
          <div>
            <h3 id="reachout-modal-title" className="font-semibold text-text">{title}</h3>
            <p className="text-xs text-text-muted mt-1">{description}</p>
          </div>
          <IconButton
            onClick={onClose}
            label={t('common.close', 'Close')}
            variant="ghost"
            size="sm"
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </IconButton>
        </div>

        <div className="p-4">
          {success ? (
            <Callout label={t('reachout.status.successLabel', 'Reachout success')} tone="success">
              {successMessage}
            </Callout>
          ) : (
            <>
              <Textarea
                id="reachout-message"
                label={t('reachout.form.messageLabel', 'Message')}
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                placeholder={t('reachout.form.placeholder', 'Write your message...')}
                rows={6}
              />
              {error && (
                <Callout
                  label={t('reachout.errors.formErrorLabel', 'Reachout form error')}
                  tone="error"
                  className="mt-3"
                >
                  {error}
                </Callout>
              )}
            </>
          )}
        </div>

        <div className="flex items-center justify-end gap-2 p-4 border-t border-border bg-surface-overlay">
          {!success && (
            <Button
              type="button"
              onClick={onClose}
              variant="ghost"
              disabled={submitting}
            >
              {t('common.cancel', 'Cancel')}
            </Button>
          )}
          {!success && (
            <Button
              type="button"
              onClick={handleSubmit}
              disabled={submitting}
            >
              {submitting ? t('common.sending', 'Sending...') : sendLabel}
            </Button>
          )}
          {success && (
            <Button
              type="button"
              onClick={onClose}
            >
              {t('common.close', 'Close')}
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}
