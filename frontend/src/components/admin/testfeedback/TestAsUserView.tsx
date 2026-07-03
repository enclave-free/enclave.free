import { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Loader2,
  LogOut,
  Play,
  RotateCcw,
  Save,
  Send,
  UserCog,
} from 'lucide-react';
import { Button, Callout, Card } from '../../ui';
import { sendLlmChatStreamWithUnifiedTools } from '../../../utils/llmChat';
import {
  createSessionLog,
  getImpersonationStatus,
  listUserTypes,
  provisionTestUser,
  requestImpersonationToken,
  saveTranscript,
  type AdminUserType,
  type TranscriptTurn,
} from '../../../utils/sessionLogsApi';
import { API_BASE } from '../../../types/onboarding';
import {
  type KnowledgeSourceScope,
  resolveUserConversationSessionDefaults,
} from '../../../utils/sessionDefaults';

let assistantTurnSequence = 0;

function generateAssistantTurnId(): string {
  if (typeof globalThis.crypto?.randomUUID === 'function') {
    return `assistant-turn-${globalThis.crypto.randomUUID()}`;
  }
  assistantTurnSequence += 1;
  return `assistant-turn-${Date.now()}-${assistantTurnSequence}`;
}

interface UserSessionToolDefaults {
  tools: string[];
  documentIds: string[];
  knowledgeSourceScope: KnowledgeSourceScope;
  status: 'configured' | 'fallback';
}

interface ActiveSession {
  testUserId: number;
  userTypeId: number | null;
  personaName: string;
  token: string; // bearer token used to chat AS the test user
  tools: string[];
  documentIds: string[];
  knowledgeSourceScope: KnowledgeSourceScope;
  defaultsStatus: UserSessionToolDefaults['status'];
}

function sessionDefaultsUrl(userTypeId: number | null): string {
  if (userTypeId === null) return `${API_BASE}/session-defaults`;
  return `${API_BASE}/session-defaults?user_type_id=${encodeURIComponent(
    String(userTypeId)
  )}`;
}

function resolveUserSessionToolDefaults(
  data: unknown
): UserSessionToolDefaults {
  const defaults = resolveUserConversationSessionDefaults(data);

  return {
    tools: defaults.tools,
    documentIds: defaults.documentIds,
    knowledgeSourceScope: defaults.knowledgeSourceScope,
    status: 'configured',
  };
}

async function fetchUserSessionToolDefaults(
  userTypeId: number | null
): Promise<UserSessionToolDefaults> {
  try {
    const response = await fetch(sessionDefaultsUrl(userTypeId), {
      credentials: 'include',
    });
    if (response.ok) {
      return resolveUserSessionToolDefaults(await response.json());
    }
  } catch {
    // Fall back below to match the normal user chat fail-closed behavior.
  }

  return {
    tools: [],
    documentIds: [],
    knowledgeSourceScope: 'none',
    status: 'fallback',
  };
}

function streamPayloadRecord(payload: unknown): Record<string, unknown> {
  return payload && typeof payload === 'object'
    ? (payload as Record<string, unknown>)
    : {};
}

function completedTranscriptTurns(
  turns: TranscriptTurn[],
  completedAssistantTurnIds: ReadonlySet<string>
): TranscriptTurn[] {
  return turns.filter((turn) => {
    if (turn.role !== 'assistant') return true;
    return (
      typeof turn.ts === 'string' && completedAssistantTurnIds.has(turn.ts)
    );
  });
}

/**
 * Test as User — provision a test user for a persona, switch into that identity,
 * and chat as a non-admin would. The session is captured and saved as a trial
 * (encrypted) for review under Feedback.
 *
 * The Admin remains authenticated for page controls, but the chat itself always
 * uses the synthetic user's bearer token. A Sage session should have one actor
 * identity for its lifetime.
 */
export function TestAsUserView({ onSaved }: { onSaved?: () => void }) {
  const { t } = useTranslation();
  const [userTypes, setUserTypes] = useState<AdminUserType[]>([]);
  const [selectedTypeId, setSelectedTypeId] = useState<number | null>(null);
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);

  const [session, setSession] = useState<ActiveSession | null>(null);

  const [turns, setTurns] = useState<TranscriptTurn[]>([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);
  const [streamStatus, setStreamStatus] = useState<string | null>(null);
  const sessionIdRef = useRef<string | null>(null);
  const completedAssistantTurnIdsRef = useRef<Set<string>>(new Set());

  const [saving, setSaving] = useState(false);
  const [savedNotice, setSavedNotice] = useState<string | null>(null);

  useEffect(() => {
    listUserTypes()
      .then((types) => setUserTypes(types ?? []))
      .catch(() => setUserTypes([]));
  }, []);

  const personaName = (typeId: number | null) =>
    userTypes.find((ut) => ut.id === typeId)?.name ??
    t('adminTestFeedback.test.genericUser', 'User');

  const startSession = useCallback(async () => {
    setStarting(true);
    setStartError(null);
    setSavedNotice(null);
    try {
      const available = await getImpersonationStatus();
      if (!available) {
        throw new Error('Test-user impersonation is not available yet');
      }
      const provisioned = await provisionTestUser(selectedTypeId);
      const token = await requestImpersonationToken(provisioned.user_id);
      if (!token?.token) {
        throw new Error('Could not create a synthetic user session token');
      }
      const defaults = await fetchUserSessionToolDefaults(selectedTypeId);
      setSession({
        testUserId: provisioned.user_id,
        userTypeId: selectedTypeId,
        personaName: personaName(selectedTypeId),
        token: token.token,
        tools: defaults.tools,
        documentIds: defaults.documentIds,
        knowledgeSourceScope: defaults.knowledgeSourceScope,
        defaultsStatus: defaults.status,
      });
      setTurns([]);
      setStreamStatus(null);
      sessionIdRef.current = null;
      completedAssistantTurnIdsRef.current.clear();
    } catch (err) {
      setStartError(
        err instanceof Error ? err.message : 'Failed to start a test session'
      );
    } finally {
      setStarting(false);
    }
  }, [selectedTypeId, userTypes]);

  const send = useCallback(async () => {
    const content = input.trim();
    if (!content || sending) return;
    setInput('');
    setChatError(null);
    setStreamStatus(null);
    const userTurn: TranscriptTurn = {
      role: 'user',
      content,
      ts: new Date().toISOString(),
      tools_used: [],
    };
    setTurns((prev) => [...prev, userTurn]);
    setSending(true);
    let assistantStarted = false;
    let assistantCompleted = false;
    let assistantTurnId: string | null = null;
    let assistantContent = '';
    let assistantTrace: TranscriptTurn['trace'] = null;
    let assistantTools: TranscriptTurn['tools_used'] = [];

    const removePendingAssistantTurn = () => {
      if (!assistantStarted || assistantCompleted || !assistantTurnId) return;
      completedAssistantTurnIdsRef.current.delete(assistantTurnId);
      setTurns((prev) => {
        return prev.filter(
          (turn) => !(turn.role === 'assistant' && turn.ts === assistantTurnId)
        );
      });
    };

    try {
      const ensureAssistantTurn = (candidateTurnId?: unknown) => {
        if (assistantStarted) return;
        assistantStarted = true;
        assistantTurnId =
          typeof candidateTurnId === 'string' && candidateTurnId.trim()
            ? candidateTurnId
            : generateAssistantTurnId();
        setTurns((prev) => [
          ...prev,
          {
            role: 'assistant',
            content: '',
            ts: assistantTurnId,
            trace: null,
            tools_used: [],
          },
        ]);
      };

      const updateAssistantTurn = (
        update: (turn: TranscriptTurn) => TranscriptTurn,
        candidateTurnId?: unknown
      ) => {
        ensureAssistantTurn(candidateTurnId);
        const targetTurnId = assistantTurnId;
        if (!targetTurnId) return;
        setTurns((prev) =>
          prev.map((turn) =>
            turn.role === 'assistant' && turn.ts === targetTurnId
              ? update(turn)
              : turn
          )
        );
      };

      // When acting as the test user, send the impersonation bearer so Sage
      // authenticates the chat as them (not the admin).
      const knowledgeSourceScope = session?.knowledgeSourceScope ?? 'none';
      const jobIds =
        knowledgeSourceScope === 'selected' ? (session?.documentIds ?? []) : [];
      await sendLlmChatStreamWithUnifiedTools({
        content,
        tools: session?.tools ?? [],
        jobIds,
        sessionId: sessionIdRef.current,
        authToken: session?.token,
        onEvent: (event, payload) => {
          const data = streamPayloadRecord(payload);
          if (typeof data.session_id === 'string' && data.session_id.trim()) {
            sessionIdRef.current = data.session_id;
          }

          if (event === 'assistant_message_started') {
            ensureAssistantTurn(data.message_id);
            setStreamStatus(
              t('chat.trace.finalizing', 'Finalizing response...')
            );
            return;
          }

          if (event === 'trace_status') {
            ensureAssistantTurn(data.message_id);
            if (typeof data.status === 'string' && data.status.trim()) {
              setStreamStatus(data.status);
            }
            return;
          }

          if (event === 'answer_delta') {
            const delta = typeof data.delta === 'string' ? data.delta : '';
            assistantContent += delta;
            setStreamStatus(null);
            updateAssistantTurn(
              (turn) => ({
                ...turn,
                content: assistantContent,
              }),
              data.message_id
            );
            return;
          }

          if (event === 'trace_final') {
            assistantTrace =
              data.trace === null || data.trace === undefined
                ? null
                : (data.trace as TranscriptTurn['trace']);
            updateAssistantTurn(
              (turn) => ({
                ...turn,
                trace: assistantTrace,
              }),
              data.message_id
            );
            return;
          }

          if (event === 'done') {
            setStreamStatus(null);
            assistantTools = Array.isArray(data.tools_used)
              ? (data.tools_used as TranscriptTurn['tools_used'])
              : [];
            updateAssistantTurn(
              (turn) => ({
                ...turn,
                content: assistantContent,
                trace: assistantTrace ?? turn.trace ?? null,
                tools_used: assistantTools ?? [],
              }),
              data.message_id
            );
            if (assistantTurnId) {
              completedAssistantTurnIdsRef.current.add(assistantTurnId);
            }
            assistantCompleted = true;
            return;
          }

          if (event === 'error') {
            throw new Error(
              typeof data.detail === 'string' && data.detail.trim()
                ? data.detail
                : 'Chat failed'
            );
          }
        },
      });
    } catch (err) {
      removePendingAssistantTurn();
      setChatError(err instanceof Error ? err.message : 'Chat failed');
    } finally {
      setStreamStatus(null);
      setSending(false);
    }
  }, [input, sending, session, t]);

  const endAndSave = useCallback(async () => {
    const completedTurns = completedTranscriptTurns(
      turns,
      completedAssistantTurnIdsRef.current
    );
    if (!session || completedTurns.length === 0 || sending) return;
    setSaving(true);
    setSavedNotice(null);
    try {
      const title = `${session.personaName} · ${new Date().toLocaleString()}`;
      const log = await createSessionLog({
        source: 'admin_test',
        title,
        subject_user_id: session.testUserId,
        user_type_id: session.userTypeId,
        sage_session_id: sessionIdRef.current,
      });
      await saveTranscript(log.log_id, completedTurns, title);
      setSavedNotice(
        t(
          'adminTestFeedback.test.saved',
          'Trial saved (encrypted). Review it under Feedback.'
        )
      );
      setSession(null);
      setTurns([]);
      sessionIdRef.current = null;
      completedAssistantTurnIdsRef.current.clear();
      onSaved?.();
    } catch (err) {
      setChatError(err instanceof Error ? err.message : 'Failed to save trial');
    } finally {
      setSaving(false);
    }
  }, [session, turns, sending, onSaved, t]);

  const resetConversation = useCallback(() => {
    setTurns([]);
    setInput('');
    setChatError(null);
    setStreamStatus(null);
    sessionIdRef.current = null;
    completedAssistantTurnIdsRef.current.clear();
  }, []);

  const exitSession = useCallback(() => {
    setSession(null);
    setTurns([]);
    setInput('');
    setChatError(null);
    setStreamStatus(null);
    setSavedNotice(null);
    sessionIdRef.current = null;
    completedAssistantTurnIdsRef.current.clear();
  }, []);

  // --- Persona picker (no active session) ---
  if (!session) {
    return (
      <Card className="flex flex-col gap-4">
        <div>
          <div className="text-base font-semibold text-text">
            {t('adminTestFeedback.test.pickPersona', 'Pick a persona to test')}
          </div>
          <p className="mt-1 text-sm text-text-secondary">
            {t(
              'adminTestFeedback.test.pickPersonaBody',
              'Provision a test user for one of your user types, then chat as them. The session is saved as an encrypted trial you can rate under Feedback.'
            )}
          </p>
        </div>

        {savedNotice && <Callout tone="success">{savedNotice}</Callout>}
        {startError && <Callout tone="error">{startError}</Callout>}

        <div className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-text-secondary">
              {t('adminTestFeedback.test.userType', 'User type')}
            </span>
            <select
              value={selectedTypeId ?? ''}
              onChange={(e) =>
                setSelectedTypeId(
                  e.target.value ? Number(e.target.value) : null
                )
              }
              className="min-w-56 rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text focus:border-accent focus:outline-none"
            >
              <option value="">
                {t(
                  'adminTestFeedback.test.genericUser',
                  'Generic user (no type)'
                )}
              </option>
              {userTypes.map((ut) => (
                <option key={ut.id} value={ut.id}>
                  {ut.name}
                </option>
              ))}
            </select>
          </label>
          <Button
            variant="primary"
            onClick={() => void startSession()}
            disabled={starting}
            leadingIcon={
              starting ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Play className="h-4 w-4" />
              )
            }
          >
            {t('adminTestFeedback.test.start', 'Start session')}
          </Button>
        </div>
      </Card>
    );
  }

  // --- Active session: synthetic user chat ---
  const showingStreamingAssistant =
    sending && turns[turns.length - 1]?.role === 'assistant';

  return (
    <div className="flex flex-col gap-4">
      <Card className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="inline-flex items-center gap-2 rounded-xl border border-border bg-surface-raised px-3 py-2 text-sm text-text">
            <UserCog className="h-4 w-4 text-accent" />
            <span className="font-medium">
              {t('adminTestFeedback.test.testingAs', 'Testing as {{persona}}', {
                persona: session.personaName,
              })}
            </span>
          </div>
          <span className="text-xs text-text-muted">
            {t('adminTestFeedback.test.testUserId', 'Test user')} #
            {session.testUserId}
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="ghost"
            onClick={resetConversation}
            disabled={saving || sending || turns.length === 0}
            leadingIcon={<RotateCcw className="h-4 w-4" />}
          >
            {t('common.reset', 'Reset')}
          </Button>
          <Button
            variant="ghost"
            onClick={exitSession}
            disabled={saving || sending}
            leadingIcon={<LogOut className="h-4 w-4" />}
          >
            {t('common.exit', 'Exit')}
          </Button>
          <Button
            variant="secondary"
            onClick={() => void endAndSave()}
            disabled={saving || sending || turns.length === 0}
            leadingIcon={
              saving ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Save className="h-4 w-4" />
              )
            }
          >
            {t('adminTestFeedback.test.endSave', 'End & save trial')}
          </Button>
        </div>
      </Card>

      {chatError && <Callout tone="error">{chatError}</Callout>}

      <Card className="flex min-h-[24rem] flex-col gap-3">
        <div className="flex flex-1 flex-col gap-3 overflow-y-auto">
          {turns.length === 0 ? (
            <div className="flex flex-1 items-center justify-center text-sm text-text-muted">
              {t(
                'adminTestFeedback.test.chatEmpty',
                'Send a message as this user to begin the trial.'
              )}
            </div>
          ) : (
            turns.map((turn, index) => {
              const isStreamingAssistant =
                sending &&
                turn.role === 'assistant' &&
                index === turns.length - 1;

              return (
                <div
                  key={index}
                  className={
                    turn.role === 'user'
                      ? 'flex justify-end'
                      : 'flex justify-start'
                  }
                >
                  <div
                    className={[
                      'max-w-[80%] whitespace-pre-wrap break-words rounded-2xl px-3.5 py-2 text-sm',
                      turn.role === 'user'
                        ? 'bg-accent text-accent-text'
                        : 'bg-surface-overlay text-text',
                    ].join(' ')}
                  >
                    {turn.content || <span className="text-text-muted">…</span>}
                    {isStreamingAssistant && streamStatus && (
                      <div className="mt-1.5 flex items-center gap-1.5 text-xs text-text-muted">
                        <Loader2 className="h-3 w-3 animate-spin" />
                        <span>{streamStatus}</span>
                      </div>
                    )}
                  </div>
                </div>
              );
            })
          )}
          {sending && !showingStreamingAssistant && (
            <div className="flex justify-start">
              <div className="rounded-2xl bg-surface-overlay px-3.5 py-2 text-text-muted">
                <Loader2 className="h-4 w-4 animate-spin" />
              </div>
            </div>
          )}
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            void send();
          }}
          className="flex items-center gap-2 border-t border-border pt-3"
        >
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={t(
              'adminTestFeedback.test.inputPlaceholder',
              'Message the assistant as this user…'
            )}
            className="min-w-0 flex-1 rounded-xl border border-border bg-surface px-3.5 py-2 text-sm text-text placeholder:text-text-muted focus:border-accent focus:outline-none"
          />
          <Button
            type="submit"
            variant="primary"
            disabled={sending || !input.trim()}
            leadingIcon={<Send className="h-4 w-4" />}
          >
            {t('common.send', 'Send')}
          </Button>
        </form>
      </Card>
    </div>
  );
}
