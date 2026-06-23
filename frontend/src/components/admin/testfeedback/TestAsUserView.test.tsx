import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { TestAsUserView } from './TestAsUserView';
import { sendLlmChatWithUnifiedTools } from '../../../utils/llmChat';
import {
  createSessionLog,
  getImpersonationStatus,
  listUserTypes,
  provisionTestUser,
  requestImpersonationToken,
  saveTranscript,
} from '../../../utils/sessionLogsApi';

vi.mock('../../../utils/llmChat', () => ({
  sendLlmChatWithUnifiedTools: vi.fn(),
}));

vi.mock('../../../utils/sessionLogsApi', () => ({
  createSessionLog: vi.fn(),
  getImpersonationStatus: vi.fn(),
  listUserTypes: vi.fn(),
  provisionTestUser: vi.fn(),
  requestImpersonationToken: vi.fn(),
  saveTranscript: vi.fn(),
}));

const mockSendLlmChatWithUnifiedTools = vi.mocked(sendLlmChatWithUnifiedTools);
const mockCreateSessionLog = vi.mocked(createSessionLog);
const mockGetImpersonationStatus = vi.mocked(getImpersonationStatus);
const mockListUserTypes = vi.mocked(listUserTypes);
const mockProvisionTestUser = vi.mocked(provisionTestUser);
const mockRequestImpersonationToken = vi.mocked(requestImpersonationToken);
const mockSaveTranscript = vi.mocked(saveTranscript);

describe('TestAsUserView', () => {
  beforeEach(() => {
    mockSendLlmChatWithUnifiedTools.mockReset();
    mockCreateSessionLog.mockReset();
    mockGetImpersonationStatus.mockReset();
    mockListUserTypes.mockReset();
    mockProvisionTestUser.mockReset();
    mockRequestImpersonationToken.mockReset();
    mockSaveTranscript.mockReset();

    mockListUserTypes.mockResolvedValue([
      { id: 1, name: 'Student', description: null },
    ]);
    mockProvisionTestUser.mockResolvedValue({
      user_id: 42,
      user_type_id: 1,
      created: true,
    });
    mockGetImpersonationStatus.mockResolvedValue(true);
    mockRequestImpersonationToken.mockResolvedValue({
      token: 'synthetic-user-token',
    });
    mockCreateSessionLog.mockResolvedValue({
      log_id: 'log-1',
      source: 'admin_test',
      title: 'Student trial',
      subject_user_id: 42,
      user_type_id: 1,
      sage_session_id: 'sage-1',
      turn_count: 0,
      status: 'active',
      created_by: 'admin',
      created_at: null,
      updated_at: null,
      completed_at: null,
      has_transcript: false,
    });
    mockSaveTranscript.mockResolvedValue({
      log_id: 'log-1',
      source: 'admin_test',
      title: 'Student trial',
      subject_user_id: 42,
      user_type_id: 1,
      sage_session_id: 'sage-1',
      turn_count: 2,
      status: 'completed',
      created_by: 'admin',
      created_at: null,
      updated_at: null,
      completed_at: null,
      has_transcript: true,
    });
    mockSendLlmChatWithUnifiedTools.mockResolvedValue(
      Response.json({ message: 'Hello from Sage', session_id: 'sage-1' })
    );
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        Response.json({
          web_search_enabled: true,
          default_document_ids: ['doc-1', 'doc-2'],
        })
      )
    );
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  async function startStudentSession() {
    const user = userEvent.setup();
    render(<TestAsUserView />);

    await screen.findByRole('option', { name: 'Student' });
    await user.selectOptions(screen.getByLabelText('User type'), '1');
    await user.click(screen.getByRole('button', { name: 'Start session' }));

    return user;
  }

  it('keeps an active test chat scoped to the synthetic User identity', async () => {
    await startStudentSession();

    expect(await screen.findByText('Testing as Student')).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'Admin' })
    ).not.toBeInTheDocument();
  });

  it('sends chat turns with the synthetic User bearer token', async () => {
    const user = await startStudentSession();

    await user.type(
      screen.getByPlaceholderText('Message the assistant as this user…'),
      'Can you help me?'
    );
    await user.click(screen.getByRole('button', { name: 'Send' }));

    await waitFor(() => {
      expect(mockSendLlmChatWithUnifiedTools).toHaveBeenCalledWith(
        expect.objectContaining({
          content: 'Can you help me?',
          authToken: 'synthetic-user-token',
        })
      );
    });
  });

  it('sends real user default Tool Sets and document constraints while impersonating the synthetic User', async () => {
    const user = await startStudentSession();

    await user.type(
      screen.getByPlaceholderText('Message the assistant as this user…'),
      'Do you have any resources you can read through?'
    );
    await user.click(screen.getByRole('button', { name: 'Send' }));

    await waitFor(() => {
      expect(mockSendLlmChatWithUnifiedTools).toHaveBeenCalledWith(
        expect.objectContaining({
          content: 'Do you have any resources you can read through?',
          tools: ['curated-resources', 'knowledge-search', 'web-search'],
          jobIds: ['doc-1', 'doc-2'],
          authToken: 'synthetic-user-token',
        })
      );
    });
    const lastCall =
      mockSendLlmChatWithUnifiedTools.mock.calls[
        mockSendLlmChatWithUnifiedTools.mock.calls.length - 1
      ];
    const request = lastCall?.[0];
    expect(request?.tools).not.toContain('admin-config');
    expect(request?.tools).not.toContain('db-query');
    expect(fetch).toHaveBeenCalledWith('/api/session-defaults?user_type_id=1');
  });

  it('does not start a test chat when synthetic User auth is unavailable', async () => {
    const user = userEvent.setup();
    mockGetImpersonationStatus.mockResolvedValue(false);

    render(<TestAsUserView />);

    await screen.findByRole('option', { name: 'Student' });
    await user.selectOptions(screen.getByLabelText('User type'), '1');
    await user.click(screen.getByRole('button', { name: 'Start session' }));

    expect(
      await screen.findByText('Test-user impersonation is not available yet')
    ).toBeInTheDocument();
    expect(mockProvisionTestUser).not.toHaveBeenCalled();
    expect(screen.queryByText('Testing as Student')).not.toBeInTheDocument();
  });

  it('resets the active test conversation without changing the synthetic User identity', async () => {
    mockSendLlmChatWithUnifiedTools
      .mockResolvedValueOnce(
        Response.json({ message: 'First answer', session_id: 'sage-1' })
      )
      .mockResolvedValueOnce(
        Response.json({ message: 'Second answer', session_id: 'sage-2' })
      );
    const user = await startStudentSession();

    await user.type(
      screen.getByPlaceholderText('Message the assistant as this user…'),
      'First message'
    );
    await user.click(screen.getByRole('button', { name: 'Send' }));
    expect(await screen.findByText('First answer')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Reset' }));

    expect(screen.queryByText('First answer')).not.toBeInTheDocument();
    expect(
      screen.getByText('Send a message as this user to begin the trial.')
    ).toBeInTheDocument();

    await user.type(
      screen.getByPlaceholderText('Message the assistant as this user…'),
      'Second message'
    );
    await user.click(screen.getByRole('button', { name: 'Send' }));

    await waitFor(() => {
      expect(mockSendLlmChatWithUnifiedTools).toHaveBeenCalledTimes(2);
    });
    expect(mockSendLlmChatWithUnifiedTools.mock.calls[1][0]).toEqual(
      expect.objectContaining({
        content: 'Second message',
        sessionId: null,
        authToken: 'synthetic-user-token',
      })
    );
  });

  it('exits the active test session back to the persona picker', async () => {
    const user = await startStudentSession();

    expect(await screen.findByText('Testing as Student')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Exit' }));

    expect(screen.getByText('Pick a persona to test')).toBeInTheDocument();
    expect(screen.queryByText('Testing as Student')).not.toBeInTheDocument();
    expect(
      screen.queryByText('Send a message as this user to begin the trial.')
    ).not.toBeInTheDocument();
  });

  it('does not save a transcript while a chat response is still pending', async () => {
    let resolveChat!: (value: Response) => void;
    mockSendLlmChatWithUnifiedTools.mockReturnValue(
      new Promise((resolve) => {
        resolveChat = resolve;
      })
    );
    const user = await startStudentSession();

    await user.type(
      screen.getByPlaceholderText('Message the assistant as this user…'),
      'Hold this save until Sage replies'
    );
    await user.click(screen.getByRole('button', { name: 'Send' }));

    const saveButton = screen.getByRole('button', { name: 'End & save trial' });
    await waitFor(() => {
      expect(saveButton).toBeDisabled();
    });
    await user.click(saveButton);
    expect(mockCreateSessionLog).not.toHaveBeenCalled();
    expect(mockSaveTranscript).not.toHaveBeenCalled();

    resolveChat(Response.json({ message: 'Done', session_id: 'sage-1' }));
    expect(await screen.findByText('Done')).toBeInTheDocument();
    expect(saveButton).not.toBeDisabled();
  });

  it('preserves Sage trace and tool metadata when saving the test transcript', async () => {
    mockSendLlmChatWithUnifiedTools.mockResolvedValueOnce(
      Response.json({
        message: 'I found vetted resources.',
        session_id: 'sage-1',
        tools_used: [
          {
            tool_id: 'curated-resources',
            tool_name: 'Curated Resources',
            query: 'Nicaragua political detention legal aid',
            output_summary: 'Found 2 vetted resources.',
          },
        ],
        trace: {
          visibility: 'detailed',
          reasoning: {
            summary: 'Sage used enabled tools before answering.',
          },
          tools: [
            {
              id: 'curated-resources',
              name: 'Curated Resources',
              status: 'succeeded',
              output_summary: 'Found 2 vetted resources.',
            },
          ],
          retrieval: [],
        },
      })
    );
    const user = await startStudentSession();

    await user.type(
      screen.getByPlaceholderText('Message the assistant as this user…'),
      'Find resources for me'
    );
    await user.click(screen.getByRole('button', { name: 'Send' }));
    expect(
      await screen.findByText('I found vetted resources.')
    ).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'End & save trial' }));

    await waitFor(() => {
      expect(mockSaveTranscript).toHaveBeenCalledWith(
        'log-1',
        expect.arrayContaining([
          expect.objectContaining({
            role: 'assistant',
            content: 'I found vetted resources.',
            tools_used: [
              expect.objectContaining({
                tool_id: 'curated-resources',
                tool_name: 'Curated Resources',
              }),
            ],
            trace: expect.objectContaining({
              tools: [
                expect.objectContaining({
                  id: 'curated-resources',
                  name: 'Curated Resources',
                }),
              ],
            }),
          }),
        ]),
        expect.any(String)
      );
    });
  });
});
