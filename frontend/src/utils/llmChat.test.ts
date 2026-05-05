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
      body: JSON.stringify({
        message: 'What was the secret word?',
        tools: [],
        session_id: 'session-123',
      }),
    }))
  })
})
