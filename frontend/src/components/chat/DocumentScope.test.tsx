import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { DocumentScope, type DocumentSource } from './DocumentScope'

const documents: DocumentSource[] = [
  {
    id: 'doc-1',
    name: 'Operator Handbook',
    description: 'Deployment guidance',
    tags: ['ops', 'private'],
  },
  {
    id: 'doc-2',
    name: 'User FAQ',
    description: 'Common questions',
    tags: ['support'],
  },
]

describe('DocumentScope', () => {
  afterEach(() => {
    cleanup()
  })

  it('opens document choices, exposes selected state, toggles docs, and clears selected docs', async () => {
    const user = userEvent.setup()
    const onToggle = vi.fn()

    render(
      <DocumentScope
        documents={documents}
        selectedDocuments={['doc-1']}
        onToggle={onToggle}
      />
    )

    const trigger = screen.getByRole('button', { name: 'Docs 1' })
    expect(trigger).toHaveAttribute('aria-expanded', 'false')

    await user.click(trigger)

    expect(trigger).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByRole('button', { name: /Operator Handbook/ })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: /User FAQ/ })).toHaveAttribute('aria-pressed', 'false')

    await user.click(screen.getByRole('button', { name: /User FAQ/ }))
    expect(onToggle).toHaveBeenCalledWith('doc-2')

    await user.click(screen.getByRole('button', { name: 'Clear all selected documents' }))
    expect(onToggle).toHaveBeenCalledWith('doc-1')
  })
})
