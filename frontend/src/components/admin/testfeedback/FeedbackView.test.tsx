import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { FeedbackView } from './FeedbackView';
import { decryptField, hasNip04Support } from '../../../utils/encryption';
import {
  deleteSessionLog,
  exportSessionLog,
  getSessionLog,
  listSessionLogs,
  setTurnFeedback,
} from '../../../utils/sessionLogsApi';

vi.mock('../../../utils/encryption', () => ({
  decryptField: vi.fn(),
  hasNip04Support: vi.fn(),
}));

vi.mock('../../../utils/sessionLogsApi', () => ({
  deleteSessionLog: vi.fn(),
  exportSessionLog: vi.fn(),
  getSessionLog: vi.fn(),
  listSessionLogs: vi.fn(),
  setTurnFeedback: vi.fn(),
}));

const mockDecryptField = vi.mocked(decryptField);
const mockHasNip04Support = vi.mocked(hasNip04Support);
const mockDeleteSessionLog = vi.mocked(deleteSessionLog);
const mockExportSessionLog = vi.mocked(exportSessionLog);
const mockGetSessionLog = vi.mocked(getSessionLog);
const mockListSessionLogs = vi.mocked(listSessionLogs);
const mockSetTurnFeedback = vi.mocked(setTurnFeedback);
const mockCreateObjectURL = vi.fn(() => 'blob:test-feedback-log-1');
const mockRevokeObjectURL = vi.fn();
const mockAnchorClick = vi.fn();

describe('FeedbackView', () => {
  beforeEach(() => {
    mockDecryptField.mockReset();
    mockHasNip04Support.mockReset();
    mockDeleteSessionLog.mockReset();
    mockExportSessionLog.mockReset();
    mockGetSessionLog.mockReset();
    mockListSessionLogs.mockReset();
    mockSetTurnFeedback.mockReset();
    mockCreateObjectURL.mockClear();
    mockRevokeObjectURL.mockClear();
    mockAnchorClick.mockClear();

    Object.defineProperty(URL, 'createObjectURL', {
      configurable: true,
      value: mockCreateObjectURL,
    });
    Object.defineProperty(URL, 'revokeObjectURL', {
      configurable: true,
      value: mockRevokeObjectURL,
    });
    Object.defineProperty(HTMLAnchorElement.prototype, 'click', {
      configurable: true,
      value: mockAnchorClick,
    });

    mockHasNip04Support.mockReturnValue(true);
    mockExportSessionLog.mockResolvedValue(
      new Blob(['zip'], { type: 'application/zip' })
    );
    mockListSessionLogs.mockResolvedValue([
      {
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
      },
    ]);
    mockGetSessionLog.mockResolvedValue({
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
      transcript_ciphertext: 'encrypted-transcript',
      transcript_ephemeral_pubkey: 'ephemeral-pubkey',
      encrypted_to_pubkey: 'admin-pubkey',
      feedback: [],
    });
    mockDecryptField.mockResolvedValue(
      JSON.stringify({
        turns: [
          { role: 'user', content: 'Can you help me?' },
          { role: 'assistant', content: 'Yes, here is a plan.' },
        ],
      })
    );
  });

  afterEach(() => {
    cleanup();
  });

  it('shows a clear error when rating feedback is rejected', async () => {
    const user = userEvent.setup();
    mockSetTurnFeedback.mockRejectedValue(
      new Error('Feedback can only be saved for assistant turns')
    );

    render(<FeedbackView />);

    const trialButton = (await screen.findByText('Student trial')).closest(
      'button'
    );
    expect(trialButton).toBeInstanceOf(HTMLButtonElement);
    await user.click(trialButton as HTMLButtonElement);
    await screen.findByText('Yes, here is a plan.');
    await user.click(screen.getByTitle('Needs work'));

    expect(
      await screen.findByText('Feedback can only be saved for assistant turns')
    ).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.queryByText('Saved')).not.toBeInTheDocument();
    });
  });

  it('exports the selected encrypted session log as a zip download', async () => {
    const user = userEvent.setup();

    render(<FeedbackView />);

    const trialButton = (await screen.findByText('Student trial')).closest(
      'button'
    );
    expect(trialButton).toBeInstanceOf(HTMLButtonElement);
    await user.click(trialButton as HTMLButtonElement);
    await screen.findByText('Yes, here is a plan.');

    await user.click(screen.getByRole('button', { name: 'Export' }));

    await waitFor(() => {
      expect(mockExportSessionLog).toHaveBeenCalledWith('log-1');
    });
    expect(mockCreateObjectURL).toHaveBeenCalledWith(expect.any(Blob));
    expect(mockRevokeObjectURL).toHaveBeenCalledWith(
      'blob:test-feedback-log-1'
    );
    expect(mockAnchorClick).toHaveBeenCalled();
  });
});
