import { describe, expect, it, vi } from 'vitest';
import {
  assertInstrumentationExcludesValues,
  buildAdminContextPlanInstrumentation,
  buildProviderFailureInstrumentation,
  emitAdminResilienceInstrumentation,
  registerAdminResilienceInstrumentationListener,
  resetAdminResilienceInstrumentationListeners,
} from './adminResilienceInstrumentation';
import type { AdminPromptBudgetPlan } from './promptBudget';
import type { SessionMemoryCompactionPlan } from './sessionMemoryCompaction';
import { classifyProviderError } from './providerErrors';

describe('buildAdminContextPlanInstrumentation', () => {
  it('emits sanitized session memory and prompt budget metadata', () => {
    const sessionMemoryPlan: SessionMemoryCompactionPlan = {
      conversationHistory: [
        {
          role: 'assistant',
          content: 'SESSION MEMORY SUMMARY\nEarlier topics',
        },
        { role: 'user', content: 'Recent question about branding' },
      ],
      compacted: true,
      compactedMessageCount: 6,
      notice: 'Session Memory was compacted...',
    };
    const promptPlan: AdminPromptBudgetPlan = {
      conversationHistory: sessionMemoryPlan.conversationHistory,
      includedSections: ['recent-conversation'],
      reducedSections: ['recent-conversation'],
      omittedSections: [],
      estimatedChars: 4_200,
      warningNote: 'PROMPT BUDGET NOTE\n- recent-conversation was reduced',
    };
    const secretPrompt = 'sk-live-secret-key-from-admin-turn';

    const event = buildAdminContextPlanInstrumentation({
      surface: 'admin_config_assistant',
      sessionMemoryPlan,
      promptPlan,
    });

    expect(event).toEqual({
      kind: 'admin_context_plan',
      surface: 'admin_config_assistant',
      sessionMemory: {
        compacted: true,
        compactedMessageCount: 6,
        estimatedHistoryChars: 67,
      },
      promptBudget: {
        includedSections: ['recent-conversation'],
        reducedSections: ['recent-conversation'],
        omittedSections: [],
        estimatedChars: 4_200,
        hasWarningNote: true,
      },
    });
    assertInstrumentationExcludesValues(event, [
      secretPrompt,
      'Recent question about branding',
      'PROMPT BUDGET NOTE',
      'SESSION MEMORY SUMMARY',
    ]);
  });
});

describe('buildProviderFailureInstrumentation', () => {
  it('emits safe provider category and recovery metadata', () => {
    const rawProviderPayload =
      'HttpError: 429 {"error":{"message":"Token limit exceeded for this session. Please start a new session."}}';
    const classified = classifyProviderError(rawProviderPayload);

    const event = buildProviderFailureInstrumentation({
      surface: 'admin_chat_page',
      classified,
    });

    expect(event).toEqual({
      kind: 'provider_failure',
      surface: 'admin_chat_page',
      category: 'context_limit',
      recoveryHint: 'Start a new assistant conversation to continue.',
      retryPolicy: 'never',
      recoveryAction: 'new_assistant_conversation',
    });
    assertInstrumentationExcludesValues(event, [
      rawProviderPayload,
      'HttpError',
      '429',
      'Please start a new session',
    ]);
  });
});

describe('emitAdminResilienceInstrumentation', () => {
  it('delivers sanitized events to registered listeners', () => {
    resetAdminResilienceInstrumentationListeners();
    const listener = vi.fn();
    registerAdminResilienceInstrumentationListener(listener);

    emitAdminResilienceInstrumentation(
      buildProviderFailureInstrumentation({
        surface: 'admin_config_assistant',
        classified: classifyProviderError('Model Provider stream timed out'),
      })
    );

    expect(listener).toHaveBeenCalledTimes(1);
    expect(listener.mock.calls[0]?.[0]).toMatchObject({
      kind: 'provider_failure',
      category: 'timeout',
      recoveryAction: 'none',
    });
    resetAdminResilienceInstrumentationListeners();
  });
});
