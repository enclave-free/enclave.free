import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {
  AssistantRuntimeProvider,
  useExternalStoreRuntime,
  type AppendMessage,
  type ThreadMessage,
} from '@assistant-ui/react';
import type { ReactNode } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { AssistantComposerInput } from './AssistantComposerInput';

function ComposerHarness({
  onNew,
  disabled = false,
  toolbar,
}: {
  onNew: (message: AppendMessage) => Promise<void>;
  disabled?: boolean;
  toolbar?: ReactNode;
}) {
  const runtime = useExternalStoreRuntime({
    messages: [] as ThreadMessage[],
    isRunning: false,
    isDisabled: disabled,
    onNew,
  });

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <AssistantComposerInput disabled={disabled} toolbar={toolbar} />
    </AssistantRuntimeProvider>
  );
}

describe('AssistantComposerInput', () => {
  afterEach(() => {
    cleanup();
  });

  it('submits prompts through the assistant-ui composer runtime', async () => {
    const user = userEvent.setup();
    const onNew = vi.fn(async () => {});

    render(<ComposerHarness onNew={onNew} />);

    await user.type(
      screen.getByRole('textbox', { name: 'Ask anything...' }),
      'Review this conversation'
    );
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    expect(onNew).toHaveBeenCalledWith(
      expect.objectContaining({
        content: [{ type: 'text', text: 'Review this conversation' }],
      })
    );
  });

  it('keeps composer context controls in a named wrapping group', () => {
    const onNew = vi.fn(async () => {});

    render(
      <ComposerHarness
        onNew={onNew}
        toolbar={
          <>
            <button>Tools</button>
            <button>Documents</button>
            <button>Export</button>
          </>
        }
      />
    );

    const context = screen.getByRole('group', { name: 'Composer context' });
    expect(context).toHaveClass('flex-wrap');
    expect(context).toContainElement(
      screen.getByRole('button', { name: 'Tools' })
    );
    expect(context).toContainElement(
      screen.getByRole('button', { name: 'Documents' })
    );
  });
});
