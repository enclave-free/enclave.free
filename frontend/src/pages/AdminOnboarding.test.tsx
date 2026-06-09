import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AdminOnboarding } from './AdminOnboarding';
import { fetchInstanceStatus } from '../utils/instanceStatus';
import { authenticateWithNostr } from '../utils/nostrAuth';

vi.mock('../utils/instanceStatus', () => ({
  fetchInstanceStatus: vi.fn(),
}));

vi.mock('../utils/nostrAuth', () => ({
  authenticateWithNostr: vi.fn(),
  hasNostrExtension: vi.fn(() => true),
}));

const mockFetchInstanceStatus = vi.mocked(fetchInstanceStatus);
const mockAuthenticateWithNostr = vi.mocked(authenticateWithNostr);

describe('AdminOnboarding', () => {
  beforeEach(() => {
    mockFetchInstanceStatus.mockResolvedValue({
      initialized: false,
      setup_complete: false,
      ready_for_users: false,
      settings: {},
    });
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  it('warns a first admin to use an Instance-specific Nostr key', async () => {
    render(
      <MemoryRouter initialEntries={['/admin']}>
        <Routes>
          <Route path="/admin" element={<AdminOnboarding />} />
        </Routes>
      </MemoryRouter>
    );

    expect(
      await screen.findByText('Use an Instance-specific Nostr key')
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Do not use your personal Nostr key/i)
    ).toBeInTheDocument();
  });

  it('clears the delayed redirect when unmounted after successful auth', async () => {
    const clearTimeoutSpy = vi.spyOn(globalThis, 'clearTimeout');
    mockFetchInstanceStatus.mockResolvedValue({
      initialized: true,
      setup_complete: true,
      ready_for_users: true,
      settings: {},
    });
    mockAuthenticateWithNostr.mockResolvedValue({
      admin: {
        id: 1,
        pubkey: 'admin-pubkey',
        created_at: null,
      },
      is_new: true,
      instance_initialized: true,
      session_token: 'session-token',
    });

    const { unmount } = render(
      <MemoryRouter initialEntries={['/admin']}>
        <Routes>
          <Route path="/admin" element={<AdminOnboarding />} />
          <Route
            path="/admin/onboarding"
            element={<div>guided setup route</div>}
          />
        </Routes>
      </MemoryRouter>
    );

    fireEvent.click(
      await screen.findByRole('button', { name: 'Connect with Nostr' })
    );

    await waitFor(() => {
      expect(mockAuthenticateWithNostr).toHaveBeenCalled();
    });

    unmount();

    expect(clearTimeoutSpy).toHaveBeenCalled();
    clearTimeoutSpy.mockRestore();
  });
});
