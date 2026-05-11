import { cleanup, render, screen, within } from '@testing-library/react'
import { Settings } from 'lucide-react'
import { afterEach, describe, expect, it } from 'vitest'
import { SectionHeader } from './SectionHeader'

describe('SectionHeader', () => {
  afterEach(() => {
    cleanup()
  })

  it('renders a labelled section heading with optional icon and actions', () => {
    render(
      <SectionHeader
        title="Admin Settings"
        description="Configure operator controls."
        icon={<Settings data-testid="settings-section-icon" aria-hidden="true" />}
        actions={<button type="button">Refresh</button>}
      />
    )

    expect(screen.getByRole('heading', { name: 'Admin Settings', level: 2 })).toBeInTheDocument()
    expect(screen.getByText('Configure operator controls.')).toBeInTheDocument()
    expect(screen.getByTestId('settings-section-icon')).toBeInTheDocument()
    expect(within(screen.getByRole('button', { name: 'Refresh' })).getByText('Refresh')).toBeInTheDocument()
  })
})
