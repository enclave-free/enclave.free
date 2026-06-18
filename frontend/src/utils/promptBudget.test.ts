import { describe, expect, it } from 'vitest';
import {
  DEFAULT_ADMIN_PROMPT_BUDGET_LIMITS,
  formatAdminReducedContextNotice,
  planAdminPromptBudget,
} from './promptBudget';

describe('planAdminPromptBudget', () => {
  it('bounds recent conversation history on its own budget', () => {
    const plan = planAdminPromptBudget({
      conversationHistory: Array.from({ length: 12 }, (_, index) => ({
        role: index % 2 === 0 ? 'user' : 'assistant',
        content: `Turn ${index} ${'H'.repeat(3_000)}`,
      })) as Array<{ role: 'user' | 'assistant'; content: string }>,
      limits: {
        conversationTurns: 4,
        conversationCharsPerTurn: 500,
      },
    });

    expect(plan.conversationHistory).toHaveLength(4);
    expect(plan.conversationHistory[0]?.content).toContain('Turn 8');
    expect(
      plan.conversationHistory[plan.conversationHistory.length - 1]?.content
    ).toContain('Turn 11');
    expect(plan.reducedSections).toContain('recent-conversation');
    expect(plan.warningNote).toMatch(/recent-conversation/i);
    expect(
      plan.conversationHistory.every((turn) => turn.content.length <= 500)
    ).toBe(true);
    expect(plan.estimatedChars).toBeGreaterThan(0);
  });

  it('uses default limits when none are provided', () => {
    const plan = planAdminPromptBudget({
      conversationHistory: [],
    });

    expect(plan.reducedSections).toEqual([]);
    expect(plan.omittedSections).toEqual(['recent-conversation']);
    expect(plan.estimatedChars).toBe(0);
    expect(DEFAULT_ADMIN_PROMPT_BUDGET_LIMITS.conversationTurns).toBe(8);
  });
});

describe('formatAdminReducedContextNotice', () => {
  it('returns operator-facing notice when sections were reduced', () => {
    expect(formatAdminReducedContextNotice(['recent-conversation'])).toMatch(
      /recent conversation history/
    );
    expect(formatAdminReducedContextNotice([])).toBeNull();
  });

  it('uses provided operator-facing notice copy and translated section labels', () => {
    expect(
      formatAdminReducedContextNotice(['recent-conversation'], {
        sectionLabels: {
          'recent-conversation': 'historial reciente traducido',
        },
        formatNotice: (labels) =>
          `contexto reducido traducido: ${labels.join(' + ')}`,
      })
    ).toBe('contexto reducido traducido: historial reciente traducido');
  });
});
