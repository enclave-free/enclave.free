/**
 * Session Memory compaction for Admin Configuration Assistant conversations.
 *
 * Collapses older turns into a deterministic summary before Model Provider calls
 * so long conversations stay useful without unbounded per-turn prompt growth.
 */

export interface SessionMemoryCompactionLimits {
  maxMessagesBeforeCompaction: number;
  keepRecentMessages: number;
  summaryMaxChars: number;
}

export const DEFAULT_SESSION_MEMORY_COMPACTION_LIMITS: SessionMemoryCompactionLimits =
  {
    maxMessagesBeforeCompaction: 30,
    keepRecentMessages: 10,
    summaryMaxChars: 1_500,
  };

export interface SessionMemoryCompactionInput {
  conversationHistory: Array<{ role: 'user' | 'assistant'; content: string }>;
  limits?: Partial<SessionMemoryCompactionLimits>;
  formatNotice?: (compactedMessageCount: number) => string;
}

export interface SessionMemoryCompactionPlan {
  conversationHistory: Array<{ role: 'user' | 'assistant'; content: string }>;
  compacted: boolean;
  compactedMessageCount: number;
  notice: string | null;
}

const SUMMARY_HEADER = 'SESSION MEMORY SUMMARY';

/**
 * Compact older admin conversation turns into a summary message for provider calls.
 */
export function compactAdminSessionMemory(
  input: SessionMemoryCompactionInput
): SessionMemoryCompactionPlan {
  const limits = {
    ...DEFAULT_SESSION_MEMORY_COMPACTION_LIMITS,
    ...input.limits,
  };

  const validHistory = input.conversationHistory.filter(
    (turn) =>
      (turn.role === 'user' || turn.role === 'assistant') &&
      typeof turn.content === 'string' &&
      turn.content.trim()
  );

  if (validHistory.length <= limits.maxMessagesBeforeCompaction) {
    return {
      conversationHistory: validHistory,
      compacted: false,
      compactedMessageCount: 0,
      notice: null,
    };
  }

  const recentHistory = validHistory.slice(-limits.keepRecentMessages);
  const compactedHistory = validHistory.slice(
    0,
    validHistory.length - limits.keepRecentMessages
  );
  const summary = buildCompactionSummary(
    compactedHistory,
    limits.summaryMaxChars
  );

  return {
    conversationHistory: [
      { role: 'assistant', content: summary },
      ...recentHistory,
    ],
    compacted: true,
    compactedMessageCount: compactedHistory.length,
    notice:
      input.formatNotice?.(compactedHistory.length) ??
      formatSessionMemoryCompactionNotice(compactedHistory.length),
  };
}

/**
 * Build operator-facing copy when Session Memory compaction runs.
 */
export function formatSessionMemoryCompactionNotice(
  compactedMessageCount: number
): string {
  return `Session Memory was compacted to keep this admin conversation within Model Provider limits (${compactedMessageCount} earlier messages summarized). Recent turns are preserved; start a new assistant conversation if you need the full earlier transcript.`;
}

function buildCompactionSummary(
  compactedHistory: Array<{ role: 'user' | 'assistant'; content: string }>,
  summaryMaxChars: number
): string {
  const userTopics = compactedHistory
    .filter((turn) => turn.role === 'user')
    .map((turn) => summarizeTurnContent(turn.content))
    .filter(Boolean);

  const lines = [
    SUMMARY_HEADER,
    `Earlier admin configuration conversation (${compactedHistory.length} messages):`,
  ];

  if (userTopics.length > 0) {
    for (const topic of userTopics) {
      lines.push(`- ${topic}`);
    }
  } else {
    lines.push('- Earlier assistant configuration guidance was provided.');
  }

  lines.push(
    'Use this summary for continuity. Recent turns follow in the conversation history.'
  );

  return boundSummaryText(lines.join('\n'), summaryMaxChars);
}

function summarizeTurnContent(content: string): string {
  const singleLine = content.trim().replace(/\s+/g, ' ');
  if (singleLine.length <= 160) {
    return singleLine;
  }
  return `${singleLine.slice(0, 157).trim()}...`;
}

function boundSummaryText(content: string, maxChars: number): string {
  if (content.length <= maxChars) {
    return content;
  }

  const suffix = '\n...[session memory summary truncated]';
  const available = Math.max(0, maxChars - suffix.length);
  return `${content.slice(0, available).trim()}${suffix}`;
}

export { SUMMARY_HEADER };
