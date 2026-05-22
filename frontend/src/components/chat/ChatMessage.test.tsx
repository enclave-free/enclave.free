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

function renderMessage(content: string, role: 'user' | 'assistant' = 'assistant', trace?: Parameters<typeof ChatMessage>[0]['message']['trace']) {
  return render(
    <ThemeProvider>
      <InstanceConfigProvider>
        <ChatMessage
          message={{
            id: 'message-1',
            role,
            content,
            trace,
          }}
        />
      </InstanceConfigProvider>
    </ThemeProvider>
  )
}

describe('ChatMessage', () => {
  beforeEach(() => {
    stubLocalStorage()
    localStorage.setItem('enclave-theme', 'light')
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

  it('keeps assistant markdown HTML and unsafe links inert', () => {
    renderMessage([
      'Hello <img src=x onerror="alert(1)" />',
      '',
      '[unsafe link](javascript:alert(1))',
      '[protocol-relative](//example.com/path)',
    ].join('\n'))

    expect(document.querySelector('img')).not.toBeInTheDocument()
    expect(document.body).toHaveTextContent('<img src=x onerror="alert(1)" />')
    expect(screen.getByText('unsafe link')).not.toHaveAttribute('href')
    expect(screen.getByText('protocol-relative')).not.toHaveAttribute('href')
  })

  it('copies fenced code content from the accessible copy action', async () => {
    const user = userEvent.setup()
    stubClipboard()

    renderMessage(['```ts', 'const answer = 42', '```'].join('\n'))

    await user.click(screen.getByRole('button', { name: 'Copy code' }))

    expect(clipboardWriteText).toHaveBeenCalledWith('const answer = 42')
  })

  it('copies the full assistant message from the message copy icon', async () => {
    const user = userEvent.setup()
    stubClipboard()
    const content = 'Here is a useful answer with **markdown**.'

    renderMessage(content)

    await user.click(screen.getByRole('button', { name: 'Copy message' }))

    expect(clipboardWriteText).toHaveBeenCalledWith(content)
    expect(screen.getByRole('button', { name: 'Copied message' })).toBeInTheDocument()
  })

  it('copies user messages from the same message copy icon', async () => {
    const user = userEvent.setup()
    stubClipboard()
    const content = 'Please make this easy to copy.'

    renderMessage(content, 'user')

    await user.click(screen.getByRole('button', { name: 'Copy message' }))

    expect(clipboardWriteText).toHaveBeenCalledWith(content)
  })

  it('renders assistant Conversation Trace details inline', () => {
    renderMessage('Here is the answer.', 'assistant', {
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
          input_summary: 'current policy updates',
          output_summary: 'Found 3 relevant results.',
          warnings: [],
          metadata: {},
        },
      ],
      retrieval: [],
      suppressed: false,
    })

    expect(screen.getByText('Conversation Trace')).toBeInTheDocument()
    expect(screen.getByText('Sage used Web search before answering.')).toBeInTheDocument()
    expect(screen.getByText('Web search')).toBeInTheDocument()
    expect(screen.getByText('Found 3 relevant results.')).toBeInTheDocument()
  })

  it('renders minimal assistant trace as compact usage badges', () => {
    renderMessage('Here is the answer.', 'assistant', {
      visibility: 'minimal',
      reasoning: {
        summary: 'Sage used internal context before answering.',
      },
      tools: [
        {
          id: 'web-search',
          name: 'Web search',
          status: 'success',
          execution: 'server',
          output_summary: 'Found 3 relevant results.',
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
    })

    expect(screen.queryByText('Conversation Trace')).not.toBeInTheDocument()
    expect(screen.queryByText('Sage used internal context before answering.')).not.toBeInTheDocument()
    expect(screen.queryByText('Found 3 relevant results.')).not.toBeInTheDocument()
    expect(screen.getByText('Web search')).toBeInTheDocument()
    expect(screen.getByText('Tenant Rights Guide')).toBeInTheDocument()
  })

  it('does not render an empty assistant bubble for non-renderable trace metadata', () => {
    renderMessage('', 'assistant', {
      visibility: 'summary',
      tools: [],
      retrieval: [],
      suppressed: false,
    })

    expect(screen.queryByText(DEFAULT_INSTANCE_CONFIG.assistantName)).not.toBeInTheDocument()
    expect(screen.queryByText('Conversation Trace')).not.toBeInTheDocument()
  })

  it('does not render a minimal trace strip when there are no visible chips', () => {
    renderMessage('Here is the answer.', 'assistant', {
      visibility: 'minimal',
      reasoning: {
        summary: 'Hidden in minimal mode.',
      },
      tools: [],
      retrieval: [],
      suppressed: false,
    })

    expect(screen.queryByLabelText('Conversation trace summary')).not.toBeInTheDocument()
    expect(screen.queryByText('Hidden in minimal mode.')).not.toBeInTheDocument()
  })

  it('does not render the internal writing trace as assistant content', () => {
    render(
      <ThemeProvider>
        <InstanceConfigProvider>
          <ChatMessage
            message={{
              id: 'message-1',
              role: 'assistant',
              content: '',
              traceStatus: 'Writing answer...',
            }}
          />
        </InstanceConfigProvider>
      </ThemeProvider>
    )

    expect(screen.queryByText('Writing answer...')).not.toBeInTheDocument()
  })

  it('renders meaningful live trace status while a streamed assistant turn is in progress', () => {
    render(
      <ThemeProvider>
        <InstanceConfigProvider>
          <ChatMessage
            message={{
              id: 'message-1',
              role: 'assistant',
              content: 'Partial answer',
              traceStatus: 'Searching documents...',
            }}
          />
        </InstanceConfigProvider>
      </ThemeProvider>
    )

    expect(screen.getByText('Searching documents...')).toBeInTheDocument()
  })
})
