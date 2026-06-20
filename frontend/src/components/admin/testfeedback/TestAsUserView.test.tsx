import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { TestAsUserView } from './TestAsUserView';
import { sendLlmChatWithUnifiedTools } from '../../../utils/llmChat';
import {
  getImpersonationStatus,
  listUserTypes,
  provisionTestUser,
  requestImpersonationToken,
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
const mockGetImpersonationStatus = vi.mocked(getImpersonationStatus);
const mockListUserTypes = vi.mocked(listUserTypes);
const mockProvisionTestUser = vi.mocked(provisionTestUser);
const mockRequestImpersonationToken = vi.mocked(requestImpersonationToken);

describe('TestAsUserView', () => {
  beforeEach(() => {
    mockSendLlmChatWithUnifiedTools.mockReset();
    mockGetImpersonationStatus.mockReset();
    mockListUserTypes.mockReset();
    mockProvisionTestUser.mockReset();
    mockRequestImpersonationToken.mockReset();

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
    mockSendLlmChatWithUnifiedTools.mockResolvedValue(
      Response.json({ message: 'Hello from Sage', session_id: 'sage-1' })
    );
  });

  afterEach(() => {
    cleanup();
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
    expect(screen.getByText('Send a message as this user to begin the trial.')).toBeInTheDocument();

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
    expect(screen.queryByText('Send a message as this user to begin the trial.')).not.toBeInTheDocument();
  });
});
