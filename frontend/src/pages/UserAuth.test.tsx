import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import i18n from '../i18n'
import { STORAGE_KEY_LANGUAGE } from '../utils/languages'
import { UserAuth } from './UserAuth'

vi.mock('../context/InstanceConfigContext', () => ({
  useInstanceConfig: () => ({
    config: {
      name: 'Enclave',
    },
  }),
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

  it('lets users change language from the auth screen', async () => {
    const user = userEvent.setup()
    const previousLanguage = i18n.language
    const changeLanguage = vi.spyOn(i18n, 'changeLanguage')

    try {
      render(
        <MemoryRouter initialEntries={['/auth']}>
          <Routes>
            <Route path="/auth" element={<UserAuth />} />
          </Routes>
        </MemoryRouter>
      )

      await user.click(screen.getByRole('button', { name: 'Change language' }))
      await user.click(screen.getByRole('menuitemradio', { name: /Español/ }))

      expect(localStorage.setItem).toHaveBeenCalledWith(
        STORAGE_KEY_LANGUAGE,
        'es'
      )
      expect(changeLanguage).toHaveBeenCalledWith('es')
    } finally {
      changeLanguage.mockRestore()
      await i18n.changeLanguage(previousLanguage)
    }
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
      const continueButton = screen.getByRole('button', { name: 'Continue with Email' })
      expect(continueButton).toBeEnabled()
      expect(continueButton).toHaveTextContent('Continue with Email')
    })
  })
})
