import { cleanup, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { SettingsDrawer } from './SettingsDrawer';
import { useAuthFlow } from '../../hooks/useAuthFlow';

vi.mock('../../hooks/useAuthFlow', () => ({
  clearAllAuth: vi.fn(),
  useAuthFlow: vi.fn(),
}));

const mockUseAuthFlow = vi.mocked(useAuthFlow);

describe('SettingsDrawer', () => {
  beforeEach(() => {
    mockUseAuthFlow.mockReturnValue({
      isAdmin: true,
      isAuthenticated: true,
      isApproved: true,
      userEmail: 'admin@example.test',
      userName: 'Admin',
      redirectPath: '/chat',
    });
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('shows the current admin navigation map in the chat settings drawer', () => {
    render(
      <MemoryRouter>
        <SettingsDrawer open onClose={vi.fn()} />
      </MemoryRouter>
    );

    const workflows = screen.getByRole('region', { name: 'Admin Workflows' });
    expect(
      within(workflows).getByRole('link', { name: /Admin Dashboard/ })
    ).toHaveAttribute('href', '/admin/setup');
    expect(
      within(workflows).getByRole('link', { name: /Guided Setup/ })
    ).toHaveAttribute('href', '/admin/onboarding');
    expect(
      within(workflows).getByRole('link', { name: /Test User Session/ })
    ).toHaveAttribute('href', '/admin/test-and-feedback');
    expect(
      within(workflows).queryByRole('link', { name: /Deployment Settings/ })
    ).not.toBeInTheDocument();

    const settings = screen.getByRole('region', { name: 'Settings' });
    expect(
      within(settings).getByRole('link', { name: /Instance Settings/ })
    ).toHaveAttribute('href', '/admin/instance');
    expect(
      within(settings).getByRole('link', { name: /User Settings/ })
    ).toHaveAttribute('href', '/admin/users');
    expect(
      within(settings).getByRole('link', { name: /Agent Settings/ })
    ).toHaveAttribute('href', '/admin/ai');

    const content = screen.getByRole('region', { name: 'Data & Content' });
    expect(
      within(content).getByRole('link', { name: /Document Upload/ })
    ).toHaveAttribute('href', '/admin/upload');
    expect(
      within(content).getByRole('link', { name: /Resource Directory/ })
    ).toHaveAttribute('href', '/admin/resources');

    const operations = screen.getByRole('region', { name: 'Operations' });
    expect(
      within(operations).getByRole('link', { name: /Database Explorer/ })
    ).toHaveAttribute('href', '/admin/database');
    expect(
      within(operations).getByRole('link', { name: /Deployment Settings/ })
    ).toHaveAttribute('href', '/admin/deployment');
    expect(
      within(operations).getByRole('link', { name: /Diagnostics/ })
    ).toHaveAttribute('href', '/diagnostics/test-dashboard');
    expect(
      within(operations).queryByRole('link', {
        name: /Diagnostics Test Dashboard/,
      })
    ).not.toBeInTheDocument();
  });
});
