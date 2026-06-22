import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ConversationSurface } from './ConversationSurface';
import type { Message } from './ChatMessage';
import type { ConversationMessageActionId } from './ConversationMessageActions';
import type { ConversationSurfaceTurn } from './ConversationSurfaceModel';
import { InstanceConfigProvider } from '../../context/InstanceConfigContext';
import { ThemeProvider } from '../../theme';
import {
  DEFAULT_INSTANCE_CONFIG,
  INSTANCE_CONFIG_KEY,
} from '../../types/instance';

function renderSurface(
  turns: ConversationSurfaceTurn[],
  onSend = vi.fn(),
  options: {
    isRunning?: boolean;
    hasPersistedSession?: boolean;
    onMessageAction?: (
      actionId: ConversationMessageActionId,
      message: Message
    ) => void;
  } = {}
) {
  render(
    <ThemeProvider>
      <InstanceConfigProvider>
        <ConversationSurface
          turns={turns}
          onSend={onSend}
          isRunning={options.isRunning}
          hasPersistedSession={options.hasPersistedSession}
          transportCapabilities={{ regenerate: true }}
          onMessageAction={options.onMessageAction}
        />
      </InstanceConfigProvider>
    </ThemeProvider>
  );
  return { onSend };
}

describe('ConversationSurface', () => {
  beforeEach(() => {
    const store = new Map<string, string>();
    vi.stubGlobal('localStorage', {
      getItem: vi.fn((key: string) => store.get(key) ?? null),
      setItem: vi.fn((key: string, value: string) => {
        store.set(key, value);
      }),
      removeItem: vi.fn((key: string) => {
        store.delete(key);
      }),
      clear: vi.fn(() => {
        store.clear();
      }),
    });
    localStorage.setItem('enclave-theme', 'light');
    localStorage.setItem(
      INSTANCE_CONFIG_KEY,
      JSON.stringify(DEFAULT_INSTANCE_CONFIG)
    );
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false }));
    vi.stubGlobal(
      'matchMedia',
      vi.fn().mockReturnValue({
        matches: false,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      })
    );
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it('renders activity steps before the assistant answer and sends prompts', async () => {
    const user = userEvent.setup();
    const { onSend } = renderSurface([
      {
        id: 'user-1',
        role: 'user',
        content: 'Check settings',
        activitySteps: [],
        traceDeltas: [],
        trace: null,
        traceStatus: null,
      },
      {
        id: 'assistant-1',
        role: 'assistant',
        content: 'Settings are configured.',
        activitySteps: [
          {
            id: 'tool-db-query',
            kind: 'tool',
            title: 'Database Query',
            status: 'succeeded',
            summary: 'Database results were redacted from the trace.',
            warnings: ['raw_results_redacted'],
          },
        ],
        traceDeltas: [],
        trace: null,
        traceStatus: null,
      },
    ]);

    const activity = screen.getByText('Database Query');
    const answer = screen.getByText('Settings are configured.');
    expect(
      activity.compareDocumentPosition(answer) &
        Node.DOCUMENT_POSITION_FOLLOWING
    ).toBeTruthy();
    expect(
      screen.getByText('Database results were redacted from the trace.')
    ).toBeInTheDocument();

    await user.type(
      screen.getByRole('textbox', { name: 'Ask anything...' }),
      'Next question'
    );
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    expect(onSend).toHaveBeenCalledWith('Next question');
  });

  it('shows the empty Conversation state before any turns exist', () => {
    renderSurface([]);

    expect(
      screen.getByRole('heading', { name: 'What would you like to know?' })
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        'Ask questions about your knowledge base or start a general conversation'
      )
    ).toBeInTheDocument();
  });

  it('shows running feedback while the assistant is preparing a response', () => {
    renderSurface([], vi.fn(), { isRunning: true });

    expect(
      screen.queryByRole('heading', { name: 'What would you like to know?' })
    ).not.toBeInTheDocument();
    expect(screen.getByText('Thinking...')).toBeInTheDocument();
  });

  it('forwards enabled message actions from the thread to the surface callback', async () => {
    const user = userEvent.setup();
    const onMessageAction = vi.fn();
    renderSurface(
      [
        {
          id: 'assistant-1',
          role: 'assistant',
          content: 'Settings are configured.',
          activitySteps: [],
          traceDeltas: [],
          trace: null,
          traceStatus: null,
        },
      ],
      vi.fn(),
      { hasPersistedSession: true, onMessageAction }
    );

    await user.click(
      screen.getByRole('button', { name: 'Regenerate response' })
    );

    expect(onMessageAction).toHaveBeenCalledWith(
      'regenerate',
      expect.objectContaining({ id: 'assistant-1' })
    );
  });
});
