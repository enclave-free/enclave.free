import { useEffect, useRef, useState, type ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { MessageCircle, PanelRightClose } from 'lucide-react'
import { isAdminAuthenticated, validateAdminSession, type AdminSessionValidationState } from '../../utils/adminApi'
import { AdminConfigAssistant } from '../admin/AdminConfigAssistant'

interface AdminRouteProps {
  children: ReactNode
}

type GuardState = 'checking' | AdminSessionValidationState

/**
 * Route guard for admin pages.
 * - Redirects to /admin on missing/expired credentials (401)
 * - Shows a retry screen for backend/network errors (5xx/unreachable)
 */
export function AdminRoute({ children }: AdminRouteProps) {
  const { t } = useTranslation()
  const [state, setState] = useState<GuardState>('checking')
  const [retryNonce, setRetryNonce] = useState(0)
  const [assistantCollapsed, setAssistantCollapsed] = useState(false)
  const [mobileAssistantOpen, setMobileAssistantOpen] = useState(false)
  const mobileDialogRef = useRef<HTMLDivElement | null>(null)
  const previousFocusRef = useRef<HTMLElement | null>(null)

  useEffect(() => {
    let active = true

    const checkSession = async () => {
      if (!isAdminAuthenticated()) {
        if (active) setState('unauthenticated')
        return
      }

      try {
        const result = await validateAdminSession()
        if (active) setState(result)
      } catch (error) {
        // Defensive fallback: if validateAdminSession throws unexpectedly,
        // treat as unavailable (backend unreachable/error) rather than
        // leaving stuck in 'checking' state
        console.error('Unexpected error in admin session validation:', error)
        if (active) setState('unavailable')
      }
    }

    void checkSession()

    return () => {
      active = false
    }
  }, [retryNonce])

  useEffect(() => {
    if (!mobileAssistantOpen) return

    previousFocusRef.current = document.activeElement instanceof HTMLElement
      ? document.activeElement
      : null

    const focusDialog = window.setTimeout(() => {
      mobileDialogRef.current?.focus()
    }, 0)

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setMobileAssistantOpen(false)
        return
      }

      if (event.key !== 'Tab' || !mobileDialogRef.current) return

      const focusable = Array.from(
        mobileDialogRef.current.querySelectorAll<HTMLElement>(
          'button, [href], input, textarea, select, [tabindex]:not([tabindex="-1"])'
        )
      ).filter((element) => !element.hasAttribute('disabled') && !element.getAttribute('aria-hidden'))

      if (focusable.length === 0) {
        event.preventDefault()
        mobileDialogRef.current.focus()
        return
      }

      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }

    document.addEventListener('keydown', handleKeyDown)

    return () => {
      window.clearTimeout(focusDialog)
      document.removeEventListener('keydown', handleKeyDown)
      previousFocusRef.current?.focus()
      previousFocusRef.current = null
    }
  }, [mobileAssistantOpen])

  if (state === 'checking') {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-accent border-t-transparent rounded-full animate-spin" />
          <p className="text-text-muted text-sm">{t('adminRoute.extracted.verifying_admin_session_87c53b', 'Verifying admin session...')}</p>
        </div>
      </div>
    )
  }

  if (state === 'unauthenticated') {
    return <Navigate to="/admin" replace />
  }

  if (state === 'unavailable') {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center p-6">
        <div className="card max-w-md w-full space-y-4">
          <h1 className="text-lg font-semibold text-text">{t('adminRoute.extracted.unable_to_verify_admin_session_5f87b8', 'Unable to verify admin session')}</h1>
          <p className="text-sm text-text-muted">
            {t('adminRoute.extracted.the_backend_returned_an_error_while_validating_authentication_0a9a16', 'The backend returned an error while validating authentication. This is not treated as a logout.')}
          </p>
          <button
            onClick={() => {
              setState('checking')
              setRetryNonce((prev) => prev + 1)
            }}
            className="w-full bg-accent text-accent-text rounded-xl px-4 py-2.5 text-sm font-medium hover:bg-accent-hover transition-colors"
          >
            {t('common.retry', 'Retry')}
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-surface lg:h-screen lg:overflow-hidden">
      <div className="lg:hidden fixed top-1/2 right-0 -translate-y-1/2 z-50">
        <button
          onClick={() => setMobileAssistantOpen(true)}
          className="h-14 w-11 rounded-l-2xl bg-accent text-accent-text shadow-lg ring-1 ring-white/10 hover:bg-accent-hover hover:shadow-xl transition-all active:scale-95 flex items-center justify-center"
          aria-label={t('admin.configAssistant.openAria', 'Open admin assistant')}
          title={t('admin.configAssistant.openTitle', 'Admin assistant')}
        >
          <MessageCircle className="w-5 h-5" />
        </button>
      </div>

      <div className="lg:flex lg:h-full">
        <div className="min-w-0 flex-1 lg:h-full lg:overflow-y-auto">
          {children}
        </div>

        <aside
          className={`hidden lg:flex border-l border-border bg-surface-raised shrink-0 transition-[width] duration-200 ease-in-out right-0 overflow-hidden ${
            assistantCollapsed ? 'w-16' : 'w-96'
          }`}
          aria-label={t('admin.configAssistant.title', 'Admin Configuration Assistant')}
        >
          <div className={`${assistantCollapsed ? 'flex' : 'hidden'} w-16 shrink-0 justify-center`}>
            <button
              onClick={() => setAssistantCollapsed(false)}
              className="mt-4 flex h-11 w-11 cursor-pointer items-center justify-center rounded-xl bg-surface text-text-muted shadow-sm ring-1 ring-border/70 transition-[background-color,color,box-shadow,transform] duration-150 hover:bg-surface-overlay hover:text-accent hover:shadow-md active:scale-[0.96]"
              aria-label={t('admin.configAssistant.expandSidebar', 'Open admin assistant sidebar')}
              title={t('admin.configAssistant.expandSidebar', 'Open admin assistant sidebar')}
            >
              <MessageCircle className="w-5 h-5" />
            </button>
          </div>
          <div
            className={`${assistantCollapsed ? 'w-0 overflow-hidden' : 'w-96'} shrink-0 transition-[width] duration-200 ease-in-out`}
            aria-hidden={assistantCollapsed}
            hidden={assistantCollapsed}
          >
            <AdminConfigAssistant
              variant="sidebar"
              onCollapse={() => setAssistantCollapsed(true)}
              collapseIcon={<PanelRightClose className="w-4 h-4" />}
            />
          </div>
        </aside>
      </div>

      {mobileAssistantOpen && (
        <div
          className="lg:hidden fixed inset-0 z-50 flex justify-end bg-black/30"
          onClick={() => setMobileAssistantOpen(false)}
        >
          <div
            ref={mobileDialogRef}
            role="dialog"
            aria-modal="true"
            aria-label={t('admin.configAssistant.title', 'Admin Configuration Assistant')}
            tabIndex={-1}
            className="h-full outline-none"
            onClick={(event) => event.stopPropagation()}
          >
            <AdminConfigAssistant
              variant="drawer"
              onClose={() => setMobileAssistantOpen(false)}
            />
          </div>
        </div>
      )}
    </div>
  )
}
