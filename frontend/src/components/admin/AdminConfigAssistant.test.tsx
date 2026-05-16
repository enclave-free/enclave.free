import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AdminConfigAssistant } from './AdminConfigAssistant'
import { sendLlmChatStreamWithUnifiedTools } from '../../utils/llmChat'
import { ThemeProvider } from '../../theme'

vi.mock('../../utils/adminApi', () => ({
  adminFetch: vi.fn(),
}))

vi.mock('../../utils/llmChat', () => ({
  sendLlmChatStreamWithUnifiedTools: vi.fn(),
  sendLlmChatWithUnifiedTools: vi.fn(),
}))

describe('AdminConfigAssistant', () => {
  beforeEach(() => {
    const store = new Map<string, string>()
    vi.stubGlobal('localStorage', {
      getItem: vi.fn((key: string) => store.get(key) ?? null),
      removeItem: vi.fn((key: string) => {
        store.delete(key)
      }),
      setItem: vi.fn((key: string, value: string) => {
        store.set(key, value)
      }),
      clear: vi.fn(() => {
        store.clear()
      }),
    })
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
      const url = String(input)
      if (url.endsWith('/session-defaults')) {
        return Promise.resolve(Response.json({ web_search_enabled: false }))
      }
      return Promise.resolve(Response.json({}))
    }))
    vi.stubGlobal('matchMedia', vi.fn().mockReturnValue({
      matches: false,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }))
    HTMLElement.prototype.scrollIntoView = vi.fn()
  })

  afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
    vi.clearAllMocks()
  })

  it('passes previous admin assistant turns into follow-up chat requests', async () => {
    const user = userEvent.setup()
    vi.mocked(sendLlmChatStreamWithUnifiedTools)
      .mockImplementationOnce(async ({ onEvent }) => {
        onEvent('assistant_message_started', { message_id: 'msg-1', session_id: 'session-1' })
        onEvent('answer_delta', {
          message_id: 'msg-1',
          delta: 'I recommend updating Instance Name and Assistant Name.',
        })
        onEvent('done', { message_id: 'msg-1', session_id: 'session-1' })
      })
      .mockImplementationOnce(async ({ onEvent }) => {
        onEvent('assistant_message_started', { message_id: 'msg-2', session_id: 'session-1' })
        onEvent('answer_delta', { message_id: 'msg-2', delta: 'Applying those suggestions.' })
        onEvent('done', { message_id: 'msg-2', session_id: 'session-1' })
      })

    render(
      <ThemeProvider>
        <AdminConfigAssistant />
      </ThemeProvider>
    )

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith('/api/session-defaults')
    })

    await user.type(
      screen.getByRole('textbox', { name: 'Ask about admin configuration...' }),
      'Change more of the copy.'
    )
    await user.click(screen.getByRole('button', { name: 'Send message' }))

    expect(await screen.findByText('I recommend updating Instance Name and Assistant Name.')).toBeInTheDocument()

    await user.type(
      screen.getByRole('textbox', { name: 'Ask about admin configuration...' }),
      'your suggestions above'
    )
    await user.click(screen.getByRole('button', { name: 'Send message' }))

    await waitFor(() => {
      expect(sendLlmChatStreamWithUnifiedTools).toHaveBeenCalledTimes(2)
    })
    expect(vi.mocked(sendLlmChatStreamWithUnifiedTools).mock.calls[1][0]).toEqual(expect.objectContaining({
      content: 'your suggestions above',
      conversationHistory: [
        { role: 'user', content: 'Change more of the copy.' },
        { role: 'assistant', content: 'I recommend updating Instance Name and Assistant Name.' },
      ],
      sessionId: 'session-1',
    }))
  })
})
