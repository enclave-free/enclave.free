import { cleanup, render, screen, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AdminSetup } from './AdminSetup';
import { isAdminAuthenticated } from '../utils/adminApi';

vi.mock('../utils/adminApi', () => ({
  isAdminAuthenticated: vi.fn(),
}));

const mockIsAdminAuthenticated = vi.mocked(isAdminAuthenticated);

function renderAdminSetup() {
  render(
    <MemoryRouter initialEntries={['/admin/setup']}>
      <Routes>
        <Route path="/admin/setup" element={<AdminSetup />} />
      </Routes>
    </MemoryRouter>
  );
}

describe('AdminSetup', () => {
  beforeEach(() => {
    mockIsAdminAuthenticated.mockReturnValue(true);
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('renders a simplified navigation-first admin dashboard', () => {
    renderAdminSetup();

    const workflows = screen.getByRole('region', { name: 'Admin Workflows' });
    expect(
      within(workflows).getByRole('link', { name: /Admin Assistant/ })
    ).toHaveAttribute('href', '/chat');
    expect(
      within(workflows).getByRole('link', { name: /Guided Setup/ })
    ).toHaveAttribute('href', '/admin/onboarding');
    expect(
      within(workflows).getByRole('link', { name: /Admin Guides/ })
    ).toHaveAttribute('href', '/admin/guides');
    expect(
      within(workflows).getByRole('link', { name: /Test User Session/ })
    ).toHaveAttribute('href', '/admin/test-and-feedback');

    expect(
      screen.queryByRole('region', { name: 'Deployment Readiness' })
    ).not.toBeInTheDocument();
    expect(screen.queryByText('Back to Chat')).not.toBeInTheDocument();
    expect(
      screen.queryByText('White-glove deployment support required')
    ).not.toBeInTheDocument();
  });

  it('keeps settings, data, and operations destinations distinct', () => {
    renderAdminSetup();

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
    expect(
      within(content).queryByRole('link', { name: /Database Explorer/ })
    ).not.toBeInTheDocument();

    const operations = screen.getByRole('region', { name: 'Operations' });
    expect(
      within(operations).getByRole('link', { name: /Deployment Settings/ })
    ).toHaveAttribute('href', '/admin/deployment');
    expect(
      within(operations).getByRole('link', { name: /Database Explorer/ })
    ).toHaveAttribute('href', '/admin/database');
    expect(
      within(operations).getByRole('link', { name: /Diagnostics/ })
    ).toHaveAttribute('href', '/diagnostics/test-dashboard');
  });
});
