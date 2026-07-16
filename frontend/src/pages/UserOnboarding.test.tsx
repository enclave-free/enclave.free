import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  STORAGE_KEY_LANGUAGE,
  STORAGE_KEY_LANGUAGE_EXPLICIT,
} from '../utils/languages';
import { UserOnboarding } from './UserOnboarding';

describe('UserOnboarding', () => {
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

  it('sends returning users with a saved language preference to email auth', async () => {
    localStorage.setItem(STORAGE_KEY_LANGUAGE, 'en');

    render(
      <MemoryRouter initialEntries={['/login']}>
        <Routes>
          <Route path="/login" element={<UserOnboarding />} />
          <Route path="/auth" element={<div>Email auth ready</div>} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Email auth ready')).toBeInTheDocument();
    });
    expect(localStorage.setItem).toHaveBeenCalledWith(
      STORAGE_KEY_LANGUAGE_EXPLICIT,
      '1'
    );
  });

  it('keeps first-time users on language selection', () => {
    render(
      <MemoryRouter initialEntries={['/login']}>
        <Routes>
          <Route path="/login" element={<UserOnboarding />} />
          <Route path="/auth" element={<div>Email auth ready</div>} />
        </Routes>
      </MemoryRouter>
    );

    expect(
      screen.getByRole('heading', { name: 'Choose your language' })
    ).toBeInTheDocument();
  });

  it('persists onboarding language selections as explicit choices', async () => {
    const user = (await import('@testing-library/user-event')).default.setup();

    render(
      <MemoryRouter initialEntries={['/login']}>
        <Routes>
          <Route path="/login" element={<UserOnboarding />} />
          <Route path="/auth" element={<div>Email auth ready</div>} />
        </Routes>
      </MemoryRouter>
    );

    await user.click(screen.getByRole('radio', { name: 'Español (Spanish)' }));
    await user.click(screen.getByRole('button', { name: 'Continuar' }));

    expect(localStorage.setItem).toHaveBeenCalledWith(
      STORAGE_KEY_LANGUAGE,
      'es'
    );
    expect(localStorage.setItem).toHaveBeenCalledWith(
      STORAGE_KEY_LANGUAGE_EXPLICIT,
      '1'
    );
    expect(screen.getByText('Email auth ready')).toBeInTheDocument();
  });
});
