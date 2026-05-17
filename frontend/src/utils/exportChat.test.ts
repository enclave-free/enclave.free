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
  copiedExportNotice: 'This export is outside Active Storage Lifecycle after download.',
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
    expect(exported).toContain('outside Active Storage Lifecycle')

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
    expect(exportedTxt).toContain('outside Active Storage Lifecycle')
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

  it('exports only compact badges for minimal Conversation Trace metadata', () => {
    const messages: TestMessage[] = [
      {
        id: 'm1',
        role: 'assistant',
        content: 'Here is the answer.',
        trace: {
          visibility: 'minimal',
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
          retrieval: [
            {
              source_type: 'document',
              title: 'Tenant Rights Guide',
              summary: 'Matched eviction timeline section.',
            },
          ],
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
    expect(exported).toContain('Web search')
    expect(exported).toContain('Tenant Rights Guide')
    expect(exported).not.toContain('Sage used Web search before answering.')
    expect(exported).not.toContain('Found 3 relevant results.')
    expect(exported).not.toContain('Matched eviction timeline section.')
  })
})
