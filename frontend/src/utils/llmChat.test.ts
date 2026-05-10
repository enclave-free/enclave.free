import { beforeEach, describe, expect, it, vi } from 'vitest'
import { sendLlmChatWithUnifiedTools } from './llmChat'

vi.mock('./adminApi', () => ({
  adminFetch: vi.fn(),
  isAdminAuthenticated: vi.fn(() => false),
}))

vi.mock('./encryption', () => ({
  decryptField: vi.fn(),
  hasNip04Support: vi.fn(() => false),
}))

describe('sendLlmChatWithUnifiedTools', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json({ message: 'ok' })))
  })

  it('sends the conversation session id on memory-backed chat turns', async () => {
    await sendLlmChatWithUnifiedTools({
      content: 'What was the secret word?',
      tools: [],
      t: (key) => key,
      sessionId: 'session-123',
    })

    expect(fetch).toHaveBeenCalledWith('/api/llm/chat', expect.objectContaining({
      method: 'POST',
      credentials: 'include',
      body: expect.any(String),
    }))
    const [, options] = vi.mocked(fetch).mock.calls[0]
    expect(JSON.parse(String(options?.body))).toEqual({
      message: 'What was the secret word?',
      tools: [],
      session_id: 'session-123',
    })
  })

  it('omits session_id when no conversation session id is provided', async () => {
    await sendLlmChatWithUnifiedTools({
      content: 'Start fresh',
      tools: [],
      t: (key) => key,
    })

    expect(fetch).toHaveBeenCalledWith('/api/llm/chat', expect.objectContaining({
      method: 'POST',
      credentials: 'include',
      body: expect.any(String),
    }))
    const [, options] = vi.mocked(fetch).mock.calls[0]
    expect(JSON.parse(String(options?.body))).not.toHaveProperty('session_id')
  })

  it('sends admin-config as a backend tool instead of requiring client tool context', async () => {
    await sendLlmChatWithUnifiedTools({
      content: 'Check my deployment config',
      tools: ['admin-config'],
      t: (key) => key,
    })

    const [, options] = vi.mocked(fetch).mock.calls[0]
    expect(JSON.parse(String(options?.body))).toEqual({
      message: 'Check my deployment config',
      tools: ['admin-config'],
    })
  })
})
