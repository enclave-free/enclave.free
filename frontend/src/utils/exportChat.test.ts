import { afterEach, describe, expect, it, vi } from 'vitest'
import { generateExport } from './exportChat'
import type { Message } from '../components/chat/ChatMessage'

type TestMessage = Message & {
  user_memory?: Array<{
    kind: string
    content: string
    importance: number
  }>
  userMemory?: string
}

const translations = {
  defaultTitle: 'Conversation Export',
  roleUser: 'User',
  roleAssistant: 'Assistant',
  footer: 'Exported from {{instanceName}}',
  exportedOn: 'Exported on {{timestamp}}',
}

describe('generateExport', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('exports conversation messages without User Memory records', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-05-10T12:00:00Z'))

    const messages: TestMessage[] = [
      {
        id: 'm1',
        role: 'user',
        content: 'Can you help me plan this?',
        user_memory: [
          {
            kind: 'preference',
            content: 'Prefers concise answers.',
            importance: 8,
          },
        ],
      },
      {
        id: 'm2',
        role: 'assistant',
        content: 'Yes. Let us make a short plan.',
        userMemory: 'Prefers high detail answers.',
      },
    ]

    const exported = generateExport({
      messages,
      format: 'md',
      translations,
    })

    expect(exported).toContain('Can you help me plan this?')
    expect(exported).toContain('Yes. Let us make a short plan.')
    expect(exported).not.toContain('USER MEMORY')
    expect(exported).not.toContain('user_memory')
    expect(exported).not.toContain('userMemory')
    expect(exported).not.toContain('Prefers concise answers.')
    expect(exported).not.toContain('Prefers high detail answers.')
    expect(exported).not.toContain('importance')

    const exportedTxt = generateExport({
      messages,
      format: 'txt',
      translations,
    })

    expect(exportedTxt).toContain('Can you help me plan this?')
    expect(exportedTxt).toContain('Yes. Let us make a short plan.')
    expect(exportedTxt).not.toContain('USER MEMORY')
    expect(exportedTxt).not.toContain('user_memory')
    expect(exportedTxt).not.toContain('userMemory')
    expect(exportedTxt).not.toContain('Prefers concise answers.')
    expect(exportedTxt).not.toContain('Prefers high detail answers.')
    expect(exportedTxt).not.toContain('importance')
  })

  it('exports viewer-visible Conversation Trace metadata', () => {
    const messages: TestMessage[] = [
      {
        id: 'm1',
        role: 'assistant',
        content: 'Here is the answer.',
        trace: {
          visibility: 'summary',
          reasoning: {
            summary: 'Sage used Web search before answering.',
          },
          tools: [
            {
              id: 'web-search',
              name: 'Web search',
              status: 'success',
              execution: 'server',
              output_summary: 'Found 3 relevant results.',
              warnings: [],
              metadata: {},
            },
          ],
          retrieval: [],
          suppressed: false,
        },
      },
    ]

    const exported = generateExport({
      messages,
      format: 'md',
      translations,
    })

    expect(exported).toContain('Conversation Trace')
    expect(exported).toContain('Sage used Web search before answering.')
    expect(exported).toContain('Web search')
    expect(exported).toContain('Found 3 relevant results.')
  })
})
