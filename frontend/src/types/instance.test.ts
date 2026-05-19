import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { DEFAULT_INSTANCE_CONFIG, getInstanceConfig, INSTANCE_CONFIG_KEY } from './instance'

describe('getInstanceConfig', () => {
  let store: Record<string, string>

  beforeEach(() => {
    store = {}
    vi.stubGlobal('localStorage', {
      getItem: vi.fn((key: string) => store[key] ?? null),
      setItem: vi.fn((key: string, value: string) => {
        store[key] = value
      }),
      removeItem: vi.fn((key: string) => {
        delete store[key]
      }),
      clear: vi.fn(() => {
        store = {}
      }),
    })
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('falls back when the stored default language is blank', () => {
    localStorage.setItem(INSTANCE_CONFIG_KEY, JSON.stringify({
      ...DEFAULT_INSTANCE_CONFIG,
      defaultLanguage: '   ',
    }))

    expect(getInstanceConfig().defaultLanguage).toBe(DEFAULT_INSTANCE_CONFIG.defaultLanguage)
  })
})
