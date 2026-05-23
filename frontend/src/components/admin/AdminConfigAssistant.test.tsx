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

describe('AdminConfigAssistant', () => {
  const mockAdminFetch = vi.mocked(adminFetch);

  beforeEach(() => {
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
    expect(context).toContain('choose reasonable defaults');
    expect(context).toContain(
      'group related settings into one reviewable Change Confirmation'
    );
    expect(mockAdminFetch).toHaveBeenCalledWith('/admin/settings', undefined);
    expect(mockAdminFetch).not.toHaveBeenCalledWith(
      '/admin/ai-config',
      undefined
    );
    expect(mockAdminFetch).not.toHaveBeenCalledWith(
      '/admin/deployment/config',
      undefined
    );
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
    expect(mockAdminFetch).toHaveBeenCalledWith(
      '/admin/deployment/config',
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
      'Apply them'
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
      'Apply them'
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
});
