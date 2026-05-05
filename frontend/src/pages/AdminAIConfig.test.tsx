import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AdminAIConfig } from './AdminAIConfig'
import { adminFetch } from '../utils/adminApi'

vi.mock('../utils/adminApi', () => ({
  adminFetch: vi.fn(),
  isAdminAuthenticated: vi.fn(() => true),
}))

const mockAdminFetch = vi.mocked(adminFetch)

const aiConfigResponse = {
  prompt_sections: [],
  parameters: [
    {
      key: 'max_tokens',
      value: '2048',
      value_type: 'number',
      category: 'parameter',
      description: 'Maximum response tokens',
    },
  ],
  defaults: [],
}

describe('AdminAIConfig', () => {
  beforeEach(() => {
    mockAdminFetch.mockImplementation((endpoint: string, options?: RequestInit) => {
      if (endpoint === '/admin/user-types') {
        return Promise.resolve(Response.json({ types: [] }))
      }
      if (endpoint === '/ingest/admin/documents/defaults') {
        return Promise.resolve(Response.json({ documents: [] }))
      }
      if (endpoint === '/admin/ai-config/max_tokens' && options?.method === 'PUT') {
        return Promise.resolve(Response.json({
          key: 'max_tokens',
          value: '4096',
          value_type: 'number',
          category: 'parameter',
        }))
      }
      if (endpoint === '/admin/ai-config') {
        return Promise.resolve(Response.json(aiConfigResponse))
      }
      return Promise.resolve(Response.json({}))
    })
  })

  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it('lets an admin configure the Max Tokens Agent Setting', async () => {
    const user = userEvent.setup()

    render(
      <MemoryRouter initialEntries={['/admin/ai']}>
        <Routes>
          <Route path="/admin/ai" element={<AdminAIConfig />} />
        </Routes>
      </MemoryRouter>
    )

    await screen.findByText('Max Tokens')

    await user.click(screen.getByRole('button', { name: 'Edit' }))
    fireEvent.change(screen.getByRole('slider'), { target: { value: '4096' } })
    await user.click(screen.getByRole('button', { name: 'Save' }))

    await waitFor(() => {
      expect(mockAdminFetch).toHaveBeenCalledWith('/admin/ai-config/max_tokens', expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify({ value: '4096' }),
      }))
    })
  })
})
