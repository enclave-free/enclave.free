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
})
