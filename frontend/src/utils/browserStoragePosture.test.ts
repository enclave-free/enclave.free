import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  BROWSER_STORAGE_ALLOWLIST,
  browserStoragePosture,
  clearLogoutBrowserStorage,
} from './browserStoragePosture'
import { STORAGE_KEYS } from '../types/onboarding'

describe('browserStoragePosture', () => {
  beforeEach(() => {
    const local = new Map<string, string>()
    const session = new Map<string, string>()
    vi.stubGlobal('localStorage', {
      getItem: vi.fn((key: string) => local.get(key) ?? null),
      setItem: vi.fn((key: string, value: string) => local.set(key, value)),
      removeItem: vi.fn((key: string) => local.delete(key)),
    })
    vi.stubGlobal('sessionStorage', {
      getItem: vi.fn((key: string) => session.get(key) ?? null),
      setItem: vi.fn((key: string, value: string) => session.set(key, value)),
      removeItem: vi.fn((key: string) => session.delete(key)),
    })
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('documents browser storage as a deployment surface without allowing conversation content keys', () => {
    const posture = browserStoragePosture()

    expect(posture.unsupportedDeploymentSurface.category).toBe('client_storage')
    expect(BROWSER_STORAGE_ALLOWLIST.map((item) => item.key)).not.toContain('enclave_conversation_content')
    expect(posture.disallowedSensitivePatterns).toContain('conversation')
  })

  it('clears logout-scoped local and session storage while preserving preferences', () => {
    localStorage.setItem(STORAGE_KEYS.USER_EMAIL, 'reader@example.com')
    localStorage.setItem(STORAGE_KEYS.USER_PROFILE, '{"fields":{"company":"Enclave"}}')
    localStorage.setItem(STORAGE_KEYS.ADMIN_PUBKEY, 'admin-pubkey')
    localStorage.setItem('enclave-theme', 'dark')
    sessionStorage.setItem(STORAGE_KEYS.USER_EMAIL, 'reader@example.com')

    clearLogoutBrowserStorage()

    expect(localStorage.getItem(STORAGE_KEYS.USER_EMAIL)).toBeNull()
    expect(localStorage.getItem(STORAGE_KEYS.USER_PROFILE)).toBeNull()
    expect(localStorage.getItem(STORAGE_KEYS.ADMIN_PUBKEY)).toBeNull()
    expect(sessionStorage.getItem(STORAGE_KEYS.USER_EMAIL)).toBeNull()
    expect(localStorage.getItem('enclave-theme')).toBe('dark')
  })
})
