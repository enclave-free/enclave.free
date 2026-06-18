/**
 * Budget-aware prompt planning for Admin Configuration Assistant turns.
 */

export type PromptBudgetSectionId = 'recent-conversation';

export interface AdminPromptBudgetLimits {
  conversationTurns: number;
  conversationCharsPerTurn: number;
}

export const DEFAULT_ADMIN_PROMPT_BUDGET_LIMITS: AdminPromptBudgetLimits = {
  conversationTurns: 8,
  conversationCharsPerTurn: 2_000,
};

export interface AdminPromptBudgetInput {
  conversationHistory: Array<{ role: 'user' | 'assistant'; content: string }>;
  limits?: Partial<AdminPromptBudgetLimits>;
}

export interface AdminPromptBudgetPlan {
  conversationHistory: Array<{ role: 'user' | 'assistant'; content: string }>;
  includedSections: PromptBudgetSectionId[];
  reducedSections: PromptBudgetSectionId[];
  omittedSections: PromptBudgetSectionId[];
  estimatedChars: number;
  warningNote: string | null;
}

const TRUNCATION_SUFFIX = '\n...[context truncated for provider budget]';

/**
 * Plan bounded admin prompt sections before a Model Provider call.
 */
export function planAdminPromptBudget(
  input: AdminPromptBudgetInput
): AdminPromptBudgetPlan {
  const limits = {
    ...DEFAULT_ADMIN_PROMPT_BUDGET_LIMITS,
    ...input.limits,
  };

  const includedSections: PromptBudgetSectionId[] = [];
  const reducedSections: PromptBudgetSectionId[] = [];
  const omittedSections: PromptBudgetSectionId[] = [];

  const conversationHistory = planConversationHistory(
    input.conversationHistory,
    limits,
    includedSections,
    reducedSections,
    omittedSections
  );

  const warningNote = buildWarningNote(reducedSections);

  const estimatedChars = conversationHistory.reduce(
    (total, turn) => total + turn.content.length,
    0
  );

  return {
    conversationHistory,
    includedSections,
    reducedSections,
    omittedSections,
    estimatedChars,
    warningNote,
  };
}

const REDUCED_SECTION_LABELS: Record<PromptBudgetSectionId, string> = {
  'recent-conversation': 'recent conversation history',
};

export interface AdminReducedContextNoticeOptions {
  sectionLabels?: Partial<Record<PromptBudgetSectionId, string>>;
  formatNotice?: (sectionLabels: string[]) => string;
}

/**
 * Build operator-facing reduced-context copy from a prompt budget plan.
 */
export function formatAdminReducedContextNotice(
  reducedSections: PromptBudgetSectionId[],
  options: AdminReducedContextNoticeOptions = {}
): string | null {
  if (reducedSections.length === 0) {
    return null;
  }

  const labels = reducedSections.map(
    (section) =>
      options.sectionLabels?.[section] ?? REDUCED_SECTION_LABELS[section]
  );
  if (options.formatNotice) {
    return options.formatNotice(labels);
  }
  return `Some context was reduced to fit the Model Provider budget (${labels.join(', ')}). Answers may be less complete until you start a new assistant conversation.`;
}

function planConversationHistory(
  conversationHistory: Array<{ role: 'user' | 'assistant'; content: string }>,
  limits: AdminPromptBudgetLimits,
  includedSections: PromptBudgetSectionId[],
  reducedSections: PromptBudgetSectionId[],
  omittedSections: PromptBudgetSectionId[]
): Array<{ role: 'user' | 'assistant'; content: string }> {
  const validTurns = conversationHistory.filter(
    (turn) =>
      (turn.role === 'user' || turn.role === 'assistant') &&
      typeof turn.content === 'string' &&
      turn.content.trim()
  );

  if (validTurns.length === 0) {
    omittedSections.push('recent-conversation');
    return [];
  }

  includedSections.push('recent-conversation');
  let reduced = false;
  const boundedTurns = validTurns
    .slice(-limits.conversationTurns)
    .map((turn) => {
      const bounded = boundSectionText(
        turn.content,
        limits.conversationCharsPerTurn
      );
      if (bounded.reduced) reduced = true;
      return {
        role: turn.role,
        content: bounded.text,
      };
    });

  if (validTurns.length > limits.conversationTurns) {
    reduced = true;
  }

  if (reduced) {
    reducedSections.push('recent-conversation');
  }

  return boundedTurns;
}

function buildWarningNote(
  reducedSections: PromptBudgetSectionId[]
): string | null {
  if (reducedSections.length === 0) {
    return null;
  }

  const lines = reducedSections.map(
    (section) => `- ${section} was reduced to fit the provider budget`
  );
  return ['PROMPT BUDGET NOTE', ...lines].join('\n');
}

function boundSectionText(
  content: string,
  maxChars: number
): { text: string; reduced: boolean } {
  const trimmed = content.trim();
  if (!trimmed) {
    return { text: '', reduced: false };
  }
  if (trimmed.length <= maxChars) {
    return { text: trimmed, reduced: false };
  }

  const available = Math.max(0, maxChars - TRUNCATION_SUFFIX.length);
  return {
    text: `${trimmed.slice(0, available)}${TRUNCATION_SUFFIX}`,
    reduced: true,
  };
}
