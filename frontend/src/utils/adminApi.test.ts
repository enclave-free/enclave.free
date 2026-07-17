import { afterEach, describe, expect, it, vi } from 'vitest';
import { STORAGE_KEYS } from '../types/onboarding';
import { isAdminAuthenticated } from './adminApi';
import {
  ADMIN_CONFIG_CHANGED_EVENT,
  notifyAdminConfigChanged,
  readAdminConfigAffectedAreas,
  subscribeAdminConfigChanges,
} from './adminConfigEvents';

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

describe('Admin Config direct-write refresh signals', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('reads only unique string affected areas from Sage completion metadata', () => {
    expect(
      readAdminConfigAffectedAreas({
        admin_config_affected_areas: [
          'instance_settings',
          'deployment_settings',
          'instance_settings',
          7,
        ],
      })
    ).toEqual(['instance_settings', 'deployment_settings']);
    expect(readAdminConfigAffectedAreas({ admin_change_set: {} })).toEqual([]);
  });

  it('dispatches one browser event with the affected areas and no write payload', () => {
    const dispatchEvent = vi.fn();
    vi.stubGlobal('window', { dispatchEvent });

    notifyAdminConfigChanged(['agent_settings', 'user_types']);

    expect(dispatchEvent).toHaveBeenCalledTimes(1);
    const event = dispatchEvent.mock.calls[0][0] as CustomEvent;
    expect(event.type).toBe(ADMIN_CONFIG_CHANGED_EVENT);
    expect(event.detail).toEqual({
      areas: ['agent_settings', 'user_types'],
    });
  });

  it('refreshes only matching settings views and can unsubscribe', () => {
    const refresh = vi.fn();
    const unsubscribe = subscribeAdminConfigChanges(
      ['agent_settings'],
      refresh
    );

    notifyAdminConfigChanged(['deployment_settings']);
    expect(refresh).not.toHaveBeenCalled();

    notifyAdminConfigChanged(['agent_settings']);
    expect(refresh).toHaveBeenCalledOnce();

    unsubscribe();
    notifyAdminConfigChanged(['agent_settings']);
    expect(refresh).toHaveBeenCalledOnce();
  });
});
