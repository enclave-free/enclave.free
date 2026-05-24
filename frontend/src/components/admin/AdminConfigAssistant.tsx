import {
  type ReactNode,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { useTranslation } from 'react-i18next';
import {
  X,
  MessageCircle,
  RefreshCw,
  ShieldAlert,
  Play,
  EyeOff,
} from 'lucide-react';
import { adminFetch } from '../../utils/adminApi';
import { ChatInput } from '../chat/ChatInput';
import { ChatMessage, type Message } from '../chat/ChatMessage';
import { ToolSelector, type Tool } from '../chat/ToolSelector';
import {
  getConfigCategories,
  getDeploymentConfigItemMeta,
} from '../../types/config';
import { API_BASE } from '../../types/onboarding';
import {
  extractAdminAssistantChangeSetStrict,
  redactAdminDeploymentSecretChangeSets,
  redactSecrets,
  validateAdminAssistantChangeSet,
  type AdminAssistantChangeSet,
} from '../../utils/adminAssistant';
import {
  buildFullAdminConfigContext,
  buildScopedAdminConfigContext,
} from '../../utils/adminConfigContext';
import { fetchBoundedAdminDocumentContext } from '../../utils/adminDocumentContext';
import {
  planAdminPromptBudget,
  formatAdminReducedContextNotice,
} from '../../utils/promptBudget';
import { compactAdminSessionMemory } from '../../utils/sessionMemoryCompaction';
import {
  recordAdminContextPlanInstrumentation,
  recordProviderFailureInstrumentation,
} from '../../utils/adminResilienceInstrumentation';
import {
  sendLlmChatStreamWithUnifiedTools,
  sendLlmChatWithUnifiedTools,
} from '../../utils/llmChat';
import {
  classifyProviderError,
  formatClassifiedProviderError,
  shouldOfferNewAssistantConversation,
  type ClassifiedProviderError,
} from '../../utils/providerErrors';
import { resolveAdminApplyIntent } from '../../utils/adminApplyIntent';

type ApplyState =
  | { state: 'idle' }
  | { state: 'review'; changeSet: AdminAssistantChangeSet }
  | { state: 'applying'; changeSet: AdminAssistantChangeSet }
  | { state: 'applied'; message: string }
  | { state: 'error'; message: string };

interface AdminConfigAssistantProps {
  variant?: 'sidebar' | 'drawer';
  onCollapse?: () => void;
  onClose?: () => void;
  collapseIcon?: ReactNode;
}

const CONFIG_TOOL_ID = 'admin-config';

export const TRACE_POLICY_CONTEXT_LINES = [
  '- Trace Visibility Policy is an Agent Setting. Use PUT /admin/ai-config/admin_trace_visibility or PUT /admin/ai-config/user_trace_visibility.',
  '- Valid trace visibility values are off, minimal, summary, and detailed for Admin Conversations; User Conversations only allow off, minimal, or summary.',
  '- Raising User Conversation trace visibility is privacy-relevant. Explain that users will see more Conversation Trace metadata before proposing the change.',
];

function generateMessageId() {
  return `admin-msg-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

function patchAssistantMessage(
  messages: Message[],
  id: string,
  patch: Partial<Message>
): Message[] {
  return messages.map((message) =>
    message.id === id ? { ...message, ...patch } : message
  );
}

function stagePendingAdminChangeSet(
  content: string,
  hasConfigTool: boolean,
  setApplyState: (state: ApplyState) => void
): void {
  if (!hasConfigTool || !content.trim()) return;
  if (!content.includes('```json') || !content.includes('"requests"')) return;

  const extracted = extractAdminAssistantChangeSetStrict(content);
  if (extracted.ok) {
    setApplyState({ state: 'review', changeSet: extracted.changeSet });
  }
}

function slugify(value: string): string {
  return String(value || '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '');
}

async function readErrorDetail(res: Response): Promise<string> {
  let detail = `HTTP ${res.status}`;
  try {
    const payload = await res.json();
    if (payload?.detail !== undefined) {
      detail =
        typeof payload.detail === 'string'
          ? payload.detail
          : JSON.stringify(payload.detail);
    }
  } catch {
    // ignore
  }
  return detail;
}

export function AdminConfigAssistant({
  variant = 'sidebar',
  onCollapse,
  onClose,
  collapseIcon,
}: AdminConfigAssistantProps) {
  const { t } = useTranslation();
  const [shareSecrets, setShareSecrets] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [conversationSessionId, setConversationSessionId] = useState<
    string | null
  >(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [recoveryError, setRecoveryError] =
    useState<ClassifiedProviderError | null>(null);
  const [reducedContextNotice, setReducedContextNotice] = useState<
    string | null
  >(null);
  const [snapshotInfo, setSnapshotInfo] = useState<{
    generatedAtIso: string;
  } | null>(null);
  const [applyState, setApplyState] = useState<ApplyState>({ state: 'idle' });
  const [selectedTools, setSelectedTools] = useState<string[]>([
    'web-search',
    CONFIG_TOOL_ID,
  ]);

  const secretsForRedactionRef = useRef<string[]>([]);
  const deploymentSecretKeysRef = useRef<Set<string>>(new Set());
  const handleApplyRef = useRef<
    (changeSet: AdminAssistantChangeSet) => Promise<void>
  >(async () => {});

  const configCategories = useMemo(() => getConfigCategories(t), [t]);
  const deploymentMeta = useMemo(() => getDeploymentConfigItemMeta(t), [t]);
  const availableTools = useMemo<Tool[]>(
    () => [
      {
        id: 'web-search',
        name: t('chat.tools.webSearchName'),
        description: t('chat.tools.webSearch'),
        icon: (
          <svg
            className="w-3.5 h-3.5"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z"
            />
          </svg>
        ),
      },
      {
        id: CONFIG_TOOL_ID,
        name: t('chat.tools.configName', 'Config'),
        description: t(
          'chat.tools.config',
          'Read and update admin configuration'
        ),
        icon: (
          <svg
            className="w-3.5 h-3.5"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M10.5 6h9m-9 6h9m-9 6h9M4.5 6h.008v.008H4.5V6zm0 6h.008v.008H4.5V12zm0 6h.008v.008H4.5V18z"
            />
          </svg>
        ),
      },
      {
        id: 'db-query',
        name: t('chat.tools.databaseName'),
        description: t('chat.tools.database'),
        icon: (
          <svg
            className="w-3.5 h-3.5"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M20.25 6.375c0 2.278-3.694 4.125-8.25 4.125S3.75 8.653 3.75 6.375m16.5 0c0-2.278-3.694-4.125-8.25-4.125S3.75 4.097 3.75 6.375m16.5 0v11.25c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125V6.375m16.5 0v3.75m-16.5-3.75v3.75m16.5 0v3.75C20.25 16.153 16.556 18 12 18s-8.25-1.847-8.25-4.125v-3.75m16.5 0c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125"
            />
          </svg>
        ),
      },
    ],
    [t]
  );

  const fetchJson = useCallback(
    async <T,>(endpoint: string, options?: RequestInit): Promise<T> => {
      const res = await adminFetch(endpoint, options);
      if (!res.ok) {
        throw new Error(await readErrorDetail(res));
      }
      return res.json() as Promise<T>;
    },
    []
  );

  const hasConfigTool = selectedTools.includes(CONFIG_TOOL_ID);

  useEffect(() => {
    let cancelled = false;

    const fetchSessionDefaults = async () => {
      try {
        const res = await fetch(`${API_BASE}/session-defaults`);
        if (!res.ok) return;
        const data = await res.json();
        if (cancelled) return;
        setSelectedTools(
          data.web_search_enabled
            ? ['web-search', CONFIG_TOOL_ID]
            : [CONFIG_TOOL_ID]
        );
      } catch {
        // Keep local defaults on error.
      }
    };

    fetchSessionDefaults();

    return () => {
      cancelled = true;
    };
  }, []);

  const handleToolToggle = useCallback(
    (toolId: string) => {
      if (toolId === CONFIG_TOOL_ID && selectedTools.includes(CONFIG_TOOL_ID)) {
        setApplyState({ state: 'idle' });
        setSnapshotInfo(null);
        setShareSecrets(false);
        secretsForRedactionRef.current = [];
        deploymentSecretKeysRef.current = new Set();
      }
      setSelectedTools((prev) =>
        prev.includes(toolId)
          ? prev.filter((id) => id !== toolId)
          : [...prev, toolId]
      );
    },
    [selectedTools]
  );

  const handleStartNewAssistantConversation = useCallback(() => {
    setConversationSessionId(null);
    setMessages([]);
    setError(null);
    setRecoveryError(null);
    setReducedContextNotice(null);
    setShareSecrets(false);
    secretsForRedactionRef.current = [];
    deploymentSecretKeysRef.current = new Set();
  }, []);

  const handleSend = useCallback(
    async (content: string) => {
      const hasPendingChangeSet = applyState.state === 'review';
      const applyIntent = hasConfigTool
        ? resolveAdminApplyIntent(content, hasPendingChangeSet)
        : { kind: 'none' as const };

      const userMessage: Message = {
        id: generateMessageId(),
        role: 'user',
        content,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, userMessage]);
      setIsLoading(true);
      setError(null);
      setRecoveryError(null);
      setReducedContextNotice(null);

      if (applyIntent.kind === 'needs-panel') {
        setMessages((prev) => [
          ...prev,
          {
            id: generateMessageId(),
            role: 'assistant',
            content: t(
              'admin.configAssistant.applyIntentUsePanel',
              'Use the pending changes panel below and click Apply to confirm these configuration updates.'
            ),
            timestamp: new Date(),
          },
        ]);
        setIsLoading(false);
        return;
      }

      try {
        let baseToolContext: string | undefined;
        let boundedConversationHistory = messages.map(
          ({ role, content: turnContent }) => ({
            role,
            content: turnContent,
          })
        );
        if (!hasConfigTool) {
          setSnapshotInfo(null);
          setApplyState({ state: 'idle' });
          setReducedContextNotice(null);
        } else {
          const sessionMemoryPlan = compactAdminSessionMemory({
            conversationHistory: boundedConversationHistory,
          });
          boundedConversationHistory = sessionMemoryPlan.conversationHistory;

          const snap = await buildScopedAdminConfigContext({
            query: content,
            shareSecrets,
            fetchJson,
            configCategories,
            deploymentMeta,
            tracePolicyLines: TRACE_POLICY_CONTEXT_LINES,
          });
          const documentContext = await fetchBoundedAdminDocumentContext({
            query: content,
            fetchJson,
          });
          const promptPlan = planAdminPromptBudget({
            adminConfigContext: snap.context,
            documentContext: documentContext.included
              ? documentContext.context
              : '',
            conversationHistory: boundedConversationHistory,
          });
          baseToolContext = promptPlan.toolContext || undefined;
          boundedConversationHistory = promptPlan.conversationHistory;
          setReducedContextNotice(
            formatAdminReducedContextNotice(promptPlan.reducedSections, {
              sectionLabels: {
                'admin-config': t(
                  'admin.configAssistant.reducedContextSections.adminConfig',
                  'admin configuration context'
                ),
                'document-context': t(
                  'admin.configAssistant.reducedContextSections.documentContext',
                  'document library context'
                ),
                'recent-conversation': t(
                  'admin.configAssistant.reducedContextSections.recentConversation',
                  'recent conversation history'
                ),
              },
              formatNotice: (sectionLabels) =>
                t(
                  'admin.configAssistant.reducedContextNotice',
                  'Some context was reduced to fit the Model Provider budget ({{sections}}). Answers may be less complete until you start a new assistant conversation.',
                  { sections: sectionLabels.join(', ') }
                ),
            })
          );
          recordAdminContextPlanInstrumentation({
            surface: 'admin_config_assistant',
            sessionMemoryPlan,
            promptPlan,
          });
          setSnapshotInfo({ generatedAtIso: snap.generatedAtIso });
          secretsForRedactionRef.current = snap.secretValues;
          deploymentSecretKeysRef.current = snap.deploymentSecretKeys;
        }

        let streamed = false;
        let streamMessageId: string | null = null;
        let raw = '';
        let streamSessionId: string | null = null;
        let streamReportedError = false;
        let classifiedStreamError: ClassifiedProviderError | null = null;
        try {
          await sendLlmChatStreamWithUnifiedTools({
            content,
            tools: selectedTools,
            baseToolContext,
            sessionId: conversationSessionId,
            conversationHistory: boundedConversationHistory,
            onEvent: (event, payload) => {
              const data = payload as Record<string, unknown>;
              if (event === 'assistant_message_started') {
                const assistantId =
                  typeof data.message_id === 'string'
                    ? data.message_id
                    : generateMessageId();
                streamMessageId = assistantId;
                if (typeof data.session_id === 'string')
                  streamSessionId = data.session_id;
                setMessages((prev) => [
                  ...prev,
                  {
                    id: assistantId,
                    role: 'assistant',
                    content: '',
                    timestamp: new Date(),
                    traceStatus: t('chat.trace.writing', 'Writing answer...'),
                  },
                ]);
              } else if (event === 'trace_status' && streamMessageId) {
                const status =
                  typeof data.status === 'string'
                    ? data.status
                    : t('chat.trace.writing', 'Writing answer...');
                setMessages((prev) =>
                  patchAssistantMessage(prev, streamMessageId!, {
                    traceStatus: status,
                  })
                );
              } else if (event === 'answer_delta' && streamMessageId) {
                const delta = typeof data.delta === 'string' ? data.delta : '';
                raw += delta;
                const redactedChangeSets =
                  redactAdminDeploymentSecretChangeSets(raw);
                const display = shareSecrets
                  ? redactSecrets(
                      redactedChangeSets,
                      secretsForRedactionRef.current
                    )
                  : redactedChangeSets;
                setMessages((prev) =>
                  patchAssistantMessage(prev, streamMessageId!, {
                    content: display,
                  })
                );
              } else if (event === 'trace_final' && streamMessageId) {
                setMessages((prev) =>
                  patchAssistantMessage(prev, streamMessageId!, {
                    trace: data.trace as Message['trace'],
                    traceStatus: null,
                  })
                );
              } else if (event === 'done') {
                if (typeof data.session_id === 'string')
                  streamSessionId = data.session_id;
              } else if (event === 'error') {
                streamReportedError = true;
                const classified = classifyProviderError(
                  typeof data.detail === 'string' ? data.detail : data
                );
                classifiedStreamError = classified;
                recordProviderFailureInstrumentation({
                  surface: 'admin_config_assistant',
                  classified,
                });
                throw new Error(
                  classified.category === 'unknown' &&
                    typeof data.detail !== 'string'
                    ? t('errors.failedToSendMessage')
                    : formatClassifiedProviderError(classified)
                );
              }
            },
          });
          if (streamSessionId) {
            setConversationSessionId(streamSessionId);
          }
          if (streamMessageId) {
            setMessages((prev) =>
              patchAssistantMessage(prev, streamMessageId!, {
                traceStatus: null,
              })
            );
          }
          streamed = true;
        } catch (streamError) {
          stagePendingAdminChangeSet(raw, hasConfigTool, setApplyState);

          if (streamMessageId && raw.trim()) {
            setMessages((prev) =>
              patchAssistantMessage(prev, streamMessageId!, {
                traceStatus: null,
              })
            );
            setError(
              streamError instanceof Error
                ? streamError.message
                : t('errors.failedToSendMessage')
            );
            if (
              classifiedStreamError &&
              shouldOfferNewAssistantConversation(classifiedStreamError)
            ) {
              setRecoveryError(classifiedStreamError);
            }
            return;
          }
          if (streamMessageId) {
            setMessages((prev) =>
              prev.filter((message) => message.id !== streamMessageId)
            );
          }
          if (streamReportedError) {
            setError(
              streamError instanceof Error
                ? streamError.message
                : t('errors.failedToSendMessage')
            );
            if (
              classifiedStreamError &&
              shouldOfferNewAssistantConversation(classifiedStreamError)
            ) {
              setRecoveryError(classifiedStreamError);
            }
            return;
          }
          console.warn(
            'Streaming admin assistant failed; falling back to non-streaming chat:',
            streamError
          );
        }

        if (!streamed) {
          const res = await sendLlmChatWithUnifiedTools({
            content,
            tools: selectedTools,
            baseToolContext,
            sessionId: conversationSessionId,
            conversationHistory: boundedConversationHistory,
          });
          if (res.status === 401) {
            window.location.href = '/admin';
            return;
          }
          if (!res.ok) {
            const detail = await readErrorDetail(res);
            const classified = classifyProviderError(detail);
            recordProviderFailureInstrumentation({
              surface: 'admin_config_assistant',
              classified,
            });
            if (shouldOfferNewAssistantConversation(classified)) {
              setRecoveryError(classified);
            }
            throw new Error(formatClassifiedProviderError(classified));
          }
          const data = (await res.json()) as {
            message?: string;
            message_id?: string;
            session_id?: string;
            trace?: Message['trace'];
          };
          if (data.session_id) {
            setConversationSessionId(data.session_id);
          }
          raw = String(data?.message || '');

          const assistantId = data.message_id || generateMessageId();

          const redactedChangeSets = redactAdminDeploymentSecretChangeSets(raw);
          const display = shareSecrets
            ? redactSecrets(redactedChangeSets, secretsForRedactionRef.current)
            : redactedChangeSets;

          const assistantMessage: Message = {
            id: assistantId,
            role: 'assistant',
            content: display,
            timestamp: new Date(),
            trace: data.trace ?? null,
          };
          setMessages((prev) => [...prev, assistantMessage]);
        }

        if (hasConfigTool) {
          const extracted = extractAdminAssistantChangeSetStrict(raw);
          if (extracted.ok)
            setApplyState({ state: 'review', changeSet: extracted.changeSet });
          else if (raw.includes('```json') && raw.includes('"requests"'))
            setApplyState({ state: 'error', message: extracted.error });
        }
      } catch (e) {
        setError(
          e instanceof Error ? e.message : t('errors.failedToSendMessage')
        );
      } finally {
        setIsLoading(false);
      }
    },
    [
      applyState,
      configCategories,
      conversationSessionId,
      deploymentMeta,
      fetchJson,
      hasConfigTool,
      messages,
      selectedTools,
      shareSecrets,
      t,
    ]
  );

  const handleApply = useCallback(
    async (changeSet: AdminAssistantChangeSet) => {
      setApplyState({ state: 'applying', changeSet });
      try {
        // Allow one change set to create user types and then reference them without
        // guessing IDs. Placeholder syntax: "@type:<slug>" where slug is the
        // slugified user type name (lowercase, alnum + underscores).
        //
        // Examples:
        // - POST /admin/user-types { "name": "Bitcoin Designer", ... }
        // - POST /admin/user-fields { ..., "user_type_id": "@type:bitcoin_designer" }
        // - PUT /admin/ai-config/user-type/@type:bitcoin_designer/top_k { "value": "8" }
        const userTypeSlugToId = new Map<string, number>();
        try {
          const existing = await fetchJson<{
            types: Array<{ id: number; name: string }>;
          }>('/admin/user-types');
          for (const ut of existing.types || []) {
            userTypeSlugToId.set(slugify(ut.name), ut.id);
          }
        } catch {
          // Best-effort; we'll still fill mapping from POST results below.
        }

        const resolveUserTypeId = (raw: unknown): number | unknown => {
          if (typeof raw !== 'string') return raw;
          if (!raw.startsWith('@type:')) return raw;
          const slug = raw.slice('@type:'.length);
          const id = userTypeSlugToId.get(slug);
          if (id === undefined)
            throw new Error(`Unknown user type placeholder: ${raw}`);
          return id;
        };

        const rewritePath = (path: string): string => {
          // Replace /user-type/@type:slug/ with /user-type/<id>/
          const parts = path.split('/');
          const idx = parts.findIndex((p) => p === 'user-type');
          if (idx !== -1 && parts[idx + 1]?.startsWith('@type:')) {
            const seg = parts[idx + 1];
            const id = resolveUserTypeId(seg);
            if (typeof id === 'number') parts[idx + 1] = String(id);
          }
          // Replace /defaults/user-type/@type:slug (ingest doc defaults overrides)
          const idx2 = parts.findIndex((p) => p === 'defaults');
          if (
            idx2 !== -1 &&
            parts[idx2 + 1] === 'user-type' &&
            parts[idx2 + 2]?.startsWith('@type:')
          ) {
            const seg = parts[idx2 + 2];
            const id = resolveUserTypeId(seg);
            if (typeof id === 'number') parts[idx2 + 2] = String(id);
          }
          return parts.join('/');
        };

        const results: Array<{
          ok: boolean;
          method: string;
          path: string;
          status?: number;
          error?: string;
        }> = [];
        for (const req of changeSet.requests) {
          try {
            const resolvedPath = rewritePath(req.path);
            const requestValidation = validateAdminAssistantChangeSet({
              version: 1,
              requests: [req],
            });
            if (!requestValidation.ok) {
              results.push({
                ok: false,
                method: req.method,
                path: resolvedPath,
                error: requestValidation.error || 'Invalid request',
              });
              continue;
            }
            let resolvedBody: unknown = req.body;
            if (
              resolvedBody &&
              typeof resolvedBody === 'object' &&
              !Array.isArray(resolvedBody)
            ) {
              const b = resolvedBody as Record<string, unknown>;
              if ('user_type_id' in b) {
                const resolved = resolveUserTypeId(b.user_type_id);
                resolvedBody = { ...b, user_type_id: resolved };
              }
            }

            const res = await adminFetch(resolvedPath, {
              method: req.method,
              body: resolvedBody ? JSON.stringify(resolvedBody) : undefined,
            });
            if (!res.ok) {
              const detail = await readErrorDetail(res);
              results.push({
                ok: false,
                method: req.method,
                path: resolvedPath,
                status: res.status,
                error: detail,
              });
              continue;
            }

            // Learn created user type IDs for later placeholder resolution.
            if (req.method === 'POST' && req.path === '/admin/user-types') {
              try {
                const payload = (await res.json()) as {
                  id?: number;
                  name?: string;
                };
                if (
                  typeof payload?.id === 'number' &&
                  typeof payload?.name === 'string'
                ) {
                  userTypeSlugToId.set(slugify(payload.name), payload.id);
                }
              } catch {
                // ignore
              }
            }

            results.push({
              ok: true,
              method: req.method,
              path: resolvedPath,
              status: res.status,
            });
          } catch (err) {
            results.push({
              ok: false,
              method: req.method,
              path: req.path,
              error: err instanceof Error ? err.message : String(err),
            });
          }
        }

        const okCount = results.filter((r) => r.ok).length;
        const failCount = results.length - okCount;
        const baseSummary = failCount
          ? t('admin.configAssistant.applySummary.appliedCountsWithFailures', {
              ok: okCount,
              total: results.length,
              failed: failCount,
            })
          : t('admin.configAssistant.applySummary.appliedCounts', {
              ok: okCount,
              total: results.length,
            });

        const failedDetails = results
          .filter((r) => !r.ok)
          .map(
            (r) => `${r.method} ${r.path}: ${r.error || `HTTP ${r.status}`}`
          );
        const failureSummary = failedDetails.length
          ? '\n' + failedDetails.join('\n')
          : '';

        // Post-apply: run deployment config validation + check restart-required keys.
        let postApplyNotes: string[] = [];
        try {
          const validationRes = await adminFetch(
            '/admin/deployment/config/validate',
            { method: 'POST' }
          );
          if (validationRes.ok) {
            const v = (await validationRes.json()) as {
              valid: boolean;
              errors?: string[];
              warnings?: string[];
            };
            if (v.valid) {
              const warnings = (v.warnings || []).filter(Boolean);
              postApplyNotes.push(
                warnings.length
                  ? t(
                      'admin.configAssistant.applySummary.configValidationValidWarnings',
                      { count: warnings.length }
                    )
                  : t(
                      'admin.configAssistant.applySummary.configValidationValid'
                    )
              );
            } else {
              const errors = (v.errors || []).filter(Boolean);
              postApplyNotes.push(
                t(
                  'admin.configAssistant.applySummary.configValidationInvalidErrors',
                  { count: errors.length }
                )
              );
            }
          } else {
            postApplyNotes.push(
              t(
                'admin.configAssistant.applySummary.configValidationFailedHttp',
                { status: validationRes.status }
              )
            );
          }
        } catch {
          postApplyNotes.push(
            t(
              'admin.configAssistant.applySummary.configValidationFailedNetwork'
            )
          );
        }

        try {
          const rr = await adminFetch('/admin/deployment/restart-required');
          if (rr.ok) {
            const data = (await rr.json()) as {
              restart_required: boolean;
              changed_keys?: Array<{ key: string }>;
            };
            const keys = (data.changed_keys || [])
              .map((k) => k.key)
              .filter(Boolean);
            if (data.restart_required && keys.length) {
              postApplyNotes.push(
                t('admin.configAssistant.applySummary.restartRequiredFor', {
                  keys: keys.join(', '),
                })
              );
            } else {
              postApplyNotes.push(
                t('admin.configAssistant.applySummary.restartRequiredNo')
              );
            }
          } else {
            postApplyNotes.push(
              t('admin.configAssistant.applySummary.restartCheckFailedHttp', {
                status: rr.status,
              })
            );
          }
        } catch {
          postApplyNotes.push(
            t('admin.configAssistant.applySummary.restartCheckFailedNetwork')
          );
        }

        const needsPageRefresh = results.some(
          (r) => r.ok && r.path === '/admin/settings'
        );
        if (needsPageRefresh) {
          postApplyNotes.push(
            t('admin.configAssistant.applySummary.pageRefreshRecommended')
          );
        }

        const summary =
          [baseSummary, ...postApplyNotes].join(' ') + failureSummary;
        setApplyState({ state: 'applied', message: summary });

        setMessages((prev) => [
          ...prev,
          {
            id: generateMessageId(),
            role: 'assistant',
            content: summary,
            timestamp: new Date(),
          },
        ]);
      } catch (e) {
        setApplyState({
          state: 'error',
          message: e instanceof Error ? e.message : String(e),
        });
      }
    },
    [fetchJson, t]
  );
  handleApplyRef.current = handleApply;

  const applyPreview = useMemo(() => {
    if (applyState.state !== 'review' && applyState.state !== 'applying')
      return null;
    const changeSet = applyState.changeSet;

    const secretKeys = deploymentSecretKeysRef.current;

    const pretty = changeSet.requests.map((r, idx) => {
      let bodyDisplay: unknown = r.body;
      // Mask deployment secrets in preview (even if they exist in body).
      if (
        r.method === 'PUT' &&
        r.path.startsWith('/admin/deployment/config/')
      ) {
        const key = r.path.split('/').pop() || '';
        if (secretKeys.has(key) && r.body && typeof r.body === 'object') {
          const o = r.body as Record<string, unknown>;
          if (typeof o.value === 'string' && o.value.length > 0) {
            bodyDisplay = { ...o, value: '[REDACTED]' };
          }
        }
      }
      return {
        idx: idx + 1,
        method: r.method,
        path: r.path,
        body: bodyDisplay,
      };
    });

    return {
      summary: changeSet.summary || '',
      requests: pretty,
    };
  }, [applyState]);

  const closeDrawer = () => {
    setError(null);
    setApplyState({ state: 'idle' });
    // Secrets are opt-in and should not persist beyond the session UI.
    setShareSecrets(false);
    secretsForRedactionRef.current = [];
    onClose?.();
  };

  const inputToolbar = (
    <ToolSelector
      tools={availableTools}
      selectedTools={selectedTools}
      onToggle={handleToolToggle}
      compact
    />
  );

  const containerClass =
    variant === 'drawer'
      ? 'ml-auto h-full w-[min(92vw,400px)] bg-surface border-l border-border shadow-2xl'
      : 'h-full w-full bg-surface';

  return (
    <div className={`${containerClass} overflow-hidden flex flex-col`}>
      <div className="px-4 py-3 border-b border-border bg-surface-raised flex items-center justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <MessageCircle className="w-4 h-4 text-accent" />
            <div className="font-semibold text-text truncate">
              {t('admin.configAssistant.title')}
            </div>
          </div>
          <div className="text-xs text-text-muted mt-0.5">
            {!hasConfigTool
              ? t('admin.configAssistant.contextToolOff')
              : snapshotInfo?.generatedAtIso
                ? t('admin.configAssistant.contextReady', {
                    timestamp: new Date(
                      snapshotInfo.generatedAtIso
                    ).toLocaleString(),
                  })
                : t('admin.configAssistant.contextNotLoaded')}
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={async () => {
              if (!hasConfigTool) return;
              setError(null);
              setIsLoading(true);
              try {
                const snap = await buildFullAdminConfigContext({
                  shareSecrets,
                  fetchJson,
                  configCategories,
                  deploymentMeta,
                  tracePolicyLines: TRACE_POLICY_CONTEXT_LINES,
                });
                setSnapshotInfo({ generatedAtIso: snap.generatedAtIso });
                secretsForRedactionRef.current = snap.secretValues;
                deploymentSecretKeysRef.current = snap.deploymentSecretKeys;
              } catch (e) {
                setError(
                  e instanceof Error
                    ? e.message
                    : t('admin.configAssistant.refreshFailed')
                );
              } finally {
                setIsLoading(false);
              }
            }}
            className="p-2 rounded-xl hover:bg-surface-overlay text-text-muted hover:text-text transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            title={t('admin.configAssistant.refreshContext')}
            aria-label={t('admin.configAssistant.refreshContext')}
            disabled={!hasConfigTool}
          >
            <RefreshCw
              className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`}
            />
          </button>
          {variant === 'sidebar' && onCollapse && (
            <button
              onClick={onCollapse}
              className="p-2 rounded-xl hover:bg-surface-overlay text-text-muted hover:text-text transition-colors"
              title={t(
                'admin.configAssistant.collapseSidebar',
                'Collapse assistant sidebar'
              )}
              aria-label={t(
                'admin.configAssistant.collapseSidebar',
                'Collapse assistant sidebar'
              )}
            >
              {collapseIcon}
            </button>
          )}
          {variant === 'drawer' && (
            <button
              onClick={closeDrawer}
              className="p-2 rounded-xl hover:bg-surface-overlay text-text-muted hover:text-text transition-colors"
              title={t('common.close')}
              aria-label={t('common.close')}
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      <div className="px-4 py-3 border-b border-border bg-surface flex items-start justify-between gap-3">
        <label
          className={`flex items-start gap-3 select-none ${hasConfigTool ? 'cursor-pointer' : 'cursor-not-allowed opacity-60'}`}
          aria-disabled={!hasConfigTool}
        >
          <input
            type="checkbox"
            checked={shareSecrets}
            disabled={!hasConfigTool}
            onChange={(e) => {
              setShareSecrets(e.target.checked);
              // Clear redaction cache until next snapshot build.
              secretsForRedactionRef.current = [];
            }}
            className="mt-1 disabled:cursor-not-allowed"
          />
          <div>
            <div className="text-sm font-medium text-text">
              {t('admin.configAssistant.shareSecretsTitle')}
            </div>
            <div className="text-xs text-text-muted">
              {t('admin.configAssistant.shareSecretsHint')}
            </div>
          </div>
        </label>
        {hasConfigTool && shareSecrets && (
          <div className="flex items-center gap-2 text-xs text-warning shrink-0">
            <ShieldAlert className="w-4 h-4" />
            <span className="hidden sm:inline">
              {t('admin.configAssistant.sensitive')}
            </span>
          </div>
        )}
      </div>

      <div className="flex-1 overflow-y-auto px-3 py-4">
        <div className="space-y-4">
          {messages.length === 0 ? (
            <div className="text-sm text-text-muted">
              {t('admin.configAssistant.emptyPrompt')}
            </div>
          ) : (
            messages.map((m) => <ChatMessage key={m.id} message={m} />)
          )}

          {isLoading && (
            <div className="animate-fade-in-up">
              <div className="flex gap-3">
                <div className="w-7 h-7 rounded-full bg-gradient-to-br from-accent to-accent-hover flex items-center justify-center shrink-0 shadow-md ring-1 ring-white/10">
                  <MessageCircle className="w-3.5 h-3.5 text-white" />
                </div>
                <div className="flex items-center gap-2 px-4 py-3 bg-surface-raised border border-border rounded-2xl rounded-bl-md">
                  <div className="flex items-center gap-1">
                    <span className="w-2 h-2 bg-accent/60 rounded-full typing-dot" />
                    <span className="w-2 h-2 bg-accent/60 rounded-full typing-dot" />
                    <span className="w-2 h-2 bg-accent/60 rounded-full typing-dot" />
                  </div>
                  <span className="text-sm text-text-secondary animate-pulse-subtle">
                    {t('chat.typing')}
                  </span>
                </div>
              </div>
            </div>
          )}

          {reducedContextNotice && (
            <div
              role="note"
              aria-label={t(
                'admin.configAssistant.reducedContextNoticeLabel',
                'Reduced context notice'
              )}
              className="text-sm text-warning bg-warning/10 border border-warning/25 rounded-xl px-3 py-2"
            >
              {reducedContextNotice}
            </div>
          )}

          {error && (
            <div className="text-sm text-error bg-error/10 border border-error/20 rounded-xl px-3 py-2 space-y-2">
              <div>{error}</div>
              {recoveryError &&
                shouldOfferNewAssistantConversation(recoveryError) && (
                  <button
                    type="button"
                    onClick={handleStartNewAssistantConversation}
                    className="inline-flex items-center gap-2 px-3 py-2 rounded-xl bg-surface-raised border border-border text-text hover:bg-surface-overlay transition-colors text-sm font-medium"
                  >
                    {t('admin.configAssistant.startNewConversation')}
                  </button>
                )}
            </div>
          )}

          {hasConfigTool && applyState.state === 'error' && (
            <div className="text-sm text-error bg-error/10 border border-error/20 rounded-xl px-3 py-2">
              {applyState.message}
            </div>
          )}

          {hasConfigTool && applyState.state === 'review' && applyPreview && (
            <div className="border border-border rounded-2xl bg-surface-raised overflow-hidden">
              <div className="px-3 py-2 border-b border-border flex items-center justify-between gap-2">
                <div className="text-sm font-medium text-text truncate">
                  {applyPreview.summary
                    ? t('admin.configAssistant.pendingChangesWithSummary', {
                        summary: applyPreview.summary,
                      })
                    : t('admin.configAssistant.pendingChanges')}
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setApplyState({ state: 'idle' })}
                    className="p-2 rounded-xl hover:bg-surface-overlay text-text-muted hover:text-text transition-colors"
                    title={t('admin.configAssistant.dismiss')}
                    aria-label={t('admin.configAssistant.dismiss')}
                  >
                    <EyeOff className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => handleApply(applyState.changeSet)}
                    className="flex items-center gap-2 px-3 py-2 rounded-xl bg-accent text-accent-text hover:bg-accent-hover transition-colors text-sm font-medium"
                  >
                    <Play className="w-4 h-4" />
                    {t('admin.configAssistant.apply')}
                  </button>
                </div>
              </div>
              <div className="px-3 py-2 text-xs text-text-muted">
                {t('admin.configAssistant.reviewMaskedSecrets')}
              </div>
              <div className="px-3 pb-3 space-y-2">
                {applyPreview.requests.map((r) => (
                  <div
                    key={r.idx}
                    className="rounded-xl border border-border bg-surface px-3 py-2"
                  >
                    <div className="text-xs font-mono text-text-secondary">
                      {r.method} {r.path}
                    </div>
                    {r.body !== undefined && (
                      <pre className="mt-2 text-xs overflow-x-auto text-text-muted">
                        {JSON.stringify(r.body, null, 2)}
                      </pre>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {hasConfigTool && applyState.state === 'applying' && (
            <div className="text-sm text-text-muted border border-border rounded-xl px-3 py-2 bg-surface-raised">
              {t('admin.configAssistant.applyingChanges')}
            </div>
          )}
        </div>
      </div>

      <ChatInput
        onSend={(msg) => void handleSend(msg)}
        disabled={isLoading}
        placeholder={t('admin.configAssistant.inputPlaceholder')}
        toolbar={inputToolbar}
      />
    </div>
  );
}
