import { describe, expect, it } from 'vitest';
import {
  DEFAULT_ADMIN_PROMPT_BUDGET_LIMITS,
  planAdminPromptBudget,
} from './promptBudget';

describe('planAdminPromptBudget', () => {
  it('bounds oversized admin config context to its separate budget', () => {
    const plan = planAdminPromptBudget({
      adminConfigContext: `SCOPED CONFIG CONTEXT\n${'A'.repeat(20_000)}`,
      conversationHistory: [],
      limits: {
        adminConfigChars: 1_000,
      },
    });

    expect(plan.toolContext).toContain('SCOPED CONFIG CONTEXT');
    expect(plan.toolContext).not.toContain('A'.repeat(2_000));
    expect(
      plan.toolContext.replace(/^PROMPT BUDGET NOTE[\s\S]*?\n\n/, '').length
    ).toBeLessThanOrEqual(1_000);
    expect(plan.reducedSections).toContain('admin-config');
    expect(plan.warningNote).toMatch(/admin-config/i);
    expect(plan.estimatedChars).toBeGreaterThan(0);
  });

  it('bounds document context separately from admin config', () => {
    const plan = planAdminPromptBudget({
      adminConfigContext: 'SCOPED CONFIG CONTEXT\nsmall admin section',
      documentContext: `BOUNDED DOCUMENT CONTEXT\n${'D'.repeat(10_000)}`,
      conversationHistory: [],
      limits: {
        adminConfigChars: 2_000,
        documentContextChars: 800,
      },
    });

    expect(plan.includedSections).toEqual(['admin-config', 'document-context']);
    expect(plan.reducedSections).toContain('document-context');
    expect(plan.reducedSections).not.toContain('admin-config');
    expect(plan.toolContext).toContain('small admin section');
    expect(plan.toolContext).toContain('BOUNDED DOCUMENT CONTEXT');
    expect(plan.toolContext).not.toContain('D'.repeat(1_000));
  });

  it('bounds recent conversation history on its own budget', () => {
    const plan = planAdminPromptBudget({
      adminConfigContext: 'SCOPED CONFIG CONTEXT',
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
    expect(plan.conversationHistory.at(-1)?.content).toContain('Turn 11');
    expect(plan.reducedSections).toContain('recent-conversation');
    expect(
      plan.conversationHistory.every((turn) => turn.content.length <= 500)
    ).toBe(true);
  });

  it('uses default limits when none are provided', () => {
    const plan = planAdminPromptBudget({
      adminConfigContext: 'SCOPED CONFIG CONTEXT',
      conversationHistory: [],
    });

    expect(plan.reducedSections).toEqual([]);
    expect(plan.estimatedChars).toBeGreaterThan(0);
    expect(DEFAULT_ADMIN_PROMPT_BUDGET_LIMITS.adminConfigChars).toBe(12_000);
  });
});
