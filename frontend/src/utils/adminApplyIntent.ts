/**
 * Resolve conversational admin apply intent against a pending change set.
 */

export type AdminApplyIntentKind = 'none' | 'unambiguous' | 'ambiguous';

export interface AdminApplyIntent {
  kind: AdminApplyIntentKind;
}

const UNAMBIGUOUS_WHEN_PENDING = [
  /^apply\.?$/i,
  /^apply\s+(them|it|changes|now|please)\.?$/i,
  /^please\s+apply(?:\s+(them|it|changes))?\s*\.?$/i,
  /^go\s+ahead(?:\s+and\s+apply(?:\s+(them|it|changes))?)?\.?$/i,
  /^yes,?\s*apply(?:\s+(them|it|changes))?\s*\.?$/i,
  /^confirm(?:\s+and\s+apply)?\.?$/i,
];

const APPLY_LANGUAGE = /\b(apply|confirm|go ahead)\b/i;

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
    if (UNAMBIGUOUS_WHEN_PENDING.some((pattern) => pattern.test(normalized))) {
      return { kind: 'unambiguous' };
    }
    if (APPLY_LANGUAGE.test(normalized)) {
      return { kind: 'ambiguous' };
    }
    return { kind: 'none' };
  }

  if (APPLY_LANGUAGE.test(normalized)) {
    return { kind: 'ambiguous' };
  }

  return { kind: 'none' };
}
