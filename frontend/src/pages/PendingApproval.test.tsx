import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { STORAGE_KEYS } from '../types/onboarding';
import { PendingApproval } from './PendingApproval';

describe('PendingApproval', () => {
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
    localStorage.setItem(STORAGE_KEYS.USER_EMAIL, 'approved@example.test');
    localStorage.setItem(STORAGE_KEYS.USER_APPROVED, 'false');
    localStorage.setItem(STORAGE_KEYS.USER_TYPE_ID, '9');
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it('continues to chat when server approval has changed', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith('/auth/me')) {
          return Promise.resolve(
            Response.json({
              authenticated: true,
              user: {
                id: 25,
                email: 'approved@example.test',
                approved: true,
                needs_onboarding: false,
                needs_user_type: false,
              },
            })
          );
        }

        return Promise.resolve(Response.json({}));
      })
    );

    render(
      <MemoryRouter initialEntries={['/pending']}>
        <Routes>
          <Route path="/pending" element={<PendingApproval />} />
          <Route path="/chat" element={<div>Chat ready</div>} />
        </Routes>
      </MemoryRouter>
    );

    expect(await screen.findByText('Chat ready')).toBeInTheDocument();

    await waitFor(() => {
      expect(localStorage.getItem(STORAGE_KEYS.USER_APPROVED)).toBe('true');
      expect(localStorage.getItem(STORAGE_KEYS.USER_TYPE_ID)).toBeNull();
    });
  });
});
