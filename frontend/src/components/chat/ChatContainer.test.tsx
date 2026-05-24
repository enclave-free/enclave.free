import { cleanup, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it } from 'vitest';
import { ChatContainer } from './ChatContainer';

describe('ChatContainer', () => {
  afterEach(() => {
    cleanup();
  });

  it('only closes the mobile session drawer for marked sidebar actions', async () => {
    const user = userEvent.setup();

    render(
      <ChatContainer
        sidebar={
          <nav aria-label="Chat sessions">
            <button type="button">Keep drawer open</button>
            <button type="button" data-dismiss-sidebar="true">
              Start chat
            </button>
          </nav>
        }
      >
        <div>Conversation</div>
      </ChatContainer>
    );

    await user.click(
      screen.getByRole('button', { name: 'Open chat sessions' })
    );
    expect(
      screen.getAllByRole('navigation', { name: 'Chat sessions' })
    ).toHaveLength(2);
    const mobileSessions = screen.getAllByRole('navigation', {
      name: 'Chat sessions',
    })[1];

    await user.click(
      within(mobileSessions).getByRole('button', { name: 'Keep drawer open' })
    );
    expect(
      screen.getAllByRole('navigation', { name: 'Chat sessions' })
    ).toHaveLength(2);

    await user.click(
      within(mobileSessions).getByRole('button', { name: 'Start chat' })
    );
    expect(
      screen.getAllByRole('navigation', { name: 'Chat sessions' })
    ).toHaveLength(1);
  });
});
