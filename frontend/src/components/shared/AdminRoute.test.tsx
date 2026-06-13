import {
  cleanup,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AdminRoute } from './AdminRoute';
import {
  isAdminAuthenticated,
  validateAdminSession,
} from '../../utils/adminApi';

vi.mock('../../utils/adminApi', () => ({
  isAdminAuthenticated: vi.fn(),
  validateAdminSession: vi.fn(),
}));

vi.mock('../admin/AdminConfigAssistant', () => ({
  AdminConfigAssistant: ({ onCollapse }: { onCollapse?: () => void }) => (
    <div>
      <div>Admin Configuration Assistant</div>
      <input aria-label="Assistant draft" defaultValue="preserved draft" />
      {onCollapse && (
        <button onClick={onCollapse}>Collapse assistant sidebar</button>
      )}
    </div>
  ),
}));

const mockIsAdminAuthenticated = vi.mocked(isAdminAuthenticated);
const mockValidateAdminSession = vi.mocked(validateAdminSession);

describe('AdminRoute', () => {
  beforeEach(() => {
    mockIsAdminAuthenticated.mockReturnValue(true);
    mockValidateAdminSession.mockResolvedValue('authenticated');
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('renders authenticated admin content with the assistant as a right sidebar instead of a floating bubble', async () => {
    render(
      <MemoryRouter initialEntries={['/admin/setup']}>
        <AdminRoute>
          <main>Admin dashboard content</main>
        </AdminRoute>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Admin dashboard content')).toBeInTheDocument();
    });

    const sidebar = screen.getByRole('complementary', {
      name: 'Admin Configuration Assistant',
    });
    await within(sidebar).findByText('Admin Configuration Assistant');
    expect(sidebar).toHaveTextContent('Admin Configuration Assistant');
    expect(sidebar).toHaveClass('right-0');
    expect(document.querySelector('.bottom-5.right-5')).not.toBeInTheDocument();
  });

  it('suppresses the shared assistant on the dedicated onboarding route', async () => {
    render(
      <MemoryRouter initialEntries={['/admin/onboarding']}>
        <AdminRoute>
          <main>Guided setup content</main>
        </AdminRoute>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Guided setup content')).toBeInTheDocument();
    });

    expect(
      screen.queryByRole('complementary', {
        name: 'Admin Configuration Assistant',
      })
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'Open admin assistant' })
    ).not.toBeInTheDocument();
  });

  it('renders when localStorage access is denied by the browser', async () => {
    const originalDescriptor = Object.getOwnPropertyDescriptor(
      window,
      'localStorage'
    );
    Object.defineProperty(window, 'localStorage', {
      configurable: true,
      get: () => {
        throw new Error('localStorage unavailable');
      },
    });

    try {
      render(
        <MemoryRouter initialEntries={['/admin/setup']}>
          <AdminRoute>
            <main>Admin dashboard content</main>
          </AdminRoute>
        </MemoryRouter>
      );

      await screen.findByText('Admin dashboard content');
    } finally {
      if (originalDescriptor) {
        Object.defineProperty(window, 'localStorage', originalDescriptor);
      } else {
        Reflect.deleteProperty(window, 'localStorage');
      }
    }
  });

  it('keeps the assistant session mounted when the desktop sidebar is collapsed and reopened', async () => {
    const user = userEvent.setup();

    render(
      <MemoryRouter initialEntries={['/admin/setup']}>
        <AdminRoute>
          <main>Admin dashboard content</main>
        </AdminRoute>
      </MemoryRouter>
    );

    await screen.findByText('Admin dashboard content');

    const draft = screen.getByRole('textbox', { name: 'Assistant draft' });
    await user.clear(draft);
    await user.type(draft, 'keep this thought');

    await user.click(
      screen.getByRole('button', { name: 'Collapse assistant sidebar' })
    );
    expect(
      screen.queryByRole('textbox', { name: 'Assistant draft' })
    ).not.toBeInTheDocument();

    await user.click(
      screen.getByRole('button', { name: 'Open admin assistant sidebar' })
    );

    expect(
      screen.getByRole('textbox', { name: 'Assistant draft' })
    ).toHaveValue('keep this thought');
  });
});
