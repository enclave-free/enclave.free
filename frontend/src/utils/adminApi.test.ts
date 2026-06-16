import { afterEach, describe, expect, it, vi } from 'vitest';
import { STORAGE_KEYS } from '../types/onboarding';
import { isAdminAuthenticated } from './adminApi';

describe('isAdminAuthenticated', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('returns false when browser storage is unavailable', () => {
    vi.stubGlobal('localStorage', {
      getItem: vi.fn(() => {
        throw new Error('storage unavailable');
      }),
    });

    expect(isAdminAuthenticated()).toBe(false);
  });

  it('returns true when an admin marker exists', () => {
    vi.stubGlobal('localStorage', {
      getItem: vi.fn((key: string) =>
        key === STORAGE_KEYS.ADMIN_PUBKEY ? 'admin-pubkey' : null
      ),
    });

    expect(isAdminAuthenticated()).toBe(true);
  });

  it('returns false when no admin marker exists', () => {
    vi.stubGlobal('localStorage', {
      getItem: vi.fn(() => null),
    });

    expect(isAdminAuthenticated()).toBe(false);
  });
});
