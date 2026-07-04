import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
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

function getConfigCard(label: string): HTMLElement {
  const card = screen.getByText(label).closest('div.bg-surface')
  expect(card).not.toBeNull()
  return card as HTMLElement
}

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
let previewShouldFail = false

describe('AdminAIConfig', () => {
  beforeEach(() => {
    aiConfigResponse = baseAIConfigResponse
    documentDefaultsResponse = { documents: [] }
    previewShouldFail = false

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
      if (endpoint === '/admin/ai-config/prompts/preview' && options?.method === 'POST') {
        if (previewShouldFail) {
          return Promise.resolve(Response.json({ detail: 'Preview unavailable' }, { status: 500 }))
        }
        return Promise.resolve(Response.json({
          assembled_prompt: 'System: You are Sage.\nQuestion: What should I know about this topic?',
          sections_used: ['prompt_system'],
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

    const maxTokensCard = getConfigCard('Max Tokens')
    await user.click(within(maxTokensCard).getByRole('button', { name: 'Edit' }))
    fireEvent.change(within(maxTokensCard).getByRole('slider'), { target: { value: '4096' } })
    await user.click(within(maxTokensCard).getByRole('button', { name: 'Save' }))

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

    const defaultToolCard = getConfigCard('Web Search')
    await user.click(within(defaultToolCard).getByRole('button', { name: 'Edit' }))
    await user.click(within(defaultToolCard).getByRole('switch', { name: 'Web Search' }))
    await user.click(within(defaultToolCard).getByRole('button', { name: 'Save' }))

    await waitFor(() => {
      expect(mockAdminFetch).toHaveBeenCalledWith('/admin/ai-config/web_search_default', expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify({ value: 'false' }),
      }))
    })
  })

  it('shows Knowledge Source defaults as a human-readable label', async () => {
    aiConfigResponse = {
      ...baseAIConfigResponse,
      defaults: [
        {
          key: 'knowledge_source_default',
          value: 'all',
          value_type: 'string',
          category: 'default',
          description: 'Knowledge source scope for new user sessions',
        },
      ],
    }

    render(
      <MemoryRouter initialEntries={['/admin/ai']}>
        <Routes>
          <Route path="/admin/ai" element={<AdminAIConfig />} />
        </Routes>
      </MemoryRouter>
    )

    await screen.findByText('Knowledge Sources')
    const knowledgeSourceCard = getConfigCard('Knowledge Sources')
    expect(knowledgeSourceCard).toHaveTextContent('All available documents')
  })

  it('lets an admin configure the AI System Prompt', async () => {
    aiConfigResponse = {
      ...baseAIConfigResponse,
      prompt_sections: [
        {
          key: 'prompt_system',
          value: 'You are Sage, a private assistant for this instance.',
          value_type: 'string',
          category: 'prompt_section',
          description: 'Core system prompt',
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

    expect(await screen.findByText('System Prompt')).toBeInTheDocument()

    const systemPromptCard = getConfigCard('System Prompt')
    await user.click(within(systemPromptCard).getByRole('button', { name: 'Edit' }))
    await user.clear(within(systemPromptCard).getByRole('textbox'))
    await user.type(within(systemPromptCard).getByRole('textbox'), 'You are Sage for a legal aid enclave.')
    await user.click(within(systemPromptCard).getByRole('button', { name: 'Save' }))

    await waitFor(() => {
      expect(mockAdminFetch).toHaveBeenCalledWith('/admin/ai-config/prompt_system', expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify({ value: 'You are Sage for a legal aid enclave.' }),
      }))
    })
  })

  it('previews the assembled Agent Settings prompt as named technical output', async () => {
    aiConfigResponse = {
      ...baseAIConfigResponse,
      prompt_sections: [
        {
          key: 'prompt_system',
          value: 'You are Sage.',
          value_type: 'string',
          category: 'prompt_section',
          description: 'Core system prompt',
        },
      ],
    }

    render(
      <MemoryRouter initialEntries={['/admin/ai']}>
        <Routes>
          <Route path="/admin/ai" element={<AdminAIConfig />} />
        </Routes>
      </MemoryRouter>
    )

    expect(await screen.findByText('System Prompt')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Preview' }))

    const output = await screen.findByRole('region', { name: 'Assembled prompt output' })
    expect(output).toHaveTextContent('System: You are Sage.')
    expect(output).toHaveTextContent('Question: What should I know about this topic?')
    expect(mockAdminFetch).toHaveBeenCalledWith('/admin/ai-config/prompts/preview', expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({
        sample_question: 'What should I know about this topic?',
        sample_facts: {},
      }),
    }))
  })

  it('shows prompt preview failures as a named Agent Settings error note', async () => {
    previewShouldFail = true
    aiConfigResponse = {
      ...baseAIConfigResponse,
      prompt_sections: [
        {
          key: 'prompt_system',
          value: 'You are Sage.',
          value_type: 'string',
          category: 'prompt_section',
          description: 'Core system prompt',
        },
      ],
    }

    render(
      <MemoryRouter initialEntries={['/admin/ai']}>
        <Routes>
          <Route path="/admin/ai" element={<AdminAIConfig />} />
        </Routes>
      </MemoryRouter>
    )

    expect(await screen.findByText('System Prompt')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Preview' }))

    const error = await screen.findByRole('note', { name: 'Agent Settings preview error' })
    expect(error).toHaveTextContent('Failed to preview prompt')
  })
})
