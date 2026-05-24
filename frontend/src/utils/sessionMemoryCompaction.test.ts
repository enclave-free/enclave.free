import { describe, expect, it } from 'vitest';
import {
  compactAdminSessionMemory,
  DEFAULT_SESSION_MEMORY_COMPACTION_LIMITS,
  formatSessionMemoryCompactionNotice,
  SUMMARY_HEADER,
} from './sessionMemoryCompaction';

describe('compactAdminSessionMemory', () => {
  it('leaves short conversations unchanged', () => {
    const history = Array.from({ length: 24 }, (_, index) => ({
      role: index % 2 === 0 ? ('user' as const) : ('assistant' as const),
      content: `Turn ${index}`,
    }));

    const plan = compactAdminSessionMemory({ conversationHistory: history });

    expect(plan.compacted).toBe(false);
    expect(plan.conversationHistory).toEqual(history);
    expect(plan.notice).toBeNull();
  });

  it('summarizes older turns and keeps recent messages for long conversations', () => {
    const history = Array.from({ length: 14 }, (_, index) => ({
      role: index % 2 === 0 ? ('user' as const) : ('assistant' as const),
      content:
        index % 2 === 0
          ? `User turn ${index}: update theme palette ${index}`
          : `Assistant turn ${index}: proposed settings ${index}`,
    }));

    const plan = compactAdminSessionMemory({
      conversationHistory: history,
      limits: {
        maxMessagesBeforeCompaction: 10,
        keepRecentMessages: 4,
      },
    });

    expect(plan.compacted).toBe(true);
    expect(plan.compactedMessageCount).toBe(10);
    expect(plan.conversationHistory).toHaveLength(5);
    expect(plan.conversationHistory[0]?.content).toContain(SUMMARY_HEADER);
    expect(plan.conversationHistory[0]?.content).toContain('User turn 0');
    expect(plan.conversationHistory[0]?.content).toContain('User turn 8');
    expect(
      plan.conversationHistory[plan.conversationHistory.length - 1]?.content
    ).toContain('Assistant turn 13');
    expect(plan.notice).toMatch(/Session Memory was compacted/);
  });

  it('uses provided operator-facing notice copy when compaction runs', () => {
    const history = Array.from({ length: 12 }, (_, index) => ({
      role: index % 2 === 0 ? ('user' as const) : ('assistant' as const),
      content: `Turn ${index}`,
    }));

    const plan = compactAdminSessionMemory({
      conversationHistory: history,
      limits: {
        maxMessagesBeforeCompaction: 10,
        keepRecentMessages: 4,
      },
      formatNotice: (count) => `translated compaction notice for ${count}`,
    });

    expect(plan.notice).toBe('translated compaction notice for 8');
  });

  it('uses default limits when none are provided', () => {
    expect(
      DEFAULT_SESSION_MEMORY_COMPACTION_LIMITS.maxMessagesBeforeCompaction
    ).toBe(30);
    expect(DEFAULT_SESSION_MEMORY_COMPACTION_LIMITS.keepRecentMessages).toBe(
      10
    );
  });
});

describe('formatSessionMemoryCompactionNotice', () => {
  it('returns operator-facing compaction copy without raw prompts', () => {
    expect(formatSessionMemoryCompactionNotice(12)).toMatch(
      /Session Memory was compacted/
    );
    expect(formatSessionMemoryCompactionNotice(12)).toMatch(
      /12 earlier messages/
    );
    expect(formatSessionMemoryCompactionNotice(12)).not.toContain('User turn');
  });
});
