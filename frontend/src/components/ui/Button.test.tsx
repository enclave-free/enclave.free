import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { Button } from './Button'

describe('Button', () => {
  afterEach(() => {
    cleanup()
  })

  it('renders an accessible action and ignores clicks while disabled', async () => {
    const user = userEvent.setup()
    const handleClick = vi.fn()

    const { rerender } = render(
      <Button onClick={handleClick}>Save Instance settings</Button>
    )

    await user.click(screen.getByRole('button', { name: 'Save Instance settings' }))
    expect(handleClick).toHaveBeenCalledTimes(1)

    rerender(
      <Button onClick={handleClick} disabled>
        Save Instance settings
      </Button>
    )

    expect(screen.getByRole('button', { name: 'Save Instance settings' })).toBeDisabled()

    await user.click(screen.getByRole('button', { name: 'Save Instance settings' }))
    expect(handleClick).toHaveBeenCalledTimes(1)
  })
})
