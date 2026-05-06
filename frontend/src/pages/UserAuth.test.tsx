import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { UserAuth } from './UserAuth'

vi.mock('../context/InstanceConfigContext', () => ({
  useInstanceConfig: () => ({
    config: {
      name: 'Sanctum',
    },
  }),
}))

vi.mock('../utils/publicConfig', () => ({
  fetchPublicConfig: vi.fn(() => Promise.resolve({ simulateUserAuth: false })),
}))

describe('UserAuth', () => {
  beforeEach(() => {
    const storage = new Map<string, string>()
    vi.stubGlobal('localStorage', {
      getItem: vi.fn((key: string) => storage.get(key) ?? null),
      removeItem: vi.fn((key: string) => {
        storage.delete(key)
      }),
      setItem: vi.fn((key: string, value: string) => {
        storage.set(key, value)
      }),
    })
  })

  afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
  })

  it('contains and names magic link request failures', async () => {
    const user = userEvent.setup()
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve(
          Response.json({ detail: 'Email service unavailable' }, { status: 503 })
        )
      )
    )

    render(
      <MemoryRouter initialEntries={['/auth']}>
        <Routes>
          <Route path="/auth" element={<UserAuth />} />
        </Routes>
      </MemoryRouter>
    )

    await user.type(screen.getByLabelText('Name'), 'Ada')
    await user.type(screen.getByLabelText('Email'), 'ada@example.com')
    await user.click(screen.getByRole('button', { name: 'Continue with Email' }))

    const failure = await screen.findByRole('note', { name: 'Magic link request error' })
    expect(failure).toHaveTextContent('Email service unavailable')
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Continue with Email' })).toHaveClass('btn-primary')
    })
  })
})
