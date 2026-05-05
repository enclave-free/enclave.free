import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { Callout } from './Callout'

describe('Callout', () => {
  afterEach(() => {
    cleanup()
  })

  it('exposes advisory content as a named note', () => {
    render(
      <Callout label="Endpoint guidance">
        <strong>GET /health</strong> pings both databases.
      </Callout>
    )

    const note = screen.getByRole('note', { name: 'Endpoint guidance' })
    expect(note).toHaveTextContent('GET /health')
    expect(note).toHaveTextContent('pings both databases')
  })
})
