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
    const content = screen.getByText('Fetch all settings').closest('[aria-hidden]') as HTMLElement
    expect(trigger).toHaveAttribute('aria-expanded', 'false')
    expect(content).toHaveAttribute('aria-hidden', 'true')
    expect(content).toHaveClass('hidden')

    await user.click(trigger)

    expect(trigger).toHaveAttribute('aria-expanded', 'true')
    expect(content).toHaveAttribute('aria-hidden', 'false')
    expect(content).not.toHaveClass('hidden')

    await user.click(trigger)

    expect(trigger).toHaveAttribute('aria-expanded', 'false')
    expect(content).toHaveAttribute('aria-hidden', 'true')
    expect(content).toHaveClass('hidden')
  })
})
