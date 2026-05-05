import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { CodeBlockSurface } from './CodeBlockSurface'

describe('CodeBlockSurface', () => {
  afterEach(() => {
    cleanup()
  })

  it('exposes labelled technical output as a named region', () => {
    render(
      <CodeBlockSurface label="Health response output">
        <pre>{JSON.stringify({ neo4j: 'ok' }, null, 2)}</pre>
      </CodeBlockSurface>
    )

    const output = screen.getByRole('region', { name: 'Health response output' })
    expect(output).toHaveTextContent('"neo4j": "ok"')
  })
})
