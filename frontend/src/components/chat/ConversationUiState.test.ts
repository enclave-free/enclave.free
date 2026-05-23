import { describe, expect, it } from 'vitest'
import {
  createConversationUiState,
  reduceConversationUiState,
} from './ConversationUiState'

describe('Conversation UI State', () => {
  it('captures selected controls on submitted turns while preserving current controls for the next turn', () => {
    const initial = createConversationUiState({
      selectedTools: ['web-search'],
      selectedDocuments: ['doc-1'],
    })

    const state = reduceConversationUiState(initial, {
      type: 'userTurnSubmitted',
      id: 'user-1',
      content: 'Summarize this document',
    })

    expect(state.turns).toEqual([
      {
        id: 'user-1',
        role: 'user',
        content: 'Summarize this document',
        activitySteps: [],
        trace: null,
        traceStatus: null,
        controlSnapshot: {
          selectedTools: ['web-search'],
          selectedDocuments: ['doc-1'],
        },
      },
    ])
    expect(state.selectedTools).toEqual(['web-search'])
    expect(state.selectedDocuments).toEqual(['doc-1'])
  })

  it('tracks assistant streaming activity and settles the final trace', () => {
    const initial = createConversationUiState()
    const activity = {
      id: 'tool-db-query',
      kind: 'tool',
      title: 'Database Query',
      status: 'succeeded',
      summary: 'Database results were redacted from the trace.',
      warnings: ['raw_results_redacted'],
    }
    const trace = {
      visibility: 'detailed' as const,
      tools: [],
      retrieval: [],
      activity_steps: [activity],
    }

    const state = [
      {
        type: 'assistantTurnStarted' as const,
        id: 'assistant-1',
        sessionId: 'session-1',
        traceStatus: 'Checking configuration...',
      },
      {
        type: 'assistantActivityStepReceived' as const,
        assistantTurnId: 'assistant-1',
        step: activity,
      },
      {
        type: 'assistantContentDeltaReceived' as const,
        assistantTurnId: 'assistant-1',
        delta: 'Settings ',
      },
      {
        type: 'assistantContentDeltaReceived' as const,
        assistantTurnId: 'assistant-1',
        delta: 'are ready.',
      },
      {
        type: 'assistantTraceSettled' as const,
        assistantTurnId: 'assistant-1',
        trace,
      },
      {
        type: 'assistantTurnFinished' as const,
        sessionId: 'session-1',
      },
    ].reduce(reduceConversationUiState, initial)

    expect(state.conversationSessionId).toBe('session-1')
    expect(state.isRunning).toBe(false)
    expect(state.turns).toEqual([
      {
        id: 'assistant-1',
        role: 'assistant',
        content: 'Settings are ready.',
        activitySteps: [activity],
        trace,
        traceStatus: null,
      },
    ])
  })

  it('replaces streamed assistant content when display text is sanitized', () => {
    const state = [
      { type: 'assistantTurnStarted' as const, id: 'assistant-1' },
      {
        type: 'assistantContentDeltaReceived' as const,
        assistantTurnId: 'assistant-1',
        delta: 'Set API_TOKEN to secret-value',
      },
      {
        type: 'assistantContentReplaced' as const,
        assistantTurnId: 'assistant-1',
        content: 'Set API_TOKEN to [REDACTED]',
      },
    ].reduce(reduceConversationUiState, createConversationUiState())

    expect(state.turns[0].content).toBe('Set API_TOKEN to [REDACTED]')
  })

  it('keeps partial assistant content but removes empty placeholders when streaming fails', () => {
    const withPartialContent = [
      { type: 'assistantTurnStarted' as const, id: 'assistant-1' },
      {
        type: 'assistantContentDeltaReceived' as const,
        assistantTurnId: 'assistant-1',
        delta: 'Partial answer',
      },
      {
        type: 'assistantTurnFailed' as const,
        assistantTurnId: 'assistant-1',
        message: 'Stream interrupted',
      },
    ].reduce(reduceConversationUiState, createConversationUiState())

    expect(withPartialContent.error).toBe('Stream interrupted')
    expect(withPartialContent.isRunning).toBe(false)
    expect(withPartialContent.turns).toHaveLength(1)
    expect(withPartialContent.turns[0]).toMatchObject({
      id: 'assistant-1',
      content: 'Partial answer',
      traceStatus: null,
    })

    const withoutContent = [
      { type: 'assistantTurnStarted' as const, id: 'assistant-2' },
      {
        type: 'assistantTurnFailed' as const,
        assistantTurnId: 'assistant-2',
        message: 'Stream interrupted',
      },
    ].reduce(reduceConversationUiState, createConversationUiState())

    expect(withoutContent.error).toBe('Stream interrupted')
    expect(withoutContent.isRunning).toBe(false)
    expect(withoutContent.turns).toEqual([])
  })

  it('toggles selected controls and starts a new Conversation without browser persistence', () => {
    const state = [
      { type: 'toolToggled' as const, toolId: 'web-search' },
      { type: 'documentToggled' as const, documentId: 'doc-1' },
      { type: 'userTurnSubmitted' as const, id: 'user-1', content: 'Use this context' },
      { type: 'assistantTurnStarted' as const, id: 'assistant-1', sessionId: 'session-1' },
      { type: 'requestFailed' as const, message: 'Network failed' },
      { type: 'newConversationStarted' as const },
    ].reduce(reduceConversationUiState, createConversationUiState())

    expect(state).toEqual({
      turns: [],
      selectedTools: ['web-search'],
      selectedDocuments: ['doc-1'],
      isRunning: false,
      error: null,
      conversationSessionId: null,
    })
  })

  it('applies selected control defaults and appends completed assistant turns', () => {
    const trace = { visibility: 'summary' as const, tools: [], retrieval: [] }
    const state = [
      { type: 'selectedToolsChanged' as const, selectedTools: ['web-search'] },
      { type: 'selectedDocumentsChanged' as const, selectedDocuments: ['doc-1'] },
      {
        type: 'assistantTurnCompleted' as const,
        id: 'assistant-1',
        content: 'Completed answer.',
        trace,
        sessionId: 'session-1',
      },
    ].reduce(reduceConversationUiState, createConversationUiState())

    expect(state.selectedTools).toEqual(['web-search'])
    expect(state.selectedDocuments).toEqual(['doc-1'])
    expect(state.conversationSessionId).toBe('session-1')
    expect(state.isRunning).toBe(false)
    expect(state.turns).toEqual([
      {
        id: 'assistant-1',
        role: 'assistant',
        content: 'Completed answer.',
        activitySteps: [],
        trace,
        traceStatus: null,
      },
    ])
  })

  it('removes generated assistant turns by content prefix without deleting matching user turns', () => {
    const state = [
      { type: 'userTurnSubmitted' as const, id: 'user-1', content: 'Search results for policy' },
      { type: 'assistantTurnAppended' as const, id: 'assistant-1', content: 'Search results for policy' },
      { type: 'assistantTurnsRemovedByContentPrefix' as const, prefix: 'Search results for' },
    ].reduce(reduceConversationUiState, createConversationUiState())

    expect(state.turns).toEqual([
      expect.objectContaining({
        id: 'user-1',
        role: 'user',
        content: 'Search results for policy',
      }),
    ])
  })
})
