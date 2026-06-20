import { StrictMode } from 'react';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { STORAGE_KEYS } from '../types/onboarding';
import { VerifyMagicLink } from './VerifyMagicLink';

describe('VerifyMagicLink', () => {
  beforeEach(() => {
    const storage = new Map<string, string>();
    vi.stubGlobal('localStorage', {
      getItem: vi.fn((key: string) => storage.get(key) ?? null),
      removeItem: vi.fn((key: string) => {
        storage.delete(key);
      }),
      setItem: vi.fn((key: string, value: string) => {
        storage.set(key, value);
      }),
    });
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it('verifies a token only once when React StrictMode remounts the page', async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith('/auth/verify') && init?.method === 'POST') {
        return Promise.resolve(
          Response.json({
            success: true,
            user: {
              id: 13,
              email: 'pending-smoke@example.test',
              name: 'Pending Smoke User',
              user_type_id: null,
              approved: false,
              created_at: '2026-06-10 14:53:00',
              needs_onboarding: false,
              needs_user_type: false,
            },
            session_token: 'session-token',
          })
        );
      }

      return Promise.resolve(Response.json({}));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(
      <StrictMode>
        <MemoryRouter initialEntries={['/verify?token=magic-token']}>
          <Routes>
            <Route path="/verify" element={<VerifyMagicLink />} />
            <Route path="/pending" element={<div>Pending approval</div>} />
          </Routes>
        </MemoryRouter>
      </StrictMode>
    );

    expect(
      await screen.findByText('pending-smoke@example.test')
    ).toBeInTheDocument();

    await waitFor(() => {
      const verifyRequests = fetchMock.mock.calls.filter(([input, init]) => {
        return (
          String(input).endsWith('/auth/verify') && init?.method === 'POST'
        );
      });
      expect(verifyRequests).toHaveLength(1);
    });

    expect(localStorage.getItem(STORAGE_KEYS.USER_APPROVED)).toBe('false');
  });

  it('clears stale selected user type when verified user has no type', async () => {
    localStorage.setItem(STORAGE_KEYS.USER_TYPE_ID, '4');

    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith('/auth/verify') && init?.method === 'POST') {
        return Promise.resolve(
          Response.json({
            success: true,
            user: {
              id: 15,
              email: 'new-user@example.test',
              name: 'New User',
              user_type_id: null,
              approved: true,
              created_at: '2026-06-10 15:01:00',
              needs_onboarding: true,
              needs_user_type: false,
            },
            session_token: 'session-token',
          })
        );
      }

      if (url.endsWith('/user-types')) {
        return Promise.resolve(Response.json({ types: [] }));
      }

      return Promise.resolve(Response.json({}));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(
      <MemoryRouter initialEntries={['/verify?token=magic-token']}>
        <Routes>
          <Route path="/verify" element={<VerifyMagicLink />} />
          <Route path="/profile" element={<div>Profile completion</div>} />
        </Routes>
      </MemoryRouter>
    );

    expect(
      await screen.findByText('new-user@example.test')
    ).toBeInTheDocument();

    await waitFor(() => {
      expect(localStorage.getItem(STORAGE_KEYS.USER_TYPE_ID)).toBeNull();
    });
  });

  it('clears stale user name when verified user has no name', async () => {
    localStorage.setItem(STORAGE_KEYS.USER_NAME, 'Previous User');

    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith('/auth/verify') && init?.method === 'POST') {
        return Promise.resolve(
          Response.json({
            success: true,
            user: {
              id: 16,
              email: 'nameless@example.test',
              name: null,
              user_type_id: null,
              approved: true,
              created_at: '2026-06-10 15:03:00',
              needs_onboarding: false,
              needs_user_type: false,
            },
            session_token: 'session-token',
          })
        );
      }

      return Promise.resolve(Response.json({}));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(
      <MemoryRouter initialEntries={['/verify?token=magic-token']}>
        <Routes>
          <Route path="/verify" element={<VerifyMagicLink />} />
          <Route path="/chat" element={<div>Chat</div>} />
        </Routes>
      </MemoryRouter>
    );

    expect(
      await screen.findByText('nameless@example.test')
    ).toBeInTheDocument();

    await waitFor(() => {
      expect(localStorage.getItem(STORAGE_KEYS.USER_NAME)).toBeNull();
    });
  });

  it('clears stale admin markers when a user magic link is verified', async () => {
    localStorage.setItem(STORAGE_KEYS.ADMIN_PUBKEY, 'stale-admin-pubkey');
    localStorage.setItem(STORAGE_KEYS.ADMIN_SESSION_TOKEN, 'legacy-token');

    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith('/auth/verify') && init?.method === 'POST') {
        return Promise.resolve(
          Response.json({
            success: true,
            user: {
              id: 17,
              email: 'reader@example.test',
              name: 'Reader',
              user_type_id: null,
              approved: true,
              created_at: '2026-06-10 15:05:00',
              needs_onboarding: false,
              needs_user_type: false,
            },
            session_token: 'session-token',
          })
        );
      }

      return Promise.resolve(Response.json({}));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(
      <MemoryRouter initialEntries={['/verify?token=magic-token']}>
        <Routes>
          <Route path="/verify" element={<VerifyMagicLink />} />
          <Route path="/chat" element={<div>Chat</div>} />
        </Routes>
      </MemoryRouter>
    );

    expect(await screen.findByText('reader@example.test')).toBeInTheDocument();

    await waitFor(() => {
      expect(localStorage.getItem(STORAGE_KEYS.ADMIN_PUBKEY)).toBeNull();
      expect(localStorage.getItem(STORAGE_KEYS.ADMIN_SESSION_TOKEN)).toBeNull();
    });
  });
});
