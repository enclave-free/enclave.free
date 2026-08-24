import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Loader2, KeyRound } from 'lucide-react';
import {
  subscribeToDecryptQueue,
  type DecryptQueueState,
} from '../../utils/encryption';

/**
 * A small always-on indicator for pending NIP-04 approvals.
 *
 * The extension popup does not always raise itself and is easy to dismiss by
 * accident, which leaves decryption silently stalled. Surfacing the queue
 * globally means the Admin can tell the difference between "working" and
 * "waiting on you" from any screen. See #648.
 */
export function DecryptStatus() {
  const { t } = useTranslation();
  const [state, setState] = useState<DecryptQueueState>({
    done: 0,
    total: 0,
    active: false,
  });

  useEffect(() => subscribeToDecryptQueue(setState), []);

  if (!state.active) return null;

  return (
    <div
      className="pointer-events-none fixed bottom-4 right-4 z-50 flex items-center gap-2 rounded-lg border border-border bg-surface-raised px-3 py-2 text-xs text-text-secondary shadow-lg"
      role="status"
      aria-live="polite"
    >
      <Loader2
        className="h-3.5 w-3.5 animate-spin text-accent"
        aria-hidden="true"
      />
      <span className="font-medium text-text">
        {t('decryptStatus.progress', 'Decrypting {{done}} of {{total}}', {
          done: state.done,
          total: state.total,
        })}
      </span>
      <span className="inline-flex items-center gap-1 text-text-muted">
        <KeyRound className="h-3.5 w-3.5" aria-hidden="true" />
        {t('decryptStatus.checkExtension', 'check your Nostr extension')}
      </span>
      <span className="text-text-muted">
        {t(
          'decryptStatus.persistentApproval',
          'Choose the remember or always option so it only asks once.'
        )}
      </span>
    </div>
  );
}

/**
 * Inline variant, for placing directly beside the control that triggers a
 * decrypt. The floating badge is easy to miss while an extension popup has
 * focus, and the Admin looks at the button they just pressed. See #648.
 */
export function DecryptProgressInline() {
  const { t } = useTranslation();
  const [state, setState] = useState<DecryptQueueState>({
    done: 0,
    total: 0,
    active: false,
  });

  useEffect(() => subscribeToDecryptQueue(setState), []);

  if (!state.active) return null;

  return (
    <span
      className="inline-flex items-center gap-2 rounded-lg border border-border bg-surface-raised px-3 py-2 text-xs text-text-secondary"
      role="status"
      aria-live="polite"
    >
      <Loader2
        className="h-3.5 w-3.5 animate-spin text-accent"
        aria-hidden="true"
      />
      <span className="font-medium text-text">
        {t('decryptStatus.progress', 'Decrypting {{done}} of {{total}}', {
          done: state.done,
          total: state.total,
        })}
      </span>
      <span className="text-text-muted">
        {t('decryptStatus.checkExtension', 'check your Nostr extension')}
      </span>
      <span className="text-text-muted">
        {t(
          'decryptStatus.persistentApproval',
          'Choose the remember or always option so it only asks once.'
        )}
      </span>
    </span>
  );
}
