import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { IconButton } from './IconButton'

describe('IconButton', () => {
  afterEach(() => {
    cleanup()
  })

  it('exposes an accessible toggle action and ignores clicks while disabled', async () => {
    const user = userEvent.setup()
    const handleClick = vi.fn()

    const { rerender } = render(
      <IconButton label="Switch to dark mode" pressed={false} onClick={handleClick}>
        <span aria-hidden="true">moon</span>
      </IconButton>
    )

    const enabledButton = screen.getByRole('button', { name: 'Switch to dark mode' })
    expect(enabledButton).toHaveAttribute('aria-pressed', 'false')

    await user.click(enabledButton)
    expect(handleClick).toHaveBeenCalledTimes(1)

    rerender(
      <IconButton label="Switch to dark mode" pressed disabled onClick={handleClick}>
        <span aria-hidden="true">moon</span>
      </IconButton>
    )

    const disabledButton = screen.getByRole('button', { name: 'Switch to dark mode' })
    expect(disabledButton).toHaveAttribute('aria-pressed', 'true')
    expect(disabledButton).toBeDisabled()

    await user.click(disabledButton)
    expect(handleClick).toHaveBeenCalledTimes(1)
  })
})
