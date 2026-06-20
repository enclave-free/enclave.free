import { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Loader2,
  ThumbsUp,
  ThumbsDown,
  Trash2,
  ShieldAlert,
  RefreshCw,
  Download,
} from 'lucide-react';
import { Button, Callout, Card } from '../../ui';
import { decryptField, hasNip04Support } from '../../../utils/encryption';
import {
  deleteSessionLog,
  exportSessionLog,
  getSessionLog,
  listSessionLogs,
  setTurnFeedback,
  type FeedbackRating,
  type SessionLogDetail,
  type SessionLogMetadata,
  type TranscriptTurn,
} from '../../../utils/sessionLogsApi';

interface TurnDraft {
  rating?: FeedbackRating;
  comment: string;
  saving?: boolean;
  saved?: boolean;
}

function downloadBlob(blob: Blob, filename: string) {
  const href = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = href;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(href);
}

/**
 * Feedback view — review a saved trial transcript and rate each turn.
 * Transcripts and comments arrive as NIP-04 ciphertext; we decrypt client-side
 * via the admin's NIP-07 extension. Ratings are plaintext; comments are encrypted.
 */
export function FeedbackView() {
  const { t } = useTranslation();
  const [logs, setLogs] = useState<SessionLogMetadata[]>([]);
  const [loadingList, setLoadingList] = useState(true);
  const [listError, setListError] = useState<string | null>(null);

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<SessionLogDetail | null>(null);
  const [turns, setTurns] = useState<TranscriptTurn[] | null>(null);
  const [drafts, setDrafts] = useState<Record<number, TurnDraft>>({});
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [feedbackError, setFeedbackError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);

  const nip04 = useMemo(() => hasNip04Support(), []);

  const loadList = useCallback(async () => {
    setLoadingList(true);
    setListError(null);
    try {
      setLogs(await listSessionLogs());
    } catch (err) {
      setListError(
        err instanceof Error ? err.message : 'Failed to load trials'
      );
    } finally {
      setLoadingList(false);
    }
  }, []);

  useEffect(() => {
    void loadList();
  }, [loadList]);

  const openLog = useCallback(async (logId: string) => {
    setSelectedId(logId);
    setLoadingDetail(true);
    setDetailError(null);
    setFeedbackError(null);
    setExportError(null);
    setTurns(null);
    setDrafts({});
    try {
      const full = await getSessionLog(logId);
      setDetail(full);

      // Decrypt the transcript ciphertext via NIP-07.
      let parsedTurns: TranscriptTurn[] = [];
      if (full.transcript_ciphertext && full.transcript_ephemeral_pubkey) {
        const plaintext = await decryptField({
          ciphertext: full.transcript_ciphertext,
          ephemeral_pubkey: full.transcript_ephemeral_pubkey,
        });
        if (plaintext == null) {
          throw new Error(
            'Could not decrypt the transcript. Approve the decryption request in your Nostr extension.'
          );
        }
        const parsed = JSON.parse(plaintext) as { turns?: TranscriptTurn[] };
        parsedTurns = parsed.turns ?? [];
      }
      setTurns(parsedTurns);

      // Hydrate per-turn drafts from existing (decrypted) feedback.
      const nextDrafts: Record<number, TurnDraft> = {};
      await Promise.all(
        full.feedback.map(async (fb) => {
          let comment = '';
          if (fb.comment_ciphertext && fb.comment_ephemeral_pubkey) {
            comment =
              (await decryptField({
                ciphertext: fb.comment_ciphertext,
                ephemeral_pubkey: fb.comment_ephemeral_pubkey,
              })) ?? '';
          }
          nextDrafts[fb.turn_index] = {
            rating: fb.rating,
            comment,
            saved: true,
          };
        })
      );
      setDrafts(nextDrafts);
    } catch (err) {
      setDetailError(
        err instanceof Error ? err.message : 'Failed to load transcript'
      );
    } finally {
      setLoadingDetail(false);
    }
  }, []);

  const updateDraft = (turnIndex: number, patch: Partial<TurnDraft>) => {
    setDrafts((prev) => {
      const existing: TurnDraft = prev[turnIndex] ?? { comment: '' };
      return {
        ...prev,
        [turnIndex]: { ...existing, ...patch, saved: false },
      };
    });
  };

  const saveFeedback = useCallback(
    async (turnIndex: number, rating: FeedbackRating) => {
      if (!selectedId) return;
      const draft = drafts[turnIndex];
      setFeedbackError(null);
      updateDraft(turnIndex, { rating, saving: true });
      try {
        await setTurnFeedback(
          selectedId,
          turnIndex,
          rating,
          draft?.comment?.trim() || null
        );
        setDrafts((prev) => {
          const existing: TurnDraft = prev[turnIndex] ?? { comment: '' };
          return {
            ...prev,
            [turnIndex]: {
              ...existing,
              rating,
              saving: false,
              saved: true,
            },
          };
        });
      } catch (err) {
        setFeedbackError(
          err instanceof Error ? err.message : 'Feedback could not be saved'
        );
        updateDraft(turnIndex, { saving: false });
      }
    },
    [selectedId, drafts]
  );

  const handleDelete = useCallback(
    async (logId: string) => {
      await deleteSessionLog(logId);
      if (selectedId === logId) {
        setSelectedId(null);
        setDetail(null);
        setTurns(null);
      }
      void loadList();
    },
    [selectedId, loadList]
  );

  const handleExport = useCallback(async () => {
    if (!selectedId) return;
    setExporting(true);
    setExportError(null);
    try {
      const blob = await exportSessionLog(selectedId);
      downloadBlob(blob, `test-feedback-${selectedId}.zip`);
    } catch (err) {
      setExportError(
        err instanceof Error ? err.message : 'Session export failed'
      );
    } finally {
      setExporting(false);
    }
  }, [selectedId]);

  return (
    <div className="grid gap-4 lg:grid-cols-[18rem_1fr]">
      {/* Trial list */}
      <div className="flex flex-col gap-2">
        <div className="flex items-center justify-between">
          <div className="label">
            {t('adminTestFeedback.feedback.trials', 'Trials')}
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => void loadList()}
            leadingIcon={<RefreshCw className="h-4 w-4" />}
          >
            {t('common.refresh', 'Refresh')}
          </Button>
        </div>
        {loadingList ? (
          <div className="flex items-center justify-center py-10 text-text-muted">
            <Loader2 className="h-5 w-5 animate-spin" />
          </div>
        ) : listError ? (
          <Callout tone="error">{listError}</Callout>
        ) : logs.length === 0 ? (
          <Card className="py-8 text-center text-sm text-text-secondary">
            {t(
              'adminTestFeedback.feedback.empty',
              'No saved trials yet. Run a session under Test as User.'
            )}
          </Card>
        ) : (
          <ul className="flex flex-col gap-2">
            {logs.map((log) => {
              const active = log.log_id === selectedId;
              return (
                <li key={log.log_id}>
                  <button
                    onClick={() => void openLog(log.log_id)}
                    className={[
                      'w-full rounded-xl border px-3 py-2.5 text-left transition-colors',
                      active
                        ? 'border-accent bg-accent/10'
                        : 'border-border bg-surface-raised hover:bg-surface-overlay',
                    ].join(' ')}
                  >
                    <div className="truncate text-sm font-medium text-text">
                      {log.title ||
                        t(
                          'adminTestFeedback.feedback.untitled',
                          'Untitled trial'
                        )}
                    </div>
                    <div className="mt-0.5 flex items-center gap-2 text-xs text-text-muted">
                      <span className="rounded bg-surface-overlay px-1.5 py-0.5">
                        {log.source}
                      </span>
                      <span>
                        {log.turn_count}{' '}
                        {t('adminTestFeedback.feedback.turns', 'turns')}
                      </span>
                    </div>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      {/* Transcript + per-turn feedback */}
      <div className="min-w-0">
        {!nip04 && (
          <Callout tone="warning" className="mb-4">
            <span className="inline-flex items-center gap-2">
              <ShieldAlert className="h-4 w-4" />
              {t(
                'adminTestFeedback.feedback.noNip04',
                'Connect a Nostr extension (Alby, nos2x) to decrypt transcripts — they are encrypted to your admin key.'
              )}
            </span>
          </Callout>
        )}

        {!selectedId ? (
          <Card className="py-16 text-center text-sm text-text-secondary">
            {t(
              'adminTestFeedback.feedback.selectPrompt',
              'Select a trial to review its transcript and rate each turn.'
            )}
          </Card>
        ) : loadingDetail ? (
          <div className="flex items-center justify-center py-16 text-text-muted">
            <Loader2 className="h-5 w-5 animate-spin" />
          </div>
        ) : detailError ? (
          <Callout tone="error">{detailError}</Callout>
        ) : (
          <div className="flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <div className="text-sm font-semibold text-text">
                {detail?.title ||
                  t('adminTestFeedback.feedback.untitled', 'Untitled trial')}
              </div>
              {selectedId && (
                <div className="flex items-center gap-2">
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => void handleExport()}
                    disabled={exporting}
                    leadingIcon={
                      exporting ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Download className="h-4 w-4" />
                      )
                    }
                  >
                    {t('common.export', 'Export')}
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => void handleDelete(selectedId)}
                    leadingIcon={<Trash2 className="h-4 w-4" />}
                  >
                    {t('common.delete', 'Delete')}
                  </Button>
                </div>
              )}
            </div>

            {feedbackError && <Callout tone="error">{feedbackError}</Callout>}
            {exportError && <Callout tone="error">{exportError}</Callout>}

            {(turns ?? []).map((turn, index) => {
              const draft = drafts[index];
              const isAssistant = turn.role === 'assistant';
              return (
                <Card key={index} className="flex flex-col gap-2">
                  <div className="flex items-center gap-2">
                    <span
                      className={[
                        'rounded px-1.5 py-0.5 text-xs font-medium',
                        isAssistant
                          ? 'bg-accent/15 text-accent'
                          : 'bg-surface-overlay text-text-secondary',
                      ].join(' ')}
                    >
                      {turn.role}
                    </span>
                    <span className="text-xs text-text-muted">
                      {t('adminTestFeedback.feedback.turn', 'Turn')} {index + 1}
                    </span>
                  </div>
                  <div className="whitespace-pre-wrap break-words text-sm text-text">
                    {turn.content}
                  </div>

                  {/* Only the assistant's (machine) turns are ratable — the
                      user's own messages aren't graded. */}
                  {isAssistant && (
                    <div className="mt-1 flex flex-wrap items-center gap-2 border-t border-border pt-2">
                      <button
                        onClick={() => void saveFeedback(index, 'up')}
                        disabled={draft?.saving}
                        aria-pressed={draft?.rating === 'up'}
                        className={[
                          'inline-flex h-8 w-8 items-center justify-center rounded-lg border transition-colors',
                          draft?.rating === 'up'
                            ? 'border-green-500/50 bg-green-500/15 text-green-400'
                            : 'border-border text-text-muted hover:bg-surface-overlay',
                        ].join(' ')}
                        title={t(
                          'adminTestFeedback.feedback.thumbUp',
                          'Good answer'
                        )}
                      >
                        <ThumbsUp className="h-4 w-4" />
                      </button>
                      <button
                        onClick={() => void saveFeedback(index, 'down')}
                        disabled={draft?.saving}
                        aria-pressed={draft?.rating === 'down'}
                        className={[
                          'inline-flex h-8 w-8 items-center justify-center rounded-lg border transition-colors',
                          draft?.rating === 'down'
                            ? 'border-red-500/50 bg-red-500/15 text-red-400'
                            : 'border-border text-text-muted hover:bg-surface-overlay',
                        ].join(' ')}
                        title={t(
                          'adminTestFeedback.feedback.thumbDown',
                          'Needs work'
                        )}
                      >
                        <ThumbsDown className="h-4 w-4" />
                      </button>
                      <input
                        type="text"
                        value={draft?.comment ?? ''}
                        onChange={(e) =>
                          updateDraft(index, { comment: e.target.value })
                        }
                        onBlur={() => {
                          if (draft?.rating)
                            void saveFeedback(index, draft.rating);
                        }}
                        placeholder={t(
                          'adminTestFeedback.feedback.notePlaceholder',
                          'Optional note (saved encrypted)…'
                        )}
                        className="min-w-0 flex-1 rounded-lg border border-border bg-surface px-3 py-1.5 text-sm text-text placeholder:text-text-muted focus:border-accent focus:outline-none"
                      />
                      {draft?.saving ? (
                        <Loader2 className="h-4 w-4 animate-spin text-text-muted" />
                      ) : draft?.saved ? (
                        <span className="text-xs text-text-muted">
                          {t('common.saved', 'Saved')}
                        </span>
                      ) : null}
                    </div>
                  )}
                </Card>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
