import { cleanup, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AdminDatabaseExplorer } from './AdminDatabaseExplorer'
import { adminFetch } from '../utils/adminApi'

vi.mock('../utils/adminApi', () => ({
  adminFetch: vi.fn(),
  isAdminAuthenticated: vi.fn(() => true),
}))

vi.mock('../utils/encryption', () => ({
  decryptField: vi.fn(),
  hasNip04Support: vi.fn(() => false),
}))

const mockAdminFetch = vi.mocked(adminFetch)

describe('AdminDatabaseExplorer', () => {
  beforeEach(() => {
    mockAdminFetch.mockImplementation((endpoint: string, options?: RequestInit) => {
      if (endpoint === '/admin/db/tables') {
        return Promise.resolve(Response.json({
          tables: [
            {
              name: 'users',
              rowCount: 1,
              columns: [
                { name: 'id', type: 'INTEGER', nullable: false, primaryKey: true },
                { name: 'role', type: 'TEXT', nullable: false, primaryKey: false },
              ],
            },
          ],
        }))
      }

      if (endpoint === '/admin/db/tables/users?page=1&page_size=10') {
        return Promise.resolve(Response.json({
          rows: [{ id: 1, role: 'admin' }],
          page: 1,
          totalPages: 1,
          totalRows: 1,
        }))
      }

      if (endpoint === '/admin/db/query' && options?.method === 'POST') {
        return Promise.resolve(Response.json({
          success: true,
          columns: ['id', 'role'],
          rows: [{ id: 1, role: 'admin' }],
          executionTimeMs: 7,
        }))
      }

      return Promise.resolve(Response.json({}))
    })
  })

  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it('contains safe database query output in a named result surface', async () => {
    const user = userEvent.setup()

    render(
      <MemoryRouter initialEntries={['/admin/database']}>
        <Routes>
          <Route path="/admin/database" element={<AdminDatabaseExplorer />} />
        </Routes>
      </MemoryRouter>
    )

    await screen.findByText('users')

    await user.click(screen.getByRole('button', { name: 'SQL Query' }))
    await user.type(
      screen.getByLabelText('SQL Query'),
      'SELECT id, role FROM users LIMIT 1;'
    )
    await user.click(screen.getByRole('button', { name: 'Run Query' }))

    await waitFor(() => {
      expect(mockAdminFetch).toHaveBeenCalledWith('/admin/db/query', expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ sql: 'SELECT id, role FROM users LIMIT 1;' }),
      }))
    })

    const results = await screen.findByRole('region', { name: 'Safe query results' })
    expect(within(results).getByText('id')).toBeInTheDocument()
    expect(within(results).getByText('role')).toBeInTheDocument()
    expect(within(results).getByText('admin')).toBeInTheDocument()
    expect(results).toHaveClass('overflow-hidden')
  })
})
