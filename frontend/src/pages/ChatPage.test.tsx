import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { type ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ChatPage } from './ChatPage'
import { InstanceConfigProvider } from '../context/InstanceConfigContext'
import { ThemeProvider } from '../theme'
import { DEFAULT_INSTANCE_CONFIG, INSTANCE_CONFIG_KEY } from '../types/instance'

vi.mock('../utils/adminApi', () => ({
  adminFetch: vi.fn(),
  isAdminAuthenticated: vi.fn(() => false),
}))

vi.mock('../utils/llmChat', () => ({
  sendLlmChatWithUnifiedTools: vi.fn(),
}))

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
    localStorage.setItem('sanctum-theme', 'light')
    localStorage.setItem(INSTANCE_CONFIG_KEY, JSON.stringify(DEFAULT_INSTANCE_CONFIG))
    localStorage.setItem('sanctum_user_email', 'reader@example.com')

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
  })

  afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
    vi.clearAllMocks()
    document.documentElement.classList.remove('dark')
  })

  it('activates the Web Search tool when it is enabled by default for new conversations', async () => {
    render(<ChatPage />, { wrapper: ChatPageTestWrapper })

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith('/api/session-defaults')
    })

    expect(screen.getByRole('button', { name: 'Web' })).toHaveAttribute('aria-pressed', 'true')
  })

  it('selects documents that are active by default for new conversations', async () => {
    render(<ChatPage />, { wrapper: ChatPageTestWrapper })

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Docs 1' })).toBeInTheDocument()
    })

    await screen.getByRole('button', { name: 'Docs 1' }).click()

    expect(screen.getByRole('button', { name: /operator-handbook/ })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: /user-faq/ })).toHaveAttribute('aria-pressed', 'false')
  })
})
