import type { ReactNode } from 'react';
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import App from './App';

const chatPageMockState = vi.hoisted(() => ({ shouldThrow: false }));

vi.mock('./pages/HomeRedirect', () => ({
  HomeRedirect: () => <main>Product home redirect</main>,
}));

vi.mock('./pages/TestDashboard', () => ({
  TestDashboard: () => <main>Diagnostics Test Dashboard</main>,
}));

vi.mock('./pages/ChatPage', () => ({
  ChatPage: () => {
    if (chatPageMockState.shouldThrow) {
      throw new Error('Chat route failed to load');
    }
    return <main>Chat route</main>;
  },
}));

vi.mock('./components/shared/AdminRoute', () => ({
  AdminRoute: ({ children }: { children: ReactNode }) => (
    <section data-testid="admin-route-shell">{children}</section>
  ),
}));

vi.mock('./pages/AdminGuides', () => ({
  AdminGuides: () => <main>Admin guides route</main>,
}));

describe('App routing', () => {
  afterEach(() => {
    cleanup();
    chatPageMockState.shouldThrow = false;
    vi.restoreAllMocks();
    window.history.pushState({}, '', '/');
  });

  it('keeps root on the product path instead of the Test Dashboard', () => {
    window.history.pushState({}, '', '/');

    render(<App />);

    expect(screen.getByText('Product home redirect')).toBeInTheDocument();
    expect(
      screen.queryByText('Diagnostics Test Dashboard')
    ).not.toBeInTheDocument();
  });

  it('keeps the Test Dashboard reachable through explicit diagnostics routing', async () => {
    window.history.pushState({}, '', '/diagnostics/test-dashboard');

    render(<App />);

    expect(
      await screen.findByText('Diagnostics Test Dashboard')
    ).toBeInTheDocument();
  });

  it('shows a route loading status while the chat page chunk loads', async () => {
    window.history.pushState({}, '', '/chat');

    render(<App />);

    expect(
      screen.getByRole('status', { name: 'Loading page' })
    ).toBeInTheDocument();
    expect(await screen.findByText('Chat route')).toBeInTheDocument();
  });

  it('shows a graceful fallback when a lazy route fails', async () => {
    chatPageMockState.shouldThrow = true;
    vi.spyOn(console, 'error').mockImplementation(() => undefined);
    window.history.pushState({}, '', '/chat');

    render(<App />);

    expect(
      await screen.findByText('Failed to load page. Please refresh.')
    ).toBeInTheDocument();
  });

  it('keeps the admin guides route behind the admin route shell', async () => {
    window.history.pushState({}, '', '/admin/guides');

    render(<App />);

    expect(await screen.findByText('Admin guides route')).toBeInTheDocument();
    expect(screen.getByTestId('admin-route-shell')).toBeInTheDocument();
  });
});
