import {
  useState,
  useCallback,
  useEffect,
  useMemo,
  useReducer,
  type Dispatch,
} from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  AlertCircle,
  CheckCircle2,
  ChevronDown,
  Database,
  Mail,
  Plus,
  Search,
  Settings2,
  MessageSquare,
  ShieldCheck,
  X,
} from 'lucide-react';
import { ChatContainer } from '../components/chat/ChatContainer';
import { ConversationSurface } from '../components/chat/ConversationSurface';
import { buildConversationSurfaceTurns } from '../components/chat/ConversationSurfaceModel';
import {
  adaptSageStreamEvent,
  buildAdminChangePreview,
  createAdminChangeConfirmationState,
  createConversationUiState,
  reduceAdminChangeConfirmationState,
  reduceConversationUiState,
  type AdminChangeConfirmationAction,
  type ConversationUiTurn,
} from '../components/chat';
import { ToolSelector, Tool } from '../components/chat/ToolSelector';
import {
  DocumentScope,
  DocumentSource,
} from '../components/chat/DocumentScope';
import { ExportButton } from '../components/chat/ExportButton';
import { AppHeader } from '../components/shared/AppHeader';
import { Message } from '../components/chat/ChatMessage';
import {
  ReachoutModal,
  type ReachoutMode,
} from '../components/reachout/ReachoutModal';
import {
  API_BASE,
  STORAGE_KEYS,
  getSelectedUserTypeId,
  saveSelectedUserTypeId,
} from '../types/onboarding';
import { adminFetch, isAdminAuthenticated } from '../utils/adminApi';
import {
  sendLlmChatStreamWithUnifiedTools,
  sendLlmChatWithUnifiedTools,
  sendQueryStream,
} from '../utils/llmChat';
import { Button, Callout, IconButton } from '../components/ui';
import {
  extractAdminAssistantChangeSetStrict,
  redactAdminDeploymentSecretChangeSets,
  stripAdminAssistantChangeSetJson,
  validateAdminAssistantChangeSet,
  type AdminAssistantChangeSet,
} from '../utils/adminAssistant';
import {
  classifyProviderError,
  formatClassifiedProviderError,
  shouldOfferNewAssistantConversation,
} from '../utils/providerErrors';
import { resolveAdminApplyIntent } from '../utils/adminApplyIntent';
import { compactAdminSessionMemory } from '../utils/sessionMemoryCompaction';
import {
  formatAdminReducedContextNotice,
  planAdminPromptBudget,
} from '../utils/promptBudget';
import {
  recordAdminContextPlanInstrumentation,
  recordProviderFailureInstrumentation,
} from '../utils/adminResilienceInstrumentation';

const CONFIG_TOOL_ID = 'admin-config';
export const ENCLAVE_USER_EMAIL_KEY = STORAGE_KEYS.USER_EMAIL;

function conversationTurnToMessage(turn: ConversationUiTurn): Message {
  return {
    id: turn.id,
    role: turn.role,
    content: turn.content,
    trace: turn.trace,
    traceStatus: turn.traceStatus,
    activitySteps: turn.activitySteps,
    controlSnapshot: turn.controlSnapshot,
  };
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

function formatProviderStreamError(
  detail: unknown,
  fallbackMessage: string,
  options?: { recordAdminInstrumentation?: boolean }
): string {
  const classified = classifyProviderError(
    typeof detail === 'string' ? detail : detail
  );
  if (options?.recordAdminInstrumentation) {
    recordProviderFailureInstrumentation({
      surface: 'admin_chat_page',
      classified,
    });
  }
  if (classified.category === 'unknown' && typeof detail !== 'string') {
    return fallbackMessage;
  }
  return formatClassifiedProviderError(classified);
}

function formatProviderResponseError(
  detail: unknown,
  statusFallback: string,
  options?: { recordAdminInstrumentation?: boolean }
): string {
  const classified = classifyProviderError(detail);
  if (options?.recordAdminInstrumentation) {
    recordProviderFailureInstrumentation({
      surface: 'admin_chat_page',
      classified,
    });
  }
  if (classified.category === 'unknown' && !detail) {
    return statusFallback;
  }
  return formatClassifiedProviderError(classified);
}

function stagePendingAdminChangeSet(
  content: string,
  hasConfigTool: boolean,
  dispatchAdminApply: Dispatch<AdminChangeConfirmationAction>
): boolean {
  if (!hasConfigTool || !content.trim()) return false;
  if (!content.includes('"requests"')) return false;

  const extracted = extractAdminAssistantChangeSetStrict(content);
  if (extracted.ok) {
    dispatchAdminApply({
      type: 'changeSetReadyForReview',
      changeSet: extracted.changeSet,
    });
    return true;
  }
  return false;
}

function prepareAssistantContentForDisplay(
  content: string,
  hasConfigTool: boolean
): string {
  const redacted = redactAdminDeploymentSecretChangeSets(content);
  return hasConfigTool ? stripAdminAssistantChangeSetJson(redacted) : redacted;
}

function AdminChangeApprovalCard({
  preview,
  state,
  message,
  onApprove,
  onReject,
}: {
  preview: ReturnType<typeof buildAdminChangePreview>;
  state: 'review' | 'applying' | 'applied' | 'rejected' | 'error';
  message?: string;
  onApprove: () => void;
  onReject: () => void;
}) {
  const { t } = useTranslation();
  const [detailsOpen, setDetailsOpen] = useState(false);
  const isApplying = state === 'applying';
  const isFinal =
    state === 'applied' || state === 'rejected' || state === 'error';

  return (
    <div
      role="group"
      aria-label="Admin Change Confirmation"
      className="mb-4 ml-10 max-w-[min(100%,48rem)] overflow-hidden rounded-xl border border-warning/25 bg-surface-raised shadow-sm"
    >
      <div className="flex items-start gap-3 px-4 py-3">
        <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-warning/10 text-warning">
          <ShieldCheck className="h-4 w-4" aria-hidden="true" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-sm font-semibold text-text">
              {t(
                'admin.configAssistant.approvalCardTitle',
                'Admin Change Confirmation'
              )}
            </h3>
            {isApplying && (
              <span className="rounded-full bg-warning/10 px-2 py-0.5 text-[11px] font-medium text-warning">
                {t('admin.configAssistant.applying', 'Applying')}
              </span>
            )}
            {state === 'applied' && (
              <span className="rounded-full bg-success/10 px-2 py-0.5 text-[11px] font-medium text-success">
                {t('admin.configAssistant.applied', 'Applied')}
              </span>
            )}
            {state === 'rejected' && (
              <span className="rounded-full bg-surface-overlay px-2 py-0.5 text-[11px] font-medium text-text-secondary">
                {t('admin.configAssistant.rejected', 'Rejected')}
              </span>
            )}
            {state === 'error' && (
              <span className="rounded-full bg-error/10 px-2 py-0.5 text-[11px] font-medium text-error">
                {t('admin.configAssistant.failed', 'Failed')}
              </span>
            )}
          </div>
          <p className="mt-1 text-sm text-text-secondary">
            {preview.summary ||
              t(
                'admin.configAssistant.pendingChanges',
                'Pending configuration changes'
              )}
          </p>
          {message && <p className="mt-2 text-xs text-text-muted">{message}</p>}
          <p className="mt-2 text-xs text-text-muted">
            {t('admin.configAssistant.reviewMaskedSecrets')}
          </p>
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border/70 px-4 py-3">
        <button
          type="button"
          onClick={() => setDetailsOpen((open) => !open)}
          aria-expanded={detailsOpen}
          className="inline-flex min-h-10 items-center gap-1 rounded-lg px-2 text-sm font-medium text-text-secondary transition-colors hover:bg-surface-overlay hover:text-text"
        >
          <ChevronDown
            className={`h-4 w-4 transition-transform ${detailsOpen ? 'rotate-180' : ''}`}
            aria-hidden="true"
          />
          {detailsOpen
            ? t('admin.configAssistant.hideDetails', 'Hide details')
            : t('admin.configAssistant.reviewDetails', 'Review details')}
        </button>
        <div className="flex items-center gap-2">
          <Button
            onClick={onReject}
            variant="ghost"
            size="sm"
            disabled={isApplying || isFinal}
            aria-label="Reject changes"
          >
            {t('admin.configAssistant.reject', 'Reject')}
          </Button>
          <Button
            onClick={onApprove}
            variant="primary"
            size="sm"
            disabled={isApplying || isFinal}
            aria-label="Approve changes"
            leadingIcon={
              <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
            }
          >
            {t('admin.configAssistant.approve', 'Approve')}
          </Button>
        </div>
      </div>

      {detailsOpen && (
        <div className="space-y-2 border-t border-border/70 bg-surface px-4 py-3">
          {preview.requests.map((request) => (
            <div
              key={request.idx}
              className="rounded-lg border border-border bg-surface-raised px-3 py-2"
            >
              <div className="text-xs font-mono text-text-secondary">
                {request.method} {request.path}
              </div>
              {request.body !== undefined && (
                <pre className="mt-2 max-h-40 overflow-auto text-xs text-text-muted">
                  {JSON.stringify(request.body, null, 2)}
                </pre>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function ChatPage() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const isAdmin = isAdminAuthenticated();
  const [conversationState, dispatchConversation] = useReducer(
    reduceConversationUiState,
    undefined,
    () =>
      createConversationUiState({
        selectedTools: isAdmin ? [CONFIG_TOOL_ID] : [],
      })
  );
  const [adminApplyState, dispatchAdminApply] = useReducer(
    reduceAdminChangeConfirmationState,
    undefined,
    () => createAdminChangeConfirmationState()
  );
  const [adminApprovalTurnId, setAdminApprovalTurnId] = useState<string | null>(
    null
  );
  const [documents, setDocuments] = useState<DocumentSource[]>([]);
  const [sessionDefaultsLoaded, setSessionDefaultsLoaded] = useState(false);
  const [pendingDefaultDocs, setPendingDefaultDocs] = useState<string[]>([]);
  const [deploymentSecretKeys, setDeploymentSecretKeys] = useState<Set<string>>(
    new Set()
  );
  const [deploymentSecretKeysLoaded, setDeploymentSecretKeysLoaded] =
    useState(false);
  const messages = useMemo(
    () => conversationState.turns.map(conversationTurnToMessage),
    [conversationState.turns]
  );
  const selectedTools = conversationState.selectedTools;
  const selectedDocuments = conversationState.selectedDocuments;
  const conversationSessionId = conversationState.conversationSessionId;
  const isLoading = conversationState.isRunning;
  const error = conversationState.error;
  const selectedDocumentSources = useMemo(
    () =>
      selectedDocuments
        .map((id) => documents.find((document) => document.id === id))
        .filter((document): document is DocumentSource => Boolean(document)),
    [documents, selectedDocuments]
  );

  const [reachoutOpen, setReachoutOpen] = useState(false);
  const [reachoutEnabled, setReachoutEnabled] = useState(false);
  const [reachoutMode, setReachoutMode] = useState<ReachoutMode>('support');
  const [reachoutOverrides, setReachoutOverrides] = useState<{
    title?: string;
    description?: string;
    buttonLabel?: string;
    successMessage?: string;
  }>({});
  const [reducedContextNotice, setReducedContextNotice] = useState<
    string | null
  >(null);

  useEffect(() => {
    if (!isAdmin) return;

    let cancelled = false;
    async function fetchDeploymentSecretKeys() {
      setDeploymentSecretKeys(new Set());
      setDeploymentSecretKeysLoaded(false);
      try {
        const res = await adminFetch('/admin/deployment/config');
        if (!res.ok) return;
        const payload = await res.json();
        const secretKeys = new Set<string>();
        for (const value of Object.values(payload || {})) {
          if (!Array.isArray(value)) continue;
          for (const item of value) {
            const configItem = item as { is_secret?: boolean; key?: unknown };
            if (configItem.is_secret && typeof configItem.key === 'string')
              secretKeys.add(configItem.key);
          }
        }
        if (!cancelled) {
          setDeploymentSecretKeys(secretKeys);
          setDeploymentSecretKeysLoaded(true);
        }
      } catch {
        // Keep pessimistic masking when metadata is unavailable.
      }
    }

    fetchDeploymentSecretKeys();
    return () => {
      cancelled = true;
    };
  }, [isAdmin]);

  // Build available tools list - db-query only visible to admins
  const availableTools = useMemo<Tool[]>(() => {
    const tools: Tool[] = [
      {
        id: 'web-search',
        name: t('chat.tools.webSearchName'),
        description: t('chat.tools.webSearch'),
        icon: <Search className="h-3.5 w-3.5" aria-hidden="true" />,
      },
    ];

    // Only show Database tool to authenticated admins
    if (isAdmin) {
      tools.push({
        id: CONFIG_TOOL_ID,
        name: t('chat.tools.configName', 'Config'),
        description: t(
          'chat.tools.config',
          'Read and update admin configuration'
        ),
        icon: <Settings2 className="h-3.5 w-3.5" aria-hidden="true" />,
      });
      tools.push({
        id: 'db-query',
        name: t('chat.tools.databaseName'),
        description: t('chat.tools.database'),
        icon: <Database className="h-3.5 w-3.5" aria-hidden="true" />,
      });
    }

    return tools;
  }, [isAdmin, t]);

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

  // Reachout settings (public)
  useEffect(() => {
    let isCancelled = false;

    async function fetchReachout() {
      try {
        const res = await fetch(`${API_BASE}/settings/public`);
        if (!res.ok) return;
        const data = await res.json();
        const s = (data?.settings ?? {}) as Record<string, string>;

        if (isCancelled) return;

        setReachoutEnabled(
          String(s.reachout_enabled ?? 'false').toLowerCase() === 'true'
        );
        const mode = String(s.reachout_mode ?? 'support').toLowerCase();
        if (mode === 'feedback' || mode === 'help' || mode === 'support') {
          setReachoutMode(mode);
        } else {
          setReachoutMode('support');
        }

        setReachoutOverrides({
          title:
            typeof s.reachout_title === 'string' ? s.reachout_title : undefined,
          description:
            typeof s.reachout_description === 'string'
              ? s.reachout_description
              : undefined,
          buttonLabel:
            typeof s.reachout_button_label === 'string'
              ? s.reachout_button_label
              : undefined,
          successMessage:
            typeof s.reachout_success_message === 'string'
              ? s.reachout_success_message
              : undefined,
        });
      } catch {
        // Best-effort: feature remains hidden if fetch fails.
      }
    }

    fetchReachout();

    return () => {
      isCancelled = true;
    };
  }, []);

  // Check auth and approval status on mount
  useEffect(() => {
    let isCancelled = false;
    const userEmail = localStorage.getItem(STORAGE_KEYS.USER_EMAIL);

    // Not authenticated at all - redirect to login
    if (!isAdmin && !userEmail) {
      navigate('/login');
      return;
    }

    // User authenticated but not approved - redirect to pending
    const approved = localStorage.getItem(STORAGE_KEYS.USER_APPROVED);
    if (!isAdmin && approved === 'false') {
      navigate('/pending');
      return;
    }

    // Keep onboarding enforcement server-authoritative for returning users.
    if (!isAdmin) {
      const checkOnboardingStatus = async () => {
        try {
          const response = await fetch(
            `${API_BASE}/users/me/onboarding-status`,
            {
              credentials: 'include',
            }
          );

          if (isCancelled) return;

          if (response.status === 401) {
            navigate('/login');
            return;
          }

          if (!response.ok) {
            return;
          }

          const status = await response.json();

          if (isCancelled) return;

          const effectiveTypeId = status.effective_user_type_id ?? null;
          saveSelectedUserTypeId(effectiveTypeId);

          if (status.needs_user_type) {
            navigate('/user-type');
            return;
          }

          if (status.needs_onboarding) {
            navigate('/profile');
          }
        } catch (err) {
          console.error('Failed to fetch onboarding status:', err);
        }
      };

      checkOnboardingStatus();
    }

    return () => {
      isCancelled = true;
    };
  }, [isAdmin, navigate]);

  // Fetch session defaults from admin config
  useEffect(() => {
    if (sessionDefaultsLoaded) return;

    const fetchSessionDefaults = async () => {
      try {
        const userTypeId = getSelectedUserTypeId();
        const url =
          userTypeId !== null
            ? `${API_BASE}/session-defaults?user_type_id=${userTypeId}`
            : `${API_BASE}/session-defaults`;
        const res = await fetch(url);
        if (res.ok) {
          const data = await res.json();
          const defaultTools = data.web_search_enabled ? ['web-search'] : [];
          dispatchConversation({
            type: 'selectedToolsChanged',
            selectedTools: isAdmin
              ? [...defaultTools, CONFIG_TOOL_ID]
              : defaultTools,
          });
          // Store default document IDs to apply once documents are loaded
          if (
            data.default_document_ids &&
            data.default_document_ids.length > 0
          ) {
            setPendingDefaultDocs(data.default_document_ids);
          }
        } else {
          // Non-2xx response - fall back to web search enabled by default
          console.warn('Failed to fetch session defaults:', res.status);
          dispatchConversation({
            type: 'selectedToolsChanged',
            selectedTools: isAdmin
              ? ['web-search', CONFIG_TOOL_ID]
              : ['web-search'],
          });
        }
      } catch (err) {
        console.error('Failed to fetch session defaults:', err);
        // Fall back to web search enabled by default on error
        dispatchConversation({
          type: 'selectedToolsChanged',
          selectedTools: isAdmin
            ? ['web-search', CONFIG_TOOL_ID]
            : ['web-search'],
        });
      } finally {
        setSessionDefaultsLoaded(true);
      }
    };

    fetchSessionDefaults();
  }, [isAdmin, sessionDefaultsLoaded]);

  // Fetch available documents from ingest jobs
  useEffect(() => {
    const fetchDocuments = async () => {
      try {
        const res = await fetch(`${API_BASE}/ingest/jobs`, {
          credentials: 'include',
        });
        if (res.ok) {
          const data = await res.json();
          const docs: DocumentSource[] = (data.jobs || [])
            .filter(
              (job: { status: string }) =>
                job.status === 'completed' ||
                job.status === 'completed_with_errors'
            )
            .map(
              (job: {
                job_id: string;
                filename: string;
                total_chunks: number;
              }) => ({
                id: job.job_id,
                name: job.filename.replace(/\.(pdf|txt|md)$/i, ''),
                description: `${job.total_chunks} chunks`,
                tags: [job.filename.split('.').pop()?.toUpperCase() || 'DOC'],
              })
            );
          setDocuments(docs);
        }
      } catch (e) {
        console.error(t('errors.failedToFetchDocuments'), e);
      }
    };
    fetchDocuments();
  }, []);

  // Apply pending default documents once documents are loaded
  useEffect(() => {
    if (pendingDefaultDocs.length > 0 && documents.length > 0) {
      // Filter to only include IDs that exist in the documents list
      const validIds = pendingDefaultDocs.filter((id) =>
        documents.some((d) => d.id === id)
      );
      if (validIds.length > 0) {
        dispatchConversation({
          type: 'selectedDocumentsChanged',
          selectedDocuments: validIds,
        });
      }
      setPendingDefaultDocs([]);
    }
  }, [pendingDefaultDocs, documents]);

  const handleToolToggle = useCallback(
    (toolId: string) => {
      const selectedAfterToggle = !selectedTools.includes(toolId);
      if (toolId === CONFIG_TOOL_ID) {
        dispatchAdminApply({
          type: 'adminConfigToolToggled',
          selectedAfterToggle,
        });
      }
      dispatchConversation({ type: 'toolToggled', toolId });
    },
    [selectedTools]
  );

  const handleDocumentToggle = useCallback((docId: string) => {
    dispatchConversation({ type: 'documentToggled', documentId: docId });
  }, []);

  const generateMessageId = () =>
    `msg-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

  const dispatchStreamEvent = (
    event: string,
    payload: Record<string, unknown>,
    assistantTurnId?: string | null
  ) => {
    const action = adaptSageStreamEvent(event, payload, assistantTurnId);
    if (action) dispatchConversation(action);
    return action;
  };

  const handleSend = async (content: string) => {
    const hasConfigTool = isAdmin && selectedTools.includes(CONFIG_TOOL_ID);
    const hasPendingChangeSet = adminApplyState.state === 'review';
    const applyIntent = hasConfigTool
      ? resolveAdminApplyIntent(content, hasPendingChangeSet)
      : { kind: 'none' as const };

    dispatchConversation({
      type: 'userTurnSubmitted',
      id: generateMessageId(),
      content,
    });

    if (applyIntent.kind === 'needs-panel') {
      dispatchConversation({
        type: 'assistantTurnAppended',
        id: generateMessageId(),
        content: t(
          'admin.configAssistant.applyIntentUsePanel',
          'Use the approval card below and click Approve to confirm these configuration updates.'
        ),
      });
      dispatchConversation({ type: 'assistantTurnFinished' });
      return;
    }

    try {
      const backendTools = selectedTools;
      const useRag = !isAdmin && selectedDocuments.length > 0;
      let conversationHistory = messages.map(
        ({ role, content: turnContent }) => ({
          role,
          content: turnContent,
        })
      );
      if (hasConfigTool) {
        const sessionMemoryPlan = compactAdminSessionMemory({
          conversationHistory,
        });
        const promptPlan = planAdminPromptBudget({
          adminConfigContext: '',
          conversationHistory: sessionMemoryPlan.conversationHistory,
        });
        conversationHistory = promptPlan.conversationHistory;
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
          surface: 'admin_chat_page',
          sessionMemoryPlan,
          promptPlan,
        });
      } else {
        setReducedContextNotice(null);
      }

      let response: Response;
      if (useRag) {
        const body = {
          question: content,
          top_k: 8,
          tools: backendTools,
          job_ids: selectedDocuments,
          ...(conversationSessionId && { session_id: conversationSessionId }),
        };

        let streamed = false;
        let streamMessageId: string | null = null;
        let streamContent = '';
        let streamSessionId: string | null = null;
        let streamSearchTerm: string | null = null;
        try {
          await sendQueryStream({
            question: content,
            tools: backendTools,
            jobIds: selectedDocuments,
            sessionId: conversationSessionId,
            onEvent: (event, payload) => {
              const data = payload as Record<string, unknown>;
              if (event === 'assistant_message_started') {
                if (typeof data.message_id !== 'string')
                  data.message_id = generateMessageId();
                const id = data.message_id as string;
                streamMessageId = id;
                streamSessionId =
                  typeof data.session_id === 'string'
                    ? data.session_id
                    : streamSessionId;
                dispatchConversation({
                  type: 'assistantTurnStarted',
                  id,
                  sessionId: streamSessionId,
                  traceStatus: t('chat.trace.writing', 'Writing answer...'),
                });
              } else if (event === 'answer_delta' && streamMessageId) {
                const delta = typeof data.delta === 'string' ? data.delta : '';
                streamContent += delta;
                dispatchConversation({
                  type: 'assistantContentReplaced',
                  assistantTurnId: streamMessageId,
                  content: prepareAssistantContentForDisplay(
                    streamContent,
                    hasConfigTool
                  ),
                });
              } else if (event === 'done') {
                if (typeof data.session_id === 'string')
                  streamSessionId = data.session_id;
                if (typeof data.search_term === 'string')
                  streamSearchTerm = data.search_term;
                dispatchStreamEvent(event, data, streamMessageId);
              } else if (event === 'error') {
                throw new Error(
                  formatProviderStreamError(
                    data.detail,
                    t('errors.failedToSendMessage')
                  )
                );
              } else if (streamMessageId) {
                dispatchStreamEvent(event, data, streamMessageId);
              }
            },
          });
          if (streamSessionId)
            dispatchConversation({
              type: 'conversationSessionChanged',
              sessionId: streamSessionId,
            });
          if (streamMessageId)
            dispatchConversation({
              type: 'assistantTurnFinished',
              sessionId: streamSessionId,
            });
          dispatchAdminApply({ type: 'dismissed' });
          if (streamSearchTerm) {
            await triggerAutoSearch(
              streamSearchTerm,
              streamSessionId ?? conversationSessionId
            );
          }
          streamed = true;
        } catch (streamError) {
          if (streamMessageId && streamContent.trim()) {
            dispatchConversation({
              type: 'assistantTurnFailed',
              assistantTurnId: streamMessageId,
              message:
                streamError instanceof Error
                  ? streamError.message
                  : t('errors.failedToSendMessage'),
            });
            return;
          }
          if (streamMessageId) {
            dispatchConversation({
              type: 'assistantTurnFailed',
              assistantTurnId: streamMessageId,
              message:
                streamError instanceof Error
                  ? streamError.message
                  : t('errors.failedToSendMessage'),
            });
          }
          console.warn(
            'Streaming query failed; falling back to non-streaming query:',
            streamError
          );
        }
        if (streamed) return;

        response = await fetch(`${API_BASE}/query`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          credentials: 'include',
          body: JSON.stringify(body),
        });
      } else {
        let streamed = false;
        let streamMessageId: string | null = null;
        let streamContent = '';
        let streamSessionId: string | null = null;
        let streamReportedError = false;
        try {
          await sendLlmChatStreamWithUnifiedTools({
            content,
            tools: backendTools,
            sessionId: conversationSessionId,
            conversationHistory,
            onEvent: (event, payload) => {
              const data = payload as Record<string, unknown>;
              if (event === 'assistant_message_started') {
                if (typeof data.message_id !== 'string')
                  data.message_id = generateMessageId();
                const id = data.message_id as string;
                streamMessageId = id;
                streamSessionId =
                  typeof data.session_id === 'string'
                    ? data.session_id
                    : streamSessionId;
                dispatchConversation({
                  type: 'assistantTurnStarted',
                  id,
                  sessionId: streamSessionId,
                  traceStatus: t('chat.trace.writing', 'Writing answer...'),
                });
              } else if (event === 'answer_delta' && streamMessageId) {
                const delta = typeof data.delta === 'string' ? data.delta : '';
                streamContent += delta;
                dispatchConversation({
                  type: 'assistantContentReplaced',
                  assistantTurnId: streamMessageId,
                  content: prepareAssistantContentForDisplay(
                    streamContent,
                    hasConfigTool
                  ),
                });
              } else if (event === 'done') {
                if (typeof data.session_id === 'string')
                  streamSessionId = data.session_id;
                dispatchStreamEvent(event, data, streamMessageId);
              } else if (event === 'error') {
                streamReportedError = true;
                throw new Error(
                  formatProviderStreamError(
                    typeof data.detail === 'string' ? data.detail : data,
                    t('errors.failedToSendMessage'),
                    { recordAdminInstrumentation: hasConfigTool }
                  )
                );
              } else if (streamMessageId) {
                dispatchStreamEvent(event, data, streamMessageId);
              }
            },
          });
          if (streamSessionId)
            dispatchConversation({
              type: 'conversationSessionChanged',
              sessionId: streamSessionId,
            });
          if (streamMessageId)
            dispatchConversation({
              type: 'assistantTurnFinished',
              sessionId: streamSessionId,
            });
          if (hasConfigTool) {
            const extracted =
              extractAdminAssistantChangeSetStrict(streamContent);
            if (extracted.ok) {
              dispatchAdminApply({
                type: 'changeSetReadyForReview',
                changeSet: extracted.changeSet,
              });
            } else if (streamContent.includes('"requests"')) {
              dispatchAdminApply({
                type: 'parseFailed',
                message: extracted.error,
              });
            }
          } else {
            dispatchAdminApply({ type: 'dismissed' });
          }
          streamed = true;
        } catch (streamError) {
          const errorMessage =
            streamError instanceof Error
              ? streamError.message
              : t('errors.failedToSendMessage');

          stagePendingAdminChangeSet(
            streamContent,
            hasConfigTool,
            dispatchAdminApply
          );

          if (streamMessageId && streamContent.trim()) {
            dispatchConversation({
              type: 'assistantTurnFailed',
              assistantTurnId: streamMessageId,
              message: errorMessage,
            });
            return;
          }

          if (streamReportedError) {
            if (streamMessageId) {
              dispatchConversation({
                type: 'assistantTurnFailed',
                assistantTurnId: streamMessageId,
                message: errorMessage,
              });
            } else {
              dispatchConversation({
                type: 'requestFailed',
                message: errorMessage,
              });
            }
            return;
          }

          if (streamMessageId) {
            dispatchConversation({
              type: 'assistantTurnFailed',
              assistantTurnId: streamMessageId,
              message: errorMessage,
            });
            dispatchConversation({ type: 'requestErrorDismissed' });
          }
          console.warn(
            'Streaming chat failed; falling back to non-streaming chat:',
            streamError
          );
        }
        if (streamed) return;

        response = await sendLlmChatWithUnifiedTools({
          content,
          tools: backendTools,
          sessionId: conversationSessionId,
          conversationHistory,
        });
      }

      const responseIsRag = useRag;

      // Handle auth errors
      if (response.status === 401) {
        // Token invalid/expired
        navigate(isAdmin ? '/admin' : '/login');
        return;
      }
      if (response.status === 403) {
        // Not approved - update localStorage and redirect
        localStorage.setItem(STORAGE_KEYS.USER_APPROVED, 'false');
        navigate('/pending');
        return;
      }

      if (!response.ok) {
        const detail = await readErrorDetail(response);
        throw new Error(
          formatProviderResponseError(detail, `HTTP ${response.status}`, {
            recordAdminInstrumentation: hasConfigTool,
          })
        );
      }

      const data = await response.json();

      let responseContent: string;
      if (responseIsRag) {
        responseContent = data.answer;

        // Save session_id for conversation continuity
        if (data.session_id) {
          dispatchConversation({
            type: 'conversationSessionChanged',
            sessionId: data.session_id,
          });
        }
      } else {
        responseContent = data.message;
        if (data.session_id) {
          dispatchConversation({
            type: 'conversationSessionChanged',
            sessionId: data.session_id,
          });
        }

        if (hasConfigTool) {
          const raw = String(data.message || '');
          const extracted = extractAdminAssistantChangeSetStrict(raw);
          if (extracted.ok) {
            dispatchAdminApply({
              type: 'changeSetReadyForReview',
              changeSet: extracted.changeSet,
            });
          } else if (raw.includes('"requests"')) {
            dispatchAdminApply({
              type: 'parseFailed',
              message: extracted.error,
            });
          }
        } else {
          dispatchAdminApply({ type: 'dismissed' });
        }
      }

      dispatchConversation({
        type: 'assistantTurnCompleted',
        id:
          typeof data.message_id === 'string'
            ? data.message_id
            : generateMessageId(),
        content: prepareAssistantContentForDisplay(
          responseContent,
          hasConfigTool
        ),
        trace: data.trace ?? null,
        sessionId:
          typeof data.session_id === 'string' ? data.session_id : undefined,
      });

      // Handle auto-search if backend returned a search term
      if (responseIsRag && data.search_term) {
        await triggerAutoSearch(
          data.search_term,
          data.session_id ?? conversationSessionId
        );
      }
    } catch (e) {
      dispatchConversation({
        type: 'requestFailed',
        message:
          e instanceof Error ? e.message : t('errors.failedToSendMessage'),
      });
    } finally {
      dispatchConversation({ type: 'assistantTurnFinished' });
    }
  };

  const handleAdminApply = useCallback(
    async (changeSet: AdminAssistantChangeSet) => {
      dispatchAdminApply({ type: 'applyStarted' });
      try {
        const userTypeSlugToId = new Map<string, number>();
        try {
          const existing = await fetchJson<{
            types: Array<{ id: number; name: string }>;
          }>('/admin/user-types');
          for (const ut of existing.types || []) {
            userTypeSlugToId.set(slugify(ut.name), ut.id);
          }
        } catch {
          // Best-effort; we'll still learn mappings from POST responses below.
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
          const parts = path.split('/');
          const idx = parts.findIndex((p) => p === 'user-type');
          if (idx !== -1 && parts[idx + 1]?.startsWith('@type:')) {
            const seg = parts[idx + 1];
            const id = resolveUserTypeId(seg);
            if (typeof id === 'number') parts[idx + 1] = String(id);
          }
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

        const postApplyNotes: string[] = [];
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
        dispatchAdminApply({ type: 'applySucceeded', message: summary });
        dispatchConversation({
          type: 'assistantTurnAppended',
          id: generateMessageId(),
          content: summary,
        });
      } catch (e) {
        dispatchAdminApply({
          type: 'applyFailed',
          message: e instanceof Error ? e.message : String(e),
        });
      }
    },
    [fetchJson, t]
  );

  // Auto-search triggered by backend - injects results back into RAG session
  const triggerAutoSearch = async (
    searchTerm: string,
    sessionId?: string | null
  ) => {
    try {
      // Show searching indicator
      const searchingMessage: Message = {
        id: generateMessageId(),
        role: 'assistant',
        content: t('chat.messages.searching', { term: searchTerm }),
        timestamp: new Date(),
      };
      dispatchConversation({
        type: 'assistantTurnAppended',
        id: searchingMessage.id,
        content: searchingMessage.content,
      });

      // Build context-aware search prompt with condensing instructions
      const searchPrompt = `Search for: ${searchTerm}

IMPORTANT: Return a CONDENSED response:
- A brief table (3-5 rows max) with Name, Contact, and Notes columns
- 2-3 sentences of practical advice
- NO lengthy explanations or backgrounds
- Focus on actionable contacts and next steps`;

      // Call the same shared chat path used by the main chat send flow.
      const searchRes = await sendLlmChatWithUnifiedTools({
        content: searchPrompt,
        tools: ['web-search'],
        sessionId,
      });

      if (!searchRes.ok) {
        throw new Error(t('errors.searchFailed', { status: searchRes.status }));
      }

      const searchData = await searchRes.json();
      if (searchData.session_id) {
        dispatchConversation({
          type: 'conversationSessionChanged',
          sessionId: searchData.session_id,
        });
      }
      const searchResults = searchData.message;

      // Replace searching message with condensed results
      const searchResultMessage: Message = {
        id: generateMessageId(),
        role: 'assistant',
        content: `${t('chat.messages.searchResults', { term: searchTerm })}\n\n${searchResults}`,
        timestamp: new Date(),
      };

      // Remove the "Searching..." message and add results
      const searchingPrefix = `🔍 ${t('chat.messages.searchingPrefix')}`;
      dispatchConversation({
        type: 'assistantTurnsRemovedByContentPrefix',
        prefix: searchingPrefix,
      });
      dispatchConversation({
        type: 'assistantTurnAppended',
        id: searchResultMessage.id,
        content: searchResultMessage.content,
      });

      // Inject search results back into RAG session for context continuity
      const injectionSessionId = searchData.session_id ?? sessionId;
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
            top_k: 1, // Minimal retrieval since this is just context injection
            tools: [], // No tools for this update
          }),
        }).catch(() => {
          // Silent failure - session update is best-effort
        });
      }
    } catch (e) {
      console.error('Auto-search failed:', e);
      // Remove searching message on error
      const searchingPrefix = `🔍 ${t('chat.messages.searchingPrefix')}`;
      dispatchConversation({
        type: 'assistantTurnsRemovedByContentPrefix',
        prefix: searchingPrefix,
      });
    }
  };

  const handleNewChat = () => {
    dispatchConversation({ type: 'newConversationStarted' });
    dispatchAdminApply({ type: 'newConversationStarted' });
  };

  const rightActions = (
    <>
      {reachoutEnabled && (
        <IconButton
          label={t(
            `reachout.mode.${reachoutMode}.openButton`,
            reachoutMode === 'feedback'
              ? 'Send feedback'
              : reachoutMode === 'help'
                ? 'Get help'
                : 'Contact support'
          )}
          onClick={() => setReachoutOpen(true)}
          title={t(
            `reachout.mode.${reachoutMode}.openButton`,
            reachoutMode === 'feedback'
              ? 'Send feedback'
              : reachoutMode === 'help'
                ? 'Get help'
                : 'Contact support'
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
    </>
  );

  const header = <AppHeader rightActions={rightActions} />;
  const sessionTitle =
    messages.find((message) => message.role === 'user')?.content.trim() ||
    t('chat.sessions.current', 'Current chat');
  const sessionMeta =
    messages.length === 0
      ? t('chat.sessions.empty', 'Empty')
      : t('chat.sessions.messageCount', {
          count: messages.length,
          defaultValue:
            messages.length === 1 ? '1 message' : `${messages.length} messages`,
        });
  const sessionSidebar = (
    <nav
      aria-label={t('chat.sessions.ariaLabel', 'Chat sessions')}
      className="flex h-full flex-col gap-3 p-3"
    >
      <Button
        onClick={handleNewChat}
        variant="primary"
        size="sm"
        leadingIcon={<Plus className="h-4 w-4" aria-hidden="true" />}
        className="w-full justify-start"
      >
        {t('chat.new', 'New chat')}
      </Button>
      <div className="space-y-1">
        <div className="px-2 text-[11px] font-medium uppercase tracking-[0.08em] text-text-muted">
          {t('chat.listTitle', 'Chats')}
        </div>
        <button
          type="button"
          aria-current="page"
          aria-label={`${sessionTitle} ${sessionMeta}`}
          className="flex w-full items-center gap-2 rounded-lg border border-border bg-surface px-2.5 py-2 text-left text-sm text-text shadow-sm"
        >
          <MessageSquare
            className="h-4 w-4 shrink-0 text-accent"
            aria-hidden="true"
          />
          <span className="min-w-0 flex-1">
            <span className="block truncate">{sessionTitle}</span>
            <span className="block truncate text-xs text-text-muted">
              {sessionMeta}
            </span>
          </span>
        </button>
      </div>
      <div className="mt-auto border-t border-border pt-3">
        <ExportButton messages={messages} />
      </div>
    </nav>
  );

  // Admin chat intentionally excludes DocumentScope. Admin tools are Sage-owned
  // assistant tools, while document-grounded retrieval remains a user chat mode.
  const inputToolbar = isAdmin ? (
    <section
      aria-label={t('chat.composerContextAria', 'Composer context')}
      className="flex w-full flex-col gap-2"
    >
      <div className="flex flex-wrap items-center gap-2">
        <ToolSelector
          tools={availableTools}
          selectedTools={selectedTools}
          onToggle={handleToolToggle}
        />
      </div>
    </section>
  ) : (
    <section
      aria-label={t('chat.composerContextAria', 'Composer context')}
      className="flex w-full flex-col gap-2"
    >
      {selectedDocumentSources.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-[11px] font-medium text-text-muted">
            {t('chat.contextTitle', 'Context')}
          </span>
          {selectedDocumentSources.map((document) => (
            <span
              key={document.id}
              className="inline-flex max-w-[14rem] items-center truncate rounded-full border border-border bg-surface px-2 py-1 text-xs text-text-secondary"
              title={document.name}
            >
              {document.name}
            </span>
          ))}
        </div>
      )}
      <div className="flex flex-wrap items-center gap-2">
        <ToolSelector
          tools={availableTools}
          selectedTools={selectedTools}
          onToggle={handleToolToggle}
        />
        <div className="h-4 w-px bg-border" />
        <DocumentScope
          selectedDocuments={selectedDocuments}
          onToggle={handleDocumentToggle}
          documents={documents}
        />
      </div>
    </section>
  );
  const conversationTurns = buildConversationSurfaceTurns(messages);
  const lastAssistantTurnId = useMemo(
    () =>
      [...conversationTurns].reverse().find((turn) => turn.role === 'assistant')
        ?.id ?? null,
    [conversationTurns]
  );
  useEffect(() => {
    if (
      adminApplyState.state === 'review' &&
      lastAssistantTurnId &&
      adminApprovalTurnId !== lastAssistantTurnId
    ) {
      setAdminApprovalTurnId(lastAssistantTurnId);
    }
    if (adminApplyState.state === 'idle' && adminApprovalTurnId) {
      setAdminApprovalTurnId(null);
    }
  }, [adminApplyState.state, adminApprovalTurnId, lastAssistantTurnId]);
  const turnAccessories = useMemo(() => {
    const isApprovalVisible =
      adminApplyState.state === 'review' ||
      adminApplyState.state === 'applying' ||
      adminApplyState.state === 'applied' ||
      adminApplyState.state === 'rejected' ||
      adminApplyState.state === 'error';
    const cardTurnId = adminApprovalTurnId ?? lastAssistantTurnId;
    const changeSet =
      'changeSet' in adminApplyState ? adminApplyState.changeSet : undefined;
    if (
      !isAdmin ||
      !selectedTools.includes(CONFIG_TOOL_ID) ||
      !changeSet ||
      !cardTurnId ||
      !isApprovalVisible
    ) {
      return undefined;
    }

    const preview = buildAdminChangePreview(changeSet, {
      deploymentSecretKeysLoaded,
      deploymentSecretKeys,
    });
    return {
      [cardTurnId]: (
        <AdminChangeApprovalCard
          preview={preview}
          state={adminApplyState.state}
          message={
            'message' in adminApplyState ? adminApplyState.message : undefined
          }
          onApprove={() => handleAdminApply(changeSet)}
          onReject={() => dispatchAdminApply({ type: 'rejected' })}
        />
      ),
    };
  }, [
    adminApprovalTurnId,
    adminApplyState,
    deploymentSecretKeys,
    deploymentSecretKeysLoaded,
    handleAdminApply,
    isAdmin,
    lastAssistantTurnId,
    selectedTools,
  ]);
  const threadNotices = (
    <div className="mt-4 space-y-2">
      {error && (
        <Callout
          label={t('chat.errors.requestLabel', 'Chat request error')}
          tone="error"
          className="flex items-center gap-3 animate-fade-in shadow-sm"
        >
          <AlertCircle
            className="h-4 w-4 shrink-0 text-error"
            aria-hidden="true"
          />
          <span className="flex-1">{error}</span>
          <IconButton
            label={t('common.close', 'Close')}
            onClick={() =>
              dispatchConversation({ type: 'requestErrorDismissed' })
            }
            variant="ghost"
            size="sm"
            className="text-error hover:bg-error/10"
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </IconButton>
        </Callout>
      )}
      {error &&
        isAdmin &&
        selectedTools.includes(CONFIG_TOOL_ID) &&
        shouldOfferNewAssistantConversation(classifyProviderError(error)) && (
          <button
            type="button"
            onClick={handleNewChat}
            className="inline-flex items-center gap-2 px-3 py-2 rounded-xl bg-surface-raised border border-border text-text hover:bg-surface-overlay transition-colors text-sm font-medium"
          >
            {t('admin.configAssistant.startNewConversation')}
          </button>
        )}
      {isAdmin &&
        selectedTools.includes(CONFIG_TOOL_ID) &&
        reducedContextNotice && (
          <div
            role="note"
            aria-label={t(
              'admin.configAssistant.reducedContextNoticeLabel',
              'Reduced context notice'
            )}
            className="rounded-xl border border-warning/25 bg-warning/10 px-3 py-2 text-sm text-warning"
          >
            {reducedContextNotice}
          </div>
        )}
      {isAdmin &&
        selectedTools.includes(CONFIG_TOOL_ID) &&
        adminApplyState.state === 'error' && (
          <Callout
            label={t(
              'admin.configAssistant.applyErrorLabel',
              'Config apply error'
            )}
            tone="error"
          >
            {adminApplyState.message}
          </Callout>
        )}
    </div>
  );

  return (
    <ChatContainer header={header} sidebar={sessionSidebar}>
      <ReachoutModal
        open={reachoutOpen}
        mode={reachoutMode}
        overrides={reachoutOverrides}
        onClose={() => setReachoutOpen(false)}
      />

      <ConversationSurface
        turns={conversationTurns}
        onSend={handleSend}
        isRunning={isLoading}
        placeholder={
          !isAdmin && selectedDocuments.length > 0
            ? t('chat.input.placeholderWithDocs')
            : t('chat.input.placeholder')
        }
        toolbar={inputToolbar}
        turnAccessories={turnAccessories}
        notices={threadNotices}
      />
    </ChatContainer>
  );
}
