import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it } from 'vitest'
import { SelectField, Textarea, TextField } from './Field'

describe('Field primitives', () => {
  afterEach(() => {
    cleanup()
  })

  it('connects labels, descriptions, and editable values for text inputs', async () => {
    const user = userEvent.setup()

    render(
      <TextField
        label="Instance name"
        description="Shown in the Instance header"
        placeholder="Enclave Free"
      />
    )

    const input = screen.getByRole('textbox', { name: 'Instance name' })
    expect(input).toHaveAccessibleDescription('Shown in the Instance header')

    await user.type(input, 'Sanctum')
    expect(input).toHaveValue('Sanctum')
  })

  it('announces textarea validation errors as field descriptions', async () => {
    render(
      <Textarea
        label="Operator note"
        error="Operator note is required"
      />
    )

    const textarea = screen.getByRole('textbox', { name: 'Operator note' })
    expect(textarea).toBeInvalid()
    expect(textarea).toHaveAccessibleDescription('Operator note is required')
  })

  it('connects labels and values for compact selects', async () => {
    const user = userEvent.setup()

    render(
      <SelectField label="Theme preference" defaultValue="system">
        <option value="system">System</option>
        <option value="dark">Dark</option>
      </SelectField>
    )

    const select = screen.getByRole('combobox', { name: 'Theme preference' })
    expect(select).toHaveValue('system')

    await user.selectOptions(select, 'dark')

    expect(select).toHaveValue('dark')
  })
})
