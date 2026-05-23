/**
 * Budget-aware prompt planning for Admin Configuration Assistant turns.
 */

export type PromptBudgetSectionId =
  | 'admin-config'
  | 'document-context'
  | 'recent-conversation';

export interface AdminPromptBudgetLimits {
  adminConfigChars: number;
  documentContextChars: number;
  conversationTurns: number;
  conversationCharsPerTurn: number;
}

export const DEFAULT_ADMIN_PROMPT_BUDGET_LIMITS: AdminPromptBudgetLimits = {
  adminConfigChars: 12_000,
  documentContextChars: 6_000,
  conversationTurns: 8,
  conversationCharsPerTurn: 2_000,
};

export interface AdminPromptBudgetInput {
  adminConfigContext: string;
  documentContext?: string;
  conversationHistory: Array<{ role: 'user' | 'assistant'; content: string }>;
  limits?: Partial<AdminPromptBudgetLimits>;
}

export interface AdminPromptBudgetPlan {
  toolContext: string;
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
  const toolContextParts: string[] = [];

  const adminConfig = boundSectionText(
    input.adminConfigContext,
    limits.adminConfigChars
  );
  if (adminConfig.text) {
    includedSections.push('admin-config');
    if (adminConfig.reduced) reducedSections.push('admin-config');
    toolContextParts.push(adminConfig.text);
  } else {
    omittedSections.push('admin-config');
  }

  const documentContext = boundSectionText(
    input.documentContext || '',
    limits.documentContextChars
  );
  if (documentContext.text) {
    includedSections.push('document-context');
    if (documentContext.reduced) reducedSections.push('document-context');
    toolContextParts.push(documentContext.text);
  } else if ((input.documentContext || '').trim()) {
    omittedSections.push('document-context');
  }

  const conversationHistory = planConversationHistory(
    input.conversationHistory,
    limits,
    includedSections,
    reducedSections,
    omittedSections
  );

  const warningNote = buildWarningNote(reducedSections);
  if (warningNote) {
    toolContextParts.unshift(warningNote);
  }

  const toolContext = toolContextParts.join('\n\n').trim();
  const estimatedChars =
    toolContext.length +
    conversationHistory.reduce((total, turn) => total + turn.content.length, 0);

  return {
    toolContext,
    conversationHistory,
    includedSections,
    reducedSections,
    omittedSections,
    estimatedChars,
    warningNote,
  };
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
