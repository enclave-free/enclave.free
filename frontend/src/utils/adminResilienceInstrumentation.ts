/**
 * Sanitized observability for Admin Configuration Assistant resilience paths.
 *
 * Emits structured metadata about Session Memory compaction, prompt budgeting,
 * and Model Provider failures without raw prompts, secrets, or provider traces.
 */

import type { ClassifiedProviderError } from './providerErrors';
import type { AdminPromptBudgetPlan } from './promptBudget';
import type { SessionMemoryCompactionPlan } from './sessionMemoryCompaction';
import { shouldOfferNewAssistantConversation } from './providerErrors';

export type AdminResilienceSurface =
  | 'admin_config_assistant'
  | 'admin_chat_page';

export type AdminResilienceInstrumentationKind =
  | 'admin_context_plan'
  | 'provider_failure';

export interface AdminContextPlanInstrumentation {
  kind: 'admin_context_plan';
  surface: AdminResilienceSurface;
  sessionMemory: {
    compacted: boolean;
    compactedMessageCount: number;
    estimatedHistoryChars: number;
  };
  promptBudget?: {
    includedSections: AdminPromptBudgetPlan['includedSections'];
    reducedSections: AdminPromptBudgetPlan['reducedSections'];
    omittedSections: AdminPromptBudgetPlan['omittedSections'];
    estimatedChars: number;
    hasWarningNote: boolean;
  };
}

export interface ProviderFailureInstrumentation {
  kind: 'provider_failure';
  surface: AdminResilienceSurface;
  category: ClassifiedProviderError['category'];
  recoveryHint: string | null;
  retryPolicy: ClassifiedProviderError['retryPolicy'];
  recoveryAction: 'new_assistant_conversation' | 'none';
}

export type AdminResilienceInstrumentationEvent =
  | AdminContextPlanInstrumentation
  | ProviderFailureInstrumentation;

const instrumentationListeners = new Set<
  (event: AdminResilienceInstrumentationEvent) => void
>();

/**
 * Register a listener for sanitized admin resilience instrumentation events.
 */
export function registerAdminResilienceInstrumentationListener(
  listener: (event: AdminResilienceInstrumentationEvent) => void
): () => void {
  instrumentationListeners.add(listener);
  return () => instrumentationListeners.delete(listener);
}

/**
 * Clear all instrumentation listeners. Intended for tests.
 */
export function resetAdminResilienceInstrumentationListeners(): void {
  instrumentationListeners.clear();
}

/**
 * Build sanitized metadata after Session Memory compaction and prompt budgeting.
 */
export function buildAdminContextPlanInstrumentation(input: {
  surface: AdminResilienceSurface;
  sessionMemoryPlan: SessionMemoryCompactionPlan;
  promptPlan?: AdminPromptBudgetPlan;
}): AdminContextPlanInstrumentation {
  const estimatedHistoryChars = estimateHistoryChars(
    input.promptPlan?.conversationHistory ??
      input.sessionMemoryPlan.conversationHistory
  );

  const event: AdminContextPlanInstrumentation = {
    kind: 'admin_context_plan',
    surface: input.surface,
    sessionMemory: {
      compacted: input.sessionMemoryPlan.compacted,
      compactedMessageCount: input.sessionMemoryPlan.compactedMessageCount,
      estimatedHistoryChars,
    },
  };

  if (input.promptPlan) {
    event.promptBudget = {
      includedSections: input.promptPlan.includedSections,
      reducedSections: input.promptPlan.reducedSections,
      omittedSections: input.promptPlan.omittedSections,
      estimatedChars: input.promptPlan.estimatedChars,
      hasWarningNote: Boolean(input.promptPlan.warningNote),
    };
  }

  return event;
}

/**
 * Build sanitized metadata for a classified Model Provider failure.
 */
export function buildProviderFailureInstrumentation(input: {
  surface: AdminResilienceSurface;
  classified: ClassifiedProviderError;
}): ProviderFailureInstrumentation {
  return {
    kind: 'provider_failure',
    surface: input.surface,
    category: input.classified.category,
    recoveryHint: input.classified.recoveryHint,
    retryPolicy: input.classified.retryPolicy,
    recoveryAction: shouldOfferNewAssistantConversation(input.classified)
      ? 'new_assistant_conversation'
      : 'none',
  };
}

/**
 * Record a sanitized admin context plan event for maintainers.
 */
export function recordAdminContextPlanInstrumentation(input: {
  surface: AdminResilienceSurface;
  sessionMemoryPlan: SessionMemoryCompactionPlan;
  promptPlan?: AdminPromptBudgetPlan;
}): void {
  emitAdminResilienceInstrumentation(
    buildAdminContextPlanInstrumentation(input)
  );
}

/**
 * Record a sanitized provider failure event for maintainers.
 */
export function recordProviderFailureInstrumentation(input: {
  surface: AdminResilienceSurface;
  classified: ClassifiedProviderError;
}): void {
  emitAdminResilienceInstrumentation(
    buildProviderFailureInstrumentation(input)
  );
}

/**
 * Emit a sanitized admin resilience instrumentation event.
 */
export function emitAdminResilienceInstrumentation(
  event: AdminResilienceInstrumentationEvent
): void {
  for (const listener of instrumentationListeners) {
    listener(event);
  }
}

/**
 * Assert instrumentation payloads exclude sensitive or raw prompt substrings.
 */
export function assertInstrumentationExcludesValues(
  event: AdminResilienceInstrumentationEvent,
  forbiddenValues: string[]
): void {
  const serialized = JSON.stringify(event);
  for (const value of forbiddenValues) {
    if (value && serialized.includes(value)) {
      throw new Error(
        `Instrumentation leaked forbidden value: ${value.slice(0, 40)}`
      );
    }
  }
}

function estimateHistoryChars(
  conversationHistory: Array<{ content: string }>
): number {
  return conversationHistory.reduce(
    (total, turn) => total + turn.content.length,
    0
  );
}
