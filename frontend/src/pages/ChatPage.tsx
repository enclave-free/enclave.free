import { useState, useCallback, useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { AlertCircle, Database, Mail, Plus, Search, Settings2, X } from 'lucide-react'
import { ChatContainer } from '../components/chat/ChatContainer'
import { MessageList } from '../components/chat/MessageList'
import { ChatInput } from '../components/chat/ChatInput'
import { ToolSelector, Tool } from '../components/chat/ToolSelector'
import { DocumentScope, DocumentSource } from '../components/chat/DocumentScope'
import { ExportButton } from '../components/chat/ExportButton'
import { AppHeader } from '../components/shared/AppHeader'
import { Message } from '../components/chat/ChatMessage'
import { ReachoutModal, type ReachoutMode } from '../components/reachout/ReachoutModal'
import { API_BASE, STORAGE_KEYS, getSelectedUserTypeId, saveSelectedUserTypeId } from '../types/onboarding'
import { adminFetch, isAdminAuthenticated } from '../utils/adminApi'
import { sendLlmChatStreamWithUnifiedTools, sendLlmChatWithUnifiedTools, sendQueryStream } from '../utils/llmChat'
import { Button, Callout, IconButton } from '../components/ui'
import {
  extractAdminAssistantChangeSetStrict,
  type AdminAssistantChangeSet,
} from '../utils/adminAssistant'

type AdminApplyState =
  | { state: 'idle' }
  | { state: 'review'; changeSet: AdminAssistantChangeSet }
  | { state: 'applying'; changeSet: AdminAssistantChangeSet }
  | { state: 'applied'; message: string }
  | { state: 'error'; message: string }

const CONFIG_TOOL_ID = 'admin-config'
export const ENCLAVE_USER_EMAIL_KEY = STORAGE_KEYS.USER_EMAIL

function slugify(value: string): string {
  return String(value || '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
}

async function readErrorDetail(res: Response): Promise<string> {
  let detail = `HTTP ${res.status}`
  try {
    const payload = await res.json()
    if (payload?.detail !== undefined) {
      detail = typeof payload.detail === 'string'
        ? payload.detail
        : JSON.stringify(payload.detail)
    }
  } catch {
    // ignore
  }
  return detail
}

export function ChatPage() {
  const navigate = useNavigate()
  const { t } = useTranslation()
  const isAdmin = isAdminAuthenticated()
  const [messages, setMessages] = useState<Message[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selectedTools, setSelectedTools] = useState<string[]>([])
  const [selectedDocuments, setSelectedDocuments] = useState<string[]>([])
  const [conversationSessionId, setConversationSessionId] = useState<string | null>(null)
  const [documents, setDocuments] = useState<DocumentSource[]>([])
  const [sessionDefaultsLoaded, setSessionDefaultsLoaded] = useState(false)
  const [pendingDefaultDocs, setPendingDefaultDocs] = useState<string[]>([])
  const [adminApplyState, setAdminApplyState] = useState<AdminApplyState>({ state: 'idle' })
  const [deploymentSecretKeys, setDeploymentSecretKeys] = useState<Set<string>>(new Set())
  const [deploymentSecretKeysLoaded, setDeploymentSecretKeysLoaded] = useState(false)

  const [reachoutOpen, setReachoutOpen] = useState(false)
  const [reachoutEnabled, setReachoutEnabled] = useState(false)
  const [reachoutMode, setReachoutMode] = useState<ReachoutMode>('support')
  const [reachoutOverrides, setReachoutOverrides] = useState<{
    title?: string
    description?: string
    buttonLabel?: string
    successMessage?: string
  }>({})

  useEffect(() => {
    if (!isAdmin) return

    let cancelled = false
    async function fetchDeploymentSecretKeys() {
      setDeploymentSecretKeys(new Set())
      setDeploymentSecretKeysLoaded(false)
      try {
        const res = await adminFetch('/admin/deployment/config')
        if (!res.ok) return
        const payload = await res.json()
        const secretKeys = new Set<string>()
        for (const value of Object.values(payload || {})) {
          if (!Array.isArray(value)) continue
          for (const item of value) {
            const configItem = item as { is_secret?: boolean; key?: unknown }
            if (configItem.is_secret && typeof configItem.key === 'string') secretKeys.add(configItem.key)
          }
        }
        if (!cancelled) {
          setDeploymentSecretKeys(secretKeys)
          setDeploymentSecretKeysLoaded(true)
        }
      } catch {
        // Keep pessimistic masking when metadata is unavailable.
      }
    }

    fetchDeploymentSecretKeys()
    return () => {
      cancelled = true
    }
  }, [isAdmin])

  // Build available tools list - db-query only visible to admins
  const availableTools = useMemo<Tool[]>(() => {
    const tools: Tool[] = [
      {
        id: 'web-search',
        name: t('chat.tools.webSearchName'),
        description: t('chat.tools.webSearch'),
        icon: <Search className="h-3.5 w-3.5" aria-hidden="true" />,
      },
    ]

    // Only show Database tool to authenticated admins
    if (isAdmin) {
      tools.push({
        id: CONFIG_TOOL_ID,
        name: t('chat.tools.configName', 'Config'),
        description: t('chat.tools.config', 'Read and update admin configuration'),
        icon: <Settings2 className="h-3.5 w-3.5" aria-hidden="true" />,
      })
      tools.push({
        id: 'db-query',
        name: t('chat.tools.databaseName'),
        description: t('chat.tools.database'),
        icon: <Database className="h-3.5 w-3.5" aria-hidden="true" />,
      })
    }

    return tools
  }, [isAdmin, t])

  const fetchJson = useCallback(async <T,>(endpoint: string, options?: RequestInit): Promise<T> => {
    const res = await adminFetch(endpoint, options)
    if (!res.ok) {
      throw new Error(await readErrorDetail(res))
    }
    return res.json() as Promise<T>
  }, [])

  // Reachout settings (public)
  useEffect(() => {
    let isCancelled = false

    async function fetchReachout() {
      try {
        const res = await fetch(`${API_BASE}/settings/public`)
        if (!res.ok) return
        const data = await res.json()
        const s = (data?.settings ?? {}) as Record<string, string>

        if (isCancelled) return

        setReachoutEnabled(String(s.reachout_enabled ?? 'false').toLowerCase() === 'true')
        const mode = String(s.reachout_mode ?? 'support').toLowerCase()
        if (mode === 'feedback' || mode === 'help' || mode === 'support') {
          setReachoutMode(mode)
        } else {
          setReachoutMode('support')
        }

        setReachoutOverrides({
          title: typeof s.reachout_title === 'string' ? s.reachout_title : undefined,
          description: typeof s.reachout_description === 'string' ? s.reachout_description : undefined,
          buttonLabel: typeof s.reachout_button_label === 'string' ? s.reachout_button_label : undefined,
          successMessage: typeof s.reachout_success_message === 'string' ? s.reachout_success_message : undefined,
        })
      } catch {
        // Best-effort: feature remains hidden if fetch fails.
      }
    }

    fetchReachout()

    return () => {
      isCancelled = true
    }
  }, [])

  // Check auth and approval status on mount
  useEffect(() => {
    let isCancelled = false
    const userEmail = localStorage.getItem(STORAGE_KEYS.USER_EMAIL)

    // Not authenticated at all - redirect to login
    if (!isAdmin && !userEmail) {
      navigate('/login')
      return
    }

    // User authenticated but not approved - redirect to pending
    const approved = localStorage.getItem(STORAGE_KEYS.USER_APPROVED)
    if (!isAdmin && approved === 'false') {
      navigate('/pending')
      return
    }

    // Keep onboarding enforcement server-authoritative for returning users.
    if (!isAdmin) {
      const checkOnboardingStatus = async () => {
        try {
          const response = await fetch(`${API_BASE}/users/me/onboarding-status`, {
            credentials: 'include',
          })

          if (isCancelled) return

          if (response.status === 401) {
            navigate('/login')
            return
          }

          if (!response.ok) {
            return
          }

          const status = await response.json()

          if (isCancelled) return

          const effectiveTypeId = status.effective_user_type_id ?? null
          saveSelectedUserTypeId(effectiveTypeId)

          if (status.needs_user_type) {
            navigate('/user-type')
            return
          }

          if (status.needs_onboarding) {
            navigate('/profile')
          }
        } catch (err) {
          console.error('Failed to fetch onboarding status:', err)
        }
      }

      checkOnboardingStatus()
    }

    return () => {
      isCancelled = true
    }
  }, [isAdmin, navigate])

  // Fetch session defaults from admin config
  useEffect(() => {
    if (sessionDefaultsLoaded) return

    const fetchSessionDefaults = async () => {
      try {
        const userTypeId = getSelectedUserTypeId()
        const url = userTypeId !== null
          ? `${API_BASE}/session-defaults?user_type_id=${userTypeId}`
          : `${API_BASE}/session-defaults`
        const res = await fetch(url)
        if (res.ok) {
          const data = await res.json()
          // Apply web search default
          if (data.web_search_enabled) {
            setSelectedTools(['web-search'])
          } else {
            setSelectedTools([])
          }
          // Store default document IDs to apply once documents are loaded
          if (data.default_document_ids && data.default_document_ids.length > 0) {
            setPendingDefaultDocs(data.default_document_ids)
          }
        } else {
          // Non-2xx response - fall back to web search enabled by default
          console.warn('Failed to fetch session defaults:', res.status)
          setSelectedTools(['web-search'])
        }
      } catch (err) {
        console.error('Failed to fetch session defaults:', err)
        // Fall back to web search enabled by default on error
        setSelectedTools(['web-search'])
      } finally {
        setSessionDefaultsLoaded(true)
      }
    }

    fetchSessionDefaults()
  }, [sessionDefaultsLoaded])

  // Fetch available documents from ingest jobs
  useEffect(() => {
    const fetchDocuments = async () => {
      try {
        const res = await fetch(`${API_BASE}/ingest/jobs`, {
          credentials: 'include',
        })
        if (res.ok) {
          const data = await res.json()
          const docs: DocumentSource[] = (data.jobs || [])
            .filter((job: { status: string }) => job.status === 'completed' || job.status === 'completed_with_errors')
            .map((job: { job_id: string; filename: string; total_chunks: number }) => ({
              id: job.job_id,
              name: job.filename.replace(/\.(pdf|txt|md)$/i, ''),
              description: `${job.total_chunks} chunks`,
              tags: [job.filename.split('.').pop()?.toUpperCase() || 'DOC']
            }))
          setDocuments(docs)
        }
      } catch (e) {
        console.error(t('errors.failedToFetchDocuments'), e)
      }
    }
    fetchDocuments()
  }, [])

  // Apply pending default documents once documents are loaded
  useEffect(() => {
    if (pendingDefaultDocs.length > 0 && documents.length > 0) {
      // Filter to only include IDs that exist in the documents list
      const validIds = pendingDefaultDocs.filter(id => documents.some(d => d.id === id))
      if (validIds.length > 0) {
        setSelectedDocuments(validIds)
      }
      setPendingDefaultDocs([])
    }
  }, [pendingDefaultDocs, documents])

  const handleToolToggle = useCallback((toolId: string) => {
    if (toolId === 'db-query' && !selectedTools.includes('db-query') && selectedDocuments.length > 0) {
      // db-query runs against /llm/chat only; clear RAG document selection
      setSelectedDocuments([])
    }
    if (toolId === CONFIG_TOOL_ID && selectedTools.includes(CONFIG_TOOL_ID)) {
      setAdminApplyState({ state: 'idle' })
    }
    setSelectedTools((prev) =>
      prev.includes(toolId) ? prev.filter((id) => id !== toolId) : [...prev, toolId]
    )
  }, [selectedDocuments.length, selectedTools])

  const handleDocumentToggle = useCallback((docId: string) => {
    setSelectedDocuments((prev) =>
      prev.includes(docId) ? prev.filter((id) => id !== docId) : [...prev, docId]
    )
  }, [])

  const generateMessageId = () => `msg-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`

  const updateAssistantMessage = (id: string, patch: Partial<Message>) => {
    setMessages((prev) => prev.map((message) => (
      message.id === id ? { ...message, ...patch } : message
    )))
  }

  const handleSend = async (content: string) => {
    const userMessage: Message = {
      id: generateMessageId(),
      role: 'user',
      content,
      timestamp: new Date(),
    }

    setMessages((prev) => [...prev, userMessage])
    setIsLoading(true)
    setError(null)
    if (adminApplyState.state === 'error' || adminApplyState.state === 'applied') {
      setAdminApplyState({ state: 'idle' })
    }

    try {
      const hasConfigTool = isAdmin && selectedTools.includes(CONFIG_TOOL_ID)
      const backendTools = selectedTools
      const wantsDbQuery = selectedTools.includes('db-query')
      const useRag = !isAdmin && selectedDocuments.length > 0 && !wantsDbQuery

      let response: Response
      if (useRag) {
        const body = {
          question: content,
          top_k: 8,
          tools: backendTools,
          job_ids: selectedDocuments,
          ...(conversationSessionId && { session_id: conversationSessionId }),
        }

        let streamed = false
        let streamMessageId: string | null = null
        let streamContent = ''
        let streamSessionId: string | null = null
        let streamSearchTerm: string | null = null
        try {
          await sendQueryStream({
            question: content,
            tools: backendTools,
            jobIds: selectedDocuments,
            sessionId: conversationSessionId,
            onEvent: (event, payload) => {
              const data = payload as Record<string, unknown>
              if (event === 'assistant_message_started') {
                const id = typeof data.message_id === 'string' ? data.message_id : generateMessageId()
                streamMessageId = id
                if (typeof data.session_id === 'string') streamSessionId = data.session_id
                setMessages((prev) => [...prev, {
                  id,
                  role: 'assistant',
                  content: '',
                  timestamp: new Date(),
                  traceStatus: t('chat.trace.writing', 'Writing answer...'),
                }])
              } else if (event === 'trace_status' && streamMessageId) {
                const status = typeof data.status === 'string' ? data.status : t('chat.trace.writing', 'Writing answer...')
                updateAssistantMessage(streamMessageId, { traceStatus: status })
              } else if (event === 'answer_delta' && streamMessageId) {
                const delta = typeof data.delta === 'string' ? data.delta : ''
                streamContent += delta
                updateAssistantMessage(streamMessageId, {
                  content: streamContent,
                })
              } else if (event === 'trace_final' && streamMessageId) {
                updateAssistantMessage(streamMessageId, {
                  trace: data.trace as Message['trace'],
                  traceStatus: null,
                })
              } else if (event === 'done') {
                if (typeof data.session_id === 'string') streamSessionId = data.session_id
                if (typeof data.search_term === 'string') streamSearchTerm = data.search_term
              } else if (event === 'error') {
                throw new Error(typeof data.detail === 'string' ? data.detail : t('errors.failedToSendMessage'))
              }
            },
          })
          if (streamSessionId) setConversationSessionId(streamSessionId)
          if (streamMessageId) {
            updateAssistantMessage(streamMessageId, { traceStatus: null })
          }
          setAdminApplyState({ state: 'idle' })
          if (streamSearchTerm) {
            await triggerAutoSearch(streamSearchTerm, streamSessionId ?? conversationSessionId)
          }
          streamed = true
        } catch (streamError) {
          if (streamMessageId) {
            setMessages((prev) => prev.filter((message) => message.id !== streamMessageId))
          }
          console.warn('Streaming query failed; falling back to non-streaming query:', streamError)
        }
        if (streamed) return

        response = await fetch(`${API_BASE}/query`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          credentials: 'include',
          body: JSON.stringify(body),
        })
      } else {
        let streamed = false
        let streamMessageId: string | null = null
        let streamContent = ''
        let streamSessionId: string | null = null
        try {
          await sendLlmChatStreamWithUnifiedTools({
            content,
            tools: backendTools,
            t,
            sessionId: conversationSessionId,
            onEvent: (event, payload) => {
              const data = payload as Record<string, unknown>
              if (event === 'assistant_message_started') {
                const id = typeof data.message_id === 'string' ? data.message_id : generateMessageId()
                streamMessageId = id
                if (typeof data.session_id === 'string') streamSessionId = data.session_id
                setMessages((prev) => [...prev, {
                  id,
                  role: 'assistant',
                  content: '',
                  timestamp: new Date(),
                  traceStatus: t('chat.trace.writing', 'Writing answer...'),
                }])
              } else if (event === 'trace_status' && streamMessageId) {
                const status = typeof data.status === 'string' ? data.status : t('chat.trace.writing', 'Writing answer...')
                updateAssistantMessage(streamMessageId, { traceStatus: status })
              } else if (event === 'answer_delta' && streamMessageId) {
                const delta = typeof data.delta === 'string' ? data.delta : ''
                streamContent += delta
                updateAssistantMessage(streamMessageId, {
                  content: streamContent,
                })
              } else if (event === 'trace_final' && streamMessageId) {
                updateAssistantMessage(streamMessageId, {
                  trace: data.trace as Message['trace'],
                  traceStatus: null,
                })
              } else if (event === 'done') {
                if (typeof data.session_id === 'string') streamSessionId = data.session_id
              } else if (event === 'error') {
                throw new Error(typeof data.detail === 'string' ? data.detail : t('errors.failedToSendMessage'))
              }
            },
          })
          if (streamSessionId) setConversationSessionId(streamSessionId)
          if (hasConfigTool) {
            const extracted = extractAdminAssistantChangeSetStrict(streamContent)
            if (extracted.ok) {
              setAdminApplyState({ state: 'review', changeSet: extracted.changeSet })
            } else if (streamContent.includes('```json') && streamContent.includes('"requests"')) {
              setAdminApplyState({ state: 'error', message: extracted.error })
            }
          } else {
            setAdminApplyState({ state: 'idle' })
          }
          streamed = true
        } catch (streamError) {
          if (streamMessageId) {
            setMessages((prev) => prev.filter((message) => message.id !== streamMessageId))
          }
          console.warn('Streaming chat failed; falling back to non-streaming chat:', streamError)
        }
        if (streamed) return

        response = await sendLlmChatWithUnifiedTools({
          content,
          tools: backendTools,
          t,
          sessionId: conversationSessionId,
        })
      }

      const responseIsRag = useRag

      // Handle auth errors
      if (response.status === 401) {
        // Token invalid/expired
        navigate(isAdmin ? '/admin' : '/login')
        return
      }
      if (response.status === 403) {
        // Not approved - update localStorage and redirect
        localStorage.setItem(STORAGE_KEYS.USER_APPROVED, 'false')
        navigate('/pending')
        return
      }

      if (!response.ok) throw new Error(`HTTP ${response.status}`)

      const data = await response.json()

      let responseContent: string
      if (responseIsRag) {
        responseContent = data.answer
        
        // Save session_id for conversation continuity
        if (data.session_id) {
          setConversationSessionId(data.session_id)
        }
      } else {
        responseContent = data.message
        if (data.session_id) {
          setConversationSessionId(data.session_id)
        }

        if (hasConfigTool) {
          const raw = String(data.message || '')
          const extracted = extractAdminAssistantChangeSetStrict(raw)
          if (extracted.ok) {
            setAdminApplyState({ state: 'review', changeSet: extracted.changeSet })
          } else if (raw.includes('```json') && raw.includes('"requests"')) {
            setAdminApplyState({ state: 'error', message: extracted.error })
          }
        } else {
          setAdminApplyState({ state: 'idle' })
        }
      }

      const assistantMessage: Message = {
        id: typeof data.message_id === 'string' ? data.message_id : generateMessageId(),
        role: 'assistant',
        content: responseContent,
        timestamp: new Date(),
        trace: data.trace ?? null,
      }

      setMessages((prev) => [...prev, assistantMessage])
      
      // Handle auto-search if backend returned a search term
      if (responseIsRag && data.search_term) {
        await triggerAutoSearch(data.search_term, data.session_id ?? conversationSessionId)
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : t('errors.failedToSendMessage'))
    } finally {
      setIsLoading(false)
    }
  }

  const handleAdminApply = useCallback(async (changeSet: AdminAssistantChangeSet) => {
    setAdminApplyState({ state: 'applying', changeSet })
    try {
      const userTypeSlugToId = new Map<string, number>()
      try {
        const existing = await fetchJson<{ types: Array<{ id: number; name: string }> }>('/admin/user-types')
        for (const ut of existing.types || []) {
          userTypeSlugToId.set(slugify(ut.name), ut.id)
        }
      } catch {
        // Best-effort; we'll still learn mappings from POST responses below.
      }

      const resolveUserTypeId = (raw: unknown): number | unknown => {
        if (typeof raw !== 'string') return raw
        if (!raw.startsWith('@type:')) return raw
        const slug = raw.slice('@type:'.length)
        const id = userTypeSlugToId.get(slug)
        if (id === undefined) throw new Error(`Unknown user type placeholder: ${raw}`)
        return id
      }

      const rewritePath = (path: string): string => {
        const parts = path.split('/')
        const idx = parts.findIndex((p) => p === 'user-type')
        if (idx !== -1 && parts[idx + 1]?.startsWith('@type:')) {
          const seg = parts[idx + 1]
          const id = resolveUserTypeId(seg)
          if (typeof id === 'number') parts[idx + 1] = String(id)
        }
        const idx2 = parts.findIndex((p) => p === 'defaults')
        if (idx2 !== -1 && parts[idx2 + 1] === 'user-type' && parts[idx2 + 2]?.startsWith('@type:')) {
          const seg = parts[idx2 + 2]
          const id = resolveUserTypeId(seg)
          if (typeof id === 'number') parts[idx2 + 2] = String(id)
        }
        return parts.join('/')
      }

      const results: Array<{ ok: boolean; method: string; path: string; status?: number; error?: string }> = []
      for (const req of changeSet.requests) {
        try {
          const resolvedPath = rewritePath(req.path)
          let resolvedBody: unknown = req.body
          if (resolvedBody && typeof resolvedBody === 'object' && !Array.isArray(resolvedBody)) {
            const b = resolvedBody as Record<string, unknown>
            if ('user_type_id' in b) {
              const resolved = resolveUserTypeId(b.user_type_id)
              resolvedBody = { ...b, user_type_id: resolved }
            }
          }

          const res = await adminFetch(resolvedPath, {
            method: req.method,
            body: resolvedBody ? JSON.stringify(resolvedBody) : undefined,
          })
          if (!res.ok) {
            const detail = await readErrorDetail(res)
            results.push({ ok: false, method: req.method, path: resolvedPath, status: res.status, error: detail })
            continue
          }

          if (req.method === 'POST' && req.path === '/admin/user-types') {
            try {
              const payload = await res.json() as { id?: number; name?: string }
              if (typeof payload?.id === 'number' && typeof payload?.name === 'string') {
                userTypeSlugToId.set(slugify(payload.name), payload.id)
              }
            } catch {
              // ignore
            }
          }

          results.push({ ok: true, method: req.method, path: resolvedPath, status: res.status })
        } catch (err) {
          results.push({ ok: false, method: req.method, path: req.path, error: err instanceof Error ? err.message : String(err) })
        }
      }

      const okCount = results.filter((r) => r.ok).length
      const failCount = results.length - okCount
      const baseSummary = failCount
        ? t('admin.configAssistant.applySummary.appliedCountsWithFailures', { ok: okCount, total: results.length, failed: failCount })
        : t('admin.configAssistant.applySummary.appliedCounts', { ok: okCount, total: results.length })

      const failedDetails = results
        .filter((r) => !r.ok)
        .map((r) => `${r.method} ${r.path}: ${r.error || `HTTP ${r.status}`}`)
      const failureSummary = failedDetails.length
        ? '\n' + failedDetails.join('\n')
        : ''

      const postApplyNotes: string[] = []
      try {
        const validationRes = await adminFetch('/admin/deployment/config/validate', { method: 'POST' })
        if (validationRes.ok) {
          const v = await validationRes.json() as { valid: boolean; errors?: string[]; warnings?: string[] }
          if (v.valid) {
            const warnings = (v.warnings || []).filter(Boolean)
            postApplyNotes.push(
              warnings.length
                ? t('admin.configAssistant.applySummary.configValidationValidWarnings', { count: warnings.length })
                : t('admin.configAssistant.applySummary.configValidationValid')
            )
          } else {
            const errors = (v.errors || []).filter(Boolean)
            postApplyNotes.push(t('admin.configAssistant.applySummary.configValidationInvalidErrors', { count: errors.length }))
          }
        } else {
          postApplyNotes.push(t('admin.configAssistant.applySummary.configValidationFailedHttp', { status: validationRes.status }))
        }
      } catch {
        postApplyNotes.push(t('admin.configAssistant.applySummary.configValidationFailedNetwork'))
      }

      try {
        const rr = await adminFetch('/admin/deployment/restart-required')
        if (rr.ok) {
          const data = await rr.json() as { restart_required: boolean; changed_keys?: Array<{ key: string }> }
          const keys = (data.changed_keys || []).map((k) => k.key).filter(Boolean)
          if (data.restart_required && keys.length) {
            postApplyNotes.push(t('admin.configAssistant.applySummary.restartRequiredFor', { keys: keys.join(', ') }))
          } else {
            postApplyNotes.push(t('admin.configAssistant.applySummary.restartRequiredNo'))
          }
        } else {
          postApplyNotes.push(t('admin.configAssistant.applySummary.restartCheckFailedHttp', { status: rr.status }))
        }
      } catch {
        postApplyNotes.push(t('admin.configAssistant.applySummary.restartCheckFailedNetwork'))
      }

      const needsPageRefresh = results.some((r) => r.ok && r.path === '/admin/settings')
      if (needsPageRefresh) {
        postApplyNotes.push(t('admin.configAssistant.applySummary.pageRefreshRecommended'))
      }

      const summary = [baseSummary, ...postApplyNotes].join(' ') + failureSummary
      setAdminApplyState({ state: 'applied', message: summary })

      setMessages((prev) => ([
        ...prev,
        {
          id: generateMessageId(),
          role: 'assistant',
          content: summary,
          timestamp: new Date(),
        },
      ]))
    } catch (e) {
      setAdminApplyState({ state: 'error', message: e instanceof Error ? e.message : String(e) })
    }
  }, [fetchJson, t])

  const adminApplyPreview = useMemo(() => {
    if (adminApplyState.state !== 'review' && adminApplyState.state !== 'applying') return null
    const changeSet = adminApplyState.changeSet

    const pretty = changeSet.requests.map((r, idx) => {
      let bodyDisplay: unknown = r.body
      if (r.method === 'PUT' && r.path.startsWith('/admin/deployment/config/')) {
        const key = r.path.split('/').pop() || ''
        const shouldRedact = !deploymentSecretKeysLoaded || deploymentSecretKeys.has(key)
        if (shouldRedact && r.body && typeof r.body === 'object') {
          const o = r.body as Record<string, unknown>
          if (typeof o.value === 'string' && o.value.length > 0) {
            bodyDisplay = { ...o, value: '[REDACTED]' }
          }
        }
      }
      return {
        idx: idx + 1,
        method: r.method,
        path: r.path,
        body: bodyDisplay,
      }
    })

    return {
      summary: changeSet.summary || '',
      requests: pretty,
    }
  }, [adminApplyState, deploymentSecretKeys, deploymentSecretKeysLoaded])
  
  // Auto-search triggered by backend - injects results back into RAG session
  const triggerAutoSearch = async (searchTerm: string, sessionId?: string | null) => {
    try {
      // Show searching indicator
      const searchingMessage: Message = {
        id: generateMessageId(),
        role: 'assistant',
        content: t('chat.messages.searching', { term: searchTerm }),
        timestamp: new Date(),
      }
      setMessages((prev) => [...prev, searchingMessage])
      
      // Build context-aware search prompt with condensing instructions
      const searchPrompt = `Search for: ${searchTerm}

IMPORTANT: Return a CONDENSED response:
- A brief table (3-5 rows max) with Name, Contact, and Notes columns
- 2-3 sentences of practical advice
- NO lengthy explanations or backgrounds
- Focus on actionable contacts and next steps`
      
      // Call the same shared chat path used by the main chat send flow.
      const searchRes = await sendLlmChatWithUnifiedTools({
        content: searchPrompt,
        tools: ['web-search'],
        t,
        sessionId,
      })
      
      if (!searchRes.ok) {
        throw new Error(t('errors.searchFailed', { status: searchRes.status }))
      }
      
      const searchData = await searchRes.json()
      if (searchData.session_id) {
        setConversationSessionId(searchData.session_id)
      }
      const searchResults = searchData.message
      
      // Replace searching message with condensed results
      const searchResultMessage: Message = {
        id: generateMessageId(),
        role: 'assistant',
        content: `${t('chat.messages.searchResults', { term: searchTerm })}\n\n${searchResults}`,
        timestamp: new Date(),
      }
      
      // Remove the "Searching..." message and add results
      const searchingPrefix = `🔍 ${t('chat.messages.searchingPrefix')}`
      setMessages((prev) => {
        const withoutSearching = prev.filter(m => !m.content.startsWith(searchingPrefix))
        return [...withoutSearching, searchResultMessage]
      })
      
      // Inject search results back into RAG session for context continuity
      const injectionSessionId = searchData.session_id ?? sessionId
      if (injectionSessionId && selectedDocuments.length > 0) {
        // Send a silent update to the RAG session with search results
        await fetch(`${API_BASE}/query`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          credentials: 'include',
          body: JSON.stringify({
            question: `[SYSTEM: Search results for "${searchTerm}" have been provided to the user. The results included: ${searchResults.slice(0, 500)}...]`,
            session_id: injectionSessionId,
            top_k: 1,  // Minimal retrieval since this is just context injection
            tools: []  // No tools for this update
          }),
        }).catch(() => {
          // Silent failure - session update is best-effort
        })
      }
    } catch (e) {
      console.error('Auto-search failed:', e)
      // Remove searching message on error
      const searchingPrefix = `🔍 ${t('chat.messages.searchingPrefix')}`
      setMessages((prev) => prev.filter(m => !m.content.startsWith(searchingPrefix)))
    }
  }

  const handleNewChat = () => {
    setMessages([])
    setError(null)
    setConversationSessionId(null) // Reset session for new conversation
    setAdminApplyState({ state: 'idle' })
  }

  const rightActions = (
    <>
      {reachoutEnabled && (
        <IconButton
          label={t(
            `reachout.mode.${reachoutMode}.openButton`,
            reachoutMode === 'feedback' ? 'Send feedback' : reachoutMode === 'help' ? 'Get help' : 'Contact support'
          )}
          onClick={() => setReachoutOpen(true)}
          title={t(
            `reachout.mode.${reachoutMode}.openButton`,
            reachoutMode === 'feedback' ? 'Send feedback' : reachoutMode === 'help' ? 'Get help' : 'Contact support'
          )}
        >
          <Mail className="h-4 w-4" aria-hidden="true" />
        </IconButton>
      )}
      <IconButton
        label={t('chat.messages.newConversation')}
        onClick={handleNewChat}
        title={t('chat.messages.newConversation')}
      >
        <Plus className="h-4 w-4" aria-hidden="true" />
      </IconButton>
      <ExportButton messages={messages} iconOnly />
    </>
  )

  const header = <AppHeader rightActions={rightActions} />

  // Admin chat intentionally excludes DocumentScope: admin workflows use CONFIG_TOOL_ID
  // and /admin configuration paths, and RAG is intentionally disabled for admins
  // (see useRag = !isAdmin && selectedDocuments.length > 0 && !wantsDbQuery).
  const inputToolbar = isAdmin
    ? <ToolSelector tools={availableTools} selectedTools={selectedTools} onToggle={handleToolToggle} />
    : (
      <>
        <ToolSelector tools={availableTools} selectedTools={selectedTools} onToggle={handleToolToggle} />
        <div className="w-px h-4 bg-border mx-1" />
        <DocumentScope selectedDocuments={selectedDocuments} onToggle={handleDocumentToggle} documents={documents} />
      </>
    )

  return (
    <ChatContainer header={header}>
      <ReachoutModal
        open={reachoutOpen}
        mode={reachoutMode}
        overrides={reachoutOverrides}
        onClose={() => setReachoutOpen(false)}
      />

      <MessageList
        messages={messages}
        isLoading={isLoading}
      />

      {error && (
        <div className="px-3 sm:px-4 pb-2">
          <div className="max-w-3xl mx-auto">
            <Callout
              label={t('chat.errors.requestLabel', 'Chat request error')}
              tone="error"
              className="flex items-center gap-3 animate-fade-in shadow-sm"
            >
              <AlertCircle className="h-4 w-4 text-error shrink-0" aria-hidden="true" />
              <span className="flex-1">{error}</span>
              <IconButton
                label={t('common.close', 'Close')}
                onClick={() => setError(null)}
                variant="ghost"
                size="sm"
                className="text-error hover:bg-error/10"
              >
                <X className="h-4 w-4" aria-hidden="true" />
              </IconButton>
            </Callout>
          </div>
        </div>
      )}

      {isAdmin && selectedTools.includes(CONFIG_TOOL_ID) && adminApplyState.state === 'error' && (
        <div className="px-3 sm:px-4 pb-2">
          <div className="max-w-3xl mx-auto">
            <Callout label={t('admin.configAssistant.applyErrorLabel', 'Config apply error')} tone="error">
              {adminApplyState.message}
            </Callout>
          </div>
        </div>
      )}

      {isAdmin && selectedTools.includes(CONFIG_TOOL_ID) && adminApplyState.state === 'review' && adminApplyPreview && (
        <div className="px-3 sm:px-4 pb-2">
          <div className="max-w-3xl mx-auto border border-warning/35 rounded-2xl bg-surface-raised overflow-hidden shadow-md">
            <div className="px-4 py-3 border-b border-border flex items-center justify-between gap-3">
              <div className="text-sm font-medium text-text truncate">
                {adminApplyPreview.summary
                  ? t('admin.configAssistant.pendingChangesWithSummary', { summary: adminApplyPreview.summary })
                  : t('admin.configAssistant.pendingChanges')}
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <Button
                  onClick={() => setAdminApplyState({ state: 'idle' })}
                  variant="ghost"
                  size="sm"
                >
                  {t('admin.configAssistant.dismiss')}
                </Button>
                <Button
                  onClick={() => handleAdminApply(adminApplyState.changeSet)}
                  variant="primary"
                  size="sm"
                >
                  {t('admin.configAssistant.apply')}
                </Button>
              </div>
            </div>
            <div className="px-4 py-2 text-xs text-text-muted border-b border-border bg-warning-subtle/40">
              {t('admin.configAssistant.reviewMaskedSecrets')}
            </div>
            <div className="px-4 py-3 space-y-2 max-h-64 overflow-y-auto">
              {adminApplyPreview.requests.map((r) => (
                <div key={r.idx} className="rounded-xl border border-border bg-surface px-3 py-2">
                  <div className="text-xs font-mono text-text-secondary">{r.method} {r.path}</div>
                  {r.body !== undefined && (
                    <pre className="mt-2 text-xs overflow-x-auto text-text-muted">{JSON.stringify(r.body, null, 2)}</pre>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {isAdmin && selectedTools.includes(CONFIG_TOOL_ID) && adminApplyState.state === 'applying' && (
        <div className="px-3 sm:px-4 pb-2">
          <div className="max-w-3xl mx-auto text-sm text-text-muted border border-border rounded-xl px-4 py-3 bg-surface-raised">
            {t('admin.configAssistant.applyingAdminChanges')}
          </div>
        </div>
      )}

      <ChatInput
        onSend={handleSend}
        disabled={isLoading}
        placeholder={
          !isAdmin && selectedDocuments.length > 0
            ? t('chat.input.placeholderWithDocs')
            : t('chat.input.placeholder')
        }
        toolbar={inputToolbar}
      />
    </ChatContainer>
  )
}
