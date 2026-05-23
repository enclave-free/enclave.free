/**
 * Safe Model Provider error classification for admin chat transports.
 */

export type ProviderErrorCategory =
  | 'context_limit'
  | 'quota_exhausted'
  | 'timeout'
  | 'unavailable'
  | 'text'
  | 'unknown';

export type ProviderRetryPolicy = 'never' | 'allow';

export interface ClassifiedProviderError {
  category: ProviderErrorCategory;
  message: string;
  recoveryHint: string | null;
  retryPolicy: ProviderRetryPolicy;
  shouldFallbackToNonStreaming: boolean;
}

const QUOTA_EXHAUSTION_PATTERNS = [
  /insufficient_quota/i,
  /exceeded your (?:current )?quota/i,
  /quota (?:has been )?exhausted/i,
];

const CONTEXT_LIMIT_PATTERNS = [
  /token limit exceeded/i,
  /context (?:length|window|limit)/i,
  /maximum context/i,
  /start a new session/i,
];

const TIMEOUT_PATTERNS = [/timed out/i, /timeout/i];

const UNAVAILABLE_PATTERNS = [
  /model (?:does not exist|is unavailable)/i,
  /provider (?:is )?unavailable/i,
  /service unavailable/i,
  /\b502\b/,
  /\b503\b/,
  /bad gateway/i,
];

const SENSITIVE_PATTERNS = [
  /Bearer\s+\S+/i,
  /sk-[A-Za-z0-9_-]+/,
  /api[_-]?key/i,
  /Authorization:/i,
  /"prompt"\s*:/i,
  /Provider\s*\{/i,
  /HttpError:/i,
];

/**
 * Classify a raw provider or transport error into a safe admin-facing shape.
 */
export function classifyProviderError(raw: unknown): ClassifiedProviderError {
  const detail = extractSafeDetail(raw);
  const normalized = detail.toLowerCase();

  if (QUOTA_EXHAUSTION_PATTERNS.some((pattern) => pattern.test(normalized))) {
    return {
      category: 'quota_exhausted',
      message: 'The Model Provider quota for this account has been exhausted.',
      recoveryHint:
        'Check billing or upgrade your Model Provider plan, then try again.',
      retryPolicy: 'never',
      shouldFallbackToNonStreaming: false,
    };
  }

  if (CONTEXT_LIMIT_PATTERNS.some((pattern) => pattern.test(normalized))) {
    return {
      category: 'context_limit',
      message: normalizeContextLimitMessage(detail),
      recoveryHint: 'Start a new assistant conversation to continue.',
      retryPolicy: 'never',
      shouldFallbackToNonStreaming: false,
    };
  }

  if (TIMEOUT_PATTERNS.some((pattern) => pattern.test(normalized))) {
    return {
      category: 'timeout',
      message: 'The Model Provider took too long to respond.',
      recoveryHint: 'Try again in a moment.',
      retryPolicy: 'never',
      shouldFallbackToNonStreaming: false,
    };
  }

  if (UNAVAILABLE_PATTERNS.some((pattern) => pattern.test(normalized))) {
    return {
      category: 'unavailable',
      message: 'The configured Model Provider model is unavailable.',
      recoveryHint: 'Check Deployment Settings and restart affected services.',
      retryPolicy: 'never',
      shouldFallbackToNonStreaming: false,
    };
  }

  if (isSafeTextError(detail)) {
    return {
      category: 'text',
      message: detail.trim(),
      recoveryHint: null,
      retryPolicy: 'never',
      shouldFallbackToNonStreaming: false,
    };
  }

  return {
    category: 'unknown',
    message: 'The Model Provider request failed.',
    recoveryHint: 'Try again or start a new assistant conversation.',
    retryPolicy: 'allow',
    shouldFallbackToNonStreaming: true,
  };
}

/**
 * Whether the admin assistant should offer a fresh-conversation recovery action.
 */
export function shouldOfferNewAssistantConversation(
  error: ClassifiedProviderError
): boolean {
  return error.category === 'context_limit';
}

/**
 * Render a classified provider error for admin chat UI copy.
 */
export function formatClassifiedProviderError(
  error: ClassifiedProviderError
): string {
  if (!error.recoveryHint) {
    return error.message;
  }

  const message = error.message.replace(/\.\s*$/, '');
  return `${message}. ${error.recoveryHint}`;
}

function extractSafeDetail(raw: unknown): string {
  if (typeof raw === 'string') {
    return extractMessageFromProviderPayload(raw);
  }

  if (raw && typeof raw === 'object') {
    const record = raw as Record<string, unknown>;
    const candidates = [record.detail, record.message, record.error];
    for (const candidate of candidates) {
      if (typeof candidate === 'string' && candidate.trim()) {
        return extractMessageFromProviderPayload(candidate);
      }
    }
  }

  return '';
}

function extractMessageFromProviderPayload(value: string): string {
  const trimmed = value.trim();
  if (!trimmed) return '';

  const jsonMessage = extractJsonMessage(trimmed);
  if (jsonMessage) {
    return jsonMessage;
  }

  const quotedMessage = trimmed.match(/"message"\s*:\s*"([^"]+)"/i)?.[1];
  if (quotedMessage) {
    return quotedMessage;
  }

  return trimmed;
}

function extractJsonMessage(value: string): string | null {
  const jsonStart = value.indexOf('{');
  if (jsonStart === -1) return null;

  const candidate = value.slice(jsonStart);
  try {
    const parsed = JSON.parse(candidate) as Record<string, unknown>;
    const nestedError = parsed.error;
    if (nestedError && typeof nestedError === 'object') {
      const message = (nestedError as Record<string, unknown>).message;
      if (typeof message === 'string' && message.trim()) {
        return message.trim();
      }
    }
    if (typeof parsed.message === 'string' && parsed.message.trim()) {
      return parsed.message.trim();
    }
    if (typeof parsed.detail === 'string' && parsed.detail.trim()) {
      return parsed.detail.trim();
    }
  } catch {
    return null;
  }

  return null;
}

function normalizeContextLimitMessage(detail: string): string {
  const normalized = detail.trim().replace(/\.\s*$/, '');
  if (/start a new session/i.test(normalized)) {
    return normalized
      .replace(/\s*please start a new session\.?/i, '.')
      .replace(/\.\./g, '.')
      .trim();
  }
  return `${normalized}.`;
}

function isSafeTextError(detail: string): boolean {
  const trimmed = detail.trim();
  if (!trimmed || trimmed.length > 240) {
    return false;
  }

  if (SENSITIVE_PATTERNS.some((pattern) => pattern.test(trimmed))) {
    return false;
  }

  return /^[\w\s.,'":;!?()/-]+$/.test(trimmed);
}
