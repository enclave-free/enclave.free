import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AdminAIConfig } from './AdminAIConfig'
import { adminFetch } from '../utils/adminApi'
import type { AIConfigResponse, DocumentDefaultsResponse } from '../types/config'

vi.mock('../utils/adminApi', () => ({
  adminFetch: vi.fn(),
  isAdminAuthenticated: vi.fn(() => true),
}))

const mockAdminFetch = vi.mocked(adminFetch)

const baseAIConfigResponse: AIConfigResponse = {
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

let aiConfigResponse = baseAIConfigResponse
let documentDefaultsResponse: DocumentDefaultsResponse = { documents: [] }

describe('AdminAIConfig', () => {
  beforeEach(() => {
    aiConfigResponse = baseAIConfigResponse
    documentDefaultsResponse = { documents: [] }

    mockAdminFetch.mockImplementation((endpoint: string, options?: RequestInit) => {
      if (endpoint === '/admin/user-types') {
        return Promise.resolve(Response.json({ types: [] }))
      }
      if (endpoint === '/ingest/admin/documents/defaults') {
        return Promise.resolve(Response.json(documentDefaultsResponse))
      }
      if (endpoint === '/ingest/admin/documents/doc-1/defaults' && options?.method === 'PUT') {
        return Promise.resolve(Response.json({
          job_id: 'doc-1',
          filename: 'ops-guide.pdf',
          total_chunks: 12,
          status: 'completed',
          is_available: true,
          is_default_active: true,
          display_order: 0,
        }))
      }
      if (endpoint === '/admin/ai-config/max_tokens' && options?.method === 'PUT') {
        return Promise.resolve(Response.json({
          key: 'max_tokens',
          value: '4096',
          value_type: 'number',
          category: 'parameter',
        }))
      }
      if (endpoint === '/admin/ai-config/web_search_default' && options?.method === 'PUT') {
        return Promise.resolve(Response.json({
          key: 'web_search_default',
          value: 'false',
          value_type: 'boolean',
          category: 'default',
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

  it('lets an admin make a document active by default for new conversations', async () => {
    documentDefaultsResponse = {
      documents: [
        {
          job_id: 'doc-1',
          filename: 'ops-guide.pdf',
          total_chunks: 12,
          status: 'completed',
          is_available: true,
          is_default_active: false,
          display_order: 0,
        },
      ],
    }

    const user = userEvent.setup()

    render(
      <MemoryRouter initialEntries={['/admin/ai']}>
        <Routes>
          <Route path="/admin/ai" element={<AdminAIConfig />} />
        </Routes>
      </MemoryRouter>
    )

    await screen.findByText('ops-guide.pdf')

    await user.click(screen.getByRole('switch', { name: 'ops-guide.pdf Active by Default' }))

    await waitFor(() => {
      expect(mockAdminFetch).toHaveBeenCalledWith('/ingest/admin/documents/doc-1/defaults', expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify({ is_default_active: true }),
      }))
    })
  })

  it('lets an admin configure whether the Web Search tool is active by default', async () => {
    aiConfigResponse = {
      ...baseAIConfigResponse,
      defaults: [
        {
          key: 'web_search_default',
          value: 'true',
          value_type: 'boolean',
          category: 'default',
          description: 'Web search active by default for new sessions',
        },
      ],
    }

    const user = userEvent.setup()

    render(
      <MemoryRouter initialEntries={['/admin/ai']}>
        <Routes>
          <Route path="/admin/ai" element={<AdminAIConfig />} />
        </Routes>
      </MemoryRouter>
    )

    await screen.findByText('Web Search')

    const defaultToolCard = screen.getByText('Allow AI to search the internet').closest('div')
    expect(defaultToolCard).not.toBeNull()

    const editButtons = screen.getAllByRole('button', { name: 'Edit' })
    await user.click(editButtons[editButtons.length - 1])
    await user.click(screen.getByRole('switch', { name: 'Web Search' }))
    await user.click(screen.getByRole('button', { name: 'Save' }))

    await waitFor(() => {
      expect(mockAdminFetch).toHaveBeenCalledWith('/admin/ai-config/web_search_default', expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify({ value: 'false' }),
      }))
    })
  })
})
