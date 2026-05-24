/**
 * Resolve conversational admin apply intent against a pending change set.
 */

export type AdminApplyIntentKind = 'none' | 'needs-panel';

export interface AdminApplyIntent {
  kind: AdminApplyIntentKind;
}

const APPLY_COMMAND_WHEN_PENDING = [
  /^apply\.?$/i,
  /^apply\b.+/i,
  /^apply\s+(them|it|changes|now|please)\.?$/i,
  /^please\s+apply(?:\s+(them|it|changes))?\s*\.?$/i,
  /^go\s+ahead(?:\s+and\s+apply(?:\s+(them|it|changes))?)?\.?$/i,
  /^yes,?\s*apply(?:\s+(them|it|changes))?\s*\.?$/i,
  /^yes,?\s*(do\s+it|please)\.?$/i,
  /^i\s+confirm\.?$/i,
  /^confirm(?:\s+and\s+apply)?\.?$/i,
];

/**
 * Classify whether an admin chat message is trying to apply a pending change set.
 */
export function resolveAdminApplyIntent(
  message: string,
  hasPendingChangeSet: boolean
): AdminApplyIntent {
  const normalized = message.trim().replace(/\s+/g, ' ');
  if (!normalized) {
    return { kind: 'none' };
  }

  if (hasPendingChangeSet) {
    if (
      APPLY_COMMAND_WHEN_PENDING.some((pattern) => pattern.test(normalized))
    ) {
      return { kind: 'needs-panel' };
    }
  }

  return { kind: 'none' };
}
