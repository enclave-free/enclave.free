import { renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { STORAGE_KEYS } from '../types/onboarding';
import { isAdminAuthenticated } from '../utils/adminApi';
import { useAuthFlow } from './useAuthFlow';

vi.mock('../utils/adminApi', () => ({
  isAdminAuthenticated: vi.fn(() => false),
}));

describe('useAuthFlow', () => {
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
    vi.mocked(isAdminAuthenticated).mockReturnValue(false);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  it('routes pending-approval users through chat so onboarding can run before pending approval', () => {
    localStorage.setItem(STORAGE_KEYS.USER_EMAIL, 'pending@example.test');
    localStorage.setItem(STORAGE_KEYS.USER_APPROVED, 'false');

    const { result } = renderHook(() => useAuthFlow());

    expect(result.current.redirectPath).toBe('/chat');
    expect(result.current.isApproved).toBe(false);
  });
});
