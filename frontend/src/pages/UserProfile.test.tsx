import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { STORAGE_KEYS } from '../types/onboarding'
import { UserProfile } from './UserProfile'

describe('UserProfile', () => {
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
    localStorage.setItem(STORAGE_KEYS.USER_EMAIL, 'ada@example.com')
    localStorage.setItem(STORAGE_KEYS.USER_NAME, 'Ada')
    localStorage.setItem(STORAGE_KEYS.USER_TYPE_ID, '7')
  })

  afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
  })

  it('submits selected type profile fields and continues to chat', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url.includes('/user-fields')) {
        return Promise.resolve(
          Response.json({
            fields: [
              {
                id: 11,
                field_name: 'Company',
                field_type: 'text',
                required: true,
                placeholder: 'Acme',
                options: null,
                user_type_id: 7,
              },
            ],
          })
        )
      }

      if (url.endsWith('/users') && init?.method === 'POST') {
        return Promise.resolve(Response.json({ ok: true }))
      }

      return Promise.resolve(Response.json({}))
    })
    vi.stubGlobal('fetch', fetchMock)

    render(
      <MemoryRouter initialEntries={['/profile']}>
        <Routes>
          <Route path="/profile" element={<UserProfile />} />
          <Route path="/chat" element={<div>Chat ready</div>} />
        </Routes>
      </MemoryRouter>
    )

    await user.type(await screen.findByLabelText('Company'), 'Enclave')
    const continueButton = screen.getByRole('button', { name: 'Continue to Chat' })
    expect(continueButton).toHaveClass('btn-primary')
    await user.click(continueButton)

    await waitFor(() => {
      const userRequest = fetchMock.mock.calls.find(([input]) => String(input).endsWith('/users'))
      expect(userRequest).toBeDefined()
      expect(userRequest?.[1]?.body).toBeDefined()
      expect(typeof userRequest?.[1]?.body).toBe('string')
      expect(JSON.parse(userRequest?.[1]?.body as string)).toMatchObject({
        email: 'ada@example.com',
        name: 'Ada',
        user_type_id: 7,
        fields: {
          Company: 'Enclave',
        },
      })
    })

    expect(localStorage.getItem(STORAGE_KEYS.USER_PROFILE)).toContain('"Company":"Enclave"')
    expect(await screen.findByText('Chat ready')).toBeInTheDocument()
  })
})
