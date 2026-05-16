import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AdminOnboarding } from './AdminOnboarding'
import { fetchInstanceStatus } from '../utils/instanceStatus'

vi.mock('../utils/instanceStatus', () => ({
  fetchInstanceStatus: vi.fn(),
}))

vi.mock('../utils/nostrAuth', () => ({
  authenticateWithNostr: vi.fn(),
  hasNostrExtension: vi.fn(() => true),
}))

const mockFetchInstanceStatus = vi.mocked(fetchInstanceStatus)

describe('AdminOnboarding', () => {
  beforeEach(() => {
    mockFetchInstanceStatus.mockResolvedValue({
      initialized: false,
      setup_complete: false,
      ready_for_users: false,
      settings: {},
    })
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it('warns a first admin to use an Instance-specific Nostr key', async () => {
    render(
      <MemoryRouter initialEntries={['/admin']}>
        <Routes>
          <Route path="/admin" element={<AdminOnboarding />} />
        </Routes>
      </MemoryRouter>
    )

    expect(await screen.findByText('Use an Instance-specific Nostr key')).toBeInTheDocument()
    expect(screen.getByText(/Do not use your personal Nostr key/i)).toBeInTheDocument()
  })
})
