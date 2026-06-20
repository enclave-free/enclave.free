import { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Loader2,
  Play,
  Save,
  Send,
  ShieldCheck,
  UserCog,
  Sparkles,
} from 'lucide-react';
import { Button, Callout, Card } from '../../ui';
import { sendLlmChatWithUnifiedTools } from '../../../utils/llmChat';
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

type Identity = 'admin' | 'user';

interface ActiveSession {
  testUserId: number;
  userTypeId: number | null;
  personaName: string;
  impersonation: boolean; // true once a real impersonation token is issued
  token: string | null; // bearer token used to chat AS the test user
}

/**
 * Test as User — provision a test user for a persona, switch into that identity,
 * and chat as a non-admin would. The session is captured and saved as a trial
 * (encrypted) for review under Feedback.
 *
 * The live impersonated identity depends on the impersonation seam; until that
 * script is wired in, the chat runs under the admin session (clearly flagged)
 * so the end-to-end capture/save/review loop is still usable today.
 */
export function TestAsUserView({ onSaved }: { onSaved?: () => void }) {
  const { t } = useTranslation();
  const [userTypes, setUserTypes] = useState<AdminUserType[]>([]);
  const [selectedTypeId, setSelectedTypeId] = useState<number | null>(null);
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);

  const [session, setSession] = useState<ActiveSession | null>(null);
  const [identity, setIdentity] = useState<Identity>('user');

  const [turns, setTurns] = useState<TranscriptTurn[]>([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);
  const sessionIdRef = useRef<string | null>(null);

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
      const provisioned = await provisionTestUser(selectedTypeId);
      // Only request a token when impersonation is actually wired in — avoids a
      // noisy 501 on every session start while the seam is unimplemented.
      const available = await getImpersonationStatus();
      const token = available
        ? await requestImpersonationToken(provisioned.user_id)
        : null;
      setSession({
        testUserId: provisioned.user_id,
        userTypeId: selectedTypeId,
        personaName: personaName(selectedTypeId),
        impersonation: token != null,
        token: token?.token ?? null,
      });
      setIdentity('user');
      setTurns([]);
      sessionIdRef.current = null;
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
    const userTurn: TranscriptTurn = {
      role: 'user',
      content,
      ts: new Date().toISOString(),
    };
    setTurns((prev) => [...prev, userTurn]);
    setSending(true);
    try {
      // When acting as the test user, send the impersonation bearer so Sage
      // authenticates the chat as them (not the admin).
      const authToken =
        identity === 'user' ? (session?.token ?? undefined) : undefined;
      const res = await sendLlmChatWithUnifiedTools({
        content,
        tools: [],
        sessionId: sessionIdRef.current,
        authToken,
      });
      const data = (await res.json()) as {
        message?: string;
        session_id?: string;
        detail?: string;
      };
      if (!res.ok) {
        throw new Error(data?.detail || `HTTP ${res.status}`);
      }
      if (typeof data.session_id === 'string') {
        sessionIdRef.current = data.session_id;
      }
      setTurns((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: data.message ?? '',
          ts: new Date().toISOString(),
        },
      ]);
    } catch (err) {
      setChatError(err instanceof Error ? err.message : 'Chat failed');
    } finally {
      setSending(false);
    }
  }, [input, sending, identity, session]);

  const endAndSave = useCallback(async () => {
    if (!session || turns.length === 0) return;
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
      await saveTranscript(log.log_id, turns, title);
      setSavedNotice(
        t(
          'adminTestFeedback.test.saved',
          'Trial saved (encrypted). Review it under Feedback.'
        )
      );
      setSession(null);
      setTurns([]);
      sessionIdRef.current = null;
      onSaved?.();
    } catch (err) {
      setChatError(err instanceof Error ? err.message : 'Failed to save trial');
    } finally {
      setSaving(false);
    }
  }, [session, turns, onSaved, t]);

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

  // --- Active session: identity switch + chat ---
  return (
    <div className="flex flex-col gap-4">
      <Card className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="inline-flex rounded-xl border border-border bg-surface-raised p-1">
            <button
              onClick={() => setIdentity('user')}
              className={[
                'inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors',
                identity === 'user'
                  ? 'bg-accent text-accent-text'
                  : 'text-text-secondary hover:text-text',
              ].join(' ')}
            >
              <UserCog className="h-4 w-4" />
              {session.personaName}
            </button>
            <button
              onClick={() => setIdentity('admin')}
              className={[
                'inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors',
                identity === 'admin'
                  ? 'bg-accent text-accent-text'
                  : 'text-text-secondary hover:text-text',
              ].join(' ')}
            >
              <ShieldCheck className="h-4 w-4" />
              {t('adminTestFeedback.test.admin', 'Admin')}
            </button>
          </div>
          <span className="text-xs text-text-muted">
            {t('adminTestFeedback.test.testUserId', 'Test user')} #
            {session.testUserId}
          </span>
        </div>
        <Button
          variant="secondary"
          onClick={() => void endAndSave()}
          disabled={saving || turns.length === 0}
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
      </Card>

      {!session.impersonation && identity === 'user' && (
        <Callout tone="warning">
          <span className="inline-flex items-center gap-2">
            <Sparkles className="h-4 w-4" />
            {t(
              'adminTestFeedback.test.previewNotice',
              'Preview mode — true impersonation is not wired in yet, so this chat runs under your admin session. The transcript still saves for review.'
            )}
          </span>
        </Callout>
      )}
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
            turns.map((turn, index) => (
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
                </div>
              </div>
            ))
          )}
          {sending && (
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
