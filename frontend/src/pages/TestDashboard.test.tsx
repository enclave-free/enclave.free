import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { TestDashboard } from './TestDashboard'
import { ThemeProvider } from '../theme'

function renderDashboard() {
  return render(
    <MemoryRouter>
      <ThemeProvider>
        <TestDashboard />
      </ThemeProvider>
    </MemoryRouter>
  )
}

describe('TestDashboard', () => {
  beforeEach(() => {
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
    localStorage.setItem('sanctum-theme', 'light')
    localStorage.setItem('sanctum_admin_pubkey', 'admin-pubkey')
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

  it('checks health and renders the returned admin status output', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn().mockResolvedValue(
      Response.json({
        neo4j: 'ok',
        qdrant: 'ok',
      })
    )
    vi.stubGlobal('fetch', fetchMock)

    renderDashboard()

    await user.click(screen.getByRole('button', { name: 'Check Health' }))

    expect(fetchMock).toHaveBeenCalledWith('/api/health')
    await waitFor(() => {
      expect(screen.getByText(/"neo4j": "ok"/)).toBeInTheDocument()
    })
    expect(screen.getByText(/"qdrant": "ok"/)).toBeInTheDocument()
  })

  it('toggles migrated admin dashboard sections through their accessible header', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('fetch', vi.fn())

    renderDashboard()

    const sectionHeader = screen.getByRole('button', { name: /10\..*Authentication Testing/ })
    expect(sectionHeader).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByText('Magic Link Authentication')).not.toBeInTheDocument()

    await user.click(sectionHeader)

    expect(sectionHeader).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByText('Magic Link Authentication')).toBeInTheDocument()

    await user.click(sectionHeader)

    expect(sectionHeader).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByText('Magic Link Authentication')).not.toBeInTheDocument()
  })

  it('keeps the dashboard theme toggle reachable by accessible name', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('fetch', vi.fn())

    renderDashboard()

    expect(document.documentElement.classList.contains('dark')).toBe(false)

    await user.click(screen.getByRole('button', { name: 'Toggle theme' }))

    expect(document.documentElement.classList.contains('dark')).toBe(true)
  })
})
