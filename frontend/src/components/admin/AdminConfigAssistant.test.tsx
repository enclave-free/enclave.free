import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AdminConfigAssistant } from './AdminConfigAssistant';
import { adminFetch } from '../../utils/adminApi';
import {
  sendLlmChatStreamWithUnifiedTools,
  sendLlmChatWithUnifiedTools,
} from '../../utils/llmChat';
import { ThemeProvider } from '../../theme';

vi.mock('../../utils/adminApi', () => ({
  adminFetch: vi.fn(),
}));

vi.mock('../../utils/llmChat', () => ({
  sendLlmChatStreamWithUnifiedTools: vi.fn(),
  sendLlmChatWithUnifiedTools: vi.fn(),
}));

vi.mock('../../utils/promptBudget', async (importOriginal) => {
  const actual =
    await importOriginal<typeof import('../../utils/promptBudget')>();
  return {
    ...actual,
    planAdminPromptBudget: vi.fn(actual.planAdminPromptBudget),
  };
});

import {
  DEFAULT_ADMIN_PROMPT_BUDGET_LIMITS,
  planAdminPromptBudget,
} from '../../utils/promptBudget';
import {
  registerAdminResilienceInstrumentationListener,
  resetAdminResilienceInstrumentationListeners,
  type AdminResilienceInstrumentationEvent,
} from '../../utils/adminResilienceInstrumentation';

describe('AdminConfigAssistant', () => {
  const mockAdminFetch = vi.mocked(adminFetch);
  const mockPlanAdminPromptBudget = vi.mocked(planAdminPromptBudget);

  beforeEach(() => {
    resetAdminResilienceInstrumentationListeners();
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
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith('/session-defaults')) {
          return Promise.resolve(Response.json({ web_search_enabled: false }));
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
    mockAdminFetch.mockImplementation((endpoint: string) => {
      if (endpoint === '/admin/settings') {
        return Promise.resolve(
          Response.json({ settings: { instance_name: 'Enclave' } })
        );
      }
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
            general: [
              {
                key: 'LLM_API_KEY',
                value: '[CONFIGURED]',
                is_secret: true,
                requires_restart: true,
                description: 'Model Provider API key',
              },
            ],
          })
        );
      }
      if (endpoint === '/admin/deployment/config/LLM_API_KEY/reveal') {
        return Promise.resolve(
          Response.json({ key: 'LLM_API_KEY', value: 'super-secret-token' })
        );
      }
      if (endpoint === '/admin/ai-config') {
        return Promise.resolve(
          Response.json({ prompt_sections: [], parameters: [], defaults: [] })
        );
      }
      if (endpoint === '/admin/user-types') {
        return Promise.resolve(Response.json({ types: [] }));
      }
      if (endpoint === '/ingest/admin/documents/defaults') {
        return Promise.resolve(Response.json({ documents: [] }));
      }
      if (endpoint === '/admin/deployment/health') {
        return Promise.resolve(Response.json({ ok: true }));
      }
      return Promise.resolve(Response.json({}));
    });
  });

  afterEach(() => {
    resetAdminResilienceInstrumentationListeners();
    cleanup();
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  it('passes previous admin assistant turns into follow-up chat requests', async () => {
    const user = userEvent.setup();
    vi.mocked(sendLlmChatStreamWithUnifiedTools)
      .mockImplementationOnce(async ({ onEvent }) => {
        onEvent('assistant_message_started', {
          message_id: 'msg-1',
          session_id: 'session-1',
        });
        onEvent('answer_delta', {
          message_id: 'msg-1',
          delta: 'I recommend updating Instance Name and Assistant Name.',
        });
        onEvent('done', { message_id: 'msg-1', session_id: 'session-1' });
      })
      .mockImplementationOnce(async ({ onEvent }) => {
        onEvent('assistant_message_started', {
          message_id: 'msg-2',
          session_id: 'session-1',
        });
        onEvent('answer_delta', {
          message_id: 'msg-2',
          delta: 'Applying those suggestions.',
        });
        onEvent('done', { message_id: 'msg-2', session_id: 'session-1' });
      });

    render(
      <ThemeProvider>
        <AdminConfigAssistant />
      </ThemeProvider>
    );

    expect(screen.getByRole('button', { name: 'Config' })).toHaveAttribute(
      'aria-pressed',
      'true'
    );

    await user.type(
      screen.getByRole('textbox', { name: 'Ask about admin configuration...' }),
      'Change more of the copy.'
    );
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    expect(
      await screen.findByText(
        'I recommend updating Instance Name and Assistant Name.'
      )
    ).toBeInTheDocument();

    await user.type(
      screen.getByRole('textbox', { name: 'Ask about admin configuration...' }),
      'your suggestions above'
    );
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    await waitFor(() => {
      expect(sendLlmChatStreamWithUnifiedTools).toHaveBeenCalledTimes(2);
    });
    expect(
      vi.mocked(sendLlmChatStreamWithUnifiedTools).mock.calls[1][0]
    ).toEqual(
      expect.objectContaining({
        content: 'your suggestions above',
        conversationHistory: [
          { role: 'user', content: 'Change more of the copy.' },
          {
            role: 'assistant',
            content: 'I recommend updating Instance Name and Assistant Name.',
          },
        ],
        sessionId: 'session-1',
      })
    );
  });

  it('ignores public web-search defaults for admin config sends', async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith('/session-defaults')) {
          return Promise.resolve(Response.json({ web_search_enabled: true }));
        }
        return Promise.resolve(Response.json({}));
      })
    );
    vi.mocked(sendLlmChatStreamWithUnifiedTools).mockImplementationOnce(
      async ({ onEvent }) => {
        onEvent('assistant_message_started', {
          message_id: 'msg-1',
          session_id: 'session-1',
        });
        onEvent('done', { message_id: 'msg-1', session_id: 'session-1' });
      }
    );

    render(
      <ThemeProvider>
        <AdminConfigAssistant />
      </ThemeProvider>
    );

    expect(screen.getByRole('button', { name: 'Config' })).toHaveAttribute(
      'aria-pressed',
      'true'
    );

    await user.type(
      screen.getByRole('textbox', { name: 'Ask about admin configuration...' }),
      'What is the SMTP host?'
    );
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    await waitFor(() => {
      expect(sendLlmChatStreamWithUnifiedTools).toHaveBeenCalled();
    });

    const callArgs = vi.mocked(sendLlmChatStreamWithUnifiedTools).mock
      .calls[0][0];
    expect(callArgs.tools).toContain('admin-config');
    expect(callArgs.tools).not.toContain('web-search');
  });

  it('relies on Sage for document context retrieval (Sage-only path)', async () => {
    const user = userEvent.setup();
    vi.mocked(sendLlmChatStreamWithUnifiedTools).mockImplementationOnce(
      async ({ onEvent }) => {
        onEvent('assistant_message_started', {
          message_id: 'msg-1',
          session_id: 'session-1',
        });
        onEvent('answer_delta', {
          message_id: 'msg-1',
          delta: 'I can update the instance settings.',
        });
        onEvent('done', { message_id: 'msg-1', session_id: 'session-1' });
      }
    );

    render(
      <ThemeProvider>
        <AdminConfigAssistant />
      </ThemeProvider>
    );

    expect(screen.getByRole('button', { name: 'Config' })).toHaveAttribute(
      'aria-pressed',
      'true'
    );

    await user.type(
      screen.getByRole('textbox', { name: 'Ask about admin configuration...' }),
      'Set up the theme from the uploaded guide.'
    );
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    await waitFor(() => {
      expect(sendLlmChatStreamWithUnifiedTools).toHaveBeenCalled();
    });
    expect(
      vi.mocked(sendLlmChatStreamWithUnifiedTools).mock.calls[0][0]
    ).toEqual(
      expect.objectContaining({
        content: 'Set up the theme from the uploaded guide.',
        tools: expect.arrayContaining(['admin-config']),
      })
    );
    expect(mockAdminFetch).toHaveBeenCalledWith(
      '/admin/deployment/config',
      undefined
    );
    expect(mockAdminFetch).not.toHaveBeenCalledWith(
      '/admin/ai-config',
      undefined
    );
  });

  it('compacts Session Memory for long admin conversations before provider calls', async () => {
    const user = userEvent.setup();
    const instrumentationEvents: AdminResilienceInstrumentationEvent[] = [];
    registerAdminResilienceInstrumentationListener((event) => {
      instrumentationEvents.push(event);
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

    render(
      <ThemeProvider>
        <AdminConfigAssistant />
      </ThemeProvider>
    );

    for (let index = 0; index < 17; index += 1) {
      await user.type(
        screen.getByRole('textbox', {
          name: 'Ask about admin configuration...',
        }),
        `Theme question ${index} about palette and typography.`
      );
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
      screen.queryByRole('note', {
        name: 'Session Memory compaction notice',
      })
    ).not.toBeInTheDocument();
    const contextPlanEvents = instrumentationEvents.filter(
      (event) => event.kind === 'admin_context_plan'
    );
    expect(contextPlanEvents[contextPlanEvents.length - 1]).toMatchObject({
      kind: 'admin_context_plan',
      surface: 'admin_config_assistant',
      sessionMemory: {
        compacted: true,
        compactedMessageCount: expect.any(Number),
      },
    });
  }, 30_000);

  it('skips client-side document context fetching (Sage-only path)', async () => {
    const user = userEvent.setup();
    const instrumentationEvents: AdminResilienceInstrumentationEvent[] = [];
    registerAdminResilienceInstrumentationListener((event) => {
      instrumentationEvents.push(event);
    });

    mockAdminFetch.mockImplementation((endpoint: string) => {
      if (endpoint === '/admin/deployment/health') {
        return Promise.resolve(Response.json({ ok: true }));
      }
      return Promise.resolve(Response.json({}));
    });
    mockPlanAdminPromptBudget.mockReturnValueOnce({
      conversationHistory: [],
      includedSections: [],
      reducedSections: [],
      omittedSections: [],
      estimatedChars: 50,
      warningNote: null,
    });

    vi.mocked(sendLlmChatStreamWithUnifiedTools).mockImplementationOnce(
      async ({ onEvent }) => {
        onEvent('assistant_message_started', {
          message_id: 'msg-1',
          session_id: 'session-1',
        });
        onEvent('done', { message_id: 'msg-1', session_id: 'session-1' });
      }
    );

    render(
      <ThemeProvider>
        <AdminConfigAssistant />
      </ThemeProvider>
    );

    await user.type(
      screen.getByRole('textbox', { name: 'Ask about admin configuration...' }),
      'Set up the theme from the uploaded guide.'
    );
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    await waitFor(() => {
      expect(sendLlmChatStreamWithUnifiedTools).toHaveBeenCalled();
    });

    expect(mockPlanAdminPromptBudget).toHaveBeenCalledWith(
      expect.objectContaining({
        conversationHistory: expect.any(Array),
      })
    );
  });

  it('bounds long conversation history for provider calls using real prompt planning', async () => {
    const user = userEvent.setup();
    const longTurnBody = `TURN-PAD-${'H'.repeat(3_000)}`;

    vi.mocked(sendLlmChatStreamWithUnifiedTools).mockImplementation(
      async ({ onEvent }) => {
        onEvent('assistant_message_started', {
          message_id: `msg-${Math.random()}`,
          session_id: 'session-1',
        });
        onEvent('answer_delta', {
          message_id: 'msg-assistant',
          delta: longTurnBody,
        });
        onEvent('done', {
          message_id: 'msg-assistant',
          session_id: 'session-1',
        });
      }
    );

    render(
      <ThemeProvider>
        <AdminConfigAssistant />
      </ThemeProvider>
    );

    for (let index = 0; index < 5; index += 1) {
      await user.type(
        screen.getByRole('textbox', {
          name: 'Ask about admin configuration...',
        }),
        `Turn ${index} question about theme.`
      );
      await user.click(screen.getByRole('button', { name: 'Send message' }));
      await waitFor(() => {
        expect(sendLlmChatStreamWithUnifiedTools).toHaveBeenCalledTimes(
          index + 1
        );
      });
    }

    const streamCalls = vi.mocked(sendLlmChatStreamWithUnifiedTools).mock.calls;
    const lastCall = streamCalls[streamCalls.length - 1]?.[0];
    expect(lastCall?.conversationHistory).toHaveLength(8);
    expect(lastCall?.conversationHistory?.[0]?.content).toContain('Turn 0');
    expect(
      lastCall?.conversationHistory?.every(
        (turn) =>
          turn.content.length <=
          DEFAULT_ADMIN_PROMPT_BUDGET_LIMITS.conversationCharsPerTurn
      )
    ).toBe(true);
    expect(lastCall?.conversationHistory?.join('')).not.toContain(
      'H'.repeat(2_500)
    );

    const notice = await screen.findByRole('note', {
      name: 'Reduced context notice',
    });
    expect(notice).toHaveTextContent(/recent conversation history/);
  });

  it('shows a reduced-context notice when prompt planning trims context', async () => {
    const user = userEvent.setup();
    mockPlanAdminPromptBudget.mockReturnValueOnce({
      conversationHistory: [],
      includedSections: ['recent-conversation'],
      reducedSections: ['recent-conversation'],
      omittedSections: [],
      estimatedChars: 500,
      warningNote:
        'PROMPT BUDGET NOTE\n- recent-conversation was reduced to fit the provider budget',
    });
    vi.mocked(sendLlmChatStreamWithUnifiedTools).mockImplementationOnce(
      async ({ onEvent }) => {
        onEvent('assistant_message_started', {
          message_id: 'msg-1',
          session_id: 'session-1',
        });
        onEvent('done', { message_id: 'msg-1', session_id: 'session-1' });
      }
    );

    render(
      <ThemeProvider>
        <AdminConfigAssistant />
      </ThemeProvider>
    );

    await user.type(
      screen.getByRole('textbox', { name: 'Ask about admin configuration...' }),
      'Review deployment config.'
    );
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    const notice = await screen.findByRole('note', {
      name: 'Reduced context notice',
    });
    expect(notice).toHaveTextContent(/recent conversation history/);
    expect(notice).not.toHaveTextContent('PROMPT BUDGET NOTE');
  });

  it('presents one reviewable Change Confirmation for coherent multi-setting admin changes', async () => {
    const user = userEvent.setup();
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
            typography_preset: 'humanist',
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
          message_id: 'msg-1',
          session_id: 'session-1',
        });
        onEvent('answer_delta', {
          message_id: 'msg-1',
          delta: `Here is the reviewable change.\n\n\`\`\`json\n${JSON.stringify(changeSet, null, 2)}\n\`\`\``,
        });
        onEvent('done', { message_id: 'msg-1', session_id: 'session-1' });
      }
    );

    render(
      <ThemeProvider>
        <AdminConfigAssistant />
      </ThemeProvider>
    );

    await user.type(
      screen.getByRole('textbox', { name: 'Ask about admin configuration...' }),
      'Update the theme and voice in one pass.'
    );
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    expect(
      await screen.findByText(
        'Pending changes: Configure instance theme and assistant voice'
      )
    ).toBeInTheDocument();
    expect(screen.getByText('PUT /admin/settings')).toBeInTheDocument();
    expect(
      screen.getByText('PUT /admin/ai-config/prompt_tone')
    ).toBeInTheDocument();
    expect(
      screen.getAllByText(/WLC Political Prisoners Resource Hub/).length
    ).toBeGreaterThan(0);
    expect(screen.getByRole('button', { name: 'Apply' })).toBeInTheDocument();
  });

  it('shows no-pending guidance for confirm language when prior guidance had no executable change set', async () => {
    const user = userEvent.setup();
    vi.mocked(sendLlmChatStreamWithUnifiedTools).mockImplementationOnce(
      async ({ onEvent }) => {
        onEvent('assistant_message_started', {
          message_id: 'msg-1',
          session_id: 'session-1',
        });
        onEvent('answer_delta', {
          message_id: 'msg-1',
          delta:
            'Here is the reviewable Change Confirmation: update the greeting and tone.',
        });
        onEvent('done', { message_id: 'msg-1', session_id: 'session-1' });
      }
    );

    render(
      <ThemeProvider>
        <AdminConfigAssistant />
      </ThemeProvider>
    );

    await user.type(
      screen.getByRole('textbox', { name: 'Ask about admin configuration...' }),
      'Style my instance.'
    );
    await user.click(screen.getByRole('button', { name: 'Send message' }));
    expect(
      await screen.findByText(/reviewable Change Confirmation/)
    ).toBeInTheDocument();

    await user.type(
      screen.getByRole('textbox', { name: 'Ask about admin configuration...' }),
      'I confirm'
    );
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    await waitFor(() => {
      expect(sendLlmChatStreamWithUnifiedTools).toHaveBeenCalledTimes(1);
    });
    expect(
      await screen.findByText(/There are no pending configuration changes/)
    ).toBeInTheDocument();
  });

  it('shows no-pending guidance for yes-do-it language when prior sidebar guidance had no executable change set', async () => {
    const user = userEvent.setup();
    vi.mocked(sendLlmChatStreamWithUnifiedTools).mockImplementationOnce(
      async ({ onEvent }) => {
        onEvent('assistant_message_started', {
          message_id: 'msg-1',
          session_id: 'session-1',
        });
        onEvent('answer_delta', {
          message_id: 'msg-1',
          delta:
            'Here is the reviewable Change Confirmation: update the greeting and tone.',
        });
        onEvent('done', { message_id: 'msg-1', session_id: 'session-1' });
      }
    );

    render(
      <ThemeProvider>
        <AdminConfigAssistant />
      </ThemeProvider>
    );

    await user.type(
      screen.getByRole('textbox', { name: 'Ask about admin configuration...' }),
      'Style my instance.'
    );
    await user.click(screen.getByRole('button', { name: 'Send message' }));
    expect(
      await screen.findByText(/reviewable Change Confirmation/)
    ).toBeInTheDocument();

    await user.type(
      screen.getByRole('textbox', { name: 'Ask about admin configuration...' }),
      'yes do it'
    );
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    await waitFor(() => {
      expect(sendLlmChatStreamWithUnifiedTools).toHaveBeenCalledTimes(1);
    });
    expect(
      await screen.findByText(/There are no pending configuration changes/)
    ).toBeInTheDocument();
  });

  it('keeps apply language from executing a pending sidebar change set', async () => {
    const user = userEvent.setup();
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
          message_id: 'msg-1',
          session_id: 'session-1',
        });
        onEvent('answer_delta', {
          message_id: 'msg-1',
          delta: `Here is the change.\n\n\`\`\`json\n${JSON.stringify(changeSet, null, 2)}\n\`\`\``,
        });
        onEvent('done', { message_id: 'msg-1', session_id: 'session-1' });
      }
    );

    render(
      <ThemeProvider>
        <AdminConfigAssistant />
      </ThemeProvider>
    );

    await user.type(
      screen.getByRole('textbox', { name: 'Ask about admin configuration...' }),
      'Propose the theme update.'
    );
    await user.click(screen.getByRole('button', { name: 'Send message' }));
    expect(
      await screen.findByText('Pending changes: Update instance theme')
    ).toBeInTheDocument();

    await user.type(
      screen.getByRole('textbox', { name: 'Ask about admin configuration...' }),
      'Apply them'
    );
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    expect(
      await screen.findByText(
        'Use the pending changes panel below and click Apply to confirm these configuration updates.'
      )
    ).toBeInTheDocument();
    expect(mockAdminFetch).not.toHaveBeenCalledWith(
      '/admin/settings',
      expect.objectContaining({ method: 'PUT' })
    );
  });

  it('keeps yes-do-it language from executing a pending sidebar change set', async () => {
    const user = userEvent.setup();
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
          message_id: 'msg-1',
          session_id: 'session-1',
        });
        onEvent('answer_delta', {
          message_id: 'msg-1',
          delta: `Here is the change.\n\n\`\`\`json\n${JSON.stringify(changeSet, null, 2)}\n\`\`\``,
        });
        onEvent('done', { message_id: 'msg-1', session_id: 'session-1' });
      }
    );

    render(
      <ThemeProvider>
        <AdminConfigAssistant />
      </ThemeProvider>
    );

    await user.type(
      screen.getByRole('textbox', { name: 'Ask about admin configuration...' }),
      'Propose the theme update.'
    );
    await user.click(screen.getByRole('button', { name: 'Send message' }));
    expect(
      await screen.findByText('Pending changes: Update instance theme')
    ).toBeInTheDocument();

    await user.type(
      screen.getByRole('textbox', { name: 'Ask about admin configuration...' }),
      'yes do it'
    );
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    expect(
      await screen.findByText(
        'Use the pending changes panel below and click Apply to confirm these configuration updates.'
      )
    ).toBeInTheDocument();
    expect(mockAdminFetch).not.toHaveBeenCalledWith(
      '/admin/settings',
      expect.objectContaining({ method: 'PUT' })
    );
  });

  it('routes bare do-it language to the pending panel and focuses Apply', async () => {
    const user = userEvent.setup();
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
          message_id: 'msg-1',
          session_id: 'session-1',
        });
        onEvent('done', {
          message_id: 'msg-1',
          session_id: 'session-1',
          admin_change_set: changeSet,
        });
      }
    );

    render(
      <ThemeProvider>
        <AdminConfigAssistant />
      </ThemeProvider>
    );

    await user.type(
      screen.getByRole('textbox', { name: 'Ask about admin configuration...' }),
      'Propose the theme update.'
    );
    await user.click(screen.getByRole('button', { name: 'Send message' }));
    expect(
      await screen.findByText('Pending changes: Update instance theme')
    ).toBeInTheDocument();

    await user.type(
      screen.getByRole('textbox', { name: 'Ask about admin configuration...' }),
      'do it'
    );
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    expect(
      await screen.findByText(
        'Use the pending changes panel below and click Apply to confirm these configuration updates.'
      )
    ).toBeInTheDocument();
    expect(sendLlmChatStreamWithUnifiedTools).toHaveBeenCalledTimes(1);
    expect(mockAdminFetch).not.toHaveBeenCalledWith(
      '/admin/settings',
      expect.objectContaining({ method: 'PUT' })
    );
    const applyButton = screen.getByRole('button', { name: 'Apply' });
    expect(applyButton).toHaveFocus();
    expect(HTMLElement.prototype.scrollIntoView).toHaveBeenCalled();
  });

  it('does not fall back to prose JSON when structured proposal payload is invalid', async () => {
    const user = userEvent.setup();
    const fallbackChangeSet = {
      version: 1,
      summary: 'Fallback theme update',
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
          message_id: 'msg-1',
          session_id: 'session-1',
        });
        onEvent('answer_delta', {
          message_id: 'msg-1',
          delta: `Here is a fallback.\n\n\`\`\`json\n${JSON.stringify(fallbackChangeSet)}\n\`\`\``,
        });
        onEvent('done', {
          message_id: 'msg-1',
          session_id: 'session-1',
          admin_change_set: {
            version: 1,
            requests: [
              {
                method: 'PUT',
                path: '/admin/settings',
                body: { made_up_setting: 'nope' },
              },
            ],
          },
        });
      }
    );

    render(
      <ThemeProvider>
        <AdminConfigAssistant />
      </ThemeProvider>
    );

    await user.type(
      screen.getByRole('textbox', { name: 'Ask about admin configuration...' }),
      'Propose the theme update.'
    );
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    expect(
      await screen.findByText(/Unsupported instance setting key/)
    ).toBeInTheDocument();
    expect(screen.queryByText(/Pending changes:/)).not.toBeInTheDocument();
  });

  it('lets non-apply confirm questions continue to Sage while a sidebar change set is pending', async () => {
    const user = userEvent.setup();
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
          message_id: 'msg-1',
          session_id: 'session-1',
        });
        onEvent('answer_delta', {
          message_id: 'msg-1',
          delta: `Here is the change.\n\n\`\`\`json\n${JSON.stringify(changeSet, null, 2)}\n\`\`\``,
        });
        onEvent('done', { message_id: 'msg-1', session_id: 'session-1' });
      })
      .mockImplementationOnce(async ({ onEvent }) => {
        onEvent('assistant_message_started', {
          message_id: 'msg-2',
          session_id: 'session-1',
        });
        onEvent('answer_delta', {
          message_id: 'msg-2',
          delta: 'The pending primary color is #1E3A8A.',
        });
        onEvent('done', { message_id: 'msg-2', session_id: 'session-1' });
      });

    render(
      <ThemeProvider>
        <AdminConfigAssistant />
      </ThemeProvider>
    );

    await user.type(
      screen.getByRole('textbox', { name: 'Ask about admin configuration...' }),
      'Propose the theme update.'
    );
    await user.click(screen.getByRole('button', { name: 'Send message' }));
    expect(
      await screen.findByText('Pending changes: Update instance theme')
    ).toBeInTheDocument();

    await user.type(
      screen.getByRole('textbox', { name: 'Ask about admin configuration...' }),
      'Can you confirm the current primary color?'
    );
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    await waitFor(() => {
      expect(sendLlmChatStreamWithUnifiedTools).toHaveBeenCalledTimes(2);
    });
    expect(
      screen.queryByText(
        'Use the pending changes panel below and click Apply to confirm these configuration updates.'
      )
    ).not.toBeInTheDocument();
    expect(
      await screen.findByText('The pending primary color is #1E3A8A.')
    ).toBeInTheDocument();
  });

  it('does not prefetch scoped deployment config or reveal secrets on send', async () => {
    const user = userEvent.setup();
    vi.mocked(sendLlmChatStreamWithUnifiedTools).mockImplementationOnce(
      async ({ onEvent }) => {
        onEvent('assistant_message_started', {
          message_id: 'msg-1',
          session_id: 'session-1',
        });
        onEvent('answer_delta', {
          message_id: 'msg-1',
          delta: 'I can review the config safely.',
        });
        onEvent('done', { message_id: 'msg-1', session_id: 'session-1' });
      }
    );

    render(
      <ThemeProvider>
        <AdminConfigAssistant />
      </ThemeProvider>
    );

    await user.type(
      screen.getByRole('textbox', { name: 'Ask about admin configuration...' }),
      'Review deployment config.'
    );
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    await waitFor(() => {
      expect(sendLlmChatStreamWithUnifiedTools).toHaveBeenCalled();
    });
    expect(mockAdminFetch).not.toHaveBeenCalledWith(
      '/admin/deployment/config/LLM_API_KEY/reveal',
      undefined
    );
    expect(mockAdminFetch).not.toHaveBeenCalledWith(
      '/admin/ai-config',
      undefined
    );
  });

  it('refreshes redaction metadata without loading prompt context', async () => {
    const user = userEvent.setup();

    render(
      <ThemeProvider>
        <AdminConfigAssistant />
      </ThemeProvider>
    );

    await user.click(screen.getByRole('button', { name: 'Refresh context' }));

    await waitFor(() => {
      expect(mockAdminFetch).toHaveBeenCalledWith(
        '/admin/deployment/config',
        undefined
      );
    });
  });

  it('surfaces early streamed provider errors without falling back to opaque HTTP errors', async () => {
    const user = userEvent.setup();
    vi.mocked(sendLlmChatStreamWithUnifiedTools).mockImplementationOnce(
      async ({ onEvent }) => {
        onEvent('assistant_message_started', {
          message_id: 'msg-1',
          session_id: 'session-1',
        });
        onEvent('error', {
          message_id: 'msg-1',
          session_id: 'session-1',
          detail:
            'Token limit exceeded for this session. Please start a new session.',
        });
      }
    );

    render(
      <ThemeProvider>
        <AdminConfigAssistant />
      </ThemeProvider>
    );

    await user.type(
      screen.getByRole('textbox', { name: 'Ask about admin configuration...' }),
      'Continue reviewing deployment config.'
    );
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    expect(
      await screen.findByText(
        'Token limit exceeded for this session. Start a new assistant conversation to continue.'
      )
    ).toBeInTheDocument();
    expect(sendLlmChatWithUnifiedTools).not.toHaveBeenCalled();
  });

  it('surfaces classified raw provider errors without falling back to non-streaming chat', async () => {
    const user = userEvent.setup();
    vi.mocked(sendLlmChatStreamWithUnifiedTools).mockImplementationOnce(
      async ({ onEvent }) => {
        onEvent('assistant_message_started', {
          message_id: 'msg-1',
          session_id: 'session-1',
        });
        onEvent('error', {
          message_id: 'msg-1',
          session_id: 'session-1',
          detail:
            'HttpError: Invalid status code 429 Too Many Requests with message: {"error":{"code":"insufficient_quota","message":"Token limit exceeded for this session. Please start a new session."}}',
        });
      }
    );

    render(
      <ThemeProvider>
        <AdminConfigAssistant />
      </ThemeProvider>
    );

    await user.type(
      screen.getByRole('textbox', { name: 'Ask about admin configuration...' }),
      'Continue reviewing deployment config.'
    );
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    expect(
      await screen.findByText(
        'Token limit exceeded for this session. Start a new assistant conversation to continue.'
      )
    ).toBeInTheDocument();
    expect(screen.queryByText(/insufficient_quota/)).not.toBeInTheDocument();
    expect(sendLlmChatWithUnifiedTools).not.toHaveBeenCalled();
  });

  it('starts a fresh assistant conversation after a context limit failure', async () => {
    const user = userEvent.setup();
    const instrumentationEvents: AdminResilienceInstrumentationEvent[] = [];
    registerAdminResilienceInstrumentationListener((event) => {
      instrumentationEvents.push(event);
    });
    const rawProviderDetail =
      'Token limit exceeded for this session. Please start a new session.';
    let streamCalls = 0;
    vi.mocked(sendLlmChatStreamWithUnifiedTools).mockImplementation(
      async ({ sessionId, onEvent }) => {
        streamCalls += 1;
        if (streamCalls === 1) {
          onEvent('assistant_message_started', {
            message_id: 'msg-1',
            session_id: 'session-1',
          });
          onEvent('error', {
            message_id: 'msg-1',
            session_id: 'session-1',
            detail: rawProviderDetail,
          });
          return;
        }

        expect(sessionId).toBeNull();
        onEvent('assistant_message_started', {
          message_id: 'msg-2',
          session_id: 'session-2',
        });
        onEvent('done', { message_id: 'msg-2', session_id: 'session-2' });
      }
    );

    render(
      <ThemeProvider>
        <AdminConfigAssistant />
      </ThemeProvider>
    );

    await user.type(
      screen.getByRole('textbox', { name: 'Ask about admin configuration...' }),
      'Continue reviewing deployment config.'
    );
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    expect(
      await screen.findByText(
        'Token limit exceeded for this session. Start a new assistant conversation to continue.'
      )
    ).toBeInTheDocument();

    const providerFailureEvents = instrumentationEvents.filter(
      (event) => event.kind === 'provider_failure'
    );
    expect(providerFailureEvents).toHaveLength(1);
    expect(providerFailureEvents[0]).toMatchObject({
      kind: 'provider_failure',
      surface: 'admin_config_assistant',
      category: 'context_limit',
      recoveryAction: 'new_assistant_conversation',
    });
    expect(JSON.stringify(providerFailureEvents[0])).not.toContain(
      rawProviderDetail
    );

    await user.click(
      screen.getByRole('button', {
        name: 'Start new assistant conversation',
      })
    );

    expect(
      screen.queryByText(
        'Token limit exceeded for this session. Start a new assistant conversation to continue.'
      )
    ).not.toBeInTheDocument();

    await user.type(
      screen.getByRole('textbox', { name: 'Ask about admin configuration...' }),
      'Review deployment config again.'
    );
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    await waitFor(() => {
      expect(sendLlmChatStreamWithUnifiedTools).toHaveBeenCalledTimes(2);
    });
  });

  it('restores the onboarding starter when starting a fresh onboarding conversation', async () => {
    const user = userEvent.setup();
    vi.mocked(sendLlmChatStreamWithUnifiedTools).mockImplementation(
      async ({ onEvent }) => {
        onEvent('assistant_message_started', {
          message_id: 'msg-1',
          session_id: 'session-1',
        });
        onEvent('error', {
          message_id: 'msg-1',
          session_id: 'session-1',
          detail:
            'Token limit exceeded for this session. Please start a new session.',
        });
      }
    );

    render(
      <ThemeProvider>
        <AdminConfigAssistant purpose="onboarding" />
      </ThemeProvider>
    );

    expect(
      screen.getByText(/Welcome — let's set up your space/)
    ).toBeInTheDocument();

    await user.type(
      screen.getByRole('textbox', { name: 'Ask about admin configuration...' }),
      'Continue setup.'
    );
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    await user.click(
      await screen.findByRole('button', {
        name: 'Start new assistant conversation',
      })
    );

    expect(
      screen.getByText(/Welcome — let's set up your space/)
    ).toBeInTheDocument();
  });

  it('preserves a pending change set when starting a fresh assistant conversation', async () => {
    const user = userEvent.setup();
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

    let streamCalls = 0;
    vi.mocked(sendLlmChatStreamWithUnifiedTools).mockImplementation(
      async ({ onEvent }) => {
        streamCalls += 1;
        if (streamCalls === 1) {
          onEvent('assistant_message_started', {
            message_id: 'msg-1',
            session_id: 'session-1',
          });
          onEvent('answer_delta', {
            message_id: 'msg-1',
            delta: `Here is the change.\n\n\`\`\`json\n${JSON.stringify(changeSet, null, 2)}\n\`\`\``,
          });
          onEvent('done', { message_id: 'msg-1', session_id: 'session-1' });
          return;
        }

        onEvent('assistant_message_started', {
          message_id: 'msg-2',
          session_id: 'session-1',
        });
        onEvent('error', {
          message_id: 'msg-2',
          detail:
            'Token limit exceeded for this session. Please start a new session.',
        });
      }
    );

    render(
      <ThemeProvider>
        <AdminConfigAssistant />
      </ThemeProvider>
    );

    await user.type(
      screen.getByRole('textbox', { name: 'Ask about admin configuration...' }),
      'Propose the theme update.'
    );
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    expect(
      await screen.findByText('Pending changes: Update instance theme')
    ).toBeInTheDocument();

    await user.type(
      screen.getByRole('textbox', { name: 'Ask about admin configuration...' }),
      'Continue reviewing deployment config.'
    );
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    await user.click(
      await screen.findByRole('button', {
        name: 'Start new assistant conversation',
      })
    );

    expect(
      screen.getByText('Pending changes: Update instance theme')
    ).toBeInTheDocument();
    expect(
      screen.queryByText(/Token limit exceeded for this session/)
    ).not.toBeInTheDocument();
  });

  it('preserves a pending change set after a provider failure and applies it without another model call', async () => {
    const user = userEvent.setup();
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

    let streamCalls = 0;
    vi.mocked(sendLlmChatStreamWithUnifiedTools).mockImplementation(
      async ({ onEvent }) => {
        streamCalls += 1;
        if (streamCalls === 1) {
          onEvent('assistant_message_started', {
            message_id: 'msg-1',
            session_id: 'session-1',
          });
          onEvent('answer_delta', {
            message_id: 'msg-1',
            delta: `Here is the change.\n\n\`\`\`json\n${JSON.stringify(changeSet, null, 2)}\n\`\`\``,
          });
          onEvent('done', { message_id: 'msg-1', session_id: 'session-1' });
          return;
        }

        onEvent('assistant_message_started', {
          message_id: 'msg-2',
          session_id: 'session-1',
        });
        onEvent('error', {
          message_id: 'msg-2',
          detail:
            'Token limit exceeded for this session. Please start a new session.',
        });
      }
    );

    mockAdminFetch.mockImplementation(
      (endpoint: string, options?: RequestInit) => {
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
        if (endpoint === '/admin/settings') {
          return Promise.resolve(
            Response.json({ settings: { instance_name: 'Enclave' } })
          );
        }
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
      }
    );

    render(
      <ThemeProvider>
        <AdminConfigAssistant />
      </ThemeProvider>
    );

    await user.type(
      screen.getByRole('textbox', { name: 'Ask about admin configuration...' }),
      'Propose the theme update.'
    );
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    expect(
      await screen.findByText('Pending changes: Update instance theme')
    ).toBeInTheDocument();

    await user.type(
      screen.getByRole('textbox', { name: 'Ask about admin configuration...' }),
      'Continue reviewing deployment config.'
    );
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    await waitFor(() => {
      expect(sendLlmChatStreamWithUnifiedTools).toHaveBeenCalledTimes(2);
    });
    expect(
      await screen.findByText(/Token limit exceeded for this session/)
    ).toBeInTheDocument();
    expect(
      screen.getByText('Pending changes: Update instance theme')
    ).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Apply' }));

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

  it('uses the onboarding guide and auto-advances after applying structured settings', async () => {
    const user = userEvent.setup();
    const changeSet = {
      version: 1,
      summary: 'Set instance name',
      requests: [
        {
          method: 'PUT',
          path: '/admin/settings',
          body: { instance_name: 'Acme Aid' },
        },
      ],
    };

    vi.mocked(sendLlmChatStreamWithUnifiedTools)
      .mockImplementationOnce(async ({ onEvent }) => {
        onEvent('assistant_message_started', {
          message_id: 'onboarding-msg-1',
          session_id: 'onboarding-session',
        });
        onEvent('answer_delta', {
          message_id: 'onboarding-msg-1',
          delta: 'I prepared these changes for review. Use Apply to confirm.',
        });
        onEvent('done', {
          message_id: 'onboarding-msg-1',
          session_id: 'onboarding-session',
          admin_change_set: changeSet,
        });
      })
      .mockImplementationOnce(async ({ onEvent }) => {
        onEvent('assistant_message_started', {
          message_id: 'onboarding-msg-2',
          session_id: 'onboarding-session',
        });
        onEvent('answer_delta', {
          message_id: 'onboarding-msg-2',
          delta: 'Saved. Here is the next setup item.',
        });
        onEvent('done', {
          message_id: 'onboarding-msg-2',
          session_id: 'onboarding-session',
        });
      });

    render(
      <ThemeProvider>
        <AdminConfigAssistant purpose="onboarding" />
      </ThemeProvider>
    );

    expect(screen.getByText(/let's set up your space/i)).toBeInTheDocument();

    await user.type(
      screen.getByRole('textbox', { name: 'Ask about admin configuration...' }),
      '1. Acme Aid'
    );
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    expect(
      await screen.findByText('Pending changes: Set instance name')
    ).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Apply' }));

    await waitFor(() => {
      expect(mockAdminFetch).toHaveBeenCalledWith(
        '/admin/settings',
        expect.objectContaining({
          method: 'PUT',
          body: JSON.stringify({ instance_name: 'Acme Aid' }),
        })
      );
    });
    await waitFor(() => {
      expect(sendLlmChatStreamWithUnifiedTools).toHaveBeenCalledTimes(2);
    });

    const hiddenTurn = vi.mocked(sendLlmChatStreamWithUnifiedTools).mock
      .calls[1][0];
    expect(hiddenTurn.content).toContain(
      'The change set was applied successfully'
    );
    expect(
      screen.queryByText(/The change set was applied successfully/)
    ).not.toBeInTheDocument();
    expect(
      await screen.findByText('Saved. Here is the next setup item.')
    ).toBeInTheDocument();
  });

  it('defaults to config-only tools without web-search', async () => {
    const user = userEvent.setup();
    vi.mocked(sendLlmChatStreamWithUnifiedTools).mockImplementation(
      async ({ onEvent }) => {
        onEvent('assistant_message_started', {
          message_id: 'msg-1',
          session_id: 'session-1',
        });
        onEvent('answer_delta', {
          message_id: 'msg-1',
          delta: 'This is the SMTP configuration.',
        });
        onEvent('done', { message_id: 'msg-1', session_id: 'session-1' });
      }
    );

    render(
      <ThemeProvider>
        <AdminConfigAssistant />
      </ThemeProvider>
    );

    await user.type(
      screen.getByRole('textbox', { name: 'Ask about admin configuration...' }),
      'What is the SMTP configuration?'
    );
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    await waitFor(() => {
      expect(sendLlmChatStreamWithUnifiedTools).toHaveBeenCalledOnce();
    });

    const callArgs = vi.mocked(sendLlmChatStreamWithUnifiedTools).mock
      .calls[0][0];
    expect(callArgs.tools).toContain('admin-config');
    expect(callArgs.tools).not.toContain('web-search');
  });
});
