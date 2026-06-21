import {
  useState,
  useCallback,
  useEffect,
  useMemo,
  useReducer,
  useRef,
  type Dispatch,
  type FormEvent,
  type Ref,
  type ReactNode,
} from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  AlertCircle,
  BookOpen,
  CheckCircle2,
  ChevronDown,
  Database,
  EyeOff,
  LifeBuoy,
  Mail,
  Pencil,
  Plus,
  Search,
  Settings2,
  MessageSquare,
  ShieldCheck,
  Trash2,
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
import type {
  ConversationActivityStep,
  ConversationTrace,
} from '../components/chat/ChatMessage';
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
import {
  adminFetch,
  isAdminAuthenticated,
  validateAdminSession,
} from '../utils/adminApi';
import {
  sendLlmChatStreamWithUnifiedTools,
  sendLlmChatWithUnifiedTools,
} from '../utils/llmChat';
import { Button, Callout, IconButton } from '../components/ui';
import {
  coerceAdminAssistantChangeSetPayload,
  extractAdminAssistantChangeSetStrict,
  redactAdminDeploymentSecretChangeSets,
  redactSecrets,
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
import { refreshAdminConfigRedactionMetadata } from '../utils/adminConfigContext';

const CONFIG_TOOL_ID = 'admin-config';
const KNOWLEDGE_TOOL_ID = 'knowledge-search';
const CURATED_RESOURCES_TOOL_ID = 'curated-resources';
const ADMIN_ONLY_TOOL_IDS = new Set([CONFIG_TOOL_ID, 'db-query']);
export const ENCLAVE_USER_EMAIL_KEY = STORAGE_KEYS.USER_EMAIL;

type ChatAdminSessionState = 'checking' | 'authenticated' | 'unauthenticated';

function filterToolsForActor(tools: string[], isAdmin: boolean): string[] {
  if (isAdmin) return tools;
  return tools.filter((tool) => !ADMIN_ONLY_TOOL_IDS.has(tool));
}

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

interface ConversationHistorySummary {
  id: string;
  title: string;
  messageCount: number | null;
  updatedAt: string | null;
}

interface ConversationSessionView {
  id: string;
  title: string | null;
  turns: ConversationUiTurn[];
}

function slugify(value: string): string {
  return String(value || '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '');
}

function conversationHistorySummaryFromApi(
  value: unknown
): ConversationHistorySummary | null {
  if (!value || typeof value !== 'object') return null;
  const record = value as Record<string, unknown>;
  if (typeof record.id !== 'string' || !record.id.trim()) return null;
  const rawTitle =
    typeof record.title === 'string' && record.title.trim()
      ? record.title.trim()
      : null;
  const messageCount =
    typeof record.message_count === 'number' &&
    Number.isFinite(record.message_count)
      ? Math.max(0, Math.floor(record.message_count))
      : null;
  const updatedAt =
    typeof record.updated_at === 'string' && record.updated_at.trim()
      ? record.updated_at
      : null;

  return {
    id: record.id,
    title: rawTitle ?? 'Untitled chat',
    messageCount,
    updatedAt,
  };
}

function conversationSessionViewFromApi(
  value: unknown
): ConversationSessionView | null {
  if (!value || typeof value !== 'object') return null;
  const record = value as Record<string, unknown>;
  if (typeof record.id !== 'string' || !record.id.trim()) return null;
  if (!Array.isArray(record.messages)) return null;
  const rawMessages = record.messages;
  return {
    id: record.id,
    title:
      typeof record.title === 'string' && record.title.trim()
        ? record.title.trim()
        : null,
    turns: rawMessages
      .map((message, index) =>
        conversationTurnFromSessionMessage(message, record.id as string, index)
      )
      .filter((turn): turn is ConversationUiTurn => Boolean(turn)),
  };
}

function conversationTurnFromSessionMessage(
  value: unknown,
  sessionId: string,
  index: number
): ConversationUiTurn | null {
  if (!value || typeof value !== 'object') return null;
  const record = value as Record<string, unknown>;
  if (record.role !== 'user' && record.role !== 'assistant') return null;
  if (typeof record.content !== 'string') return null;
  const trace = conversationTraceFromApi(record.trace);
  const activitySteps = activityStepsFromApi(record.activity_steps);
  return {
    id:
      typeof record.id === 'string' && record.id.trim()
        ? record.id
        : `${sessionId}-${index}`,
    role: record.role,
    content: record.content,
    activitySteps:
      activitySteps.length > 0
        ? activitySteps
        : trace?.activity_steps
          ? activityStepsFromApi(trace.activity_steps)
          : [],
    trace,
    traceStatus: null,
  };
}

function conversationTraceFromApi(value: unknown): ConversationTrace | null {
  if (!value || typeof value !== 'object') return null;
  const record = value as Record<string, unknown>;
  if (
    !['off', 'minimal', 'summary', 'detailed'].includes(
      String(record.visibility)
    )
  ) {
    return null;
  }
  if (!isOptionalObjectArray(record.tools)) return null;
  if (!isOptionalObjectArray(record.retrieval)) {
    return null;
  }
  if (!isOptionalObjectArray(record.activity_steps)) {
    return null;
  }
  return record as unknown as ConversationTrace;
}

function isOptionalObjectArray(value: unknown): boolean {
  return (
    value === undefined ||
    (Array.isArray(value) &&
      value.every((item) => Boolean(item) && typeof item === 'object'))
  );
}

function activityStepsFromApi(value: unknown): ConversationActivityStep[] {
  if (!Array.isArray(value)) return [];
  return value
    .map((item): ConversationActivityStep | null => {
      if (!item || typeof item !== 'object') return null;
      const step = item as Record<string, unknown>;
      if (
        typeof step.id !== 'string' ||
        typeof step.kind !== 'string' ||
        typeof step.title !== 'string' ||
        typeof step.status !== 'string'
      ) {
        return null;
      }
      return {
        id: step.id,
        kind: step.kind,
        title: step.title,
        status: step.status,
        summary: typeof step.summary === 'string' ? step.summary : undefined,
        warnings: Array.isArray(step.warnings)
          ? step.warnings.filter(
              (warning): warning is string => typeof warning === 'string'
            )
          : undefined,
      };
    })
    .filter((step): step is ConversationActivityStep => Boolean(step));
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
): AdminAssistantChangeSet | null {
  if (!hasConfigTool || !content.trim()) return null;
  if (!content.includes('"requests"')) return null;

  const extracted = extractAdminAssistantChangeSetStrict(content);
  if (extracted.ok) {
    dispatchAdminApply({
      type: 'changeSetReadyForReview',
      changeSet: extracted.changeSet,
    });
    return extracted.changeSet;
  }
  return null;
}

function stageStructuredAdminChangeSet(
  payload: unknown,
  dispatchAdminApply: Dispatch<AdminChangeConfirmationAction>
): AdminAssistantChangeSet | null {
  if (payload === undefined || payload === null) return null;
  const extracted = coerceAdminAssistantChangeSetPayload(payload);
  if (extracted.ok) {
    dispatchAdminApply({
      type: 'changeSetReadyForReview',
      changeSet: extracted.changeSet,
    });
    return extracted.changeSet;
  }
  dispatchAdminApply({
    type: 'parseFailed',
    message: extracted.error,
  });
  return null;
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
  cardRef,
  approveButtonRef,
}: {
  preview: ReturnType<typeof buildAdminChangePreview>;
  state:
    | 'review'
    | 'applying'
    | 'applied'
    | 'rejected'
    | 'error'
    | 'superseded';
  message?: string;
  onApprove: () => void;
  onReject: () => void;
  cardRef?: Ref<HTMLDivElement>;
  approveButtonRef?: Ref<HTMLButtonElement>;
}) {
  const { t } = useTranslation();
  const [detailsOpen, setDetailsOpen] = useState(false);
  const isApplying = state === 'applying';
  const isFinal =
    state === 'applied' ||
    state === 'rejected' ||
    state === 'error' ||
    state === 'superseded';

  return (
    <div
      ref={cardRef}
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
                'Approve configuration changes'
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
            {state === 'superseded' && (
              <span className="rounded-full bg-surface-overlay px-2 py-0.5 text-[11px] font-medium text-text-secondary">
                {t('admin.configAssistant.superseded', 'Superseded')}
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
            ref={approveButtonRef}
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
  const [adminSessionState, setAdminSessionState] =
    useState<ChatAdminSessionState>(() =>
      isAdminAuthenticated() ? 'checking' : 'unauthenticated'
    );
  const isAdmin = adminSessionState === 'authenticated';
  const adminSessionChecking = adminSessionState === 'checking';
  const [conversationState, dispatchConversation] = useReducer(
    reduceConversationUiState,
    undefined,
    () =>
      createConversationUiState({
        selectedTools: [],
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
  const [supersededAdminApprovals, setSupersededAdminApprovals] = useState<
    Array<{
      turnId: string;
      changeSet: AdminAssistantChangeSet;
    }>
  >([]);
  const adminApprovalCardRef = useRef<HTMLDivElement | null>(null);
  const adminApprovalApproveButtonRef = useRef<HTMLButtonElement | null>(null);
  const [documents, setDocuments] = useState<DocumentSource[]>([]);
  const [sessionDefaultsLoaded, setSessionDefaultsLoaded] = useState(false);
  const [pendingDefaultDocs, setPendingDefaultDocs] = useState<string[]>([]);
  const [deploymentSecretKeys, setDeploymentSecretKeys] = useState<Set<string>>(
    new Set()
  );
  const [deploymentSecretKeysLoaded, setDeploymentSecretKeysLoaded] =
    useState(false);
  const [shareSecrets, setShareSecrets] = useState(false);
  const [secretsForRedaction, setSecretsForRedaction] = useState<string[]>([]);
  const messages = useMemo(
    () => conversationState.turns.map(conversationTurnToMessage),
    [conversationState.turns]
  );
  const selectedTools = conversationState.selectedTools;
  const actorScopedSelectedTools = useMemo(
    () => filterToolsForActor(selectedTools, isAdmin),
    [isAdmin, selectedTools]
  );
  const selectedDocuments = conversationState.selectedDocuments;
  const conversationSessionId = conversationState.conversationSessionId;
  const configToolEnabled = isAdmin && selectedTools.includes(CONFIG_TOOL_ID);
  const prevConversationSessionIdRef = useRef<string | null>(
    conversationSessionId
  );
  const isLoading = conversationState.isRunning;
  const error = conversationState.error;
  const selectedDocumentSources = useMemo(
    () =>
      selectedDocuments
        .map((id) => documents.find((document) => document.id === id))
        .filter((document): document is DocumentSource => Boolean(document)),
    [documents, selectedDocuments]
  );

  useEffect(() => {
    let cancelled = false;

    if (!isAdminAuthenticated()) {
      setAdminSessionState('unauthenticated');
      return;
    }

    setAdminSessionState('checking');
    validateAdminSession()
      .then((state) => {
        if (cancelled) return;
        setAdminSessionState(
          state === 'authenticated' ? 'authenticated' : 'unauthenticated'
        );
      })
      .catch(() => {
        if (!cancelled) setAdminSessionState('unauthenticated');
      });

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (adminSessionChecking || isAdmin) return;
    const filteredTools = filterToolsForActor(selectedTools, false);
    if (filteredTools.length !== selectedTools.length) {
      dispatchConversation({
        type: 'selectedToolsChanged',
        selectedTools: filteredTools,
      });
    }
    setShareSecrets(false);
    setSecretsForRedaction([]);
  }, [adminSessionChecking, isAdmin, selectedTools]);

  useEffect(() => {
    const previousSessionId = prevConversationSessionIdRef.current;
    const sessionWasReset = conversationSessionId === null;
    const sessionWasSwapped =
      previousSessionId !== null && conversationSessionId !== previousSessionId;

    if (!configToolEnabled || sessionWasReset || sessionWasSwapped) {
      setShareSecrets(false);
      setSecretsForRedaction([]);
    }

    prevConversationSessionIdRef.current = conversationSessionId;
  }, [conversationSessionId, configToolEnabled]);

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
  const [sessionMemoryNotice, setSessionMemoryNotice] = useState<string | null>(
    null
  );
  const [conversationHistory, setConversationHistory] = useState<
    ConversationHistorySummary[]
  >([]);
  const [conversationHistoryStatus, setConversationHistoryStatus] = useState<
    'loading' | 'ready' | 'error'
  >('loading');
  const [activeConversationTitle, setActiveConversationTitle] = useState<
    string | null
  >(null);
  const [renameDraft, setRenameDraft] = useState<{
    id: string;
    title: string;
  } | null>(null);
  const [renameStatus, setRenameStatus] = useState<'idle' | 'saving' | 'error'>(
    'idle'
  );
  const [renameError, setRenameError] = useState<string | null>(null);
  const [deleteDraft, setDeleteDraft] =
    useState<ConversationHistorySummary | null>(null);
  const [deleteStatus, setDeleteStatus] = useState<
    'idle' | 'deleting' | 'error'
  >('idle');
  const [deleteError, setDeleteError] = useState<string | null>(null);

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
        id: KNOWLEDGE_TOOL_ID,
        name: t('chat.tools.knowledgeSearchName', 'Knowledge'),
        description: t(
          'chat.tools.knowledgeSearch',
          'Search uploaded documents and knowledge chunks'
        ),
        icon: <BookOpen className="h-3.5 w-3.5" aria-hidden="true" />,
      },
      {
        id: CURATED_RESOURCES_TOOL_ID,
        name: t('chat.tools.curatedResourcesName', 'Resources'),
        description: t(
          'chat.tools.curatedResources',
          'Find admin-vetted referral resources and trusted organizations'
        ),
        icon: <LifeBuoy className="h-3.5 w-3.5" aria-hidden="true" />,
      },
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

  const handleShareSecretsToggle = useCallback(
    async (checked: boolean) => {
      setShareSecrets(checked);
      if (!checked) {
        setSecretsForRedaction([]);
        return;
      }
      try {
        const metadata = await refreshAdminConfigRedactionMetadata({
          shareSecrets: true,
          fetchJson,
        });
        setSecretsForRedaction(metadata.secretValues);
        setDeploymentSecretKeys(metadata.deploymentSecretKeys);
        setDeploymentSecretKeysLoaded(true);
      } catch {
        setSecretsForRedaction([]);
      }
    },
    [fetchJson]
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

  const loadConversationHistory = useCallback(async () => {
    setConversationHistoryStatus('loading');
    try {
      const res = await fetch(`${API_BASE}/query/sessions`, {
        credentials: 'include',
      });
      if (!res.ok) {
        setConversationHistoryStatus('error');
        return;
      }

      const payload = await res.json();
      const rawConversations: unknown[] = Array.isArray(payload?.conversations)
        ? payload.conversations
        : [];
      setConversationHistory(
        rawConversations
          .map(conversationHistorySummaryFromApi)
          .filter((conversation): conversation is ConversationHistorySummary =>
            Boolean(conversation)
          )
      );
      setConversationHistoryStatus('ready');
    } catch {
      setConversationHistoryStatus('error');
    }
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function fetchConversationHistory() {
      await loadConversationHistory();
      if (cancelled) return;
    }

    fetchConversationHistory();

    return () => {
      cancelled = true;
    };
  }, [loadConversationHistory]);

  // Check auth and approval status on mount
  useEffect(() => {
    if (adminSessionChecking) return;

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
  }, [adminSessionChecking, isAdmin, navigate]);

  // Fetch session defaults from admin config
  useEffect(() => {
    if (sessionDefaultsLoaded || adminSessionChecking) return;

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
          // Admin config sidebar: config-only by default, no inherited web-search
          if (isAdmin) {
            dispatchConversation({
              type: 'selectedToolsChanged',
              selectedTools: [CONFIG_TOOL_ID],
            });
          } else {
            const hasDefaultDocuments =
              Array.isArray(data.default_document_ids) &&
              data.default_document_ids.length > 0;
            const defaultTools = [
              CURATED_RESOURCES_TOOL_ID,
              ...(hasDefaultDocuments ? [KNOWLEDGE_TOOL_ID] : []),
              ...(data.web_search_enabled ? ['web-search'] : []),
            ];
            dispatchConversation({
              type: 'selectedToolsChanged',
              selectedTools: defaultTools,
            });
          }
          // Store default document IDs to apply once documents are loaded
          if (
            data.default_document_ids &&
            data.default_document_ids.length > 0
          ) {
            setPendingDefaultDocs(data.default_document_ids);
          }
        } else {
          // Non-2xx response - fall back to web search enabled by default (non-admin only)
          console.warn('Failed to fetch session defaults:', res.status);
          dispatchConversation({
            type: 'selectedToolsChanged',
            selectedTools: isAdmin
              ? [CONFIG_TOOL_ID]
              : [CURATED_RESOURCES_TOOL_ID, 'web-search'],
          });
        }
      } catch (err) {
        console.error('Failed to fetch session defaults:', err);
        // Fall back to web search enabled by default on error (non-admin only)
        dispatchConversation({
          type: 'selectedToolsChanged',
          selectedTools: isAdmin
            ? [CONFIG_TOOL_ID]
            : [CURATED_RESOURCES_TOOL_ID, 'web-search'],
        });
      } finally {
        setSessionDefaultsLoaded(true);
      }
    };

    fetchSessionDefaults();
  }, [adminSessionChecking, isAdmin, sessionDefaultsLoaded]);

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
      if (!isAdmin && ADMIN_ONLY_TOOL_IDS.has(toolId)) return;

      const selectedAfterToggle = !selectedTools.includes(toolId);
      if (toolId === CONFIG_TOOL_ID) {
        dispatchAdminApply({
          type: 'adminConfigToolToggled',
          selectedAfterToggle,
        });
        if (!selectedAfterToggle) {
          setShareSecrets(false);
          setSecretsForRedaction([]);
        }
      }
      dispatchConversation({ type: 'toolToggled', toolId });
    },
    [isAdmin, selectedTools]
  );

  const handleDocumentToggle = useCallback(
    (docId: string) => {
      const selectedAfterToggle = !selectedDocuments.includes(docId);
      dispatchConversation({ type: 'documentToggled', documentId: docId });
      if (selectedAfterToggle && !selectedTools.includes(KNOWLEDGE_TOOL_ID)) {
        dispatchConversation({
          type: 'toolToggled',
          toolId: KNOWLEDGE_TOOL_ID,
        });
      }
    },
    [selectedDocuments, selectedTools]
  );

  const handleConversationSelect = useCallback(
    async (conversation: ConversationHistorySummary) => {
      try {
        const res = await fetch(
          `${API_BASE}/query/session/${encodeURIComponent(conversation.id)}`,
          {
            credentials: 'include',
          }
        );
        if (!res.ok) {
          dispatchConversation({
            type: 'requestFailed',
            message: await readErrorDetail(res),
          });
          return;
        }
        const payload = await res.json();
        const view = conversationSessionViewFromApi(payload);
        if (!view) {
          dispatchConversation({
            type: 'requestFailed',
            message: t(
              'chat.sessions.resumeInvalid',
              'Unable to load that Conversation.'
            ),
          });
          return;
        }
        dispatchConversation({
          type: 'conversationHydrated',
          sessionId: view.id,
          turns: view.turns,
        });
        setActiveConversationTitle(view.title ?? conversation.title);
        dispatchAdminApply({ type: 'newConversationStarted' });
        setSupersededAdminApprovals([]);
        setSessionMemoryNotice(null);
        setReducedContextNotice(null);
        setRenameDraft(null);
        setRenameStatus('idle');
        setRenameError(null);
        setDeleteDraft(null);
        setDeleteStatus('idle');
        setDeleteError(null);
      } catch (err) {
        dispatchConversation({
          type: 'requestFailed',
          message:
            err instanceof Error
              ? err.message
              : t(
                  'chat.sessions.resumeInvalid',
                  'Unable to load that Conversation.'
                ),
        });
      }
    },
    [t]
  );

  const handleRenameSubmit = useCallback(
    async (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      if (!renameDraft) return;
      const title = renameDraft.title.trim();
      if (!title) {
        setRenameStatus('error');
        setRenameError(
          t('chat.sessions.renameEmpty', 'Conversation title is required.')
        );
        return;
      }

      setRenameStatus('saving');
      setRenameError(null);
      try {
        const res = await fetch(
          `${API_BASE}/query/session/${encodeURIComponent(renameDraft.id)}`,
          {
            method: 'PATCH',
            headers: {
              'Content-Type': 'application/json',
            },
            credentials: 'include',
            body: JSON.stringify({ title }),
          }
        );
        if (!res.ok) {
          throw new Error(await readErrorDetail(res));
        }
        const payload = await res.json();
        const confirmedTitle =
          typeof payload?.title === 'string' && payload.title.trim()
            ? payload.title.trim()
            : title;

        setConversationHistory((existing) =>
          existing.map((conversation) =>
            conversation.id === renameDraft.id
              ? { ...conversation, title: confirmedTitle }
              : conversation
          )
        );
        if (conversationSessionId === renameDraft.id) {
          setActiveConversationTitle(confirmedTitle);
        }
        setRenameDraft(null);
        setRenameStatus('idle');
      } catch (err) {
        setRenameStatus('error');
        setRenameError(
          err instanceof Error
            ? err.message
            : t('chat.sessions.renameError', 'Unable to rename Conversation.')
        );
      }
    },
    [conversationSessionId, renameDraft, t]
  );

  const handleDeleteConversation = useCallback(async () => {
    if (!deleteDraft) return;

    setDeleteStatus('deleting');
    setDeleteError(null);
    try {
      const res = await fetch(
        `${API_BASE}/query/session/${encodeURIComponent(deleteDraft.id)}`,
        {
          method: 'DELETE',
          credentials: 'include',
        }
      );
      if (!res.ok) {
        throw new Error(await readErrorDetail(res));
      }

      setConversationHistory((existing) =>
        existing.filter((conversation) => conversation.id !== deleteDraft.id)
      );
      if (conversationSessionId === deleteDraft.id) {
        dispatchConversation({ type: 'newConversationStarted' });
        dispatchAdminApply({ type: 'newConversationStarted' });
        setSupersededAdminApprovals([]);
        setSessionMemoryNotice(null);
        setReducedContextNotice(null);
        setActiveConversationTitle(null);
      }
      setDeleteDraft(null);
      setDeleteStatus('idle');
      setDeleteError(null);
    } catch (err) {
      setDeleteStatus('error');
      setDeleteError(
        err instanceof Error
          ? err.message
          : t('chat.sessions.deleteError', 'Unable to delete Conversation.')
      );
    }
  }, [conversationSessionId, deleteDraft, t]);

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

  const stageAdminChangeSetForTurn = useCallback(
    (turnId: string | null | undefined) => {
      if (!turnId) return;
      if (
        (adminApplyState.state === 'review' ||
          adminApplyState.state === 'applying') &&
        adminApprovalTurnId
      ) {
        setSupersededAdminApprovals((existing) => {
          if (
            existing.some((approval) => approval.turnId === adminApprovalTurnId)
          )
            return existing;
          return [
            ...existing,
            {
              turnId: adminApprovalTurnId,
              changeSet: adminApplyState.changeSet,
            },
          ];
        });
      }
      setAdminApprovalTurnId(turnId);
    },
    [adminApplyState, adminApprovalTurnId]
  );

  const focusPendingAdminApproval = useCallback(() => {
    const focusApproval = () => {
      adminApprovalCardRef.current?.scrollIntoView({
        block: 'nearest',
        behavior: 'smooth',
      });
      adminApprovalApproveButtonRef.current?.focus();
    };

    focusApproval();
    window.setTimeout(focusApproval, 0);
  }, []);

  const handleSend = async (content: string) => {
    const hasConfigTool = configToolEnabled;
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
      focusPendingAdminApproval();
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

    if (applyIntent.kind === 'no-pending') {
      dispatchConversation({
        type: 'assistantTurnAppended',
        id: generateMessageId(),
        content: t(
          'admin.configAssistant.applyIntentNoPending',
          'There are no pending configuration changes to apply. Ask the assistant to propose a change set first.'
        ),
      });
      dispatchConversation({ type: 'assistantTurnFinished' });
      return;
    }

    try {
      const backendTools =
        selectedDocuments.length > 0 &&
        !actorScopedSelectedTools.includes(KNOWLEDGE_TOOL_ID)
          ? [...actorScopedSelectedTools, KNOWLEDGE_TOOL_ID]
          : actorScopedSelectedTools;
      let conversationHistory = messages.map(
        ({ role, content: turnContent }) => ({
          role,
          content: turnContent,
        })
      );
      let secretsForThisRequest = secretsForRedaction;
      if (hasConfigTool) {
        const sessionMemoryPlan = compactAdminSessionMemory({
          conversationHistory,
        });
        setSessionMemoryNotice(
          sessionMemoryPlan.compacted
            ? t(
                'admin.configAssistant.sessionMemoryNotice',
                'Older context was summarized to keep this conversation going.'
              )
            : null
        );

        if (shareSecrets) {
          const metadata = await refreshAdminConfigRedactionMetadata({
            shareSecrets: true,
            fetchJson,
          });
          secretsForThisRequest = metadata.secretValues;
          setSecretsForRedaction(metadata.secretValues);
        }

        const promptPlan = planAdminPromptBudget({
          conversationHistory: sessionMemoryPlan.conversationHistory,
        });
        conversationHistory = promptPlan.conversationHistory;
        setReducedContextNotice(
          formatAdminReducedContextNotice(promptPlan.reducedSections, {
            sectionLabels: {
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
        setSessionMemoryNotice(null);
      }

      let response: Response;
      {
        let streamed = false;
        let streamMessageId: string | null = null;
        let streamContent = '';
        let streamSessionId: string | null = null;
        let streamReportedError = false;
        let sawStructuredChangeSetPayload = false;
        let structuredChangeSet: AdminAssistantChangeSet | null = null;
        const stageStructuredForCurrentTurn = (payload: unknown) => {
          if (payload !== undefined && payload !== null) {
            sawStructuredChangeSetPayload = true;
          }
          if (structuredChangeSet) return;
          const staged = stageStructuredAdminChangeSet(
            payload,
            dispatchAdminApply
          );
          if (staged) {
            structuredChangeSet = staged;
            stageAdminChangeSetForTurn(streamMessageId);
          }
        };
        try {
          await sendLlmChatStreamWithUnifiedTools({
            content,
            tools: backendTools,
            sessionId: conversationSessionId,
            jobIds: selectedDocuments,
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
                  traceStatus: t(
                    'chat.trace.finalizing',
                    'Finalizing response...'
                  ),
                });
              } else if (event === 'answer_delta' && streamMessageId) {
                const delta = typeof data.delta === 'string' ? data.delta : '';
                streamContent += delta;
                dispatchConversation({
                  type: 'assistantContentReplaced',
                  assistantTurnId: streamMessageId,
                  content: prepareAssistantContentForDisplay(
                    shareSecrets
                      ? redactSecrets(streamContent, secretsForThisRequest)
                      : streamContent,
                    hasConfigTool
                  ),
                });
              } else if (event === 'done') {
                if (typeof data.session_id === 'string')
                  streamSessionId = data.session_id;
                stageStructuredForCurrentTurn(data.admin_change_set);
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
                stageStructuredForCurrentTurn(data.admin_change_set);
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
          if (hasConfigTool && !structuredChangeSet) {
            const extracted =
              extractAdminAssistantChangeSetStrict(streamContent);
            if (extracted.ok) {
              stageAdminChangeSetForTurn(streamMessageId);
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
          } else if (!hasConfigTool && !sawStructuredChangeSetPayload) {
            dispatchAdminApply({ type: 'dismissed' });
          }
          streamed = true;
        } catch (streamError) {
          const errorMessage =
            streamError instanceof Error
              ? streamError.message
              : t('errors.failedToSendMessage');

          const stagedChangeSet = stagePendingAdminChangeSet(
            streamContent,
            hasConfigTool,
            dispatchAdminApply
          );
          if (stagedChangeSet) stageAdminChangeSetForTurn(streamMessageId);

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
        if (streamed) {
          await loadConversationHistory();
          return;
        }

        response = await sendLlmChatWithUnifiedTools({
          content,
          tools: backendTools,
          sessionId: conversationSessionId,
          jobIds: selectedDocuments,
          conversationHistory,
        });
      }

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

      const responseContent = data.message;
      if (data.session_id) {
        dispatchConversation({
          type: 'conversationSessionChanged',
          sessionId: data.session_id,
        });
      }

      const hasStructuredChangeSetPayload =
        data.admin_change_set !== undefined && data.admin_change_set !== null;
      if (hasConfigTool || hasStructuredChangeSetPayload) {
        const structuredChangeSet = stageStructuredAdminChangeSet(
          data.admin_change_set,
          dispatchAdminApply
        );
        if (structuredChangeSet) {
          stageAdminChangeSetForTurn(
            typeof data.message_id === 'string' ? data.message_id : null
          );
        }
        const raw = String(data.message || '');
        if (hasConfigTool && !structuredChangeSet) {
          const extracted = extractAdminAssistantChangeSetStrict(raw);
          if (extracted.ok) {
            stageAdminChangeSetForTurn(
              typeof data.message_id === 'string' ? data.message_id : null
            );
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
        }
      } else {
        dispatchAdminApply({ type: 'dismissed' });
      }

      dispatchConversation({
        type: 'assistantTurnCompleted',
        id:
          typeof data.message_id === 'string'
            ? data.message_id
            : generateMessageId(),
        content: prepareAssistantContentForDisplay(
          shareSecrets
            ? redactSecrets(responseContent, secretsForThisRequest)
            : responseContent,
          hasConfigTool
        ),
        trace: data.trace ?? null,
        sessionId:
          typeof data.session_id === 'string' ? data.session_id : undefined,
      });

      await loadConversationHistory();
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

  const handleNewChat = () => {
    dispatchConversation({ type: 'newConversationStarted' });
    dispatchAdminApply({ type: 'newConversationStarted' });
    setSupersededAdminApprovals([]);
    setSessionMemoryNotice(null);
    setReducedContextNotice(null);
    setShareSecrets(false);
    setSecretsForRedaction([]);
    setActiveConversationTitle(null);
    setRenameDraft(null);
    setRenameStatus('idle');
    setRenameError(null);
    setDeleteDraft(null);
    setDeleteStatus('idle');
    setDeleteError(null);
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
  const activeHistoryConversation = conversationHistory.find(
    (conversation) => conversation.id === conversationSessionId
  );
  const sessionTitle =
    activeHistoryConversation?.title ||
    activeConversationTitle ||
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
        data-dismiss-sidebar="true"
      >
        {t('chat.new', 'New chat')}
      </Button>
      <div className="space-y-1">
        <div className="px-2 text-[11px] font-medium uppercase tracking-[0.08em] text-text-muted">
          {t('chat.listTitle', 'Chats')}
        </div>
        {conversationHistoryStatus === 'loading' && (
          <div className="px-2 py-1 text-xs text-text-muted">
            {t('chat.sessions.loading', 'Loading chats...')}
          </div>
        )}
        {conversationHistoryStatus === 'error' && (
          <div role="note" className="px-2 py-1 text-xs text-text-muted">
            {t('chat.sessions.error', 'Unable to load chats')}
          </div>
        )}
        {conversationHistory.map((conversation) => {
          const meta =
            conversation.messageCount === null
              ? t('chat.sessions.saved', 'Saved chat')
              : t('chat.sessions.messageCount', {
                  count: conversation.messageCount,
                  defaultValue:
                    conversation.messageCount === 1
                      ? '1 message'
                      : `${conversation.messageCount} messages`,
                });
          if (deleteDraft?.id === conversation.id) {
            return (
              <div
                key={conversation.id}
                className="rounded-lg border border-danger/40 bg-surface p-2"
              >
                <div className="text-sm font-medium text-text">
                  {t('chat.sessions.deleteConfirmTitle', {
                    title: conversation.title,
                    defaultValue: `Delete "${conversation.title}"?`,
                  })}
                </div>
                <div className="mt-1 text-xs text-text-muted">
                  {t(
                    'chat.sessions.deleteConfirmBody',
                    'This removes the saved Conversation and its Session Memory.'
                  )}
                </div>
                <div className="mt-2 flex items-center justify-end gap-1">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      setDeleteDraft(null);
                      setDeleteStatus('idle');
                      setDeleteError(null);
                    }}
                    disabled={deleteStatus === 'deleting'}
                    aria-label={t(
                      'chat.sessions.deleteCancel',
                      'Cancel conversation delete'
                    )}
                  >
                    {t('chat.sessions.cancel', 'Cancel')}
                  </Button>
                  <Button
                    variant="danger"
                    size="sm"
                    onClick={handleDeleteConversation}
                    disabled={deleteStatus === 'deleting'}
                  >
                    {t('chat.sessions.deleteConfirm', 'Delete conversation')}
                  </Button>
                </div>
                {deleteStatus === 'deleting' && (
                  <div role="status" className="mt-1 text-xs text-text-muted">
                    {t('chat.sessions.deleteDeleting', 'Deleting...')}
                  </div>
                )}
                {deleteStatus === 'error' && deleteError && (
                  <div role="note" className="mt-1 text-xs text-danger">
                    {deleteError}
                  </div>
                )}
              </div>
            );
          }
          if (renameDraft?.id === conversation.id) {
            return (
              <form
                key={conversation.id}
                onSubmit={handleRenameSubmit}
                className="rounded-lg border border-border bg-surface p-2"
              >
                <label
                  htmlFor={`conversation-title-${conversation.id}`}
                  className="sr-only"
                >
                  {t('chat.sessions.renameInput', 'Conversation title')}
                </label>
                <input
                  id={`conversation-title-${conversation.id}`}
                  value={renameDraft.title}
                  onChange={(event) =>
                    setRenameDraft({
                      id: conversation.id,
                      title: event.target.value,
                    })
                  }
                  className="w-full rounded-md border border-border bg-surface-raised px-2 py-1.5 text-sm text-text focus-ring"
                  aria-invalid={renameStatus === 'error' ? true : undefined}
                  autoFocus
                />
                <div className="mt-2 flex items-center justify-end gap-1">
                  <IconButton
                    label={t(
                      'chat.sessions.renameCancel',
                      'Cancel conversation rename'
                    )}
                    title={t(
                      'chat.sessions.renameCancel',
                      'Cancel conversation rename'
                    )}
                    onClick={() => {
                      setRenameDraft(null);
                      setRenameStatus('idle');
                      setRenameError(null);
                    }}
                    disabled={renameStatus === 'saving'}
                  >
                    <X className="h-4 w-4" aria-hidden="true" />
                  </IconButton>
                  <IconButton
                    label={t(
                      'chat.sessions.renameSave',
                      'Save conversation title'
                    )}
                    title={t(
                      'chat.sessions.renameSave',
                      'Save conversation title'
                    )}
                    type="submit"
                    disabled={renameStatus === 'saving'}
                  >
                    <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
                  </IconButton>
                </div>
                {renameStatus === 'saving' && (
                  <div role="status" className="mt-1 text-xs text-text-muted">
                    {t('chat.sessions.renameSaving', 'Renaming...')}
                  </div>
                )}
                {renameStatus === 'error' && renameError && (
                  <div role="note" className="mt-1 text-xs text-danger">
                    {renameError}
                  </div>
                )}
              </form>
            );
          }
          return (
            <div
              key={conversation.id}
              className={
                conversation.id === conversationSessionId
                  ? 'flex w-full items-center gap-1 rounded-lg border border-border bg-surface px-2 py-1.5 text-sm text-text shadow-sm'
                  : 'flex w-full items-center gap-1 rounded-lg px-2 py-1.5 text-sm text-text transition-colors hover:bg-surface-overlay'
              }
            >
              <button
                type="button"
                onClick={() => handleConversationSelect(conversation)}
                aria-current={
                  conversation.id === conversationSessionId ? 'page' : undefined
                }
                aria-label={`${conversation.title} ${meta}`}
                className="flex min-w-0 flex-1 items-center gap-2 rounded-md px-0.5 py-0.5 text-left"
                data-dismiss-sidebar="true"
              >
                <MessageSquare
                  className="h-4 w-4 shrink-0 text-text-muted"
                  aria-hidden="true"
                />
                <span className="min-w-0 flex-1">
                  <span className="block truncate">{conversation.title}</span>
                  <span className="block truncate text-xs text-text-muted">
                    {meta}
                  </span>
                </span>
              </button>
              <IconButton
                label={t('chat.sessions.rename', {
                  title: conversation.title,
                  defaultValue: `Rename ${conversation.title}`,
                })}
                title={t('chat.sessions.rename', {
                  title: conversation.title,
                  defaultValue: `Rename ${conversation.title}`,
                })}
                onClick={() => {
                  setRenameDraft({
                    id: conversation.id,
                    title: conversation.title,
                  });
                  setRenameStatus('idle');
                  setRenameError(null);
                  setDeleteDraft(null);
                  setDeleteStatus('idle');
                  setDeleteError(null);
                }}
                className="h-8 w-8 p-1.5"
              >
                <Pencil className="h-3.5 w-3.5" aria-hidden="true" />
              </IconButton>
              <IconButton
                label={t('chat.sessions.delete', {
                  title: conversation.title,
                  defaultValue: `Delete ${conversation.title}`,
                })}
                title={t('chat.sessions.delete', {
                  title: conversation.title,
                  defaultValue: `Delete ${conversation.title}`,
                })}
                onClick={() => {
                  setDeleteDraft(conversation);
                  setDeleteStatus('idle');
                  setDeleteError(null);
                  setRenameDraft(null);
                  setRenameStatus('idle');
                  setRenameError(null);
                }}
                variant="danger"
                className="h-8 w-8 p-1.5"
              >
                <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
              </IconButton>
            </div>
          );
        })}
        {!activeHistoryConversation && (
          <button
            type="button"
            aria-current="page"
            aria-label={`${sessionTitle} ${sessionMeta}`}
            className="flex w-full items-center gap-2 rounded-lg border border-border bg-surface px-2.5 py-2 text-left text-sm text-text shadow-sm"
            data-dismiss-sidebar="true"
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
        )}
      </div>
      <div className="mt-auto border-t border-border pt-3">
        <ExportButton messages={messages} />
      </div>
    </nav>
  );
  const conversationTopbar = (
    <div
      role="region"
      aria-label={t('chat.currentChatAria', 'Current chat')}
      className="mx-auto flex w-full max-w-3xl items-center justify-between gap-3"
    >
      <div className="min-w-0">
        <div className="truncate text-sm font-semibold text-text">
          {sessionTitle}
        </div>
        <div className="truncate text-xs text-text-muted">{sessionMeta}</div>
      </div>
      <Button
        onClick={handleNewChat}
        aria-label={t('chat.newFromCurrent', 'Start a new chat')}
        variant="secondary"
        size="sm"
        leadingIcon={<Plus className="h-4 w-4" aria-hidden="true" />}
        className="shrink-0"
      >
        {t('chat.new', 'New chat')}
      </Button>
    </div>
  );

  // Tool Sets stay visible in the composer; admin-only capabilities are gated
  // through the available tool list.
  const inputToolbar = isAdmin ? (
    <section
      aria-label={t('chat.composerContextAria', 'Composer context')}
      className="flex w-full flex-col gap-2"
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-[11px] font-medium text-text-muted">
          {t('chat.tools.label', 'Tools')}
        </span>
        <ToolSelector
          tools={availableTools}
          selectedTools={selectedTools}
          onToggle={handleToolToggle}
          compact
        />
        {isAdmin && selectedTools.includes(CONFIG_TOOL_ID) && (
          <>
            <div className="h-4 w-px bg-border" />
            <label
              htmlFor="share-secrets-toggle-compact"
              className="flex items-center gap-2 cursor-pointer"
            >
              <input
                id="share-secrets-toggle-compact"
                type="checkbox"
                checked={shareSecrets}
                onChange={(e) => {
                  void handleShareSecretsToggle(e.target.checked);
                }}
                className="w-3 h-3"
              />
              <EyeOff className="w-3 h-3 text-text-muted" />
              <span className="text-[10px] text-text-muted">
                {t(
                  'admin.configAssistant.shareSecretsTitle',
                  'Share secret env vars'
                )}
              </span>
            </label>
          </>
        )}
        {selectedTools.includes(KNOWLEDGE_TOOL_ID) && (
          <>
            <div className="h-4 w-px bg-border" />
            <span className="text-[11px] font-medium text-text-muted">
              {t('chat.documentsContextTitle', 'Documents')}
            </span>
            <DocumentScope
              selectedDocuments={selectedDocuments}
              onToggle={handleDocumentToggle}
              documents={documents}
              compact
            />
          </>
        )}
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
            {t('chat.documentsContextTitle', 'Documents')}
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
        <span className="text-[11px] font-medium text-text-muted">
          {t('chat.tools.label', 'Tools')}
        </span>
        <ToolSelector
          tools={availableTools}
          selectedTools={selectedTools}
          onToggle={handleToolToggle}
          compact
        />
        {isAdmin && selectedTools.includes(CONFIG_TOOL_ID) && (
          <>
            <div className="h-4 w-px bg-border" />
            <label
              htmlFor="share-secrets-toggle"
              className="flex items-center gap-2 cursor-pointer"
            >
              <input
                id="share-secrets-toggle"
                type="checkbox"
                checked={shareSecrets}
                onChange={(e) => {
                  void handleShareSecretsToggle(e.target.checked);
                }}
                className="w-3 h-3"
              />
              <EyeOff className="w-3 h-3 text-text-muted" />
              <span className="text-[10px] text-text-muted">
                {t(
                  'admin.configAssistant.shareSecretsTitle',
                  'Share secret env vars'
                )}
              </span>
            </label>
          </>
        )}
        <div className="h-4 w-px bg-border" />
        <span className="text-[11px] font-medium text-text-muted">
          {t('chat.documentsContextTitle', 'Documents')}
        </span>
        <DocumentScope
          selectedDocuments={selectedDocuments}
          onToggle={handleDocumentToggle}
          documents={documents}
          compact
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
    if (adminApplyState.state === 'idle' && adminApprovalTurnId) {
      setAdminApprovalTurnId(null);
    }
  }, [adminApplyState.state, adminApprovalTurnId]);
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
    const accessories: Record<string, ReactNode> = {};

    for (const supersededApproval of supersededAdminApprovals) {
      const preview = buildAdminChangePreview(supersededApproval.changeSet, {
        deploymentSecretKeysLoaded,
        deploymentSecretKeys,
      });
      accessories[supersededApproval.turnId] = (
        <AdminChangeApprovalCard
          preview={preview}
          state="superseded"
          onApprove={() => undefined}
          onReject={() => undefined}
        />
      );
    }

    if (!isAdmin || !changeSet || !cardTurnId || !isApprovalVisible) {
      return Object.keys(accessories).length > 0 ? accessories : undefined;
    }

    const preview = buildAdminChangePreview(changeSet, {
      deploymentSecretKeysLoaded,
      deploymentSecretKeys,
    });
    accessories[cardTurnId] = (
      <AdminChangeApprovalCard
        preview={preview}
        state={adminApplyState.state}
        message={
          'message' in adminApplyState ? adminApplyState.message : undefined
        }
        onApprove={() => handleAdminApply(changeSet)}
        onReject={() => dispatchAdminApply({ type: 'rejected' })}
        cardRef={adminApprovalCardRef}
        approveButtonRef={adminApprovalApproveButtonRef}
      />
    );
    return accessories;
  }, [
    adminApprovalTurnId,
    adminApplyState,
    deploymentSecretKeys,
    deploymentSecretKeysLoaded,
    handleAdminApply,
    isAdmin,
    lastAssistantTurnId,
    supersededAdminApprovals,
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
        sessionMemoryNotice && (
          <div
            role="note"
            aria-label={t(
              'admin.configAssistant.sessionMemoryNoticeLabel',
              'Session Memory compaction notice'
            )}
            className="rounded-xl border border-border bg-surface-raised px-3 py-2 text-sm text-text-secondary"
          >
            {sessionMemoryNotice}
          </div>
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
      {isAdmin && adminApplyState.state === 'error' && (
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
    <ChatContainer
      header={header}
      sidebar={sessionSidebar}
      topbar={conversationTopbar}
    >
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
        hasPersistedSession={Boolean(conversationSessionId)}
      />
    </ChatContainer>
  );
}
