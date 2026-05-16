import { cleanup, render, screen, waitFor, within } from '@testing-library/react'
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
    localStorage.setItem('enclave-theme', 'light')
    localStorage.setItem('enclave_admin_pubkey', 'admin-pubkey')
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

    const endpointNotes = screen.getAllByRole('note', { name: 'Endpoint guidance' })
    expect(endpointNotes[0]).toHaveTextContent('GET /health')

    await user.click(screen.getByRole('button', { name: 'Check Health' }))

    expect(fetchMock).toHaveBeenCalledWith('/api/health')
    await waitFor(() => {
      expect(screen.getByRole('region', { name: 'Health response output' })).toHaveTextContent('"neo4j": "ok"')
    })
    expect(screen.getByText(/"qdrant": "ok"/)).toBeInTheDocument()
  })

  it('toggles migrated admin dashboard sections through their accessible header', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('fetch', vi.fn())

    renderDashboard()

    const sectionHeader = screen.getByRole('button', { name: /10\..*Authentication Testing/ })
    const sectionContent = document.getElementById(sectionHeader.getAttribute('aria-controls') ?? '')
    expect(sectionHeader).toHaveAttribute('aria-expanded', 'false')
    expect(sectionContent).toHaveAttribute('aria-hidden', 'true')

    await user.click(sectionHeader)

    expect(sectionHeader).toHaveAttribute('aria-expanded', 'true')
    expect(sectionContent).toHaveAttribute('aria-hidden', 'false')
    expect(within(sectionContent as HTMLElement).getByText('Magic Link Authentication')).toBeInTheDocument()

    await user.click(sectionHeader)

    expect(sectionHeader).toHaveAttribute('aria-expanded', 'false')
    expect(sectionContent).toHaveAttribute('aria-hidden', 'true')
  })

  it('keeps the dashboard theme toggle reachable by accessible name', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('fetch', vi.fn())

    renderDashboard()

    expect(document.documentElement.classList.contains('dark')).toBe(false)

    await user.click(screen.getByRole('button', { name: 'Toggle theme' }))

    expect(document.documentElement.classList.contains('dark')).toBe(true)
    expect(screen.getByRole('combobox', { name: 'Theme preference' })).toHaveValue('dark')
  })

  it('keeps migrated dashboard selects labelled and wired to their controls', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(null, { status: 200 }))
      .mockResolvedValueOnce(new Response(null, { status: 429 }))
      .mockResolvedValue(new Response(null, { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    renderDashboard()

    await user.click(screen.getByRole('button', { name: /16\..*Rate Limiting Test/ }))

    const testType = screen.getByRole('combobox', { name: 'Rate limit test type' })
    expect(testType).toHaveValue('magic_link')
    expect(screen.getByRole('button', { name: 'Send 6 Rapid Requests' })).toBeInTheDocument()

    await user.selectOptions(testType, 'admin_auth')

    expect(testType).toHaveValue('admin_auth')
    expect(screen.getByRole('button', { name: 'Send 11 Rapid Requests' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Send 11 Rapid Requests' }))

    await waitFor(() => {
      expect(screen.getByRole('group', { name: 'Successful requests' })).toHaveTextContent('10')
    })
    expect(screen.getByRole('group', { name: 'Blocked requests' })).toHaveTextContent('1')
    expect(fetchMock).toHaveBeenCalledTimes(11)
  })
})
