import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  AssistantRuntimeProvider,
  useExternalStoreRuntime,
} from '@assistant-ui/react';
import { AssistantConversationThread } from './AssistantConversationThread';
import { buildAssistantConversationState } from './AssistantTurnAdapter';
import type { AssistantConversationState } from './AssistantTurnAdapter';
import { InstanceConfigProvider } from '../../context/InstanceConfigContext';
import { ThemeProvider } from '../../theme';
import {
  DEFAULT_INSTANCE_CONFIG,
  INSTANCE_CONFIG_KEY,
} from '../../types/instance';

function ThreadHarness({
  state,
  notices,
}: {
  state: AssistantConversationState;
  notices?: React.ReactNode;
}) {
  const runtime = useExternalStoreRuntime({
    messages: state.messages,
    isRunning: state.isRunning,
    isDisabled: state.isDisabled,
    onNew: async () => {},
  });

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <AssistantConversationThread
        assistantState={state}
        runningLabel="Thinking..."
        notices={notices}
      />
    </AssistantRuntimeProvider>
  );
}

function renderThread(
  state: AssistantConversationState,
  notices?: React.ReactNode
) {
  render(
    <ThemeProvider>
      <InstanceConfigProvider>
        <ThreadHarness state={state} notices={notices} />
      </InstanceConfigProvider>
    </ThemeProvider>
  );
}

describe('AssistantConversationThread', () => {
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
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(Response.json({ settings: {} }))
    );
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it('renders generic thread scaffolding around turns, accessories, notices, and running feedback', () => {
    const state = buildAssistantConversationState({
      turns: [
        {
          id: 'user-1',
          role: 'user',
          content: 'Review the policy',
          activitySteps: [],
          traceDeltas: [],
          trace: null,
          traceStatus: null,
        },
        {
          id: 'assistant-1',
          role: 'assistant',
          content: 'The policy is ready.',
          activitySteps: [],
          traceDeltas: [],
          trace: null,
          traceStatus: null,
        },
      ],
      isRunning: true,
      turnAccessories: {
        'assistant-1': <button>Approve change</button>,
      },
    });

    renderThread(state, <div role="note">Reduced context applied.</div>);

    const thread = screen.getByRole('region', { name: 'Conversation thread' });
    const userTurn = screen.getByText('Review the policy');
    const answer = screen.getByText('The policy is ready.');
    const approval = screen.getByRole('button', { name: 'Approve change' });
    const notice = screen.getByRole('note');
    const running = screen.getByText('Thinking...');

    expect(thread).toContainElement(userTurn);
    expect(
      userTurn.compareDocumentPosition(answer) &
        Node.DOCUMENT_POSITION_FOLLOWING
    ).toBeTruthy();
    expect(
      answer.compareDocumentPosition(approval) &
        Node.DOCUMENT_POSITION_FOLLOWING
    ).toBeTruthy();
    expect(
      approval.compareDocumentPosition(notice) &
        Node.DOCUMENT_POSITION_FOLLOWING
    ).toBeTruthy();
    expect(
      notice.compareDocumentPosition(running) & Node.DOCUMENT_POSITION_FOLLOWING
    ).toBeTruthy();
  });
});
