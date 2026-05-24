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
      if (endpoint === '/ingest/admin/documents/context-preview') {
        return Promise.resolve(
          Response.json({
            documents: [
              {
                job_id: 'job-brand-guide',
                filename: 'brand-guide.pdf',
                preview_chunks: [
                  {
                    text: 'Use muted blue tones for the primary brand palette.',
                  },
                ],
              },
            ],
            limits: {
              max_documents: 5,
              max_chunks_per_document: 3,
              max_chars_per_chunk: 1200,
            },
          })
        );
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

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith('/api/session-defaults');
    });

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

  it('sends scoped Config context by default in admin configuration conversations', async () => {
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

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith('/api/session-defaults');
    });

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
        baseToolContext: expect.stringContaining('SCOPED CONFIG CONTEXT'),
      })
    );
    const context =
      vi.mocked(sendLlmChatStreamWithUnifiedTools).mock.calls[0][0]
        .baseToolContext || '';
    expect(context).toContain('scope: instance-settings');
    expect(context).toContain('INSTANCE VISUAL IDENTITY SETTINGS');
    expect(context).toContain('BOUNDED DOCUMENT CONTEXT');
    expect(context).toContain('brand-guide.pdf');
    expect(context).toContain('choose reasonable defaults');
    expect(context).toContain(
      'group related settings into one executable change set'
    );
    expect(context).toContain(
      'Never call prose-only bullets or recommendations a Change Confirmation'
    );
    expect(mockAdminFetch).toHaveBeenCalledWith('/admin/settings', undefined);
    expect(mockAdminFetch).toHaveBeenCalledWith(
      '/ingest/admin/documents/context-preview',
      undefined
    );
    expect(mockAdminFetch).not.toHaveBeenCalledWith(
      '/admin/ai-config',
      undefined
    );
    expect(mockAdminFetch).not.toHaveBeenCalledWith(
      '/admin/deployment/config',
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
  }, 15_000);

  it('bounds oversized assembled context for provider calls and surfaces a reduced-context notice', async () => {
    const user = userEvent.setup();
    const oversizedAdminPadding = `ADMIN-PAD-${'A'.repeat(20_000)}`;
    const oversizedDocumentPadding = `DOC-PAD-${'D'.repeat(10_000)}`;
    const instrumentationEvents: AdminResilienceInstrumentationEvent[] = [];
    registerAdminResilienceInstrumentationListener((event) => {
      instrumentationEvents.push(event);
    });

    mockAdminFetch.mockImplementation((endpoint: string) => {
      if (endpoint === '/admin/settings') {
        return Promise.resolve(
          Response.json({
            settings: {
              instance_name: 'Enclave',
              brand_notes: oversizedAdminPadding,
            },
          })
        );
      }
      if (endpoint === '/ingest/admin/documents/context-preview') {
        return Promise.resolve(
          Response.json({
            documents: [
              {
                job_id: 'job-brand-guide',
                filename: 'brand-guide.pdf',
                preview_chunks: [{ text: oversizedDocumentPadding }],
              },
            ],
            limits: {
              max_documents: 5,
              max_chunks_per_document: 3,
              max_chars_per_chunk: 12_000,
            },
          })
        );
      }
      if (endpoint === '/admin/deployment/health') {
        return Promise.resolve(Response.json({ ok: true }));
      }
      return Promise.resolve(Response.json({}));
    });
    mockPlanAdminPromptBudget.mockReturnValueOnce({
      toolContext:
        'PROMPT BUDGET NOTE\n- admin configuration context was reduced to fit the provider budget\n- document library context was reduced to fit the provider budget\n\nSCOPED CONFIG CONTEXT\nGenerated: 2026-05-24T00:00:00.000Z\nscope: overview\n\nINSTANCE OVERVIEW (/admin/settings)\n- instance_name: Enclave\n...[context truncated for provider budget]\n\nBOUNDED DOCUMENT CONTEXT\n- brand-guide.pdf\n...[context truncated for provider budget]',
      conversationHistory: [],
      includedSections: ['admin-config', 'document-context'],
      reducedSections: ['admin-config', 'document-context'],
      omittedSections: [],
      estimatedChars: 600,
      warningNote:
        'PROMPT BUDGET NOTE\n- admin configuration context was reduced to fit the provider budget\n- document library context was reduced to fit the provider budget',
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

    const providerCall = vi.mocked(sendLlmChatStreamWithUnifiedTools).mock
      .calls[0][0];
    const context = providerCall.baseToolContext || '';

    expect(context).not.toContain(oversizedAdminPadding);
    expect(context).not.toContain(oversizedDocumentPadding);
    expect(context).toContain('...[context truncated for provider budget]');
    expect(context.length).toBeLessThanOrEqual(
      DEFAULT_ADMIN_PROMPT_BUDGET_LIMITS.adminConfigChars +
        DEFAULT_ADMIN_PROMPT_BUDGET_LIMITS.documentContextChars +
        500
    );
    expect(mockPlanAdminPromptBudget).toHaveBeenCalled();

    const notice = await screen.findByRole('note', {
      name: 'Reduced context notice',
    });
    expect(notice).toHaveTextContent(/admin configuration context/);
    expect(notice).toHaveTextContent(/document library context/);
    expect(notice).not.toHaveTextContent('ADMIN-PAD-');
    expect(notice).not.toHaveTextContent('DOC-PAD-');

    expect(instrumentationEvents).toHaveLength(1);
    expect(instrumentationEvents[0]).toMatchObject({
      kind: 'admin_context_plan',
      surface: 'admin_config_assistant',
      promptBudget: {
        reducedSections: expect.arrayContaining([
          'admin-config',
          'document-context',
        ]),
        hasWarningNote: true,
      },
    });
    expect(JSON.stringify(instrumentationEvents[0])).not.toContain(
      'ADMIN-PAD-'
    );
    expect(JSON.stringify(instrumentationEvents[0])).not.toContain('DOC-PAD-');
    expect(JSON.stringify(instrumentationEvents[0])).not.toContain(
      'PROMPT BUDGET NOTE'
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
      toolContext: 'SCOPED CONFIG CONTEXT\nsmall section',
      conversationHistory: [],
      includedSections: ['admin-config', 'document-context'],
      reducedSections: ['admin-config', 'document-context'],
      omittedSections: ['recent-conversation'],
      estimatedChars: 500,
      warningNote:
        'PROMPT BUDGET NOTE\n- admin-config was reduced to fit the provider budget',
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
    expect(notice).toHaveTextContent(/admin configuration context/);
    expect(notice).toHaveTextContent(/document library context/);
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

  it('sends confirm language back to Sage when prior guidance had no executable change set', async () => {
    const user = userEvent.setup();
    vi.mocked(sendLlmChatStreamWithUnifiedTools)
      .mockImplementationOnce(async ({ onEvent }) => {
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
      })
      .mockImplementationOnce(async ({ onEvent }) => {
        onEvent('assistant_message_started', {
          message_id: 'msg-2',
          session_id: 'session-1',
        });
        onEvent('answer_delta', {
          message_id: 'msg-2',
          delta: 'I need to generate an executable JSON change set first.',
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
      expect(sendLlmChatStreamWithUnifiedTools).toHaveBeenCalledTimes(2);
    });
    expect(
      screen.queryByText(/There are no pending configuration changes/)
    ).not.toBeInTheDocument();
    expect(
      await screen.findByText(/executable JSON change set/)
    ).toBeInTheDocument();
  });

  it('sends yes-do-it language back to Sage when prior sidebar guidance had no executable change set', async () => {
    const user = userEvent.setup();
    vi.mocked(sendLlmChatStreamWithUnifiedTools)
      .mockImplementationOnce(async ({ onEvent }) => {
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
      })
      .mockImplementationOnce(async ({ onEvent }) => {
        onEvent('assistant_message_started', {
          message_id: 'msg-2',
          session_id: 'session-1',
        });
        onEvent('answer_delta', {
          message_id: 'msg-2',
          delta: 'I need to generate an executable JSON change set first.',
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
      expect(sendLlmChatStreamWithUnifiedTools).toHaveBeenCalledTimes(2);
    });
    expect(
      screen.queryByText(/There are no pending configuration changes/)
    ).not.toBeInTheDocument();
    expect(
      await screen.findByText(/executable JSON change set/)
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

  it('does not reveal secret Deployment Setting values in default Config context', async () => {
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
    const context =
      vi.mocked(sendLlmChatStreamWithUnifiedTools).mock.calls[0][0]
        .baseToolContext || '';
    expect(context).toContain('LLM_API_KEY');
    expect(context).toContain('secret=true');
    expect(context).toContain('Secret env vars are NOT included');
    expect(context).not.toContain('super-secret-token');
    expect(context).not.toContain('BOUNDED DOCUMENT CONTEXT');
    expect(mockAdminFetch).toHaveBeenCalledWith(
      '/admin/deployment/config',
      undefined
    );
    expect(mockAdminFetch).not.toHaveBeenCalledWith(
      '/ingest/admin/documents/context-preview',
      undefined
    );
    expect(mockAdminFetch).not.toHaveBeenCalledWith(
      '/admin/deployment/config/LLM_API_KEY/reveal',
      undefined
    );
    expect(mockAdminFetch).not.toHaveBeenCalledWith(
      '/admin/ai-config',
      undefined
    );
  });

  it('loads the full admin snapshot only when context is manually refreshed', async () => {
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
      expect(mockAdminFetch).toHaveBeenCalledWith(
        '/admin/ai-config',
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
});
