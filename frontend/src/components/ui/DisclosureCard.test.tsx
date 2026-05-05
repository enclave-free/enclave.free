import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it } from 'vitest'
import { DisclosureCard } from './DisclosureCard'

describe('DisclosureCard', () => {
  afterEach(() => {
    cleanup()
  })

  it('toggles labelled content through an accessible button', async () => {
    const user = userEvent.setup()

    render(
      <DisclosureCard title="Instance Settings" eyebrow="11" badge="Admin">
        <p>Fetch all settings</p>
      </DisclosureCard>
    )

    const trigger = screen.getByRole('button', { name: /11.*Instance Settings.*Admin/ })
    expect(trigger).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByText('Fetch all settings')).not.toBeInTheDocument()

    await user.click(trigger)

    expect(trigger).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByText('Fetch all settings')).toBeInTheDocument()

    await user.click(trigger)

    expect(trigger).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByText('Fetch all settings')).not.toBeInTheDocument()
  })
})
