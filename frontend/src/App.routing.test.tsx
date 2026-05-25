import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import App from './App';

vi.mock('./pages/HomeRedirect', () => ({
  HomeRedirect: () => <main>Product home redirect</main>,
}));

vi.mock('./pages/TestDashboard', () => ({
  TestDashboard: () => <main>Diagnostics Test Dashboard</main>,
}));

vi.mock('./pages/ChatPage', () => ({
  ChatPage: () => <main>Chat route</main>,
}));

describe('App routing', () => {
  afterEach(() => {
    cleanup();
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
});
