import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { type ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ChatPage, ENCLAVE_USER_EMAIL_KEY } from './ChatPage'
import { InstanceConfigProvider } from '../context/InstanceConfigContext'
import { ThemeProvider } from '../theme'
import { DEFAULT_INSTANCE_CONFIG, INSTANCE_CONFIG_KEY } from '../types/instance'
import { adminFetch, isAdminAuthenticated } from '../utils/adminApi'
import { sendLlmChatStreamWithUnifiedTools, sendLlmChatWithUnifiedTools } from '../utils/llmChat'

vi.mock('../utils/adminApi', () => ({
  adminFetch: vi.fn(),
  isAdminAuthenticated: vi.fn(() => false),
}))

vi.mock('../utils/llmChat', () => ({
  sendLlmChatStreamWithUnifiedTools: vi.fn(),
  sendLlmChatWithUnifiedTools: vi.fn(),
}))

const originalScrollIntoView = HTMLElement.prototype.scrollIntoView

function ChatPageTestWrapper({ children }: { children: ReactNode }) {
  return (
    <MemoryRouter initialEntries={['/']}>
      <ThemeProvider>
        <InstanceConfigProvider>
          {children}
        </InstanceConfigProvider>
      </ThemeProvider>
    </MemoryRouter>
  )
}

describe('ChatPage', () => {
  const mockAdminFetch = vi.mocked(adminFetch)
  const mockIsAdminAuthenticated = vi.mocked(isAdminAuthenticated)

  beforeEach(() => {
    mockIsAdminAuthenticated.mockReturnValue(false)
    mockAdminFetch.mockResolvedValue(Response.json({}))
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
    localStorage.setItem('enclave-theme', 'light')
    localStorage.setItem(INSTANCE_CONFIG_KEY, JSON.stringify(DEFAULT_INSTANCE_CONFIG))
    localStorage.setItem(ENCLAVE_USER_EMAIL_KEY, 'reader@example.com')

    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
      const url = String(input)

      if (url.endsWith('/settings/public')) {
        return Promise.resolve(Response.json({ settings: {} }))
      }

      if (url.endsWith('/session-defaults')) {
        return Promise.resolve(Response.json({
          web_search_enabled: true,
          default_document_ids: ['doc-1'],
        }))
      }

      if (url.endsWith('/ingest/jobs')) {
        return Promise.resolve(Response.json({
          jobs: [
            {
              job_id: 'doc-1',
              filename: 'operator-handbook.pdf',
              status: 'completed',
              total_chunks: 12,
            },
            {
              job_id: 'doc-2',
              filename: 'user-faq.md',
              status: 'completed',
              total_chunks: 4,
            },
          ],
        }))
      }

      if (url.endsWith('/users/me/onboarding-status')) {
        return Promise.resolve(Response.json({
          needs_user_type: false,
          needs_onboarding: false,
          effective_user_type_id: null,
        }))
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
    HTMLElement.prototype.scrollIntoView = originalScrollIntoView
    vi.clearAllMocks()
    document.documentElement.classList.remove('dark')
  })

  it('activates the Web Search tool when it is enabled by default for new conversations', async () => {
    render(<ChatPage />, { wrapper: ChatPageTestWrapper })

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(expect.stringMatching(/^\/api\/session-defaults(?:\?|$)/))
    })

    expect(screen.getByRole('button', { name: 'Web' })).toHaveAttribute('aria-pressed', 'true')
  })

  it('selects documents that are active by default for new conversations', async () => {
    render(<ChatPage />, { wrapper: ChatPageTestWrapper })

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Docs 1' })).toBeInTheDocument()
    })

    await userEvent.click(screen.getByRole('button', { name: 'Docs 1' }))

    expect(screen.getByRole('button', { name: /operator-handbook/ })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: /user-faq/ })).toHaveAttribute('aria-pressed', 'false')
  })

  it('contains chat request failures in a named error note', async () => {
    const user = (await import('@testing-library/user-event')).default.setup()
    vi.mocked(sendLlmChatStreamWithUnifiedTools).mockRejectedValueOnce(new Error('Stream unavailable'))
    vi.mocked(sendLlmChatWithUnifiedTools).mockRejectedValueOnce(new Error('Model gateway unavailable'))

    render(<ChatPage />, { wrapper: ChatPageTestWrapper })

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Docs 1' })).toBeInTheDocument()
    })
    await user.click(screen.getByRole('button', { name: 'Docs 1' }))
    await user.click(screen.getByRole('button', { name: /operator-handbook/ }))

    await user.type(screen.getByRole('textbox', { name: 'Ask anything...' }), 'Hello')
    await user.click(screen.getByRole('button', { name: 'Send message' }))

    const errorNote = await screen.findByRole('note', { name: 'Chat request error' })
    expect(errorNote).toHaveTextContent('Model gateway unavailable')
  })

  it('clears the live trace status when a chat stream finishes without a final trace', async () => {
    const user = userEvent.setup()
    vi.mocked(sendLlmChatStreamWithUnifiedTools).mockImplementationOnce(async ({ onEvent }) => {
      onEvent('assistant_message_started', { message_id: 'msg-stream', session_id: 'session-1' })
      onEvent('trace_status', { message_id: 'msg-stream', status: 'Writing answer...' })
      onEvent('answer_delta', { message_id: 'msg-stream', delta: 'Streamed hello.' })
      onEvent('done', { message_id: 'msg-stream', session_id: 'session-1' })
    })

    render(<ChatPage />, { wrapper: ChatPageTestWrapper })

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Docs 1' })).toBeInTheDocument()
    })
    await user.click(screen.getByRole('button', { name: 'Docs 1' }))
    await user.click(screen.getByRole('button', { name: /operator-handbook/ }))

    await user.type(screen.getByRole('textbox', { name: 'Ask anything...' }), 'Hello')
    await user.click(screen.getByRole('button', { name: 'Send message' }))

    expect(await screen.findByText('Streamed hello.')).toBeInTheDocument()
    await waitFor(() => {
      expect(screen.queryByText('Writing answer...')).not.toBeInTheDocument()
    })
    expect(sendLlmChatWithUnifiedTools).not.toHaveBeenCalled()
  })

  it('surfaces stream errors without retrying after answer text has started', async () => {
    const user = userEvent.setup()
    vi.mocked(sendLlmChatStreamWithUnifiedTools).mockImplementationOnce(async ({ onEvent }) => {
      onEvent('assistant_message_started', { message_id: 'msg-stream', session_id: 'session-1' })
      onEvent('answer_delta', { message_id: 'msg-stream', delta: 'Partial answer.' })
      onEvent('error', { message_id: 'msg-stream', detail: 'Model stream interrupted' })
    })

    render(<ChatPage />, { wrapper: ChatPageTestWrapper })

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Docs 1' })).toBeInTheDocument()
    })
    await user.click(screen.getByRole('button', { name: 'Docs 1' }))
    await user.click(screen.getByRole('button', { name: /operator-handbook/ }))

    await user.type(screen.getByRole('textbox', { name: 'Ask anything...' }), 'Hello')
    await user.click(screen.getByRole('button', { name: 'Send message' }))

    expect(await screen.findByText('Partial answer.')).toBeInTheDocument()
    const errorNote = await screen.findByRole('note', { name: 'Chat request error' })
    expect(errorNote).toHaveTextContent('Model stream interrupted')
    expect(sendLlmChatWithUnifiedTools).not.toHaveBeenCalled()
  })

  it('keeps Config selected by default for authenticated admin chat turns', async () => {
    const user = userEvent.setup()
    mockIsAdminAuthenticated.mockReturnValue(true)
    mockAdminFetch.mockImplementation((endpoint: string) => {
      if (endpoint === '/admin/deployment/config') {
        return Promise.resolve(Response.json({
          llm: [],
          embedding: [],
          email: [],
          storage: [],
          security: [],
          search: [],
          domains: [],
          ssl: [],
          general: [],
        }))
      }
      return Promise.resolve(Response.json({}))
    })
    vi.mocked(sendLlmChatStreamWithUnifiedTools).mockImplementationOnce(async ({ onEvent }) => {
      onEvent('assistant_message_started', { message_id: 'admin-msg', session_id: 'session-1' })
      onEvent('answer_delta', { message_id: 'admin-msg', delta: 'I can inspect config.' })
      onEvent('done', { message_id: 'admin-msg', session_id: 'session-1' })
    })

    render(<ChatPage />, { wrapper: ChatPageTestWrapper })

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Config Name' })).toHaveAttribute('aria-pressed', 'true')
    })

    await user.type(screen.getByRole('textbox', { name: 'Ask anything...' }), 'Review instance config.')
    await user.click(screen.getByRole('button', { name: 'Send message' }))

    await waitFor(() => {
      expect(sendLlmChatStreamWithUnifiedTools).toHaveBeenCalled()
    })
    expect(vi.mocked(sendLlmChatStreamWithUnifiedTools).mock.calls[0][0]).toEqual(expect.objectContaining({
      content: 'Review instance config.',
      tools: expect.arrayContaining(['admin-config']),
    }))
  })

  it('applies a grouped admin Change Confirmation from authenticated admin chat', async () => {
    const user = userEvent.setup()
    mockIsAdminAuthenticated.mockReturnValue(true)
    mockAdminFetch.mockImplementation((endpoint: string, options?: RequestInit) => {
      if (endpoint === '/admin/deployment/config') {
        return Promise.resolve(Response.json({
          llm: [],
          embedding: [],
          email: [],
          storage: [],
          security: [],
          search: [],
          domains: [],
          ssl: [],
          general: [],
        }))
      }
      if (endpoint === '/admin/user-types') {
        return Promise.resolve(Response.json({ types: [] }))
      }
      if (endpoint === '/admin/settings' && options?.method === 'PUT') {
        return Promise.resolve(Response.json({ ok: true }))
      }
      if (endpoint === '/admin/ai-config/prompt_tone' && options?.method === 'PUT') {
        return Promise.resolve(Response.json({ ok: true }))
      }
      if (endpoint === '/admin/deployment/config/validate') {
        return Promise.resolve(Response.json({ valid: true, warnings: [] }))
      }
      if (endpoint === '/admin/deployment/restart-required') {
        return Promise.resolve(Response.json({ restart_required: false, changed_keys: [] }))
      }
      return Promise.resolve(Response.json({}))
    })
    const changeSet = {
      version: 1,
      summary: 'Configure instance theme and assistant voice',
      requests: [
        {
          method: 'PUT',
          path: '/admin/settings',
          body: {
            instance_name: 'WLC Political Prisoners Resource Hub',
            primary_color: '#1E3A8A',
          },
        },
        {
          method: 'PUT',
          path: '/admin/ai-config/prompt_tone',
          body: { value: 'Helpful, concise, and direct.' },
        },
      ],
    }
    vi.mocked(sendLlmChatStreamWithUnifiedTools).mockImplementationOnce(async ({ onEvent }) => {
      onEvent('assistant_message_started', { message_id: 'admin-msg', session_id: 'session-1' })
      onEvent('answer_delta', {
        message_id: 'admin-msg',
        delta: `Here is the change.\n\n\`\`\`json\n${JSON.stringify(changeSet, null, 2)}\n\`\`\``,
      })
      onEvent('done', { message_id: 'admin-msg', session_id: 'session-1' })
    })

    render(<ChatPage />, { wrapper: ChatPageTestWrapper })

    await user.type(screen.getByRole('textbox', { name: 'Ask anything...' }), 'Set up the theme in one pass.')
    await user.click(screen.getByRole('button', { name: 'Send message' }))

    expect(await screen.findByText('Pending changes: Configure instance theme and assistant voice')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Apply' }))

    await waitFor(() => {
      expect(mockAdminFetch).toHaveBeenCalledWith('/admin/settings', expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify({
          instance_name: 'WLC Political Prisoners Resource Hub',
          primary_color: '#1E3A8A',
        }),
      }))
      expect(mockAdminFetch).toHaveBeenCalledWith('/admin/ai-config/prompt_tone', expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify({ value: 'Helpful, concise, and direct.' }),
      }))
    })
  })

  it('masks secret Deployment Setting values in authenticated admin chat Change Confirmation previews', async () => {
    const user = userEvent.setup()
    mockIsAdminAuthenticated.mockReturnValue(true)
    mockAdminFetch.mockImplementation((endpoint: string) => {
      if (endpoint === '/admin/deployment/config') {
        return Promise.resolve(Response.json({
          llm: [
            {
              key: 'LLM_API_KEY',
              value: '[CONFIGURED]',
              is_secret: true,
              requires_restart: true,
            },
          ],
          embedding: [],
          email: [],
          storage: [],
          security: [],
          search: [],
          domains: [],
          ssl: [],
          general: [],
        }))
      }
      return Promise.resolve(Response.json({}))
    })
    const changeSet = {
      version: 1,
      summary: 'Update model provider secret',
      requests: [
        {
          method: 'PUT',
          path: '/admin/deployment/config/LLM_API_KEY',
          body: { value: 'sk-live-secret-value' },
        },
      ],
    }
    vi.mocked(sendLlmChatStreamWithUnifiedTools).mockImplementationOnce(async ({ onEvent }) => {
      onEvent('assistant_message_started', { message_id: 'admin-msg', session_id: 'session-1' })
      onEvent('answer_delta', {
        message_id: 'admin-msg',
        delta: `Here is the secret update.\n\n\`\`\`json\n${JSON.stringify(changeSet, null, 2)}\n\`\`\``,
      })
      onEvent('done', { message_id: 'admin-msg', session_id: 'session-1' })
    })

    render(<ChatPage />, { wrapper: ChatPageTestWrapper })

    await user.type(screen.getByRole('textbox', { name: 'Ask anything...' }), 'Rotate the model secret.')
    await user.click(screen.getByRole('button', { name: 'Send message' }))

    expect(await screen.findByText('Pending changes: Update model provider secret')).toBeInTheDocument()
    expect(screen.getByText('PUT /admin/deployment/config/LLM_API_KEY')).toBeInTheDocument()
    expect(document.body.textContent).toContain('[REDACTED]')
    expect(document.body.textContent).not.toContain('sk-live-secret-value')
  })
})
