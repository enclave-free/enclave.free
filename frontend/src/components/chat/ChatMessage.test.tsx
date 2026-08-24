import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ChatMessage } from './ChatMessage';
import { InstanceConfigProvider } from '../../context/InstanceConfigContext';
import { ThemeProvider } from '../../theme';
import {
  DEFAULT_INSTANCE_CONFIG,
  INSTANCE_CONFIG_KEY,
} from '../../types/instance';

let clipboardWriteText: ReturnType<typeof vi.fn>;
const originalClipboardDescriptor = Object.getOwnPropertyDescriptor(
  window.navigator,
  'clipboard'
);

function stubLocalStorage() {
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
}

function renderMessage(
  content: string,
  role: 'user' | 'assistant' = 'assistant',
  trace?: Parameters<typeof ChatMessage>[0]['message']['trace'],
  props?: Partial<Parameters<typeof ChatMessage>[0]>
) {
  return render(
    <ThemeProvider>
      <InstanceConfigProvider>
        <ChatMessage
          activityAudience="user"
          {...props}
          message={{
            id: 'message-1',
            role,
            content,
            trace,
            ...props?.message,
          }}
        />
      </InstanceConfigProvider>
    </ThemeProvider>
  );
}

describe('ChatMessage', () => {
  beforeEach(() => {
    stubLocalStorage();
    localStorage.setItem('enclave-theme', 'light');
    localStorage.setItem(
      INSTANCE_CONFIG_KEY,
      JSON.stringify(DEFAULT_INSTANCE_CONFIG)
    );
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
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
  });

  afterEach(() => {
    cleanup();
    if (originalClipboardDescriptor) {
      Object.defineProperty(
        window.navigator,
        'clipboard',
        originalClipboardDescriptor
      );
    } else {
      delete (window.navigator as unknown as { clipboard?: Clipboard })
        .clipboard;
    }
    vi.unstubAllGlobals();
    vi.clearAllMocks();
    document.documentElement.classList.remove('dark');
  });

  function stubClipboard() {
    clipboardWriteText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(window.navigator, 'clipboard', {
      configurable: true,
      writable: true,
      value: {
        writeText: clipboardWriteText,
      },
    });
  }

  it('renders representative assistant markdown through public elements', () => {
    renderMessage(
      [
        '## Brief',
        '',
        'Read [the docs](https://example.com) and keep `inline code` visible.',
        '',
        '- First point',
        '- Second point',
        '',
        '1. Review requested changes',
        '2. Confirm the Change Confirmation',
        '',
        '> Keep secrets masked.',
        '',
        '| Setting | Value |',
        '| --- | --- |',
        '| Model Provider | Tinfoil |',
        '',
        '```ts',
        'const answer = 42',
        '```',
      ].join('\n')
    );

    expect(screen.getByRole('heading', { name: 'Brief' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'the docs' })).toHaveAttribute(
      'href',
      'https://example.com'
    );
    expect(screen.getByText('inline code')).toBeInTheDocument();
    expect(screen.getByText('First point')).toBeInTheDocument();
    expect(screen.getByText('Second point')).toBeInTheDocument();
    expect(screen.getByText('Review requested changes')).toBeInTheDocument();
    expect(screen.getByText('Keep secrets masked.')).toBeInTheDocument();
    expect(screen.getByRole('table')).toHaveTextContent('Model Provider');
    expect(screen.getByRole('table')).toHaveTextContent('Tinfoil');
    expect(screen.getByText('ts')).toBeInTheDocument();
    expect(document.body).toHaveTextContent('const answer = 42');
  });

  it('keeps assistant markdown HTML and unsafe links inert', () => {
    renderMessage(
      [
        'Hello <img src=x onerror="alert(1)" />',
        '',
        '[unsafe link](javascript:alert(1))',
        '[protocol-relative](//example.com/path)',
      ].join('\n')
    );

    expect(document.querySelector('img')).not.toBeInTheDocument();
    expect(document.body).toHaveTextContent('<img src=x onerror="alert(1)" />');
    expect(screen.getByText('unsafe link')).not.toHaveAttribute('href');
    expect(screen.getByText('protocol-relative')).not.toHaveAttribute('href');
  });

  it('copies fenced code content from the accessible copy action', async () => {
    const user = userEvent.setup();
    stubClipboard();

    renderMessage(['```ts', 'const answer = 42', '```'].join('\n'));

    await user.click(screen.getByRole('button', { name: 'Copy code' }));

    expect(clipboardWriteText).toHaveBeenCalledWith('const answer = 42');
  });

  it('copies the full assistant message from the message copy icon', async () => {
    const user = userEvent.setup();
    stubClipboard();
    const content = 'Here is a useful answer with **markdown**.';

    renderMessage(content);

    await user.click(screen.getByRole('button', { name: 'Copy message' }));

    expect(clipboardWriteText).toHaveBeenCalledWith(content);
    expect(
      screen.getByRole('button', { name: 'Copied message' })
    ).toBeInTheDocument();
  });

  it('copies user messages from the same message copy icon', async () => {
    const user = userEvent.setup();
    stubClipboard();
    const content = 'Please make this easy to copy.';

    renderMessage(content, 'user');

    await user.click(screen.getByRole('button', { name: 'Copy message' }));

    expect(clipboardWriteText).toHaveBeenCalledWith(content);
  });

  it('renders capability-gated message actions without mutating by default', async () => {
    const user = userEvent.setup();
    const onAction = vi.fn();
    const message = {
      id: 'message-1',
      role: 'assistant' as const,
      content: 'Answer ready.',
      actions: [
        {
          id: 'regenerate' as const,
          label: 'Regenerate response',
          disabled: true,
          disabledReason: 'Wait for the current response to finish first.',
        },
        {
          id: 'stop' as const,
          label: 'Stop response',
          disabled: false,
        },
      ],
    };

    renderMessage('Answer ready.', 'assistant', undefined, {
      onAction,
      message,
    });

    expect(
      screen.getByRole('toolbar', { name: 'Message actions' })
    ).toBeInTheDocument();
    const disabledAction = screen.getByRole('button', {
      name: 'Regenerate response',
    });
    expect(disabledAction).toBeDisabled();
    expect(disabledAction).toHaveAttribute(
      'title',
      'Wait for the current response to finish first.'
    );

    await user.click(disabledAction);

    expect(onAction).not.toHaveBeenCalled();

    const enabledAction = screen.getByRole('button', {
      name: 'Stop response',
    });
    expect(enabledAction).toBeEnabled();

    await user.click(enabledAction);

    expect(onAction).toHaveBeenCalledWith(
      'stop',
      expect.objectContaining({ id: 'message-1' })
    );
  });

  it('collapses Activity by default for Users and opens it on the arrow', async () => {
    const user = userEvent.setup();
    renderMessage('Here is the answer.', 'assistant', {
      visibility: 'minimal',
      reasoning: { summary: 'Sage used Web search before answering.' },
      tools: [
        {
          id: 'web-search',
          name: 'Web search',
          status: 'success',
          execution: 'server',
          input_summary: 'current policy updates',
          output_summary: 'Found 3 relevant results.',
          warnings: [],
          metadata: {},
        },
      ],
      retrieval: [],
      suppressed: false,
      activity_steps: [
        {
          id: 'step-1',
          kind: 'tool',
          title: 'Web Search',
          status: 'succeeded',
          summary: 'Found three relevant results.',
        },
      ],
    });

    const toggle = screen.getByRole('button', { name: 'Show Activity' });
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    expect(
      document.getElementById(toggle.getAttribute('aria-controls')!)
    ).toHaveAttribute('hidden');

    await user.click(toggle);

    expect(
      screen.getByRole('button', { name: 'Hide Activity' })
    ).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getAllByText('Web Search')).toHaveLength(1);
  });

  it('keeps Activity collapsed even when the trace says detailed', () => {
    // Sage hardcodes visibility "detailed" for every Conversation, so the
    // default must not be derived from it. See #636.
    renderMessage('Here is the answer.', 'assistant', {
      visibility: 'detailed',
      reasoning: { summary: 'Sage answered.' },
      tools: [],
      retrieval: [],
      suppressed: false,
      activity_steps: [
        {
          id: 'step-1',
          kind: 'timing',
          title: 'Provider first-event wait',
          status: 'timed_out',
          summary:
            'Provider produced no event before the first-event deadline.',
        },
      ],
    });

    expect(
      screen.getByRole('button', { name: 'Show Activity' })
    ).toHaveAttribute('aria-expanded', 'false');
  });

  it('opens Activity by default when the surface opts in', () => {
    renderMessage(
      'Here is the answer.',
      'assistant',
      {
        visibility: 'detailed',
        reasoning: { summary: 'Sage answered.' },
        tools: [],
        retrieval: [],
        suppressed: false,
        activity_steps: [
          {
            id: 'step-1',
            kind: 'timing',
            title: 'Provider first-event wait',
            status: 'timed_out',
            summary:
              'Provider produced no event before the first-event deadline.',
          },
        ],
      },
      { activityAudience: 'admin', defaultActivityOpen: true }
    );

    expect(
      screen.getByRole('button', { name: 'Hide Activity' })
    ).toHaveAttribute('aria-expanded', 'true');
  });

  it('shows product work but omits operational rows from User Activity', () => {
    renderMessage(
      'Here is the answer.',
      'assistant',
      {
        visibility: 'detailed',
        tools: [],
        retrieval: [],
        activity_steps: [
          {
            id: 'provider-wait',
            kind: 'timing',
            title: 'Provider first-event wait',
            status: 'timed_out',
            summary: 'Provider produced no event before the deadline.',
          },
          {
            id: 'web-search',
            kind: 'tool',
            title: 'Web Search',
            status: 'succeeded',
            summary: 'Found three relevant results.',
          },
        ],
        trace_deltas: [
          {
            id: 'model-request',
            kind: 'timing',
            title: 'Model request',
            content: 'Model request: 820 ms.',
          },
          {
            id: 'tool-result',
            kind: 'tool_result',
            title: 'Web Search',
            content: 'Found three results with retry guidance.',
          },
        ],
      },
      { activityAudience: 'user', defaultActivityOpen: true }
    );

    expect(screen.getAllByText('Web Search')).toHaveLength(2);
    expect(
      screen.getByText('Found three relevant results.')
    ).toBeInTheDocument();
    expect(
      screen.getByText('Found three results with retry guidance.')
    ).toBeInTheDocument();
    expect(
      screen.queryByText('Provider first-event wait')
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText('Model request: 820 ms.')
    ).not.toBeInTheDocument();
    expect(screen.queryByText('timed_out')).not.toBeInTheDocument();
  });

  it('keeps raw operational rows visible in Admin Activity', () => {
    renderMessage(
      'Here is the answer.',
      'assistant',
      {
        visibility: 'detailed',
        activity_steps: [
          {
            id: 'provider-wait',
            kind: 'timing',
            title: 'Provider first-event wait',
            status: 'timed_out',
          },
        ],
      },
      { activityAudience: 'admin', defaultActivityOpen: true }
    );

    expect(screen.getByText('Provider first-event wait')).toBeInTheDocument();
    expect(screen.getByText('timed_out')).toBeInTheDocument();
  });

  it('does not leave an empty User Activity panel for only operational rows', () => {
    renderMessage(
      'The answer is still available.',
      'assistant',
      {
        visibility: 'detailed',
        activity_steps: [
          {
            id: 'provider-wait',
            kind: 'timing',
            title: 'Provider first-event wait',
            status: 'timed_out',
          },
        ],
      },
      {
        activityAudience: 'user',
        message: {
          id: 'message-1',
          role: 'assistant',
          content: 'The answer is still available.',
          traceStatus: 'TIMED_OUT',
        },
      }
    );

    expect(
      screen.getByText('The answer is still available.')
    ).toBeInTheDocument();
    expect(screen.queryByLabelText('Activity')).not.toBeInTheDocument();
    expect(screen.queryByText('TIMED_OUT')).not.toBeInTheDocument();
  });

  it('keeps optional Activity summaries behind a distinct nested disclosure', async () => {
    const user = userEvent.setup();
    renderMessage('Here is the answer.', 'assistant', {
      visibility: 'summary',
      reasoning: {
        summary: 'Sage used Web search before answering.',
      },
      tools: [
        {
          id: 'web-search',
          name: 'Web search',
          status: 'success',
          execution: 'server',
          input_summary: 'current policy updates',
          output_summary: 'Found 3 relevant results.',
          warnings: [],
          metadata: {},
        },
      ],
      retrieval: [
        {
          source_type: 'document',
          title: 'Policy guide',
          summary: 'Matched the current policy section.',
        },
      ],
      suppressed: false,
    });

    expect(screen.getByText('Activity')).toBeInTheDocument();
    // Activity is collapsed by default (see #636); this test is about the
    // nested optional-details disclosure, so open the outer panel first.
    await user.click(screen.getByRole('button', { name: 'Show Activity' }));
    expect(screen.queryByText('Conversation Trace')).not.toBeInTheDocument();
    expect(screen.queryByText('summary')).not.toBeInTheDocument();
    expect(screen.getByText('Tool calls')).toBeInTheDocument();
    expect(screen.queryByText('Tools')).not.toBeInTheDocument();
    expect(screen.getByText('Web search')).toBeInTheDocument();
    expect(
      screen.getByText('Sage used Web search before answering.')
    ).not.toBeVisible();
    expect(screen.getByText('Found 3 relevant results.')).not.toBeVisible();
    expect(
      screen.getByText('Matched the current policy section.')
    ).not.toBeVisible();

    const optionalDetails = screen.getByRole('button', {
      name: 'Show optional details',
    });
    const controlledDetailIds = optionalDetails
      .getAttribute('aria-controls')
      ?.split(/\s+/);

    expect(optionalDetails).toHaveAttribute('aria-expanded', 'false');
    expect(controlledDetailIds).toHaveLength(3);
    controlledDetailIds?.forEach((id) => {
      expect(document.getElementById(id)).toHaveAttribute('hidden');
    });

    await user.click(optionalDetails);

    expect(
      screen.getByRole('button', { name: 'Hide optional details' })
    ).toHaveAttribute('aria-expanded', 'true');
    expect(
      screen.getByText('Sage used Web search before answering.')
    ).toBeInTheDocument();
    expect(screen.getByText('Found 3 relevant results.')).toBeInTheDocument();
    expect(
      screen.getByText('Matched the current policy section.')
    ).toBeInTheDocument();
    controlledDetailIds?.forEach((id) => {
      expect(document.getElementById(id)).not.toHaveAttribute('hidden');
    });
  });

  it('collapses and restores the complete Activity body from its accessible header control', async () => {
    const user = userEvent.setup();

    renderMessage(
      'Here is the answer.',
      'assistant',
      {
        visibility: 'detailed',
        tools: [
          {
            id: 'knowledge-search',
            name: 'Knowledge Search',
            status: 'succeeded',
            output_summary: 'Found the relevant guide.',
          },
        ],
        retrieval: [
          {
            source_type: 'document',
            title: 'Rights Guide',
            summary: 'Matched the current policy section.',
          },
        ],
        activity_steps: [
          {
            id: 'activity-1',
            kind: 'retrieval',
            title: 'Searching documents',
            status: 'succeeded',
          },
        ],
      },
      {
        message: {
          id: 'message-1',
          role: 'assistant',
          content: 'Here is the answer.',
          traceStatus: 'Preparing response...',
          traceDeltas: [
            {
              id: 'trace-1',
              kind: 'timing',
              title: 'Model request',
              content: 'Model request: 820 ms.',
              status: 'succeeded',
            },
          ],
        },
        // This test covers the collapse/restore round-trip, so start expanded.
        // The default is collapsed (see #636).
        activityAudience: 'admin',
        defaultActivityOpen: true,
      }
    );

    const collapse = screen.getByRole('button', { name: 'Hide Activity' });
    const activityBody = screen.getByRole('region', {
      name: 'Activity details',
    });

    expect(collapse).toHaveAttribute('aria-expanded', 'true');
    expect(collapse).toHaveAttribute('aria-controls', activityBody.id);
    expect(screen.getByText('Searching documents')).toBeInTheDocument();
    expect(screen.getByText('Model request: 820 ms.')).toBeInTheDocument();
    expect(screen.getByText('Tool calls')).toBeInTheDocument();
    expect(screen.getByText('Retrieval')).toBeInTheDocument();

    const optionalDetails = screen.getByRole('button', {
      name: 'Show optional details',
    });
    const optionalDetailIds = optionalDetails
      .getAttribute('aria-controls')
      ?.split(' ');
    await user.click(optionalDetails);
    expect(
      screen.getByRole('button', { name: 'Hide optional details' })
    ).toHaveAttribute('aria-expanded', 'true');
    optionalDetailIds?.forEach((id) => {
      expect(document.getElementById(id)).not.toHaveAttribute('hidden');
    });

    await user.click(collapse);

    expect(
      screen.getByRole('button', { name: 'Show Activity' })
    ).toHaveAttribute('aria-expanded', 'false');
    expect(
      screen.queryByRole('region', { name: 'Activity details' })
    ).not.toBeInTheDocument();
    expect(document.getElementById(activityBody.id)).toHaveAttribute('hidden');
    expect(screen.getByText('Searching documents')).not.toBeVisible();
    expect(screen.getByText('Model request: 820 ms.')).not.toBeVisible();
    expect(screen.getByText('Activity')).toBeInTheDocument();
    expect(screen.getByText('Preparing response...')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Show Activity' }));

    expect(
      screen.getByRole('region', { name: 'Activity details' })
    ).toBeInTheDocument();
    expect(document.getElementById(activityBody.id)).not.toHaveAttribute(
      'hidden'
    );
    expect(screen.getByText('Searching documents')).toBeInTheDocument();
    expect(screen.getByText('Model request: 820 ms.')).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'Hide optional details' })
    ).toHaveAttribute('aria-expanded', 'true');
    optionalDetailIds?.forEach((id) => {
      expect(document.getElementById(id)).not.toHaveAttribute('hidden');
    });
  });

  it('renders Activity from trace metadata when no separate activity prop is present', () => {
    renderMessage('Here is the answer.', 'assistant', {
      visibility: 'summary',
      tools: [],
      retrieval: [],
      activity_steps: [
        {
          id: 'activity-1',
          kind: 'tool',
          title: 'Checking configuration',
          status: 'completed',
          summary: 'Loaded Instance visual identity context.',
        },
      ],
      suppressed: false,
    });

    expect(screen.getByText('Activity')).toBeInTheDocument();
    expect(screen.getByText('Checking configuration')).toBeInTheDocument();
    expect(screen.queryByText('completed')).not.toBeInTheDocument();
    expect(
      screen.getByText('Loaded Instance visual identity context.')
    ).toBeInTheDocument();
  });

  it('omits a content-free Tool selection observation from User Activity', () => {
    renderMessage('I could not find a current contact.', 'assistant', {
      visibility: 'detailed',
      tools: [],
      retrieval: [],
      activity_steps: [
        {
          id: 'activity-tool-selection-1',
          kind: 'tool_selection_observation',
          title: 'Tool Selection',
          status: 'succeeded',
          summary: 'No Tools were selected.',
        },
      ],
      suppressed: false,
    });

    expect(screen.queryByLabelText('Activity')).not.toBeInTheDocument();
    expect(screen.queryByText('Tool Selection')).not.toBeInTheDocument();
    expect(
      screen.queryByText('No Tools were selected.')
    ).not.toBeInTheDocument();
  });

  it('renders minimal assistant trace as compact usage badges', () => {
    renderMessage('Here is the answer.', 'assistant', {
      visibility: 'minimal',
      reasoning: {
        summary: 'Sage used internal context before answering.',
      },
      tools: [
        {
          id: 'web-search',
          name: 'Web search',
          status: 'success',
          execution: 'server',
          output_summary: 'Found 3 relevant results.',
        },
      ],
      retrieval: [
        {
          source_type: 'document',
          title: 'Tenant Rights Guide',
          summary: 'Matched eviction timeline section.',
        },
      ],
      suppressed: false,
    });

    expect(screen.queryByText('Conversation Trace')).not.toBeInTheDocument();
    expect(
      screen.queryByText('Sage used internal context before answering.')
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText('Found 3 relevant results.')
    ).not.toBeInTheDocument();
    expect(screen.getByText('Web search')).toBeInTheDocument();
    expect(screen.getByText('Tenant Rights Guide')).toBeInTheDocument();
  });

  it('does not render an empty assistant bubble for non-renderable trace metadata', () => {
    renderMessage('', 'assistant', {
      visibility: 'summary',
      tools: [],
      retrieval: [],
      suppressed: false,
    });

    expect(
      screen.queryByText(DEFAULT_INSTANCE_CONFIG.assistantName)
    ).not.toBeInTheDocument();
    expect(screen.queryByText('Conversation Trace')).not.toBeInTheDocument();
  });

  it('does not render a minimal trace strip when there are no visible chips', () => {
    renderMessage('Here is the answer.', 'assistant', {
      visibility: 'minimal',
      reasoning: {
        summary: 'Hidden in minimal mode.',
      },
      tools: [],
      retrieval: [],
      suppressed: false,
    });

    expect(screen.queryByLabelText('Activity summary')).not.toBeInTheDocument();
    expect(
      screen.queryByText('Hidden in minimal mode.')
    ).not.toBeInTheDocument();
  });

  it('does not render the internal writing trace as assistant content', () => {
    render(
      <ThemeProvider>
        <InstanceConfigProvider>
          <ChatMessage
            activityAudience="admin"
            message={{
              id: 'message-1',
              role: 'assistant',
              content: '',
              traceStatus: 'Finalizing response...',
            }}
          />
        </InstanceConfigProvider>
      </ThemeProvider>
    );

    expect(
      screen.queryByText('Finalizing response...')
    ).not.toBeInTheDocument();
  });

  it('renders meaningful live trace status while a streamed assistant turn is in progress', () => {
    render(
      <ThemeProvider>
        <InstanceConfigProvider>
          <ChatMessage
            activityAudience="user"
            message={{
              id: 'message-1',
              role: 'assistant',
              content: 'Partial answer',
              traceStatus: 'Writing answer...',
            }}
          />
        </InstanceConfigProvider>
      </ThemeProvider>
    );

    expect(screen.getByText('Writing answer...')).toBeInTheDocument();
  });

  it('renders live Trace Deltas as Activity rows before the final answer finishes', () => {
    render(
      <ThemeProvider>
        <InstanceConfigProvider>
          <ChatMessage
            activityAudience="user"
            message={{
              id: 'message-1',
              role: 'assistant',
              content: '',
              traceStatus: 'Writing answer...',
              traceDeltas: [
                {
                  id: 'trace-admin-config-call',
                  kind: 'tool_call',
                  title: 'Admin Config',
                  content: 'Calling read_instance_settings.',
                  tool_name: 'read_instance_settings',
                  status: 'running',
                  metadata: { phase: 'tool_loop' },
                  created_at: '2026-06-18T12:00:00Z',
                },
                {
                  id: 'trace-redacted-secret',
                  kind: 'tool_result',
                  title: 'Admin Config',
                  content: '[redacted]',
                  tool_name: 'read_deployment_settings',
                  status: 'guarded',
                },
              ],
            }}
          />
        </InstanceConfigProvider>
      </ThemeProvider>
    );

    expect(screen.getByText('Activity')).toBeInTheDocument();
    expect(screen.getAllByText('Admin Config')).toHaveLength(2);
    expect(
      screen.getByText('Calling read_instance_settings.')
    ).toBeInTheDocument();
    expect(screen.getByText('[redacted]')).toBeInTheDocument();
    expect(screen.getByText('guarded')).toBeInTheDocument();
  });

  it('renders read-only Tool retry and timeout evidence as accessible Activity rows', () => {
    render(
      <ThemeProvider>
        <InstanceConfigProvider>
          <ChatMessage
            activityAudience="admin"
            message={{
              id: 'message-1',
              role: 'assistant',
              content: '',
              traceDeltas: [
                {
                  id: 'trace-tool-retry',
                  kind: 'tool_retry',
                  title: 'Curated Resources',
                  content: 'Retrying Curated Resources after attempt 1.',
                  tool_name: 'find_resources',
                  status: 'running',
                  metadata: { phase: 'retry', call_id: 'call-1', attempt: 1 },
                },
                {
                  id: 'trace-tool-timeout',
                  kind: 'timeout',
                  title: 'Knowledge Search',
                  content: 'Knowledge Search timed out.',
                  tool_name: 'knowledge_search',
                  status: 'timed_out',
                  metadata: { phase: 'timeout', call_id: 'call-2', attempt: 2 },
                },
              ],
            }}
          />
        </InstanceConfigProvider>
      </ThemeProvider>
    );

    expect(screen.getByLabelText('Activity')).toBeInTheDocument();
    expect(
      screen.getByText('Retrying Curated Resources after attempt 1.')
    ).toBeInTheDocument();
    expect(screen.getByText('Knowledge Search timed out.')).toBeInTheDocument();
    expect(screen.getByText('timed_out')).toBeInTheDocument();
  });

  it('renders backend timing deltas with phase, duration, and guarded outcome', () => {
    render(
      <ThemeProvider>
        <InstanceConfigProvider>
          <ChatMessage
            activityAudience="admin"
            message={{
              id: 'message-timing-1',
              role: 'assistant',
              content: 'The answer is ready.',
              traceDeltas: [
                {
                  id: 'timing-tool-guarded-1',
                  kind: 'timing',
                  title: 'Tool execution',
                  content: 'Tool execution: 9 ms.',
                  status: 'guarded',
                  metadata: {
                    phase: 'tool_execution',
                    step: null,
                    attempt: 1,
                    call_id: 'call-guarded',
                    tool_name: 'db_query',
                    outcome: 'guarded',
                    duration_ms: 9,
                    provider_wait_proxy: false,
                    args: 'SELECT email FROM contacts WHERE email = contact@example.test',
                    output: 'contact@example.test',
                  },
                  created_at: '2026-07-28T12:00:00Z',
                },
                {
                  id: 'timing-provider-first-1',
                  kind: 'timing',
                  title: 'Provider first-event wait',
                  content:
                    'Provider first-event wait: 184 ms (combined provider wait).',
                  status: 'succeeded',
                  metadata: {
                    phase: 'provider_first_event_wait',
                    step: 1,
                    attempt: 1,
                    outcome: 'succeeded',
                    duration_ms: 184,
                    provider_wait_proxy: true,
                  },
                  created_at: '2026-07-28T12:00:00Z',
                },
              ],
            }}
          />
        </InstanceConfigProvider>
      </ThemeProvider>
    );

    expect(screen.getByLabelText('Activity')).toBeInTheDocument();
    expect(screen.getByText('Tool execution')).toBeInTheDocument();
    expect(screen.getByText('Provider first-event wait')).toBeInTheDocument();
    expect(screen.getByText('Tool execution: 9 ms.')).toBeInTheDocument();
    expect(
      screen.getByText(/Provider first-event wait: 184 ms/)
    ).toBeInTheDocument();
    expect(screen.getByText('guarded')).toBeInTheDocument();
    expect(screen.queryByText(/contact@example\.test/)).not.toBeInTheDocument();
    expect(
      screen.queryByText(/SELECT email FROM contacts/)
    ).not.toBeInTheDocument();
  });

  it('groups streamed provider reasoning into one expandable transcript', async () => {
    const user = userEvent.setup();

    render(
      <ThemeProvider>
        <InstanceConfigProvider>
          <ChatMessage
            activityAudience="user"
            message={{
              id: 'message-1',
              role: 'assistant',
              content: '',
              traceStatus: 'Writing answer...',
              traceDeltas: [
                {
                  id: 'reasoning-1',
                  kind: 'reasoning',
                  title: 'Provider reasoning',
                  content: 'I need to be careful not to fabric',
                  status: 'succeeded',
                  metadata: { step: 2, source: 'provider' },
                },
                {
                  id: 'reasoning-2',
                  kind: 'reasoning',
                  title: 'Provider reasoning',
                  content: 'ate contact information. ',
                  status: 'succeeded',
                  metadata: { step: 2, source: 'provider' },
                },
                {
                  id: 'reasoning-3',
                  kind: 'reasoning',
                  title: 'Provider reasoning',
                  content:
                    'I will reference the organizations in the documents.',
                  status: 'succeeded',
                  metadata: { step: 2, source: 'provider' },
                },
                {
                  id: 'trace-tool-call',
                  kind: 'tool_call',
                  title: 'Knowledge Search',
                  content: 'Calling knowledge_search.',
                  status: 'running',
                },
              ],
            }}
          />
        </InstanceConfigProvider>
      </ThemeProvider>
    );

    await user.click(screen.getByRole('button', { name: 'Show Activity' }));

    const disclosure = screen.getByRole('button', { name: /Thinking/ });
    expect(disclosure).toHaveAttribute('aria-expanded', 'false');
    expect(screen.queryAllByText('Provider reasoning')).toHaveLength(0);
    expect(
      screen.queryByRole('region', { name: 'Reasoning transcript' })
    ).not.toBeInTheDocument();
    expect(screen.getByText('Calling knowledge_search.')).toBeInTheDocument();

    await user.click(disclosure);

    const transcript = screen.getByRole('region', {
      name: 'Reasoning transcript',
    });
    expect(disclosure).toHaveAttribute('aria-expanded', 'true');
    expect(transcript).toHaveTextContent(
      'I need to be careful not to fabricate contact information. I will reference the organizations in the documents.'
    );
  });
});
