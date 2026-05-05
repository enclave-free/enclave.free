import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { MetricCard } from './MetricCard'

describe('MetricCard', () => {
  afterEach(() => {
    cleanup()
  })

  it('exposes a named metric with stable numeric rendering', () => {
    render(<MetricCard label="Queued jobs" value={12} tone="accent" />)

    const metric = screen.getByRole('group', { name: 'Queued jobs' })
    expect(metric).toHaveTextContent('Queued jobs')
    expect(metric).toHaveTextContent('12')
    expect(screen.getByText('12')).toHaveClass('tabular-nums')
  })
})
