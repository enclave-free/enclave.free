import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ChatMessage } from './ChatMessage'
import { InstanceConfigProvider } from '../../context/InstanceConfigContext'
import { ThemeProvider } from '../../theme'
import { DEFAULT_INSTANCE_CONFIG, INSTANCE_CONFIG_KEY } from '../../types/instance'

let clipboardWriteText: ReturnType<typeof vi.fn>
const originalClipboardDescriptor = Object.getOwnPropertyDescriptor(window.navigator, 'clipboard')

function stubLocalStorage() {
  const store = new Map<string, string>()
  vi.stubGlobal('localStorage', {
    getItem: vi.fn((key: string) => store.get(key) ?? null),
    setItem: vi.fn((key: string, value: string) => {
      store.set(key, value)
    }),
    removeItem: vi.fn((key: string) => {
      store.delete(key)
    }),
    clear: vi.fn(() => {
      store.clear()
    }),
  })
}

function renderMessage(content: string) {
  return render(
    <ThemeProvider>
      <InstanceConfigProvider>
        <ChatMessage
          message={{
            id: 'message-1',
            role: 'assistant',
            content,
          }}
        />
      </InstanceConfigProvider>
    </ThemeProvider>
  )
}

describe('ChatMessage', () => {
  beforeEach(() => {
    stubLocalStorage()
    localStorage.setItem('sanctum-theme', 'light')
    localStorage.setItem(INSTANCE_CONFIG_KEY, JSON.stringify(DEFAULT_INSTANCE_CONFIG))
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
      })
    )
    vi.stubGlobal('matchMedia', vi.fn().mockReturnValue({
      matches: false,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }))
  })

  afterEach(() => {
    cleanup()
    if (originalClipboardDescriptor) {
      Object.defineProperty(window.navigator, 'clipboard', originalClipboardDescriptor)
    } else {
      delete (window.navigator as unknown as { clipboard?: Clipboard }).clipboard
    }
    vi.unstubAllGlobals()
    vi.clearAllMocks()
    document.documentElement.classList.remove('dark')
  })

  function stubClipboard() {
    clipboardWriteText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(window.navigator, 'clipboard', {
      configurable: true,
      writable: true,
      value: {
        writeText: clipboardWriteText,
      },
    })
  }

  it('renders representative assistant markdown through public elements', () => {
    renderMessage(
      [
        '## Brief',
        '',
        'Read [the docs](https://example.com) and keep `inline code` visible.',
        '',
        '- First point',
        '- Second point',
        '',
        '1. Review requested changes',
        '2. Confirm the Change Confirmation',
        '',
        '> Keep secrets masked.',
        '',
        '| Setting | Value |',
        '| --- | --- |',
        '| Model Provider | Tinfoil |',
        '',
        '```ts',
        'const answer = 42',
        '```',
      ].join('\n')
    )

    expect(screen.getByRole('heading', { name: 'Brief' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'the docs' })).toHaveAttribute('href', 'https://example.com')
    expect(screen.getByText('inline code')).toBeInTheDocument()
    expect(screen.getByText('First point')).toBeInTheDocument()
    expect(screen.getByText('Second point')).toBeInTheDocument()
    expect(screen.getByText('Review requested changes')).toBeInTheDocument()
    expect(screen.getByText('Keep secrets masked.')).toBeInTheDocument()
    expect(screen.getByRole('table')).toHaveTextContent('Model Provider')
    expect(screen.getByRole('table')).toHaveTextContent('Tinfoil')
    expect(screen.getByText('ts')).toBeInTheDocument()
    expect(document.body).toHaveTextContent('const answer = 42')
  })

  it('copies fenced code content from the accessible copy action', async () => {
    const user = userEvent.setup()
    stubClipboard()

    renderMessage(['```ts', 'const answer = 42', '```'].join('\n'))

    await user.click(screen.getByRole('button', { name: 'Copy code' }))

    expect(clipboardWriteText).toHaveBeenCalledWith('const answer = 42')
  })
})
