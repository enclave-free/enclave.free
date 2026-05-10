import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { UserTypeSelection } from './UserTypeSelection'
import { STORAGE_KEYS } from '../types/onboarding'

describe('UserTypeSelection', () => {
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
    localStorage.setItem(STORAGE_KEYS.USER_EMAIL, 'member@example.com')

    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
      const url = String(input)
      if (url.endsWith('/user-types')) {
        return Promise.resolve(Response.json({
          types: [
            {
              id: 7,
              name: 'Member',
              description: 'Get community-specific guidance.',
              icon: 'Users',
              display_order: 0,
            },
            {
              id: 8,
              name: 'Builder',
              description: 'Work on projects with Sage.',
              icon: 'Hammer',
              display_order: 1,
            },
          ],
        }))
      }

      return Promise.resolve(Response.json({}))
    }))
  })

  afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
  })

  it('lets an authenticated user choose a user type before completing their profile', async () => {
    const user = userEvent.setup()

    render(
      <MemoryRouter initialEntries={['/choose-type']}>
        <Routes>
          <Route path="/choose-type" element={<UserTypeSelection />} />
          <Route path="/profile" element={<div>Profile completion</div>} />
        </Routes>
      </MemoryRouter>
    )

    await user.click(await screen.findByRole('radio', { name: 'Member' }))
    const continueButton = screen.getByRole('button', { name: 'Continue' })

    await user.click(continueButton)

    await waitFor(() => {
      expect(localStorage.getItem(STORAGE_KEYS.USER_TYPE_ID)).toBe('7')
    })
    expect(await screen.findByText('Profile completion')).toBeInTheDocument()
  })
})
