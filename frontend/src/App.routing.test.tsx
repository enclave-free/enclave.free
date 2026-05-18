import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'

vi.mock('./pages/HomeRedirect', () => ({
  HomeRedirect: () => <main>Product home redirect</main>,
}))

vi.mock('./pages/TestDashboard', () => ({
  TestDashboard: () => <main>Diagnostics Test Dashboard</main>,
}))

describe('App routing', () => {
  afterEach(() => {
    cleanup()
    window.history.pushState({}, '', '/')
  })

  it('keeps root on the product path instead of the Test Dashboard', () => {
    window.history.pushState({}, '', '/')

    render(<App />)

    expect(screen.getByText('Product home redirect')).toBeInTheDocument()
    expect(screen.queryByText('Diagnostics Test Dashboard')).not.toBeInTheDocument()
  })

  it('keeps the Test Dashboard reachable through explicit diagnostics routing', () => {
    window.history.pushState({}, '', '/diagnostics/test-dashboard')

    render(<App />)

    expect(screen.getByText('Diagnostics Test Dashboard')).toBeInTheDocument()
  })
})
