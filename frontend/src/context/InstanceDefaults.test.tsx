import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import i18n from '../i18n'
import { InstanceConfigProvider, useInstanceConfig } from './InstanceConfigContext'
import { ThemeProvider } from '../theme'

function CurrentInstanceDefaults() {
  const { config } = useInstanceConfig()
  return (
    <div>
      <span>{config.defaultLanguage}</span>
      <span>{config.defaultTheme}</span>
    </div>
  )
}

describe('Instance defaults', () => {
  beforeEach(() => {
    vi.stubGlobal('localStorage', {
      getItem: vi.fn(() => null),
      setItem: vi.fn(),
      removeItem: vi.fn(),
    })
    vi.stubGlobal('matchMedia', vi.fn(() => ({
      matches: false,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })))
    document.documentElement.classList.remove('dark')
  })

  afterEach(async () => {
    cleanup()
    vi.unstubAllGlobals()
    vi.clearAllMocks()
    document.documentElement.classList.remove('dark')
    await i18n.changeLanguage('en')
  })

  it('applies public Instance language defaults after safe fallback initialization', async () => {
    const changeLanguage = vi.spyOn(i18n, 'changeLanguage')
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(Response.json({
      settings: {
        default_language: 'es',
        default_theme: 'dark',
      },
    }))))

    render(
      <InstanceConfigProvider>
        <CurrentInstanceDefaults />
      </InstanceConfigProvider>
    )

    expect(screen.getByText('en')).toBeInTheDocument()
    await waitFor(() => expect(screen.getByText('es')).toBeInTheDocument())
    expect(screen.getByText('dark')).toBeInTheDocument()
    expect(changeLanguage).toHaveBeenCalledWith('es')
  })

  it('applies public Instance theme defaults when they load', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(Response.json({
      settings: {
        default_theme: 'dark',
      },
    }))))

    render(
      <ThemeProvider>
        <div>theme mounted</div>
      </ThemeProvider>
    )

    expect(document.documentElement.classList.contains('dark')).toBe(false)
    await waitFor(() => expect(document.documentElement.classList.contains('dark')).toBe(true))
  })

  it('keeps a saved user theme preference over the public Instance default', async () => {
    vi.stubGlobal('localStorage', {
      getItem: vi.fn(() => 'light'),
      setItem: vi.fn(),
      removeItem: vi.fn(),
    })
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(Response.json({
      settings: {
        default_theme: 'dark',
      },
    }))))

    render(
      <ThemeProvider>
        <div>theme mounted</div>
      </ThemeProvider>
    )

    await waitFor(() => expect(document.documentElement.classList.contains('dark')).toBe(false))
    expect(fetch).not.toHaveBeenCalled()
    expect(document.documentElement.classList.contains('dark')).toBe(false)
  })
})
