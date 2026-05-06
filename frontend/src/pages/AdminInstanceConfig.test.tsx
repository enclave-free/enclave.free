import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AdminInstanceConfig } from './AdminInstanceConfig'
import { adminFetch } from '../utils/adminApi'
import { DEFAULT_INSTANCE_CONFIG } from '../types/instance'

vi.mock('../utils/adminApi', () => ({
  adminFetch: vi.fn(),
  isAdminAuthenticated: vi.fn(() => true),
}))

vi.mock('../components/onboarding/IconPicker', () => ({
  IconPicker: ({ 'aria-labelledby': ariaLabelledby }: { 'aria-labelledby'?: string }) => (
    <div
      role="group"
      aria-labelledby={ariaLabelledby}
      aria-label={ariaLabelledby ? undefined : 'mock-icon-picker'}
    />
  ),
}))

vi.mock('../components/onboarding/ColorPicker', () => ({
  ColorPicker: ({ 'aria-labelledby': ariaLabelledby }: { 'aria-labelledby'?: string }) => (
    <div
      role="group"
      aria-labelledby={ariaLabelledby}
      aria-label={ariaLabelledby ? undefined : 'mock-color-picker'}
    />
  ),
}))

const updateConfig = vi.fn()

vi.mock('../context/InstanceConfigContext', async () => {
  const actual = await vi.importActual<typeof import('../context/InstanceConfigContext')>('../context/InstanceConfigContext')
  const { DEFAULT_INSTANCE_CONFIG } = await vi.importActual<typeof import('../types/instance')>('../types/instance')

  return {
    ...actual,
    useInstanceConfig: () => ({
      config: DEFAULT_INSTANCE_CONFIG,
      setConfig: vi.fn(),
      updateConfig,
    }),
  }
})

const mockAdminFetch = vi.mocked(adminFetch)

describe('AdminInstanceConfig', () => {
  beforeEach(() => {
    updateConfig.mockReset()
    mockAdminFetch.mockResolvedValue(Response.json({ settings: {} }))
  })

  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it('lets an admin update Instance branding and chat identity settings', async () => {
    render(
      <MemoryRouter initialEntries={['/admin/instance']}>
        <Routes>
          <Route path="/admin/instance" element={<AdminInstanceConfig />} />
          <Route path="/admin/setup" element={<div>Admin Dashboard</div>} />
        </Routes>
      </MemoryRouter>
    )

    fireEvent.change(screen.getByRole('textbox', { name: 'Display Name' }), {
      target: { value: 'Operator Desk' },
    })
    fireEvent.change(screen.getByRole('textbox', { name: 'Logo URL' }), {
      target: { value: 'https://example.com/logo.png' },
    })
    fireEvent.change(screen.getByRole('textbox', { name: 'Assistant display name' }), {
      target: { value: 'Sage' },
    })
    fireEvent.change(screen.getByRole('textbox', { name: 'User label' }), {
      target: { value: 'Operator' },
    })

    fireEvent.click(screen.getByRole('button', { name: 'Save Configuration' }))

    await waitFor(() => {
      expect(mockAdminFetch).toHaveBeenCalledWith('/admin/settings', expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify({
          instance_name: 'Operator Desk',
          primary_color: DEFAULT_INSTANCE_CONFIG.accentColor,
          icon: DEFAULT_INSTANCE_CONFIG.icon,
          logo_url: 'https://example.com/logo.png',
          favicon_url: '',
          apple_touch_icon_url: '',
          assistant_icon: DEFAULT_INSTANCE_CONFIG.assistantIcon,
          user_icon: DEFAULT_INSTANCE_CONFIG.userIcon,
          assistant_name: 'Sage',
          user_label: 'Operator',
          header_layout: DEFAULT_INSTANCE_CONFIG.headerLayout,
          header_tagline: '',
          chat_bubble_style: DEFAULT_INSTANCE_CONFIG.chatBubbleStyle,
          chat_bubble_shadow: String(DEFAULT_INSTANCE_CONFIG.chatBubbleShadow),
          surface_style: DEFAULT_INSTANCE_CONFIG.surfaceStyle,
          status_icon_set: DEFAULT_INSTANCE_CONFIG.statusIconSet,
          typography_preset: DEFAULT_INSTANCE_CONFIG.typographyPreset,
        }),
      }))
    })

    expect(updateConfig).toHaveBeenCalledWith(expect.objectContaining({
      name: 'Operator Desk',
      logoUrl: 'https://example.com/logo.png',
      assistantName: 'Sage',
      userLabel: 'Operator',
    }))
  })
})
