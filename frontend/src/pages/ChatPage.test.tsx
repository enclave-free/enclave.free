import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { type ReactNode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ChatPage, ENCLAVE_USER_EMAIL_KEY } from './ChatPage';
import { InstanceConfigProvider } from '../context/InstanceConfigContext';
import { ThemeProvider } from '../theme';
import {
  DEFAULT_INSTANCE_CONFIG,
  INSTANCE_CONFIG_KEY,
} from '../types/instance';
import {
  adminFetch,
  isAdminAuthenticated,
  validateAdminSession,
} from '../utils/adminApi';
import {
  sendLlmChatStreamWithUnifiedTools,
  sendLlmChatWithUnifiedTools,
} from '../utils/llmChat';
import {
  registerAdminResilienceInstrumentationListener,
  resetAdminResilienceInstrumentationListeners,
  type AdminResilienceInstrumentationEvent,
} from '../utils/adminResilienceInstrumentation';

vi.mock('../utils/adminApi', () => ({
  adminFetch: vi.fn(),
  isAdminAuthenticated: vi.fn(() => false),
  validateAdminSession: vi.fn(() => Promise.resolve('unauthenticated')),
}));

vi.mock('../utils/llmChat', () => ({
  sendLlmChatStreamWithUnifiedTools: vi.fn(),
  sendLlmChatWithUnifiedTools: vi.fn(),
}));

const originalScrollIntoView = HTMLElement.prototype.scrollIntoView;

function ChatPageTestWrapper({ children }: { children: ReactNode }) {
  return (
    <MemoryRouter initialEntries={['/']}>
      <ThemeProvider>
        <InstanceConfigProvider>{children}</InstanceConfigProvider>
      </ThemeProvider>
    </MemoryRouter>
  );
}

describe('ChatPage', () => {
  const mockAdminFetch = vi.mocked(adminFetch);
  const mockIsAdminAuthenticated = vi.mocked(isAdminAuthenticated);
  const mockValidateAdminSession = vi.mocked(validateAdminSession);
  const rawMockAdminFetchImplementation =
    mockAdminFetch.mockImplementation.bind(mockAdminFetch);

  const defaultAdminFetch = (_endpoint: string) => null;

  async function waitForValidatedAdminConfig() {
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Config' })).toHaveAttribute(
        'aria-pressed',
        'true'
      );
    });
  }

  function getComposerTextbox() {
    return screen.getByRole('textbox');
  }

  beforeEach(() => {
    resetAdminResilienceInstrumentationListeners();
    mockIsAdminAuthenticated.mockReturnValue(false);
    mockValidateAdminSession.mockImplementation(() =>
      Promise.resolve(
        mockIsAdminAuthenticated() ? 'authenticated' : 'unauthenticated'
      )
    );
    mockAdminFetch.mockImplementation = ((implementation) =>
      rawMockAdminFetchImplementation((endpoint, options) => {
        const defaultResponse = defaultAdminFetch(endpoint);
        if (defaultResponse) return defaultResponse;
        return implementation(endpoint, options);
      })) as typeof mockAdminFetch.mockImplementation;
    const store = new Map<string, string>();
    vi.stubGlobal('localStorage', {
      getItem: vi.fn((key: string) => store.get(key) ?? null),
      removeItem: vi.fn((key: string) => {
        store.delete(key);
      }),
      setItem: vi.fn((key: string, value: string) => {
        store.set(key, value);
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
    localStorage.setItem(ENCLAVE_USER_EMAIL_KEY, 'reader@example.com');
    vi.mocked(isAdminAuthenticated).mockReturnValue(false);
    vi.mocked(adminFetch).mockImplementation((endpoint: string) => {
      return defaultAdminFetch(endpoint) ?? Promise.resolve(Response.json({}));
    });

    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);

        if (url.endsWith('/settings/public')) {
          return Promise.resolve(Response.json({ settings: {} }));
        }

        if (url.endsWith('/session-defaults')) {
          return Promise.resolve(
            Response.json({
              web_search_enabled: true,
              default_document_ids: ['doc-1'],
            })
          );
        }

        if (url.endsWith('/query/sessions')) {
          return Promise.resolve(Response.json({ conversations: [] }));
        }

        if (url.endsWith('/ingest/jobs')) {
          return Promise.resolve(
            Response.json({
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
            })
          );
        }

        if (url.endsWith('/users/me/onboarding-status')) {
          return Promise.resolve(
            Response.json({
              needs_user_type: false,
              needs_onboarding: false,
              effective_user_type_id: null,
            })
          );
        }

        return Promise.resolve(Response.json({}));
      })
    );
    vi.stubGlobal(
      'matchMedia',
      vi.fn().mockReturnValue({
        matches: false,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      })
    );
    HTMLElement.prototype.scrollIntoView = vi.fn();
  });

  afterEach(() => {
    resetAdminResilienceInstrumentationListeners();
    cleanup();
    vi.unstubAllGlobals();
    HTMLElement.prototype.scrollIntoView = originalScrollIntoView;
    vi.clearAllMocks();
    document.documentElement.classList.remove('dark');
  });

  it('activates the Web Search tool when it is enabled by default for new conversations', async () => {
    render(<ChatPage />, { wrapper: ChatPageTestWrapper });

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        expect.stringMatching(/^\/api\/session-defaults(?:\?|$)/)
      );
    });

    expect(screen.getByRole('button', { name: 'Web' })).toHaveAttribute(
      'aria-pressed',
      'true'
    );
  });

  it('activates Curated Resources by default for user chat turns', async () => {
    const user = userEvent.setup();
    vi.mocked(sendLlmChatStreamWithUnifiedTools).mockImplementationOnce(
      async ({ onEvent }) => {
        onEvent('assistant_message_started', {
          message_id: 'msg-resources',
          session_id: 'session-1',
        });
        onEvent('answer_delta', {
          message_id: 'msg-resources',
          delta: 'Try these vetted resources.',
        });
        onEvent('done', {
          message_id: 'msg-resources',
          session_id: 'session-1',
        });
      }
    );

    render(<ChatPage />, { wrapper: ChatPageTestWrapper });

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Resources' })).toHaveAttribute(
        'aria-pressed',
        'true'
      );
    });

    await user.type(getComposerTextbox(), 'Who can help in Nicaragua?');
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    await waitFor(() => {
      expect(sendLlmChatStreamWithUnifiedTools).toHaveBeenCalled();
    });

    const callArgs = vi.mocked(sendLlmChatStreamWithUnifiedTools).mock
      .calls[0][0];
    expect(callArgs.tools).toContain('curated-resources');
    expect(callArgs.tools).not.toContain('admin-config');
    expect(callArgs.tools).not.toContain('db-query');
  });

  it('selects documents that are active by default for new conversations', async () => {
    render(<ChatPage />, { wrapper: ChatPageTestWrapper });

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: 'Docs 1' })
      ).toBeInTheDocument();
    });

    await userEvent.click(screen.getByRole('button', { name: 'Docs 1' }));

    expect(
      screen.getByRole('button', { name: /operator-handbook/ })
    ).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: /user-faq/ })).toHaveAttribute(
      'aria-pressed',
      'false'
    );
  });

  it('sends document-grounded chat through unified Knowledge Search tools', async () => {
    const user = userEvent.setup();
    vi.mocked(fetch).mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);

      if (url.endsWith('/settings/public')) {
        return Promise.resolve(Response.json({ settings: {} }));
      }

      if (url.endsWith('/session-defaults')) {
        return Promise.resolve(
          Response.json({
            web_search_enabled: true,
            default_document_ids: ['doc-1'],
          })
        );
      }

      if (url.endsWith('/query/sessions')) {
        return Promise.resolve(Response.json({ conversations: [] }));
      }

      if (url.endsWith('/ingest/jobs')) {
        return Promise.resolve(
          Response.json({
            jobs: [
              {
                job_id: 'doc-1',
                filename: 'operator-handbook.pdf',
                status: 'completed',
                total_chunks: 12,
              },
            ],
          })
        );
      }

      if (url.endsWith('/users/me/onboarding-status')) {
        return Promise.resolve(
          Response.json({
            needs_user_type: false,
            needs_onboarding: false,
            effective_user_type_id: null,
          })
        );
      }

      return Promise.resolve(Response.json({}));
    });
    vi.mocked(sendLlmChatStreamWithUnifiedTools).mockImplementationOnce(
      async ({ onEvent }) => {
        onEvent('assistant_message_started', {
          message_id: 'msg-docs',
          session_id: 'session-1',
        });
        onEvent('answer_delta', {
          message_id: 'msg-docs',
          delta: 'The handbook answer.',
        });
        onEvent('done', { message_id: 'msg-docs', session_id: 'session-1' });
      }
    );

    render(<ChatPage />, { wrapper: ChatPageTestWrapper });

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: 'Docs 1' })
      ).toBeInTheDocument();
    });
    await user.type(
      screen.getByRole('textbox', {
        name: 'Ask about your selected documents...',
      }),
      'What does the handbook say?'
    );
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    expect(await screen.findByText('The handbook answer.')).toBeInTheDocument();
    expect(sendLlmChatStreamWithUnifiedTools).toHaveBeenCalledWith(
      expect.objectContaining({
        content: 'What does the handbook say?',
        tools: expect.arrayContaining([
          'web-search',
          'knowledge-search',
          'curated-resources',
        ]),
        jobIds: ['doc-1'],
      })
    );
    expect(fetch).not.toHaveBeenCalledWith(
      expect.stringMatching(/\/query$/),
      expect.anything()
    );
    expect(fetch).not.toHaveBeenCalledWith(
      expect.stringMatching(/\/query\/stream$/),
      expect.anything()
    );
  });

  it('shows selected Documents as composer context for the next turn', async () => {
    render(<ChatPage />, { wrapper: ChatPageTestWrapper });

    const composerContext = await screen.findByRole('region', {
      name: 'Composer context',
    });
    expect(composerContext).toBeInTheDocument();
    expect(within(composerContext).getByText('Tools')).toBeInTheDocument();
    expect(
      within(composerContext).getAllByText('Documents').length
    ).toBeGreaterThan(0);
    expect(await screen.findByText('operator-handbook')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Web' })).toHaveAttribute(
      'aria-pressed',
      'true'
    );
    expect(
      document.querySelector('input[type="file"]')
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: /attach|upload/i })
    ).not.toBeInTheDocument();
  });

  it('uses the shared Conversation Surface for User Conversations while preserving surrounding controls', async () => {
    vi.mocked(fetch).mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);

      if (url.endsWith('/settings/public')) {
        return Promise.resolve(
          Response.json({
            settings: {
              reachout_enabled: 'true',
              reachout_mode: 'help',
            },
          })
        );
      }

      if (url.endsWith('/session-defaults')) {
        return Promise.resolve(
          Response.json({
            web_search_enabled: true,
            default_document_ids: ['doc-1'],
          })
        );
      }

      if (url.endsWith('/ingest/jobs')) {
        return Promise.resolve(
          Response.json({
            jobs: [
              {
                job_id: 'doc-1',
                filename: 'operator-handbook.pdf',
                status: 'completed',
                total_chunks: 12,
              },
            ],
          })
        );
      }

      if (url.endsWith('/users/me/onboarding-status')) {
        return Promise.resolve(
          Response.json({
            needs_user_type: false,
            needs_onboarding: false,
            effective_user_type_id: null,
          })
        );
      }

      return Promise.resolve(Response.json({}));
    });

    render(<ChatPage />, { wrapper: ChatPageTestWrapper });

    expect(
      await screen.findByRole('region', { name: 'Conversation surface' })
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Web' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Docs 1' })).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'Get help' })
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Export' })).toHaveAttribute(
      'title',
      'No messages to export'
    );
  });

  it('shows a session sidebar shell and starts a fresh chat from it', async () => {
    const user = userEvent.setup();
    vi.mocked(sendLlmChatStreamWithUnifiedTools).mockImplementationOnce(
      async ({ onEvent }) => {
        onEvent('assistant_message_started', {
          message_id: 'msg-stream',
          session_id: 'session-1',
        });
        onEvent('answer_delta', {
          message_id: 'msg-stream',
          delta: 'First answer.',
        });
        onEvent('done', { message_id: 'msg-stream', session_id: 'session-1' });
      }
    );

    render(<ChatPage />, { wrapper: ChatPageTestWrapper });

    expect(
      await screen.findByRole('navigation', { name: 'Chat sessions' })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'Open chat sessions' })
    ).toBeInTheDocument();
    await user.click(
      screen.getByRole('button', { name: 'Open chat sessions' })
    );
    expect(
      screen.getAllByRole('navigation', { name: 'Chat sessions' })
    ).toHaveLength(2);
    await user.click(
      screen.getByRole('button', { name: 'Close chat sessions' })
    );
    expect(
      screen.getAllByRole('navigation', { name: 'Chat sessions' })
    ).toHaveLength(1);
    expect(
      screen.getByRole('button', { name: 'New chat' })
    ).toBeInTheDocument();
    const currentChatBar = screen.getByRole('region', {
      name: 'Current chat',
    });
    expect(
      within(currentChatBar).getByRole('button', { name: 'Start a new chat' })
    ).toBeInTheDocument();
    expect(screen.getAllByText('Current chat').length).toBeGreaterThan(0);

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: 'Docs 1' })
      ).toBeInTheDocument();
    });
    await user.click(screen.getByRole('button', { name: 'Docs 1' }));
    await user.click(screen.getByRole('button', { name: /operator-handbook/ }));
    await user.type(getComposerTextbox(), 'Hello');
    await user.click(screen.getByRole('button', { name: 'Send message' }));
    expect(await screen.findByText('First answer.')).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'Hello 2 messages' })
    ).toHaveAttribute('aria-current', 'page');

    await user.click(
      screen.getByRole('button', { name: 'Open chat sessions' })
    );
    const mobileSessions = screen.getAllByRole('navigation', {
      name: 'Chat sessions',
    })[1];
    await user.click(
      within(mobileSessions).getByRole('button', { name: 'New chat' })
    );

    expect(screen.queryByText('First answer.')).not.toBeInTheDocument();
    expect(
      screen.getAllByRole('navigation', { name: 'Chat sessions' })
    ).toHaveLength(1);
    expect(
      screen.getByRole('button', { name: 'Current chat Empty' })
    ).toHaveAttribute('aria-current', 'page');
    expect(
      screen.getByRole('heading', { name: 'What would you like to know?' })
    ).toBeInTheDocument();
  });

  it('lists durable Conversations in the session sidebar', async () => {
    vi.mocked(fetch).mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);

      if (url.endsWith('/settings/public')) {
        return Promise.resolve(Response.json({ settings: {} }));
      }

      if (url.endsWith('/session-defaults')) {
        return Promise.resolve(
          Response.json({
            web_search_enabled: true,
            default_document_ids: [],
          })
        );
      }

      if (url.endsWith('/query/sessions')) {
        return Promise.resolve(
          Response.json({
            conversations: [
              {
                id: 'session-1',
                title: 'Draft membership policy',
                updated_at: '2026-05-24T20:00:00Z',
                message_count: 4,
              },
            ],
          })
        );
      }

      if (url.endsWith('/ingest/jobs')) {
        return Promise.resolve(Response.json({ jobs: [] }));
      }

      if (url.endsWith('/users/me/onboarding-status')) {
        return Promise.resolve(
          Response.json({
            needs_user_type: false,
            needs_onboarding: false,
            effective_user_type_id: null,
          })
        );
      }

      return Promise.resolve(Response.json({}));
    });

    render(<ChatPage />, { wrapper: ChatPageTestWrapper });

    const sidebar = await screen.findByRole('navigation', {
      name: 'Chat sessions',
    });

    expect(
      within(sidebar).getByRole('button', {
        name: 'Draft membership policy 4 messages',
      })
    ).toBeInTheDocument();
  });

  it('rejects malformed resumed Conversations instead of clearing the thread', async () => {
    const user = userEvent.setup();
    vi.mocked(sendLlmChatStreamWithUnifiedTools).mockImplementationOnce(
      async ({ onEvent }) => {
        onEvent('assistant_message_started', {
          message_id: 'msg-local',
          session_id: 'local-session',
        });
        onEvent('answer_delta', {
          message_id: 'msg-local',
          delta: 'Local answer remains.',
        });
        onEvent('done', {
          message_id: 'msg-local',
          session_id: 'local-session',
        });
      }
    );

    vi.mocked(fetch).mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);

      if (url.endsWith('/settings/public')) {
        return Promise.resolve(Response.json({ settings: {} }));
      }

      if (url.endsWith('/session-defaults')) {
        return Promise.resolve(
          Response.json({
            web_search_enabled: true,
            default_document_ids: [],
          })
        );
      }

      if (url.endsWith('/query/sessions')) {
        return Promise.resolve(
          Response.json({
            conversations: [
              {
                id: 'session-1',
                title: 'Malformed saved chat',
                updated_at: '2026-05-24T20:00:00Z',
                message_count: 2,
              },
            ],
          })
        );
      }

      if (url.endsWith('/query/session/session-1')) {
        return Promise.resolve(
          Response.json({
            id: 'session-1',
            title: 'Malformed saved chat',
            messages: null,
          })
        );
      }

      if (url.endsWith('/ingest/jobs')) {
        return Promise.resolve(Response.json({ jobs: [] }));
      }

      if (url.endsWith('/users/me/onboarding-status')) {
        return Promise.resolve(
          Response.json({
            needs_user_type: false,
            needs_onboarding: false,
            effective_user_type_id: null,
          })
        );
      }

      return Promise.resolve(Response.json({}));
    });

    render(<ChatPage />, { wrapper: ChatPageTestWrapper });

    await user.type(getComposerTextbox(), 'Keep this local thread');
    await user.click(screen.getByRole('button', { name: 'Send message' }));
    expect(
      await screen.findByText('Local answer remains.')
    ).toBeInTheDocument();

    const sidebar = await screen.findByRole('navigation', {
      name: 'Chat sessions',
    });
    await user.click(
      within(sidebar).getByRole('button', {
        name: 'Malformed saved chat 2 messages',
      })
    );

    expect(
      await screen.findByRole('note', { name: 'Chat request error' })
    ).toHaveTextContent('Unable to load that Conversation.');
    expect(screen.getByText('Local answer remains.')).toBeInTheDocument();
  });

  it('resumes a selected durable Conversation and continues the same session on the next turn', async () => {
    const user = userEvent.setup();
    vi.mocked(fetch).mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);

      if (url.endsWith('/settings/public')) {
        return Promise.resolve(Response.json({ settings: {} }));
      }

      if (url.endsWith('/session-defaults')) {
        return Promise.resolve(
          Response.json({
            web_search_enabled: true,
            default_document_ids: [],
          })
        );
      }

      if (url.endsWith('/query/sessions')) {
        return Promise.resolve(
          Response.json({
            conversations: [
              {
                id: 'session-1',
                title: 'Draft membership policy',
                updated_at: '2026-05-24T20:00:00Z',
                message_count: 2,
              },
            ],
          })
        );
      }

      if (url.endsWith('/query/session/session-1')) {
        return Promise.resolve(
          Response.json({
            id: 'session-1',
            title: 'Draft membership policy',
            messages: [
              {
                id: 'msg-user-1',
                role: 'user',
                content: 'What should membership include?',
              },
              {
                id: 'msg-assistant-1',
                role: 'assistant',
                content: 'Membership should include clear renewal terms.',
                activity_steps: [
                  {
                    id: 'knowledge-search',
                    kind: 'tool',
                    title: 'Knowledge Search',
                    status: 'completed',
                    summary: 'Checked uploaded policy material.',
                  },
                ],
                trace: {
                  visibility: 'summary',
                  tools: [
                    {
                      id: 'knowledge-search',
                      name: 'Knowledge Search',
                      status: 'completed',
                    },
                  ],
                  activity_steps: [
                    {
                      id: 'knowledge-search',
                      kind: 'tool',
                      title: 'Knowledge Search',
                      status: 'completed',
                      summary: 'Checked uploaded policy material.',
                    },
                  ],
                },
              },
            ],
          })
        );
      }

      if (url.endsWith('/ingest/jobs')) {
        return Promise.resolve(Response.json({ jobs: [] }));
      }

      if (url.endsWith('/users/me/onboarding-status')) {
        return Promise.resolve(
          Response.json({
            needs_user_type: false,
            needs_onboarding: false,
            effective_user_type_id: null,
          })
        );
      }

      return Promise.resolve(Response.json({}));
    });
    vi.mocked(sendLlmChatStreamWithUnifiedTools).mockImplementationOnce(
      async ({ sessionId, onEvent }) => {
        expect(sessionId).toBe('session-1');
        onEvent('assistant_message_started', {
          message_id: 'msg-assistant-2',
          session_id: 'session-1',
        });
        onEvent('answer_delta', {
          message_id: 'msg-assistant-2',
          delta: 'Continued in the saved Conversation.',
        });
        onEvent('done', {
          message_id: 'msg-assistant-2',
          session_id: 'session-1',
        });
      }
    );

    render(<ChatPage />, { wrapper: ChatPageTestWrapper });

    const sidebar = await screen.findByRole('navigation', {
      name: 'Chat sessions',
    });
    await user.click(
      within(sidebar).getByRole('button', {
        name: 'Draft membership policy 2 messages',
      })
    );

    expect(
      await screen.findByText('What should membership include?')
    ).toBeInTheDocument();
    expect(
      screen.getByText('Membership should include clear renewal terms.')
    ).toBeInTheDocument();
    expect(screen.getAllByText('Knowledge Search').length).toBeGreaterThan(0);
    expect(
      within(sidebar).getByRole('button', {
        name: 'Draft membership policy 2 messages',
      })
    ).toHaveAttribute('aria-current', 'page');
    expect(
      screen.getByRole('region', { name: 'Current chat' })
    ).toHaveTextContent('Draft membership policy');

    await user.type(getComposerTextbox(), 'What comes next?');
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    expect(
      await screen.findByText('Continued in the saved Conversation.')
    ).toBeInTheDocument();
    expect(sendLlmChatStreamWithUnifiedTools).toHaveBeenCalledTimes(1);
  });

  it('keeps server history titles and preserves the list when refresh fails', async () => {
    const user = userEvent.setup();
    let historyCalls = 0;
    vi.mocked(fetch).mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);

      if (url.endsWith('/settings/public')) {
        return Promise.resolve(Response.json({ settings: {} }));
      }

      if (url.endsWith('/session-defaults')) {
        return Promise.resolve(
          Response.json({
            web_search_enabled: true,
            default_document_ids: [],
          })
        );
      }

      if (url.endsWith('/query/sessions')) {
        historyCalls += 1;
        if (historyCalls > 1) {
          return Promise.resolve(Response.json({}, { status: 503 }));
        }
        return Promise.resolve(
          Response.json({
            conversations: [
              {
                id: 'session-1',
                title: 'Server saved title',
                updated_at: '2026-05-24T20:00:00Z',
                message_count: 2,
              },
            ],
          })
        );
      }

      if (url.endsWith('/query/session/session-1')) {
        return Promise.resolve(
          Response.json({
            id: 'session-1',
            title: 'Stale hydrated title',
            messages: [
              {
                id: 'msg-user-1',
                role: 'user',
                content: 'Existing question',
              },
              {
                id: 'msg-assistant-1',
                role: 'assistant',
                content: 'Existing answer with malformed trace.',
                trace: {
                  visibility: 'summary',
                  tools: 'not-an-array',
                },
              },
            ],
          })
        );
      }

      if (url.endsWith('/ingest/jobs')) {
        return Promise.resolve(Response.json({ jobs: [] }));
      }

      if (url.endsWith('/users/me/onboarding-status')) {
        return Promise.resolve(
          Response.json({
            needs_user_type: false,
            needs_onboarding: false,
            effective_user_type_id: null,
          })
        );
      }

      return Promise.resolve(Response.json({}));
    });
    vi.mocked(sendLlmChatStreamWithUnifiedTools).mockImplementationOnce(
      async ({ sessionId, onEvent }) => {
        expect(sessionId).toBe('session-1');
        onEvent('assistant_message_started', {
          message_id: 'msg-assistant-2',
          session_id: 'session-1',
        });
        onEvent('answer_delta', {
          message_id: 'msg-assistant-2',
          delta: 'Refresh failed but list stayed.',
        });
        onEvent('done', {
          message_id: 'msg-assistant-2',
          session_id: 'session-1',
        });
      }
    );

    render(<ChatPage />, { wrapper: ChatPageTestWrapper });

    const sidebar = await screen.findByRole('navigation', {
      name: 'Chat sessions',
    });
    await user.click(
      within(sidebar).getByRole('button', {
        name: 'Server saved title 2 messages',
      })
    );

    expect(
      screen.getByRole('region', { name: 'Current chat' })
    ).toHaveTextContent('Server saved title');
    expect(
      await screen.findByText('Existing answer with malformed trace.')
    ).toBeInTheDocument();

    await user.type(getComposerTextbox(), 'Continue');
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    expect(
      await screen.findByText('Refresh failed but list stayed.')
    ).toBeInTheDocument();
    expect(
      within(sidebar).getByRole('button', {
        name: 'Server saved title 2 messages',
      })
    ).toHaveAttribute('aria-current', 'page');
  });

  it('starts a durable-history-aware New Chat without deleting saved Conversations', async () => {
    const user = userEvent.setup();
    let historyCalls = 0;
    vi.mocked(fetch).mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);

      if (url.endsWith('/settings/public')) {
        return Promise.resolve(Response.json({ settings: {} }));
      }

      if (url.endsWith('/session-defaults')) {
        return Promise.resolve(
          Response.json({
            web_search_enabled: true,
            default_document_ids: [],
          })
        );
      }

      if (url.endsWith('/query/sessions')) {
        historyCalls += 1;
        return Promise.resolve(
          Response.json({
            conversations:
              historyCalls === 1
                ? [
                    {
                      id: 'session-1',
                      title: 'Existing policy chat',
                      updated_at: '2026-05-24T20:00:00Z',
                      message_count: 2,
                    },
                  ]
                : [
                    {
                      id: 'session-2',
                      title: 'Start separate thread',
                      updated_at: '2026-05-24T20:05:00Z',
                      message_count: 2,
                    },
                    {
                      id: 'session-1',
                      title: 'Existing policy chat',
                      updated_at: '2026-05-24T20:00:00Z',
                      message_count: 2,
                    },
                  ],
          })
        );
      }

      if (url.endsWith('/query/session/session-1')) {
        return Promise.resolve(
          Response.json({
            id: 'session-1',
            title: 'Existing policy chat',
            messages: [
              {
                id: 'msg-user-1',
                role: 'user',
                content: 'Existing question',
              },
              {
                id: 'msg-assistant-1',
                role: 'assistant',
                content: 'Existing answer',
              },
            ],
          })
        );
      }

      if (url.endsWith('/ingest/jobs')) {
        return Promise.resolve(Response.json({ jobs: [] }));
      }

      if (url.endsWith('/users/me/onboarding-status')) {
        return Promise.resolve(
          Response.json({
            needs_user_type: false,
            needs_onboarding: false,
            effective_user_type_id: null,
          })
        );
      }

      return Promise.resolve(Response.json({}));
    });
    vi.mocked(sendLlmChatStreamWithUnifiedTools).mockImplementationOnce(
      async ({ sessionId, onEvent }) => {
        expect(sessionId).toBeNull();
        onEvent('assistant_message_started', {
          message_id: 'msg-assistant-2',
          session_id: 'session-2',
        });
        onEvent('answer_delta', {
          message_id: 'msg-assistant-2',
          delta: 'Fresh answer',
        });
        onEvent('done', {
          message_id: 'msg-assistant-2',
          session_id: 'session-2',
        });
      }
    );

    render(<ChatPage />, { wrapper: ChatPageTestWrapper });

    const sidebar = await screen.findByRole('navigation', {
      name: 'Chat sessions',
    });
    await user.click(
      within(sidebar).getByRole('button', {
        name: 'Existing policy chat 2 messages',
      })
    );
    expect(await screen.findByText('Existing answer')).toBeInTheDocument();

    await user.click(within(sidebar).getByRole('button', { name: 'New chat' }));
    expect(screen.queryByText('Existing answer')).not.toBeInTheDocument();
    expect(
      within(sidebar).getByRole('button', {
        name: 'Existing policy chat 2 messages',
      })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'Current chat Empty' })
    ).toHaveAttribute('aria-current', 'page');

    await user.type(getComposerTextbox(), 'Start separate thread');
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    expect(await screen.findByText('Fresh answer')).toBeInTheDocument();
    expect(
      await within(sidebar).findByRole('button', {
        name: 'Start separate thread 2 messages',
      })
    ).toHaveAttribute('aria-current', 'page');
    expect(
      within(sidebar).getByRole('button', {
        name: 'Existing policy chat 2 messages',
      })
    ).toBeInTheDocument();
  });

  it('renames the active durable Conversation and keeps the hydrated turns intact', async () => {
    const user = userEvent.setup();
    vi.mocked(fetch).mockImplementation((input: RequestInfo | URL, init) => {
      const url = String(input);

      if (url.endsWith('/settings/public')) {
        return Promise.resolve(Response.json({ settings: {} }));
      }

      if (url.endsWith('/session-defaults')) {
        return Promise.resolve(
          Response.json({
            web_search_enabled: true,
            default_document_ids: [],
          })
        );
      }

      if (url.endsWith('/query/sessions')) {
        return Promise.resolve(
          Response.json({
            conversations: [
              {
                id: 'session-1',
                title: 'Draft membership policy',
                updated_at: '2026-05-24T20:00:00Z',
                message_count: 2,
              },
            ],
          })
        );
      }

      if (
        url.endsWith('/query/session/session-1') &&
        init?.method === 'PATCH'
      ) {
        expect(JSON.parse(String(init.body))).toEqual({
          title: 'Board policy',
        });
        return Promise.resolve(
          Response.json({
            id: 'session-1',
            title: 'Board policy',
            message_count: 2,
          })
        );
      }

      if (url.endsWith('/query/session/session-1')) {
        return Promise.resolve(
          Response.json({
            id: 'session-1',
            title: 'Draft membership policy',
            messages: [
              {
                id: 'msg-user-1',
                role: 'user',
                content: 'Existing question',
              },
              {
                id: 'msg-assistant-1',
                role: 'assistant',
                content: 'Existing answer',
              },
            ],
          })
        );
      }

      if (url.endsWith('/ingest/jobs')) {
        return Promise.resolve(Response.json({ jobs: [] }));
      }

      if (url.endsWith('/users/me/onboarding-status')) {
        return Promise.resolve(
          Response.json({
            needs_user_type: false,
            needs_onboarding: false,
            effective_user_type_id: null,
          })
        );
      }

      return Promise.resolve(Response.json({}));
    });

    render(<ChatPage />, { wrapper: ChatPageTestWrapper });

    const sidebar = await screen.findByRole('navigation', {
      name: 'Chat sessions',
    });
    await user.click(
      within(sidebar).getByRole('button', {
        name: 'Draft membership policy 2 messages',
      })
    );
    expect(await screen.findByText('Existing answer')).toBeInTheDocument();

    await user.click(
      within(sidebar).getByRole('button', {
        name: 'Rename Draft membership policy',
      })
    );
    const titleInput = within(sidebar).getByRole('textbox', {
      name: 'Conversation title',
    });
    await user.clear(titleInput);
    await user.type(titleInput, 'Board policy');
    await user.click(
      within(sidebar).getByRole('button', {
        name: 'Save conversation title',
      })
    );

    expect(
      await within(sidebar).findByRole('button', {
        name: 'Board policy 2 messages',
      })
    ).toHaveAttribute('aria-current', 'page');
    expect(
      screen.getByRole('region', { name: 'Current chat' })
    ).toHaveTextContent('Board policy');
    expect(screen.getByText('Existing answer')).toBeInTheDocument();
  });

  it('deletes the active durable Conversation from the sidebar without exposing turn contents in the confirmation', async () => {
    const user = userEvent.setup();
    const conversations = [
      {
        id: 'session-1',
        title: 'Safe board policy title',
        updated_at: '2026-05-24T20:00:00Z',
        message_count: 2,
      },
    ];
    vi.mocked(fetch).mockImplementation((input: RequestInfo | URL, init) => {
      const url = String(input);

      if (url.endsWith('/settings/public')) {
        return Promise.resolve(Response.json({ settings: {} }));
      }

      if (url.endsWith('/session-defaults')) {
        return Promise.resolve(
          Response.json({
            web_search_enabled: true,
            default_document_ids: [],
          })
        );
      }

      if (url.endsWith('/query/sessions')) {
        return Promise.resolve(Response.json({ conversations }));
      }

      if (
        url.endsWith('/query/session/session-1') &&
        init?.method === 'DELETE'
      ) {
        conversations.length = 0;
        return Promise.resolve(
          Response.json({
            status: 'deleted',
            deletion: {
              session_id: 'session-1',
              message_count: 2,
              deleted_at: '2026-05-24T20:05:00Z',
            },
          })
        );
      }

      if (url.endsWith('/query/session/session-1')) {
        return Promise.resolve(
          Response.json({
            id: 'session-1',
            title: 'Safe board policy title',
            messages: [
              {
                id: 'msg-user-1',
                role: 'user',
                content: 'Raw question with secret@example.com inside',
              },
              {
                id: 'msg-assistant-1',
                role: 'assistant',
                content: 'Private answer that should never enter confirmation',
              },
            ],
          })
        );
      }

      if (url.endsWith('/ingest/jobs')) {
        return Promise.resolve(Response.json({ jobs: [] }));
      }

      if (url.endsWith('/users/me/onboarding-status')) {
        return Promise.resolve(
          Response.json({
            needs_user_type: false,
            needs_onboarding: false,
            effective_user_type_id: null,
          })
        );
      }

      return Promise.resolve(Response.json({}));
    });

    render(<ChatPage />, { wrapper: ChatPageTestWrapper });

    const sidebar = await screen.findByRole('navigation', {
      name: 'Chat sessions',
    });
    await user.click(
      within(sidebar).getByRole('button', {
        name: 'Safe board policy title 2 messages',
      })
    );
    expect(
      await screen.findByText(
        'Private answer that should never enter confirmation'
      )
    ).toBeInTheDocument();

    await user.click(
      within(sidebar).getByRole('button', {
        name: 'Delete Safe board policy title',
      })
    );
    expect(
      within(sidebar).getByText('Delete "Safe board policy title"?')
    ).toBeInTheDocument();
    expect(
      within(sidebar).queryByText(/secret@example.com/)
    ).not.toBeInTheDocument();
    expect(
      within(sidebar).queryByText(
        /Private answer that should never enter confirmation/
      )
    ).not.toBeInTheDocument();

    await user.click(
      within(sidebar).getByRole('button', {
        name: 'Cancel conversation delete',
      })
    );
    expect(
      within(sidebar).getByRole('button', {
        name: 'Safe board policy title 2 messages',
      })
    ).toHaveAttribute('aria-current', 'page');
    expect(
      screen.getByText('Private answer that should never enter confirmation')
    ).toBeInTheDocument();

    await user.click(
      within(sidebar).getByRole('button', {
        name: 'Delete Safe board policy title',
      })
    );
    await user.click(
      within(sidebar).getByRole('button', {
        name: 'Delete conversation',
      })
    );

    await waitFor(() => {
      expect(
        within(sidebar).queryByRole('button', {
          name: 'Safe board policy title 2 messages',
        })
      ).not.toBeInTheDocument();
    });
    expect(
      screen.queryByText('Private answer that should never enter confirmation')
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'Current chat Empty' })
    ).toHaveAttribute('aria-current', 'page');
  });

  it('contains chat request failures in a named error note', async () => {
    const user = (await import('@testing-library/user-event')).default.setup();
    vi.mocked(sendLlmChatStreamWithUnifiedTools).mockRejectedValueOnce(
      new Error('Stream unavailable')
    );
    vi.mocked(sendLlmChatWithUnifiedTools).mockRejectedValueOnce(
      new Error('Model gateway unavailable')
    );

    render(<ChatPage />, { wrapper: ChatPageTestWrapper });

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: 'Docs 1' })
      ).toBeInTheDocument();
    });
    await user.click(screen.getByRole('button', { name: 'Docs 1' }));
    await user.click(screen.getByRole('button', { name: /operator-handbook/ }));

    await user.type(getComposerTextbox(), 'Hello');
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    const errorNote = await screen.findByRole('note', {
      name: 'Chat request error',
    });
    expect(errorNote).toHaveTextContent('Model gateway unavailable');
    expect(
      within(
        screen.getByRole('region', { name: 'Conversation surface' })
      ).getByRole('note', { name: 'Chat request error' })
    ).toBe(errorNote);
  });

  it('clears the live trace status when a chat stream finishes without a final trace', async () => {
    const user = userEvent.setup();
    vi.mocked(sendLlmChatStreamWithUnifiedTools).mockImplementationOnce(
      async ({ onEvent }) => {
        onEvent('assistant_message_started', {
          message_id: 'msg-stream',
          session_id: 'session-1',
        });
        onEvent('trace_status', {
          message_id: 'msg-stream',
          status: 'Finalizing response...',
        });
        onEvent('answer_delta', {
          message_id: 'msg-stream',
          delta: 'Streamed hello.',
        });
        onEvent('done', { message_id: 'msg-stream', session_id: 'session-1' });
      }
    );

    render(<ChatPage />, { wrapper: ChatPageTestWrapper });

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: 'Docs 1' })
      ).toBeInTheDocument();
    });
    await user.click(screen.getByRole('button', { name: 'Docs 1' }));
    await user.click(screen.getByRole('button', { name: /operator-handbook/ }));

    await user.type(getComposerTextbox(), 'Hello');
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    expect(await screen.findByText('Streamed hello.')).toBeInTheDocument();
    await waitFor(() => {
      expect(
        screen.queryByText('Finalizing response...')
      ).not.toBeInTheDocument();
    });
    expect(sendLlmChatWithUnifiedTools).not.toHaveBeenCalled();
  });

  it('renders streamed Conversation Activity Steps before the assistant answer', async () => {
    const user = userEvent.setup();
    vi.mocked(sendLlmChatStreamWithUnifiedTools).mockImplementationOnce(
      async ({ onEvent }) => {
        onEvent('assistant_message_started', {
          message_id: 'msg-stream',
          session_id: 'session-1',
        });
        onEvent('activity_step', {
          message_id: 'msg-stream',
          activity_step: {
            id: 'tool-web-search',
            kind: 'tool',
            title: 'Web Search',
            status: 'succeeded',
            summary: 'Tool completed.',
          },
        });
        onEvent('answer_delta', {
          message_id: 'msg-stream',
          delta: 'Streamed hello.',
        });
        onEvent('done', { message_id: 'msg-stream', session_id: 'session-1' });
      }
    );

    render(<ChatPage />, { wrapper: ChatPageTestWrapper });

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: 'Docs 1' })
      ).toBeInTheDocument();
    });
    await user.click(screen.getByRole('button', { name: 'Docs 1' }));
    await user.click(screen.getByRole('button', { name: /operator-handbook/ }));

    await user.type(getComposerTextbox(), 'Hello');
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    const activity = await screen.findByText('Web Search');
    const answer = await screen.findByText('Streamed hello.');
    expect(
      activity.compareDocumentPosition(answer) &
        Node.DOCUMENT_POSITION_FOLLOWING
    ).toBeTruthy();
    expect(screen.getByText('Tool completed.')).toBeInTheDocument();
  });

  it('uses the shared surface for Admin Conversations while preserving admin-only tools', async () => {
    const user = userEvent.setup();
    vi.mocked(isAdminAuthenticated).mockReturnValue(true);
    vi.mocked(sendLlmChatStreamWithUnifiedTools).mockImplementationOnce(
      async ({ onEvent }) => {
        onEvent('assistant_message_started', {
          message_id: 'msg-stream',
          session_id: 'session-1',
        });
        onEvent('activity_step', {
          message_id: 'msg-stream',
          activity_step: {
            id: 'tool-admin-config',
            kind: 'tool',
            title: 'Admin Config',
            status: 'succeeded',
            summary: 'Tool completed.',
          },
        });
        onEvent('answer_delta', {
          message_id: 'msg-stream',
          delta: 'Admin answer.',
        });
        onEvent('done', { message_id: 'msg-stream', session_id: 'session-1' });
      }
    );

    render(<ChatPage />, { wrapper: ChatPageTestWrapper });

    await waitForValidatedAdminConfig();
    expect(
      screen.getByRole('region', { name: 'Conversation surface' })
    ).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: /Docs/ })
    ).not.toBeInTheDocument();

    await user.type(getComposerTextbox(), 'Check config');
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    expect(await screen.findByText('Admin Config')).toBeInTheDocument();
    expect(await screen.findByText('Admin answer.')).toBeInTheDocument();
  });

  it('surfaces stream errors without retrying after answer text has started', async () => {
    const user = userEvent.setup();
    vi.mocked(sendLlmChatStreamWithUnifiedTools).mockImplementationOnce(
      async ({ onEvent }) => {
        onEvent('assistant_message_started', {
          message_id: 'msg-stream',
          session_id: 'session-1',
        });
        onEvent('answer_delta', {
          message_id: 'msg-stream',
          delta: 'Partial answer.',
        });
        onEvent('error', {
          message_id: 'msg-stream',
          detail: 'Model stream interrupted',
        });
      }
    );

    render(<ChatPage />, { wrapper: ChatPageTestWrapper });

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: 'Docs 1' })
      ).toBeInTheDocument();
    });
    await user.click(screen.getByRole('button', { name: 'Docs 1' }));
    await user.click(screen.getByRole('button', { name: /operator-handbook/ }));

    await user.type(getComposerTextbox(), 'Hello');
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    expect(await screen.findByText('Partial answer.')).toBeInTheDocument();
    const errorNote = await screen.findByRole('note', {
      name: 'Chat request error',
    });
    expect(errorNote).toHaveTextContent('Model stream interrupted');
    expect(sendLlmChatWithUnifiedTools).not.toHaveBeenCalled();
  });

  it('keeps Config selected by default for authenticated admin chat turns', async () => {
    const user = userEvent.setup();
    mockIsAdminAuthenticated.mockReturnValue(true);
    mockAdminFetch.mockImplementation((endpoint: string) => {
      if (endpoint === '/admin/deployment/config') {
        return Promise.resolve(
          Response.json({
            llm: [],
            embedding: [],
            email: [],
            storage: [],
            security: [],
            search: [],
            domains: [],
            ssl: [],
            general: [],
          })
        );
      }
      return Promise.resolve(Response.json({}));
    });
    vi.mocked(sendLlmChatStreamWithUnifiedTools).mockImplementationOnce(
      async ({ onEvent }) => {
        onEvent('assistant_message_started', {
          message_id: 'admin-msg',
          session_id: 'session-1',
        });
        onEvent('answer_delta', {
          message_id: 'admin-msg',
          delta: 'I can inspect config.',
        });
        onEvent('done', { message_id: 'admin-msg', session_id: 'session-1' });
      }
    );

    render(<ChatPage />, { wrapper: ChatPageTestWrapper });

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Config' })).toHaveAttribute(
        'aria-pressed',
        'true'
      );
    });

    await user.type(getComposerTextbox(), 'Review instance config.');
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    await waitFor(() => {
      expect(sendLlmChatStreamWithUnifiedTools).toHaveBeenCalled();
    });
    expect(
      vi.mocked(sendLlmChatStreamWithUnifiedTools).mock.calls[0][0]
    ).toEqual(
      expect.objectContaining({
        content: 'Review instance config.',
        tools: expect.arrayContaining(['admin-config']),
      })
    );
  });

  it('does not expose admin-only tools when a stale admin marker fails server validation', async () => {
    const user = userEvent.setup();
    mockIsAdminAuthenticated.mockReturnValue(true);
    mockValidateAdminSession.mockResolvedValue('unauthenticated');
    localStorage.setItem('enclave_admin_pubkey', 'stale-admin-pubkey');
    vi.mocked(sendLlmChatStreamWithUnifiedTools).mockImplementationOnce(
      async ({ onEvent }) => {
        onEvent('assistant_message_started', {
          message_id: 'user-msg',
          session_id: 'session-1',
        });
        onEvent('answer_delta', {
          message_id: 'user-msg',
          delta: 'User answer.',
        });
        onEvent('done', { message_id: 'user-msg', session_id: 'session-1' });
      }
    );

    render(<ChatPage />, { wrapper: ChatPageTestWrapper });

    await waitFor(() => {
      expect(mockValidateAdminSession).toHaveBeenCalled();
    });
    await waitFor(() => {
      expect(
        screen.queryByRole('button', { name: 'Config' })
      ).not.toBeInTheDocument();
      expect(
        screen.queryByRole('button', { name: 'Database' })
      ).not.toBeInTheDocument();
    });

    expect(screen.getByRole('button', { name: 'Web' })).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Resources' })).toHaveAttribute(
        'aria-pressed',
        'true'
      );
    });

    await user.type(getComposerTextbox(), 'I need user help.');
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    await waitFor(() => {
      expect(sendLlmChatStreamWithUnifiedTools).toHaveBeenCalled();
    });
    const callArgs = vi.mocked(sendLlmChatStreamWithUnifiedTools).mock
      .calls[0][0];
    expect(callArgs.tools).toContain('curated-resources');
    expect(callArgs.tools).not.toContain('admin-config');
    expect(callArgs.tools).not.toContain('db-query');
  });

  it('admin config defaults to config-only tools without web-search', async () => {
    const user = userEvent.setup();
    mockIsAdminAuthenticated.mockReturnValue(true);
    mockAdminFetch.mockImplementation((endpoint: string) => {
      if (endpoint === '/admin/deployment/config') {
        return Promise.resolve(
          Response.json({
            llm: [],
            embedding: [],
            email: [],
            storage: [],
            security: [],
            search: [],
            domains: [],
            ssl: [],
            general: [],
          })
        );
      }
      return Promise.resolve(Response.json({}));
    });
    vi.mocked(sendLlmChatStreamWithUnifiedTools).mockImplementationOnce(
      async ({ onEvent }) => {
        onEvent('assistant_message_started', {
          message_id: 'admin-msg',
          session_id: 'session-1',
        });
        onEvent('answer_delta', {
          message_id: 'admin-msg',
          delta: 'SMTP is configured.',
        });
        onEvent('done', { message_id: 'admin-msg', session_id: 'session-1' });
      }
    );

    render(<ChatPage />, { wrapper: ChatPageTestWrapper });

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Config' })).toHaveAttribute(
        'aria-pressed',
        'true'
      );
    });

    expect(screen.getByRole('button', { name: 'Web' })).toHaveAttribute(
      'aria-pressed',
      'false'
    );

    await user.type(getComposerTextbox(), 'What is the SMTP host?');
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    await waitFor(() => {
      expect(sendLlmChatStreamWithUnifiedTools).toHaveBeenCalled();
    });

    const callArgs = vi.mocked(sendLlmChatStreamWithUnifiedTools).mock
      .calls[0][0];
    expect(callArgs.tools).toContain('admin-config');
    expect(callArgs.tools).not.toContain('web-search');
  });

  it('clears admin secret sharing when starting fresh or disabling Config', async () => {
    const user = userEvent.setup();
    mockIsAdminAuthenticated.mockReturnValue(true);

    render(<ChatPage />, { wrapper: ChatPageTestWrapper });

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Config' })).toHaveAttribute(
        'aria-pressed',
        'true'
      );
    });

    const shareToggle = screen.getByLabelText(
      'Share secret env vars'
    ) as HTMLInputElement;
    await user.click(shareToggle);
    expect(shareToggle).toBeChecked();

    await user.click(screen.getByRole('button', { name: 'Start a new chat' }));
    expect(screen.getByLabelText('Share secret env vars')).not.toBeChecked();

    await user.click(screen.getByLabelText('Share secret env vars'));
    expect(screen.getByLabelText('Share secret env vars')).toBeChecked();

    await user.click(screen.getByRole('button', { name: 'Config' }));
    expect(
      screen.queryByLabelText('Share secret env vars')
    ).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Config' }));
    expect(screen.getByLabelText('Share secret env vars')).not.toBeChecked();
  });

  it('preserves admin secret sharing on first persisted session assignment', async () => {
    const user = userEvent.setup();
    mockIsAdminAuthenticated.mockReturnValue(true);
    vi.mocked(sendLlmChatStreamWithUnifiedTools).mockImplementationOnce(
      async ({ onEvent }) => {
        onEvent('assistant_message_started', {
          message_id: 'admin-msg',
          session_id: 'session-1',
        });
        onEvent('answer_delta', {
          message_id: 'admin-msg',
          delta: 'Admin answer.',
        });
        onEvent('done', { message_id: 'admin-msg', session_id: 'session-1' });
      }
    );

    render(<ChatPage />, { wrapper: ChatPageTestWrapper });

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Config' })).toHaveAttribute(
        'aria-pressed',
        'true'
      );
    });

    await user.click(screen.getByLabelText('Share secret env vars'));
    expect(screen.getByLabelText('Share secret env vars')).toBeChecked();

    await user.type(getComposerTextbox(), 'Review instance config.');
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    expect(await screen.findByText('Admin answer.')).toBeInTheDocument();
    expect(screen.getByLabelText('Share secret env vars')).toBeChecked();
  });

  it('applies a grouped admin Change Confirmation from authenticated admin chat', async () => {
    const user = userEvent.setup();
    mockIsAdminAuthenticated.mockReturnValue(true);
    mockAdminFetch.mockImplementation(
      (endpoint: string, options?: RequestInit) => {
        if (endpoint === '/admin/deployment/config') {
          return Promise.resolve(
            Response.json({
              llm: [],
              embedding: [],
              email: [],
              storage: [],
              security: [],
              search: [],
              domains: [],
              ssl: [],
              general: [],
            })
          );
        }
        if (endpoint === '/admin/user-types') {
          return Promise.resolve(Response.json({ types: [] }));
        }
        if (endpoint === '/admin/settings' && options?.method === 'PUT') {
          return Promise.resolve(Response.json({ ok: true }));
        }
        if (
          endpoint === '/admin/ai-config/prompt_tone' &&
          options?.method === 'PUT'
        ) {
          return Promise.resolve(Response.json({ ok: true }));
        }
        if (endpoint === '/admin/deployment/config/validate') {
          return Promise.resolve(Response.json({ valid: true, warnings: [] }));
        }
        if (endpoint === '/admin/deployment/restart-required') {
          return Promise.resolve(
            Response.json({ restart_required: false, changed_keys: [] })
          );
        }
        return Promise.resolve(Response.json({}));
      }
    );
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
    };
    vi.mocked(sendLlmChatStreamWithUnifiedTools).mockImplementationOnce(
      async ({ onEvent }) => {
        onEvent('assistant_message_started', {
          message_id: 'admin-msg',
          session_id: 'session-1',
        });
        onEvent('answer_delta', {
          message_id: 'admin-msg',
          delta:
            'I prepared these configuration changes for review. Use Approve changes to confirm.',
        });
        onEvent('done', {
          message_id: 'admin-msg',
          session_id: 'session-1',
          admin_change_set: changeSet,
        });
      }
    );

    render(<ChatPage />, { wrapper: ChatPageTestWrapper });

    await waitForValidatedAdminConfig();

    await user.type(getComposerTextbox(), 'Set up the theme in one pass.');
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    expect(
      await screen.findByText('Configure instance theme and assistant voice')
    ).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Approve changes' }));

    await waitFor(() => {
      expect(mockAdminFetch).toHaveBeenCalledWith(
        '/admin/settings',
        expect.objectContaining({
          method: 'PUT',
          body: JSON.stringify({
            instance_name: 'WLC Political Prisoners Resource Hub',
            primary_color: '#1E3A8A',
          }),
        })
      );
      expect(mockAdminFetch).toHaveBeenCalledWith(
        '/admin/ai-config/prompt_tone',
        expect.objectContaining({
          method: 'PUT',
          body: JSON.stringify({ value: 'Helpful, concise, and direct.' }),
        })
      );
    });
    expect(
      screen.getByRole('group', { name: 'Admin Change Confirmation' })
    ).toHaveTextContent('Applied');
  });

  it('renders admin Change Confirmation as an inline approval card with collapsed details', async () => {
    const user = userEvent.setup();
    mockIsAdminAuthenticated.mockReturnValue(true);
    mockAdminFetch.mockImplementation((endpoint: string) => {
      if (endpoint === '/admin/deployment/config') {
        return Promise.resolve(
          Response.json({
            llm: [],
            embedding: [],
            email: [],
            storage: [],
            security: [],
            search: [],
            domains: [],
            ssl: [],
            general: [],
          })
        );
      }
      return Promise.resolve(Response.json({ ok: true }));
    });
    const changeSet = {
      version: 1,
      summary: 'Update instance theme',
      requests: [
        {
          method: 'PUT',
          path: '/admin/settings',
          body: { primary_color: '#1E3A8A' },
        },
      ],
    };
    vi.mocked(sendLlmChatStreamWithUnifiedTools).mockImplementationOnce(
      async ({ onEvent }) => {
        onEvent('assistant_message_started', {
          message_id: 'admin-msg',
          session_id: 'session-1',
        });
        onEvent('answer_delta', {
          message_id: 'admin-msg',
          delta: `Here is the change.\n\n\`\`\`json\n${JSON.stringify(changeSet, null, 2)}\n\`\`\``,
        });
        onEvent('done', { message_id: 'admin-msg', session_id: 'session-1' });
      }
    );

    render(<ChatPage />, { wrapper: ChatPageTestWrapper });

    await waitForValidatedAdminConfig();

    await user.type(getComposerTextbox(), 'Propose the theme update.');
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    const approvalCard = await screen.findByRole('group', {
      name: 'Admin Change Confirmation',
    });
    expect(
      within(approvalCard).getByRole('heading', {
        name: 'Approve configuration changes',
      })
    ).toBeInTheDocument();
    expect(approvalCard).toHaveTextContent('Update instance theme');
    expect(
      screen.getByRole('button', { name: 'Approve changes' })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'Reject changes' })
    ).toBeInTheDocument();
    expect(screen.getByText('Here is the change.')).toBeInTheDocument();
    expect(screen.queryByText(/"requests"/)).not.toBeInTheDocument();
    expect(screen.queryByText('/admin/settings')).not.toBeInTheDocument();
    expect(
      within(approvalCard).queryByText('/admin/settings')
    ).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Review details' }));

    expect(approvalCard).toHaveTextContent('PUT /admin/settings');
  });

  it('supersedes an older pending admin Change Confirmation when a newer change set appears', async () => {
    const user = userEvent.setup();
    mockIsAdminAuthenticated.mockReturnValue(true);
    mockAdminFetch.mockImplementation((endpoint: string) => {
      if (endpoint === '/admin/deployment/config') {
        return Promise.resolve(
          Response.json({
            llm: [],
            embedding: [],
            email: [],
            storage: [],
            security: [],
            search: [],
            domains: [],
            ssl: [],
            general: [],
          })
        );
      }
      return Promise.resolve(Response.json({ ok: true }));
    });
    const firstChangeSet = {
      version: 1,
      summary: 'Update instance theme',
      requests: [
        {
          method: 'PUT',
          path: '/admin/settings',
          body: { primary_color: '#1E3A8A' },
        },
      ],
    };
    const secondChangeSet = {
      version: 1,
      summary: 'Update assistant voice',
      requests: [
        {
          method: 'PUT',
          path: '/admin/ai-config/prompt_tone',
          body: { value: 'Warm and direct.' },
        },
      ],
    };
    vi.mocked(sendLlmChatStreamWithUnifiedTools)
      .mockImplementationOnce(async ({ onEvent }) => {
        onEvent('assistant_message_started', {
          message_id: 'admin-msg-1',
          session_id: 'session-1',
        });
        onEvent('answer_delta', {
          message_id: 'admin-msg-1',
          delta: `First proposal.\n\n\`\`\`json\n${JSON.stringify(firstChangeSet, null, 2)}\n\`\`\``,
        });
        onEvent('done', {
          message_id: 'admin-msg-1',
          session_id: 'session-1',
        });
      })
      .mockImplementationOnce(async ({ onEvent }) => {
        onEvent('assistant_message_started', {
          message_id: 'admin-msg-2',
          session_id: 'session-1',
        });
        onEvent('answer_delta', {
          message_id: 'admin-msg-2',
          delta: `Second proposal.\n\n\`\`\`json\n${JSON.stringify(secondChangeSet, null, 2)}\n\`\`\``,
        });
        onEvent('done', {
          message_id: 'admin-msg-2',
          session_id: 'session-1',
        });
      });

    render(<ChatPage />, { wrapper: ChatPageTestWrapper });

    await waitForValidatedAdminConfig();

    await user.type(getComposerTextbox(), 'Propose theme update.');
    await user.click(screen.getByRole('button', { name: 'Send message' }));
    expect(
      await screen.findByText('Update instance theme')
    ).toBeInTheDocument();

    await user.type(getComposerTextbox(), 'Actually propose the voice update.');
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    expect(
      await screen.findByText('Update assistant voice')
    ).toBeInTheDocument();
    const cards = screen.getAllByRole('group', {
      name: 'Admin Change Confirmation',
    });
    expect(cards).toHaveLength(2);
    expect(cards[0]).toHaveTextContent('Update instance theme');
    expect(cards[0]).toHaveTextContent('Superseded');
    expect(
      within(cards[0]).getByRole('button', { name: 'Approve changes' })
    ).toBeDisabled();
    expect(cards[1]).toHaveTextContent('Update assistant voice');
    expect(
      within(cards[1]).getByRole('button', { name: 'Approve changes' })
    ).toBeEnabled();
  });

  it('keeps a rejected admin Change Confirmation card in the thread history', async () => {
    const user = userEvent.setup();
    mockIsAdminAuthenticated.mockReturnValue(true);
    mockAdminFetch.mockImplementation((endpoint: string) => {
      if (endpoint === '/admin/deployment/config') {
        return Promise.resolve(
          Response.json({
            llm: [],
            embedding: [],
            email: [],
            storage: [],
            security: [],
            search: [],
            domains: [],
            ssl: [],
            general: [],
          })
        );
      }
      return Promise.resolve(Response.json({ ok: true }));
    });
    const changeSet = {
      version: 1,
      summary: 'Update instance theme',
      requests: [
        {
          method: 'PUT',
          path: '/admin/settings',
          body: { primary_color: '#1E3A8A' },
        },
      ],
    };
    vi.mocked(sendLlmChatStreamWithUnifiedTools).mockImplementationOnce(
      async ({ onEvent }) => {
        onEvent('assistant_message_started', {
          message_id: 'admin-msg',
          session_id: 'session-1',
        });
        onEvent('answer_delta', {
          message_id: 'admin-msg',
          delta: `Here is the change.\n\n\`\`\`json\n${JSON.stringify(changeSet, null, 2)}\n\`\`\``,
        });
        onEvent('done', { message_id: 'admin-msg', session_id: 'session-1' });
      }
    );

    render(<ChatPage />, { wrapper: ChatPageTestWrapper });

    await waitForValidatedAdminConfig();

    await user.type(getComposerTextbox(), 'Propose the theme update.');
    await user.click(screen.getByRole('button', { name: 'Send message' }));
    await screen.findByRole('group', {
      name: 'Admin Change Confirmation',
    });

    await user.click(screen.getByRole('button', { name: 'Reject changes' }));

    const approvalCard = screen.getByRole('group', {
      name: 'Admin Change Confirmation',
    });
    expect(approvalCard).toHaveTextContent('Rejected');
    expect(
      screen.getByRole('button', { name: 'Approve changes' })
    ).toBeDisabled();
    expect(mockAdminFetch).not.toHaveBeenCalledWith(
      '/admin/settings',
      expect.objectContaining({ method: 'PUT' })
    );
  });

  it('shows no-pending guidance for confirm language when admin chat has no executable change set', async () => {
    const user = userEvent.setup();
    mockIsAdminAuthenticated.mockReturnValue(true);
    mockAdminFetch.mockImplementation((endpoint: string) => {
      if (endpoint === '/admin/deployment/config') {
        return Promise.resolve(
          Response.json({
            llm: [],
            embedding: [],
            email: [],
            storage: [],
            security: [],
            search: [],
            domains: [],
            ssl: [],
            general: [],
          })
        );
      }
      return Promise.resolve(Response.json({}));
    });
    vi.mocked(sendLlmChatStreamWithUnifiedTools).mockImplementationOnce(
      async ({ onEvent }) => {
        onEvent('assistant_message_started', {
          message_id: 'admin-msg-1',
          session_id: 'session-1',
        });
        onEvent('answer_delta', {
          message_id: 'admin-msg-1',
          delta:
            'Here is the reviewable Change Confirmation: update greeting and tone.',
        });
        onEvent('done', { message_id: 'admin-msg-1', session_id: 'session-1' });
      }
    );

    render(<ChatPage />, { wrapper: ChatPageTestWrapper });

    await waitForValidatedAdminConfig();

    await user.type(getComposerTextbox(), 'Style my instance.');
    await user.click(screen.getByRole('button', { name: 'Send message' }));
    expect(
      await screen.findByText(/reviewable Change Confirmation/)
    ).toBeInTheDocument();

    await user.type(getComposerTextbox(), 'I confirm');
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    await waitFor(() => {
      expect(sendLlmChatStreamWithUnifiedTools).toHaveBeenCalledTimes(1);
    });
    expect(
      await screen.findByText(/There are no pending configuration changes/)
    ).toBeInTheDocument();
  });

  it('shows no-pending guidance for yes-do-it language when admin chat has no executable change set', async () => {
    const user = userEvent.setup();
    mockIsAdminAuthenticated.mockReturnValue(true);
    mockAdminFetch.mockImplementation((endpoint: string) => {
      if (endpoint === '/admin/deployment/config') {
        return Promise.resolve(
          Response.json({
            llm: [],
            embedding: [],
            email: [],
            storage: [],
            security: [],
            search: [],
            domains: [],
            ssl: [],
            general: [],
          })
        );
      }
      return Promise.resolve(Response.json({}));
    });
    vi.mocked(sendLlmChatStreamWithUnifiedTools).mockImplementationOnce(
      async ({ onEvent }) => {
        onEvent('assistant_message_started', {
          message_id: 'admin-msg-1',
          session_id: 'session-1',
        });
        onEvent('answer_delta', {
          message_id: 'admin-msg-1',
          delta:
            'Here is the reviewable Change Confirmation: update greeting and tone.',
        });
        onEvent('done', { message_id: 'admin-msg-1', session_id: 'session-1' });
      }
    );

    render(<ChatPage />, { wrapper: ChatPageTestWrapper });

    await waitForValidatedAdminConfig();

    await user.type(getComposerTextbox(), 'Style my instance.');
    await user.click(screen.getByRole('button', { name: 'Send message' }));
    expect(
      await screen.findByText(/reviewable Change Confirmation/)
    ).toBeInTheDocument();

    await user.type(getComposerTextbox(), 'yes do it');
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    await waitFor(() => {
      expect(sendLlmChatStreamWithUnifiedTools).toHaveBeenCalledTimes(1);
    });
    expect(
      await screen.findByText(/There are no pending configuration changes/)
    ).toBeInTheDocument();
  });

  it('sends pasted confirm prose back to Sage when admin chat has no executable change set', async () => {
    const user = userEvent.setup();
    mockIsAdminAuthenticated.mockReturnValue(true);
    mockAdminFetch.mockImplementation((endpoint: string) => {
      if (endpoint === '/admin/deployment/config') {
        return Promise.resolve(
          Response.json({
            llm: [],
            embedding: [],
            email: [],
            storage: [],
            security: [],
            search: [],
            domains: [],
            ssl: [],
            general: [],
          })
        );
      }
      return Promise.resolve(Response.json({}));
    });
    vi.mocked(sendLlmChatStreamWithUnifiedTools)
      .mockImplementationOnce(async ({ onEvent }) => {
        onEvent('assistant_message_started', {
          message_id: 'admin-msg-1',
          session_id: 'session-1',
        });
        onEvent('answer_delta', {
          message_id: 'admin-msg-1',
          delta:
            'Here is the reviewable Change Confirmation: update greeting and tone.',
        });
        onEvent('done', { message_id: 'admin-msg-1', session_id: 'session-1' });
      })
      .mockImplementationOnce(async ({ onEvent }) => {
        onEvent('assistant_message_started', {
          message_id: 'admin-msg-2',
          session_id: 'session-1',
        });
        onEvent('answer_delta', {
          message_id: 'admin-msg-2',
          delta: 'I need to generate an executable JSON change set first.',
        });
        onEvent('done', { message_id: 'admin-msg-2', session_id: 'session-1' });
      });

    render(<ChatPage />, { wrapper: ChatPageTestWrapper });

    await waitForValidatedAdminConfig();

    await user.type(getComposerTextbox(), 'Style my instance.');
    await user.click(screen.getByRole('button', { name: 'Send message' }));
    expect(
      await screen.findByText(/reviewable Change Confirmation/)
    ).toBeInTheDocument();

    await user.type(
      getComposerTextbox(),
      'I confirm: "Greeting: update greeting. Tone: update tone."'
    );
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    await waitFor(() => {
      expect(sendLlmChatStreamWithUnifiedTools).toHaveBeenCalledTimes(2);
    });
    expect(
      screen.queryByText(/There are no pending configuration changes/)
    ).not.toBeInTheDocument();
    expect(
      await screen.findByText(/executable JSON change set/)
    ).toBeInTheDocument();
  });

  it('routes plain do-it language to the pending admin chat approval card', async () => {
    const user = userEvent.setup();
    mockIsAdminAuthenticated.mockReturnValue(true);
    mockAdminFetch.mockImplementation((endpoint: string) => {
      if (endpoint === '/admin/deployment/config') {
        return Promise.resolve(
          Response.json({
            llm: [],
            embedding: [],
            email: [],
            storage: [],
            security: [],
            search: [],
            domains: [],
            ssl: [],
            general: [],
          })
        );
      }
      return Promise.resolve(Response.json({ ok: true }));
    });
    const changeSet = {
      version: 1,
      summary: 'Update instance theme',
      requests: [
        {
          method: 'PUT',
          path: '/admin/settings',
          body: { primary_color: '#1E3A8A' },
        },
      ],
    };
    vi.mocked(sendLlmChatStreamWithUnifiedTools).mockImplementationOnce(
      async ({ onEvent }) => {
        onEvent('assistant_message_started', {
          message_id: 'admin-msg-1',
          session_id: 'session-1',
        });
        onEvent('answer_delta', {
          message_id: 'admin-msg-1',
          delta: `Here is the change.\n\n\`\`\`json\n${JSON.stringify(changeSet, null, 2)}\n\`\`\``,
        });
        onEvent('done', { message_id: 'admin-msg-1', session_id: 'session-1' });
      }
    );

    render(<ChatPage />, { wrapper: ChatPageTestWrapper });

    await waitForValidatedAdminConfig();

    await user.type(getComposerTextbox(), 'Propose the theme update.');
    await user.click(screen.getByRole('button', { name: 'Send message' }));
    expect(
      await screen.findByText('Update instance theme')
    ).toBeInTheDocument();

    await user.type(getComposerTextbox(), 'do it');
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    expect(
      screen.getByRole('group', { name: 'Admin Change Confirmation' })
    ).toHaveTextContent('Update instance theme');
    expect(sendLlmChatStreamWithUnifiedTools).toHaveBeenCalledTimes(1);
    expect(mockAdminFetch).not.toHaveBeenCalledWith(
      '/admin/settings',
      expect.objectContaining({ method: 'PUT' })
    );
    await waitFor(() => {
      expect(HTMLElement.prototype.scrollIntoView).toHaveBeenCalled();
      expect(
        screen.getByRole('button', { name: 'Approve changes' })
      ).toHaveFocus();
    });
  });

  it('keeps imperative apply requests from executing a pending admin chat change set', async () => {
    const user = userEvent.setup();
    mockIsAdminAuthenticated.mockReturnValue(true);
    mockAdminFetch.mockImplementation((endpoint: string) => {
      if (endpoint === '/admin/deployment/config') {
        return Promise.resolve(
          Response.json({
            llm: [],
            embedding: [],
            email: [],
            storage: [],
            security: [],
            search: [],
            domains: [],
            ssl: [],
            general: [],
          })
        );
      }
      return Promise.resolve(Response.json({ ok: true }));
    });
    const changeSet = {
      version: 1,
      summary: 'Update instance theme',
      requests: [
        {
          method: 'PUT',
          path: '/admin/settings',
          body: { primary_color: '#1E3A8A' },
        },
      ],
    };
    vi.mocked(sendLlmChatStreamWithUnifiedTools).mockImplementationOnce(
      async ({ onEvent }) => {
        onEvent('assistant_message_started', {
          message_id: 'admin-msg-1',
          session_id: 'session-1',
        });
        onEvent('answer_delta', {
          message_id: 'admin-msg-1',
          delta: `Here is the change.\n\n\`\`\`json\n${JSON.stringify(changeSet, null, 2)}\n\`\`\``,
        });
        onEvent('done', { message_id: 'admin-msg-1', session_id: 'session-1' });
      }
    );

    render(<ChatPage />, { wrapper: ChatPageTestWrapper });

    await waitForValidatedAdminConfig();

    await user.type(getComposerTextbox(), 'Propose the theme update.');
    await user.click(screen.getByRole('button', { name: 'Send message' }));
    expect(
      await screen.findByText('Update instance theme')
    ).toBeInTheDocument();

    await user.type(
      getComposerTextbox(),
      'Apply the theme changes we discussed earlier'
    );
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    expect(
      screen.getByRole('group', { name: 'Admin Change Confirmation' })
    ).toHaveTextContent('Update instance theme');
    expect(mockAdminFetch).not.toHaveBeenCalledWith(
      '/admin/settings',
      expect.objectContaining({ method: 'PUT' })
    );
  });

  it('keeps yes-do-it language from executing a pending admin chat change set', async () => {
    const user = userEvent.setup();
    mockIsAdminAuthenticated.mockReturnValue(true);
    mockAdminFetch.mockImplementation((endpoint: string) => {
      if (endpoint === '/admin/deployment/config') {
        return Promise.resolve(
          Response.json({
            llm: [],
            embedding: [],
            email: [],
            storage: [],
            security: [],
            search: [],
            domains: [],
            ssl: [],
            general: [],
          })
        );
      }
      return Promise.resolve(Response.json({ ok: true }));
    });
    const changeSet = {
      version: 1,
      summary: 'Update instance theme',
      requests: [
        {
          method: 'PUT',
          path: '/admin/settings',
          body: { primary_color: '#1E3A8A' },
        },
      ],
    };
    vi.mocked(sendLlmChatStreamWithUnifiedTools).mockImplementationOnce(
      async ({ onEvent }) => {
        onEvent('assistant_message_started', {
          message_id: 'admin-msg-1',
          session_id: 'session-1',
        });
        onEvent('answer_delta', {
          message_id: 'admin-msg-1',
          delta: `Here is the change.\n\n\`\`\`json\n${JSON.stringify(changeSet, null, 2)}\n\`\`\``,
        });
        onEvent('done', { message_id: 'admin-msg-1', session_id: 'session-1' });
      }
    );

    render(<ChatPage />, { wrapper: ChatPageTestWrapper });

    await waitForValidatedAdminConfig();

    await user.type(getComposerTextbox(), 'Propose the theme update.');
    await user.click(screen.getByRole('button', { name: 'Send message' }));
    expect(
      await screen.findByText('Update instance theme')
    ).toBeInTheDocument();

    await user.type(getComposerTextbox(), 'yes do it');
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    expect(
      screen.getByRole('group', { name: 'Admin Change Confirmation' })
    ).toHaveTextContent('Update instance theme');
    expect(mockAdminFetch).not.toHaveBeenCalledWith(
      '/admin/settings',
      expect.objectContaining({ method: 'PUT' })
    );
  });

  it('lets non-apply confirm questions continue to Sage while a change set is pending', async () => {
    const user = userEvent.setup();
    mockIsAdminAuthenticated.mockReturnValue(true);
    mockAdminFetch.mockImplementation((endpoint: string) => {
      if (endpoint === '/admin/deployment/config') {
        return Promise.resolve(
          Response.json({
            llm: [],
            embedding: [],
            email: [],
            storage: [],
            security: [],
            search: [],
            domains: [],
            ssl: [],
            general: [],
          })
        );
      }
      return Promise.resolve(Response.json({ ok: true }));
    });
    const changeSet = {
      version: 1,
      summary: 'Update instance theme',
      requests: [
        {
          method: 'PUT',
          path: '/admin/settings',
          body: { primary_color: '#1E3A8A' },
        },
      ],
    };
    vi.mocked(sendLlmChatStreamWithUnifiedTools)
      .mockImplementationOnce(async ({ onEvent }) => {
        onEvent('assistant_message_started', {
          message_id: 'admin-msg-1',
          session_id: 'session-1',
        });
        onEvent('answer_delta', {
          message_id: 'admin-msg-1',
          delta: `Here is the change.\n\n\`\`\`json\n${JSON.stringify(changeSet, null, 2)}\n\`\`\``,
        });
        onEvent('done', { message_id: 'admin-msg-1', session_id: 'session-1' });
      })
      .mockImplementationOnce(async ({ onEvent }) => {
        onEvent('assistant_message_started', {
          message_id: 'admin-msg-2',
          session_id: 'session-1',
        });
        onEvent('answer_delta', {
          message_id: 'admin-msg-2',
          delta: 'The pending primary color is #1E3A8A.',
        });
        onEvent('done', { message_id: 'admin-msg-2', session_id: 'session-1' });
      });

    render(<ChatPage />, { wrapper: ChatPageTestWrapper });

    await waitForValidatedAdminConfig();

    await user.type(getComposerTextbox(), 'Propose the theme update.');
    await user.click(screen.getByRole('button', { name: 'Send message' }));
    expect(
      await screen.findByText('Update instance theme')
    ).toBeInTheDocument();

    await user.type(
      getComposerTextbox(),
      'Can you confirm the current primary color?'
    );
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    await waitFor(() => {
      expect(sendLlmChatStreamWithUnifiedTools).toHaveBeenCalledTimes(2);
    });
    expect(
      screen.queryByText(
        'Use the approval card below and click Approve to confirm these configuration updates.'
      )
    ).not.toBeInTheDocument();
    expect(
      await screen.findByText('The pending primary color is #1E3A8A.')
    ).toBeInTheDocument();
  });

  it('surfaces safe provider context limit errors in admin chat without non-streaming fallback', async () => {
    const user = userEvent.setup();
    mockIsAdminAuthenticated.mockReturnValue(true);
    mockAdminFetch.mockImplementation((endpoint: string) => {
      if (endpoint === '/admin/deployment/config') {
        return Promise.resolve(
          Response.json({
            llm: [],
            embedding: [],
            email: [],
            storage: [],
            security: [],
            search: [],
            domains: [],
            ssl: [],
            general: [],
          })
        );
      }
      return Promise.resolve(Response.json({}));
    });
    vi.mocked(sendLlmChatStreamWithUnifiedTools).mockImplementationOnce(
      async ({ onEvent }) => {
        onEvent('assistant_message_started', {
          message_id: 'admin-msg',
          session_id: 'session-1',
        });
        onEvent('error', {
          message_id: 'admin-msg',
          detail:
            'Token limit exceeded for this session. Please start a new session.',
        });
      }
    );

    render(<ChatPage />, { wrapper: ChatPageTestWrapper });

    await waitForValidatedAdminConfig();

    await user.type(getComposerTextbox(), 'Continue this long session.');
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    const errorNote = await screen.findByRole('note', {
      name: 'Chat request error',
    });
    expect(errorNote).toHaveTextContent(
      'Token limit exceeded for this session. Start a new assistant conversation to continue.'
    );
    expect(sendLlmChatWithUnifiedTools).not.toHaveBeenCalled();
  });

  it('offers a fresh assistant conversation recovery action after admin context limit failures', async () => {
    const user = userEvent.setup();
    mockIsAdminAuthenticated.mockReturnValue(true);
    mockAdminFetch.mockImplementation((endpoint: string) => {
      if (endpoint === '/admin/deployment/config') {
        return Promise.resolve(
          Response.json({
            llm: [],
            embedding: [],
            email: [],
            storage: [],
            security: [],
            search: [],
            domains: [],
            ssl: [],
            general: [],
          })
        );
      }
      return Promise.resolve(Response.json({}));
    });

    let streamCalls = 0;
    vi.mocked(sendLlmChatStreamWithUnifiedTools).mockImplementation(
      async ({ sessionId, onEvent }) => {
        streamCalls += 1;
        if (streamCalls === 1) {
          onEvent('assistant_message_started', {
            message_id: 'admin-msg',
            session_id: 'session-1',
          });
          onEvent('error', {
            message_id: 'admin-msg',
            detail:
              'Token limit exceeded for this session. Please start a new session.',
          });
          return;
        }

        expect(sessionId).toBeNull();
        onEvent('assistant_message_started', {
          message_id: 'admin-msg-2',
          session_id: 'session-2',
        });
        onEvent('done', { message_id: 'admin-msg-2', session_id: 'session-2' });
      }
    );

    render(<ChatPage />, { wrapper: ChatPageTestWrapper });

    await waitForValidatedAdminConfig();

    await user.type(getComposerTextbox(), 'Continue this long session.');
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    await user.click(
      await screen.findByRole('button', {
        name: 'Start new assistant conversation',
      })
    );

    await user.type(getComposerTextbox(), 'Try again after reset.');
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    await waitFor(() => {
      expect(sendLlmChatStreamWithUnifiedTools).toHaveBeenCalledTimes(2);
    });
  });

  it('surfaces safe non-streaming provider failures for admin chat', async () => {
    const user = userEvent.setup();
    mockIsAdminAuthenticated.mockReturnValue(true);
    mockAdminFetch.mockImplementation((endpoint: string) => {
      if (endpoint === '/admin/deployment/config') {
        return Promise.resolve(
          Response.json({
            llm: [],
            embedding: [],
            email: [],
            storage: [],
            security: [],
            search: [],
            domains: [],
            ssl: [],
            general: [],
          })
        );
      }
      return Promise.resolve(Response.json({}));
    });
    vi.mocked(sendLlmChatStreamWithUnifiedTools).mockRejectedValueOnce(
      new Error('Stream transport failed')
    );
    vi.mocked(sendLlmChatWithUnifiedTools).mockResolvedValueOnce(
      Response.json(
        {
          detail:
            'Configured Tinfoil model is unavailable. Check TINFOIL_MODEL and restart Sage.',
        },
        { status: 503 }
      )
    );

    render(<ChatPage />, { wrapper: ChatPageTestWrapper });

    await waitForValidatedAdminConfig();

    await user.type(getComposerTextbox(), 'Check model availability.');
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    const errorNote = await screen.findByRole('note', {
      name: 'Chat request error',
    });
    expect(errorNote).toHaveTextContent(
      'The configured Model Provider model is unavailable. Check Deployment Settings and restart affected services.'
    );
  });

  it('masks secret Deployment Setting values in authenticated admin chat Change Confirmation previews', async () => {
    const user = userEvent.setup();
    mockIsAdminAuthenticated.mockReturnValue(true);
    mockAdminFetch.mockImplementation((endpoint: string) => {
      if (endpoint === '/admin/deployment/config') {
        return Promise.resolve(
          Response.json({
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
          })
        );
      }
      return Promise.resolve(Response.json({}));
    });
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
    };
    vi.mocked(sendLlmChatStreamWithUnifiedTools).mockImplementationOnce(
      async ({ onEvent }) => {
        onEvent('assistant_message_started', {
          message_id: 'admin-msg',
          session_id: 'session-1',
        });
        onEvent('answer_delta', {
          message_id: 'admin-msg',
          delta: `Here is the secret update.\n\n\`\`\`json\n${JSON.stringify(changeSet, null, 2)}\n\`\`\``,
        });
        onEvent('done', { message_id: 'admin-msg', session_id: 'session-1' });
      }
    );

    render(<ChatPage />, { wrapper: ChatPageTestWrapper });

    await waitForValidatedAdminConfig();

    await user.type(getComposerTextbox(), 'Rotate the model secret.');
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    expect(
      await screen.findByText('Update model provider secret')
    ).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Review details' }));
    expect(
      screen.getByText('PUT /admin/deployment/config/LLM_API_KEY')
    ).toBeInTheDocument();
    expect(document.body.textContent).toContain('[REDACTED]');
    expect(document.body.textContent).not.toContain('sk-live-secret-value');
  });

  it('preserves a pending change set after a provider failure and applies it without another model call', async () => {
    const user = userEvent.setup();
    mockIsAdminAuthenticated.mockReturnValue(true);
    const changeSet = {
      version: 1,
      summary: 'Update instance theme',
      requests: [
        {
          method: 'PUT',
          path: '/admin/settings',
          body: { primary_color: '#1E3A8A' },
        },
      ],
    };

    mockAdminFetch.mockImplementation(
      (endpoint: string, options?: RequestInit) => {
        if (endpoint === '/admin/deployment/config') {
          return Promise.resolve(
            Response.json({
              llm: [],
              embedding: [],
              email: [],
              storage: [],
              security: [],
              search: [],
              domains: [],
              ssl: [],
              general: [],
            })
          );
        }
        if (endpoint === '/admin/user-types') {
          return Promise.resolve(Response.json({ types: [] }));
        }
        if (endpoint === '/admin/settings' && options?.method === 'PUT') {
          return Promise.resolve(Response.json({ ok: true }));
        }
        if (endpoint === '/admin/deployment/config/validate') {
          return Promise.resolve(Response.json({ valid: true, warnings: [] }));
        }
        if (endpoint === '/admin/deployment/restart-required') {
          return Promise.resolve(
            Response.json({ restart_required: false, changed_keys: [] })
          );
        }
        return Promise.resolve(Response.json({}));
      }
    );

    vi.mocked(sendLlmChatStreamWithUnifiedTools)
      .mockImplementationOnce(async ({ onEvent }) => {
        onEvent('assistant_message_started', {
          message_id: 'admin-msg-1',
          session_id: 'session-1',
        });
        onEvent('answer_delta', {
          message_id: 'admin-msg-1',
          delta: `Here is the change.\n\n\`\`\`json\n${JSON.stringify(changeSet, null, 2)}\n\`\`\``,
        });
        onEvent('done', { message_id: 'admin-msg-1', session_id: 'session-1' });
      })
      .mockImplementationOnce(async ({ onEvent }) => {
        onEvent('assistant_message_started', {
          message_id: 'admin-msg-2',
          session_id: 'session-1',
        });
        onEvent('error', {
          message_id: 'admin-msg-2',
          detail:
            'Token limit exceeded for this session. Please start a new session.',
        });
      });

    render(<ChatPage />, { wrapper: ChatPageTestWrapper });

    await waitForValidatedAdminConfig();

    await user.type(getComposerTextbox(), 'Propose the theme update.');
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    expect(
      await screen.findByText('Update instance theme')
    ).toBeInTheDocument();

    await user.type(
      getComposerTextbox(),
      'Continue reviewing deployment config.'
    );
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    expect(
      await screen.findByRole('note', { name: 'Chat request error' })
    ).toHaveTextContent(
      'Token limit exceeded for this session. Start a new assistant conversation to continue.'
    );
    expect(screen.getByText('Update instance theme')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Approve changes' }));

    await waitFor(() => {
      expect(mockAdminFetch).toHaveBeenCalledWith(
        '/admin/settings',
        expect.objectContaining({
          method: 'PUT',
          body: JSON.stringify({ primary_color: '#1E3A8A' }),
        })
      );
    });
    expect(sendLlmChatStreamWithUnifiedTools).toHaveBeenCalledTimes(2);
    expect(sendLlmChatWithUnifiedTools).not.toHaveBeenCalled();
  });

  it('compacts Session Memory for long authenticated admin chat turns', async () => {
    const user = userEvent.setup();
    const instrumentationEvents: AdminResilienceInstrumentationEvent[] = [];
    registerAdminResilienceInstrumentationListener((event) => {
      instrumentationEvents.push(event);
    });
    mockIsAdminAuthenticated.mockReturnValue(true);
    mockAdminFetch.mockImplementation((endpoint: string) => {
      if (endpoint === '/admin/deployment/config') {
        return Promise.resolve(
          Response.json({
            llm: [],
            embedding: [],
            email: [],
            storage: [],
            security: [],
            search: [],
            domains: [],
            ssl: [],
            general: [],
          })
        );
      }
      return Promise.resolve(Response.json({}));
    });
    vi.mocked(sendLlmChatStreamWithUnifiedTools).mockImplementation(
      async ({ onEvent }) => {
        onEvent('assistant_message_started', {
          message_id: `msg-${Math.random()}`,
          session_id: 'session-1',
        });
        onEvent('answer_delta', {
          message_id: 'msg-assistant',
          delta: 'Acknowledged.',
        });
        onEvent('done', {
          message_id: 'msg-assistant',
          session_id: 'session-1',
        });
      }
    );

    render(<ChatPage />, { wrapper: ChatPageTestWrapper });

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Config' })).toHaveAttribute(
        'aria-pressed',
        'true'
      );
    });

    for (let index = 0; index < 17; index += 1) {
      fireEvent.change(getComposerTextbox(), {
        target: {
          value: `Theme question ${index} about palette and typography.`,
        },
      });
      await user.click(screen.getByRole('button', { name: 'Send message' }));
      await waitFor(() => {
        expect(sendLlmChatStreamWithUnifiedTools).toHaveBeenCalledTimes(
          index + 1
        );
      });
    }

    const streamCalls = vi.mocked(sendLlmChatStreamWithUnifiedTools).mock.calls;
    const lastCall = streamCalls[streamCalls.length - 1]?.[0];
    expect(lastCall?.conversationHistory?.[0]?.content).toContain(
      'Theme question 12'
    );
    const lastHistory = lastCall?.conversationHistory;
    expect(lastHistory?.[lastHistory.length - 1]?.content).toBe(
      'Acknowledged.'
    );

    expect(
      screen.getByRole('note', {
        name: 'Session Memory compaction notice',
      })
    ).toHaveTextContent(
      'Older context was summarized to keep this conversation going.'
    );

    const contextPlanEvents = instrumentationEvents.filter(
      (event) => event.kind === 'admin_context_plan'
    );
    expect(contextPlanEvents.length).toBeGreaterThan(0);
    const lastContextPlanEvent =
      contextPlanEvents[contextPlanEvents.length - 1];
    expect(lastContextPlanEvent).toMatchObject({
      kind: 'admin_context_plan',
      surface: 'admin_chat_page',
      sessionMemory: {
        compacted: true,
        compactedMessageCount: expect.any(Number),
      },
    });
    expect(JSON.stringify(lastContextPlanEvent)).not.toContain(
      'Theme question 0'
    );
  }, 30_000);

  it('surfaces a reduced-context notice for oversized admin chat Config history', async () => {
    const user = userEvent.setup();
    mockIsAdminAuthenticated.mockReturnValue(true);
    mockAdminFetch.mockImplementation((endpoint: string) => {
      if (endpoint === '/admin/deployment/config') {
        return Promise.resolve(
          Response.json({
            llm: [],
            embedding: [],
            email: [],
            storage: [],
            security: [],
            search: [],
            domains: [],
            ssl: [],
            general: [],
          })
        );
      }
      return Promise.resolve(Response.json({}));
    });
    vi.mocked(sendLlmChatStreamWithUnifiedTools).mockImplementation(
      async ({ onEvent }) => {
        onEvent('assistant_message_started', {
          message_id: `msg-${Math.random()}`,
          session_id: 'session-1',
        });
        onEvent('answer_delta', {
          message_id: 'msg-assistant',
          delta: 'Acknowledged.',
        });
        onEvent('done', {
          message_id: 'msg-assistant',
          session_id: 'session-1',
        });
      }
    );

    render(<ChatPage />, { wrapper: ChatPageTestWrapper });

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Config' })).toHaveAttribute(
        'aria-pressed',
        'true'
      );
    });

    fireEvent.change(getComposerTextbox(), {
      target: {
        value: `Summarize this admin context ${'SAFE_PADDING '.repeat(220)}`,
      },
    });
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    await waitFor(() => {
      expect(sendLlmChatStreamWithUnifiedTools).toHaveBeenCalledTimes(1);
    });

    fireEvent.change(getComposerTextbox(), {
      target: { value: 'Continue with config advice.' },
    });
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    const notice = await screen.findByRole('note', {
      name: 'Reduced context notice',
    });
    expect(notice).toHaveTextContent(
      /Some context was reduced to fit the Model Provider budget/
    );
    expect(notice).toHaveTextContent(/recent conversation history/);
    expect(notice).not.toHaveTextContent('SAFE_PADDING');
  });
});
