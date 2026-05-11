import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ToolSelector, type Tool } from './ToolSelector'

const tools: Tool[] = [
  {
    id: 'web-search',
    name: 'Web',
    description: 'Search the web',
    icon: <span aria-hidden="true">W</span>,
  },
  {
    id: 'db-query',
    name: 'Database',
    description: 'Query the database',
    icon: <span aria-hidden="true">D</span>,
  },
]

describe('ToolSelector', () => {
  afterEach(() => {
    cleanup()
  })

  it('exposes selected tools as pressed toggle buttons and calls onToggle', async () => {
    const user = userEvent.setup()
    const onToggle = vi.fn()

    render(
      <ToolSelector
        tools={tools}
        selectedTools={['web-search']}
        onToggle={onToggle}
      />
    )

    expect(screen.getByRole('button', { name: 'Web' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: 'Database' })).toHaveAttribute('aria-pressed', 'false')

    await user.click(screen.getByRole('button', { name: 'Database' }))

    expect(onToggle).toHaveBeenCalledWith('db-query')
  })
})
