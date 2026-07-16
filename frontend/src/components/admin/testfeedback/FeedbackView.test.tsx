import { act, cleanup, render, screen, waitFor } from '@testing-library/react';
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
let originalCreateObjectURLDescriptor: PropertyDescriptor | undefined;
let originalRevokeObjectURLDescriptor: PropertyDescriptor | undefined;
let originalAnchorClickDescriptor: PropertyDescriptor | undefined;

function restoreProperty(
  target: object,
  property: PropertyKey,
  descriptor: PropertyDescriptor | undefined
) {
  if (descriptor) {
    Object.defineProperty(target, property, descriptor);
  } else {
    Reflect.deleteProperty(target, property);
  }
}

describe('FeedbackView', () => {
  beforeEach(() => {
    originalCreateObjectURLDescriptor = Object.getOwnPropertyDescriptor(
      URL,
      'createObjectURL'
    );
    originalRevokeObjectURLDescriptor = Object.getOwnPropertyDescriptor(
      URL,
      'revokeObjectURL'
    );
    originalAnchorClickDescriptor = Object.getOwnPropertyDescriptor(
      HTMLAnchorElement.prototype,
      'click'
    );

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
    restoreProperty(URL, 'createObjectURL', originalCreateObjectURLDescriptor);
    restoreProperty(URL, 'revokeObjectURL', originalRevokeObjectURLDescriptor);
    restoreProperty(
      HTMLAnchorElement.prototype,
      'click',
      originalAnchorClickDescriptor
    );
  });

  it('shows a clear error when rating feedback is rejected', async () => {
    const user = userEvent.setup();
    mockSetTurnFeedback.mockRejectedValue(
      new Error('Feedback can only be saved for assistant turns')
    );

    render(<FeedbackView />);

    expect(await screen.findByText('Test User Session')).toBeInTheDocument();
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

  it('exports the selected session log as a decrypted plaintext JSON download', async () => {
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
      expect(mockCreateObjectURL).toHaveBeenCalledWith(expect.any(Blob));
    });
    // The backend ciphertext (.zip) export is no longer used.
    expect(mockExportSessionLog).not.toHaveBeenCalled();
    expect(mockAnchorClick).toHaveBeenCalled();
    expect(mockRevokeObjectURL).toHaveBeenCalledWith(
      'blob:test-feedback-log-1'
    );

    // The download is decrypted plaintext JSON containing the transcript.
    const blob = (mockCreateObjectURL.mock.calls[0] as unknown as [Blob])[0];
    expect(blob.type).toBe('application/json');
    const text = await blob.text();
    expect(text).toContain('Yes, here is a plan.');
    expect(text).toContain('"log_id": "log-1"');
  });

  it('shows saved assistant tool trace metadata after decrypting a transcript', async () => {
    const user = userEvent.setup();
    mockDecryptField.mockResolvedValue(
      JSON.stringify({
        turns: [
          { role: 'user', content: 'Find resources' },
          {
            role: 'assistant',
            content: 'I found vetted resources.',
            tools_used: [
              {
                tool_id: 'curated-resources',
                tool_name: 'Curated Resources',
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
          },
        ],
      })
    );

    render(<FeedbackView />);

    const trialButton = (await screen.findByText('Student trial')).closest(
      'button'
    );
    expect(trialButton).toBeInstanceOf(HTMLButtonElement);
    await user.click(trialButton as HTMLButtonElement);

    expect(
      await screen.findByText('I found vetted resources.')
    ).toBeInTheDocument();
    expect(
      await screen.findByText('Sage used enabled tools before answering.')
    ).toBeInTheDocument();
    expect(await screen.findByText('Curated Resources')).toBeInTheDocument();
    expect(screen.getByText('Found 2 vetted resources.')).toBeInTheDocument();
  });

  it('ignores stale transcript loads after a newer log is selected', async () => {
    const user = userEvent.setup();
    let resolveFirstLog!: (
      value: Awaited<ReturnType<typeof getSessionLog>>
    ) => void;
    mockListSessionLogs.mockResolvedValue([
      {
        log_id: 'log-1',
        source: 'admin_test',
        title: 'First trial',
        subject_user_id: 42,
        user_type_id: 1,
        sage_session_id: 'sage-1',
        turn_count: 0,
        status: 'completed',
        created_by: 'admin',
        created_at: null,
        updated_at: null,
        completed_at: null,
        has_transcript: false,
      },
      {
        log_id: 'log-2',
        source: 'admin_test',
        title: 'Second trial',
        subject_user_id: 43,
        user_type_id: 1,
        sage_session_id: 'sage-2',
        turn_count: 0,
        status: 'completed',
        created_by: 'admin',
        created_at: null,
        updated_at: null,
        completed_at: null,
        has_transcript: false,
      },
    ]);
    mockGetSessionLog.mockImplementation((logId) => {
      if (logId === 'log-1') {
        return new Promise((resolve) => {
          resolveFirstLog = resolve;
        });
      }
      return Promise.resolve({
        log_id: 'log-2',
        source: 'admin_test',
        title: 'Loaded second trial',
        subject_user_id: 43,
        user_type_id: 1,
        sage_session_id: 'sage-2',
        turn_count: 0,
        status: 'completed',
        created_by: 'admin',
        created_at: null,
        updated_at: null,
        completed_at: null,
        has_transcript: false,
        transcript_ciphertext: null,
        transcript_ephemeral_pubkey: null,
        encrypted_to_pubkey: 'admin-pubkey',
        feedback: [],
      });
    });

    render(<FeedbackView />);

    await user.click(await screen.findByText('First trial'));
    await user.click(await screen.findByText('Second trial'));
    expect(await screen.findByText('Loaded second trial')).toBeInTheDocument();

    await act(async () => {
      resolveFirstLog({
        log_id: 'log-1',
        source: 'admin_test',
        title: 'Loaded first trial',
        subject_user_id: 42,
        user_type_id: 1,
        sage_session_id: 'sage-1',
        turn_count: 0,
        status: 'completed',
        created_by: 'admin',
        created_at: null,
        updated_at: null,
        completed_at: null,
        has_transcript: false,
        transcript_ciphertext: null,
        transcript_ephemeral_pubkey: null,
        encrypted_to_pubkey: 'admin-pubkey',
        feedback: [],
      });
      await Promise.resolve();
    });

    expect(screen.getByText('Loaded second trial')).toBeInTheDocument();
    expect(screen.queryByText('Loaded first trial')).not.toBeInTheDocument();
  });

  it('keeps the selected log visible when delete fails', async () => {
    const user = userEvent.setup();
    mockDeleteSessionLog.mockRejectedValue(new Error('Delete failed'));

    render(<FeedbackView />);

    const trialButton = (await screen.findByText('Student trial')).closest(
      'button'
    );
    expect(trialButton).toBeInstanceOf(HTMLButtonElement);
    await user.click(trialButton as HTMLButtonElement);
    await screen.findByText('Yes, here is a plan.');

    await user.click(screen.getByRole('button', { name: 'Delete' }));

    expect(await screen.findByText('Delete failed')).toBeInTheDocument();
    expect(screen.getByText('Yes, here is a plan.')).toBeInTheDocument();
    expect(mockListSessionLogs).toHaveBeenCalledTimes(1);
  });
});
