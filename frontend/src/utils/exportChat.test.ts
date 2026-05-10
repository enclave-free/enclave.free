import { afterEach, describe, expect, it, vi } from 'vitest'
import { generateExport } from './exportChat'
import type { Message } from '../components/chat/ChatMessage'

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

    const messages = [
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
    ] as unknown as Message[]

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
  })
})
