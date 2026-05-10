import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ChatInput } from './ChatInput'

describe('ChatInput', () => {
  afterEach(() => {
    cleanup()
  })

  it('sends a trimmed message from the accessible send action and clears the composer', async () => {
    const user = userEvent.setup()
    const onSend = vi.fn()

    render(<ChatInput onSend={onSend} />)

    const composer = screen.getByRole('textbox', { name: 'Ask anything...' })
    await user.type(composer, '  Summarize the latest upload  ')
    await user.click(screen.getByRole('button', { name: 'Send message' }))

    expect(onSend).toHaveBeenCalledWith('Summarize the latest upload')
    expect(composer).toHaveValue('')
  })

  it('does not send while disabled', async () => {
    const user = userEvent.setup()
    const onSend = vi.fn()

    render(<ChatInput onSend={onSend} disabled />)

    expect(screen.getByRole('button', { name: 'Send message' })).toBeDisabled()

    const composer = screen.getByRole('textbox', { name: 'Ask anything...' })
    await user.type(composer, 'Can this send?')
    await user.click(screen.getByRole('button', { name: 'Send message' }))

    expect(onSend).not.toHaveBeenCalled()
  })

  it('keeps Shift+Enter as multiline input and submits with Enter', async () => {
    const user = userEvent.setup()
    const onSend = vi.fn()

    render(<ChatInput onSend={onSend} />)

    const composer = screen.getByRole('textbox', { name: 'Ask anything...' })
    await user.type(composer, 'Line one{Shift>}{Enter}{/Shift}Line two')
    expect(composer).toHaveValue('Line one\nLine two')

    await user.keyboard('{Enter}')

    expect(onSend).toHaveBeenCalledWith('Line one\nLine two')
    expect(composer).toHaveValue('')
  })
})
