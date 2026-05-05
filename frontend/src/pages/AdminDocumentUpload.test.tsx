import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AdminDocumentUpload } from './AdminDocumentUpload'
import { adminFetch } from '../utils/adminApi'

vi.mock('../utils/adminApi', () => ({
  adminFetch: vi.fn(),
  isAdminAuthenticated: vi.fn(() => true),
}))

vi.mock('../components/shared/InstanceLogo', () => ({
  InstanceLogo: () => null,
}))

const mockAdminFetch = vi.mocked(adminFetch)

function deferredResponse() {
  let resolve!: (response: Response) => void
  const promise = new Promise<Response>((resolvePromise) => {
    resolve = resolvePromise
  })
  return { promise, resolve }
}

describe('AdminDocumentUpload', () => {
  beforeEach(() => {
    mockAdminFetch.mockReset()
    vi.spyOn(window, 'confirm').mockReset()
  })

  afterEach(() => {
    cleanup()
  })

  it('asks before leaving while document transfer has not produced an ingestion job', async () => {
    const user = userEvent.setup()
    const uploadResponse = deferredResponse()
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false)

    mockAdminFetch
      .mockResolvedValueOnce(Response.json({ total: 0, jobs: [] }))
      .mockReturnValueOnce(uploadResponse.promise)

    render(
      <MemoryRouter initialEntries={['/admin/upload']}>
        <Routes>
          <Route path="/" element={<div>Dashboard</div>} />
          <Route path="/admin/upload" element={<AdminDocumentUpload />} />
        </Routes>
      </MemoryRouter>
    )

    await screen.findByText('No uploads yet')

    const file = new File(['operator knowledge'], 'guide.txt', { type: 'text/plain' })
    const input = document.querySelector('input[type="file"]')
    expect(input).toBeInstanceOf(HTMLInputElement)

    await user.upload(input as HTMLInputElement, file)
    await user.click(screen.getByRole('button', { name: 'Upload Document' }))
    await user.click(screen.getByRole('link', { name: 'Back to Dashboard' }))

    expect(confirmSpy).toHaveBeenCalledWith(
      'Your document is still being transferred. Leave only after processing has started, or the upload may not be saved.'
    )
    expect(screen.getByRole('button', { name: /uploading/i })).toBeInTheDocument()
    expect(screen.queryByText('Dashboard')).not.toBeInTheDocument()

    uploadResponse.resolve(Response.json({
      job_id: 'job-1',
      filename: 'guide.txt',
      status: 'pending',
      message: 'Document queued for processing',
    }))

    await waitFor(() => {
      expect(screen.queryByRole('button', { name: /uploading/i })).not.toBeInTheDocument()
    })
  })

  it('uploads multiple valid files with one batch request', async () => {
    const user = userEvent.setup()

    mockAdminFetch
      .mockResolvedValueOnce(Response.json({ total: 0, jobs: [] }))
      .mockResolvedValueOnce(Response.json({
        accepted: [
          { job_id: 'job-1', filename: 'guide.txt', status: 'pending', message: 'queued' },
          { job_id: 'job-2', filename: 'faq.md', status: 'pending', message: 'queued' },
        ],
        rejected: [],
      }))
      .mockResolvedValueOnce(Response.json({ total: 0, jobs: [] }))

    render(
      <MemoryRouter initialEntries={['/admin/upload']}>
        <Routes>
          <Route path="/admin/upload" element={<AdminDocumentUpload />} />
        </Routes>
      </MemoryRouter>
    )

    await screen.findByText('No uploads yet')

    const input = document.querySelector('input[type="file"]')
    expect(input).toBeInstanceOf(HTMLInputElement)

    await user.upload(input as HTMLInputElement, [
      new File(['guide'], 'guide.txt', { type: 'text/plain' }),
      new File(['faq'], 'faq.md', { type: 'text/markdown' }),
    ])
    await user.click(screen.getByRole('button', { name: 'Upload documents' }))

    await waitFor(() => {
      expect(mockAdminFetch).toHaveBeenCalledWith('/ingest/upload/batch', expect.objectContaining({
        method: 'POST',
        body: expect.any(FormData),
      }))
    })

    const batchCall = mockAdminFetch.mock.calls.find(([url]) => url === '/ingest/upload/batch')
    const body = batchCall?.[1]?.body as FormData
    expect(body.getAll('files')).toHaveLength(2)
    expect(body.getAll('relative_paths')).toEqual(['', ''])
  })

  it('shows invalid and duplicate selected files as skipped', async () => {
    mockAdminFetch.mockResolvedValueOnce(Response.json({ total: 0, jobs: [] }))

    render(
      <MemoryRouter initialEntries={['/admin/upload']}>
        <Routes>
          <Route path="/admin/upload" element={<AdminDocumentUpload />} />
        </Routes>
      </MemoryRouter>
    )

    await screen.findByText('No uploads yet')

    const input = document.querySelector<HTMLInputElement>('input[type="file"]')
    expect(input).toBeInstanceOf(HTMLInputElement)
    if (!input) throw new Error('file input not found')

    fireEvent.change(input, {
      target: {
        files: [
          new File(['one'], 'guide.txt', { type: 'text/plain' }),
          new File(['two'], 'guide.txt', { type: 'text/plain' }),
          new File(['png'], 'logo.png', { type: 'image/png' }),
        ],
      },
    })

    expect(screen.getByText('Duplicate document name in this batch')).toBeInTheDocument()
    expect(screen.getByText('Invalid file type. Allowed: PDF, TXT, MD')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Upload Document' })).toBeEnabled()
  })
})
