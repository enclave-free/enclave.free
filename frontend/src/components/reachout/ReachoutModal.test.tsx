import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ReachoutModal } from './ReachoutModal'

describe('ReachoutModal', () => {
  afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
  })

  it('contains validation failures in a named form error note', async () => {
    const user = userEvent.setup()

    render(
      <ReachoutModal
        open
        mode="feedback"
        onClose={vi.fn()}
      />
    )

    await user.click(screen.getByRole('button', { name: 'Send' }))

    const errorNote = await screen.findByRole('note', { name: 'Reachout form error' })
    expect(errorNote).toHaveTextContent('Message is required.')
  })

  it('shows one close action after a successful submission', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(null, { status: 204 })))

    render(
      <ReachoutModal
        open
        mode="feedback"
        onClose={vi.fn()}
      />
    )

    await user.type(screen.getByLabelText('Message'), 'This is useful feedback.')
    await user.click(screen.getByRole('button', { name: 'Send' }))

    await screen.findByRole('note', { name: 'Reachout success' })
    expect(screen.queryByRole('button', { name: 'Cancel' })).not.toBeInTheDocument()
    const footerCloseButtons = screen
      .getAllByRole('button', { name: 'Close' })
      .filter((button) => button.textContent?.trim() === 'Close')
    expect(footerCloseButtons).toHaveLength(1)
  })
})
