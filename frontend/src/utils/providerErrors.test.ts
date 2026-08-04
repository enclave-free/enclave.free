import { describe, expect, it } from 'vitest';
import {
  classifyProviderError,
  formatClassifiedProviderError,
  shouldOfferNewAssistantConversation,
} from './providerErrors';

describe('classifyProviderError', () => {
  it('classifies context limit errors with a recovery hint', () => {
    const classified = classifyProviderError(
      'Token limit exceeded for this session. Please start a new session.'
    );

    expect(classified).toEqual({
      category: 'context_limit',
      message: 'Token limit exceeded for this session.',
      recoveryHint: 'Start a new assistant conversation to continue.',
      retryPolicy: 'never',
      shouldFallbackToNonStreaming: false,
    });
  });

  it('classifies quota exhaustion separately from context limits', () => {
    const classified = classifyProviderError(
      '{"error":{"code":"insufficient_quota","message":"You exceeded your current quota."}}'
    );

    expect(classified).toEqual({
      category: 'quota_exhausted',
      message: 'The Model Provider quota for this account has been exhausted.',
      recoveryHint:
        'Check billing or upgrade your Model Provider plan, then try again.',
      retryPolicy: 'never',
      shouldFallbackToNonStreaming: false,
    });
  });

  it('extracts safe context limit messages from raw provider payloads', () => {
    const classified = classifyProviderError(
      'HttpError: Invalid status code 429 Too Many Requests with message: {"error":{"code":"insufficient_quota","message":"Token limit exceeded for this session. Please start a new session."}}'
    );

    expect(classified.category).toBe('context_limit');
    expect(classified.message).toBe('Token limit exceeded for this session.');
    expect(classified.recoveryHint).toBe(
      'Start a new assistant conversation to continue.'
    );
    expect(classified.shouldFallbackToNonStreaming).toBe(false);
    expect(JSON.stringify(classified)).not.toContain('insufficient_quota');
    expect(JSON.stringify(classified)).not.toContain('HttpError');
  });

  it('classifies timeout errors without retry or fallback', () => {
    const classified = classifyProviderError(
      'Model Provider stream timed out waiting for data'
    );

    expect(classified).toEqual({
      category: 'timeout',
      message: 'The Model Provider took too long to respond.',
      recoveryHint: 'Try again in a moment.',
      retryPolicy: 'never',
      shouldFallbackToNonStreaming: false,
    });
  });

  it('classifies unavailable model errors', () => {
    const classified = classifyProviderError(
      'The configured Conversation model is temporarily unavailable. Please try again.'
    );

    expect(classified).toEqual({
      category: 'unavailable',
      message: 'The configured Model Provider model is unavailable.',
      recoveryHint: 'Check Deployment Settings and restart affected services.',
      retryPolicy: 'never',
      shouldFallbackToNonStreaming: false,
    });
  });

  it('passes through short safe text errors', () => {
    const classified = classifyProviderError('Authentication failed');

    expect(classified).toEqual({
      category: 'text',
      message: 'Authentication failed',
      recoveryHint: null,
      retryPolicy: 'never',
      shouldFallbackToNonStreaming: false,
    });
  });

  it('redacts sensitive provider details from unknown errors', () => {
    const classified = classifyProviderError(
      'Lm { source: Provider { provider: "kimi-k2-6", message: "Authorization: Bearer sk-live-secret-key" } }'
    );

    expect(classified.category).toBe('unknown');
    expect(classified.message).toBe('The Model Provider request failed.');
    expect(classified.recoveryHint).toBe(
      'Try again or start a new assistant conversation.'
    );
    expect(classified.shouldFallbackToNonStreaming).toBe(true);
    expect(JSON.stringify(classified)).not.toContain('sk-live-secret-key');
    expect(JSON.stringify(classified)).not.toContain('kimi-k2-6');
  });
});

describe('formatClassifiedProviderError', () => {
  it('appends recovery hints for actionable provider failures', () => {
    const formatted = formatClassifiedProviderError(
      classifyProviderError(
        'Token limit exceeded for this session. Please start a new session.'
      )
    );

    expect(formatted).toBe(
      'Token limit exceeded for this session. Start a new assistant conversation to continue.'
    );
  });
});

describe('shouldOfferNewAssistantConversation', () => {
  it('offers recovery for context limit failures only', () => {
    expect(
      shouldOfferNewAssistantConversation(
        classifyProviderError(
          'Token limit exceeded for this session. Please start a new session.'
        )
      )
    ).toBe(true);
    expect(
      shouldOfferNewAssistantConversation(
        classifyProviderError(
          '{"error":{"code":"insufficient_quota","message":"You exceeded your current quota."}}'
        )
      )
    ).toBe(false);
  });
});
