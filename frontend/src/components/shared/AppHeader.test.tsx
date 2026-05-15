import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { type ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AppHeader } from './AppHeader'
import { InstanceConfigProvider } from '../../context/InstanceConfigContext'
import { ThemeProvider } from '../../theme'
import { DEFAULT_INSTANCE_CONFIG, INSTANCE_CONFIG_KEY } from '../../types/instance'
import { isAdminAuthenticated } from '../../utils/adminApi'

vi.mock('../../utils/adminApi', () => ({
  isAdminAuthenticated: vi.fn(),
}))

const mockIsAdminAuthenticated = vi.mocked(isAdminAuthenticated)

function stubLocalStorage() {
  const store = new Map<string, string>()
  vi.stubGlobal('localStorage', {
    getItem: vi.fn((key: string) => store.get(key) ?? null),
    setItem: vi.fn((key: string, value: string) => {
      store.set(key, value)
    }),
    removeItem: vi.fn((key: string) => {
      store.delete(key)
    }),
    clear: vi.fn(() => {
      store.clear()
    }),
  })
}

function AppHeaderTestWrapper({ children }: { children: ReactNode }) {
  return (
    <MemoryRouter>
      <ThemeProvider>
        <InstanceConfigProvider>
          {children}
        </InstanceConfigProvider>
      </ThemeProvider>
    </MemoryRouter>
  )
}

function renderHeader(ui = <AppHeader />) {
  return render(ui, { wrapper: AppHeaderTestWrapper })
}

describe('AppHeader', () => {
  beforeEach(() => {
    mockIsAdminAuthenticated.mockReturnValue(false)
    stubLocalStorage()
    localStorage.setItem('enclave-theme', 'light')
    localStorage.setItem(
      INSTANCE_CONFIG_KEY,
      JSON.stringify({
        ...DEFAULT_INSTANCE_CONFIG,
        name: 'Enclave Research',
        icon: 'ShieldCheck',
        headerTagline: 'Private answers',
      })
    )
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        json: vi.fn().mockResolvedValue({}),
      })
    )
    vi.stubGlobal('matchMedia', vi.fn().mockReturnValue({
      matches: false,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }))
  })

  afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
    vi.clearAllMocks()
    document.documentElement.classList.remove('dark')
  })

  it('shows configured branding and keeps the theme control reachable by accessible name', async () => {
    const user = userEvent.setup()
    renderHeader()

    expect(await screen.findByText('Enclave Research')).toBeInTheDocument()
    expect(screen.getByText('Private answers')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Toggle theme' }))

    await waitFor(() => {
      expect(document.documentElement).toHaveClass('dark')
    })
    expect(localStorage.getItem('enclave-theme')).toBe('dark')
  })

  it('shows configured back navigation', async () => {
    renderHeader(<AppHeader showBackButton backTo="/chat" />)

    const backLink = await screen.findByRole('link', { name: 'Back' })
    expect(backLink).toHaveAttribute('href', '/chat')
  })

  it('only shows settings access for authenticated admins', async () => {
    const { rerender } = renderHeader()

    expect(await screen.findByText('Enclave Research')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Settings' })).not.toBeInTheDocument()

    mockIsAdminAuthenticated.mockReturnValue(true)
    rerender(<AppHeader />)

    expect(await screen.findByRole('button', { name: 'Settings' })).toBeInTheDocument()
  })
})
