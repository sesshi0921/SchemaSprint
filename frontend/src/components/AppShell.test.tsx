import { render, screen } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { AppShell } from './AppShell'

describe('AppShell accessibility states', () => {
  it('exposes labeled navigation and honest preview state when signed out', () => {
    render(<BrowserRouter><AppShell session={{ authenticated: false, csrfToken: null, gates: null }}><main>content</main></AppShell></BrowserRouter>)
    expect(screen.getByRole('navigation', { name: 'Mobile navigation' })).toBeInTheDocument()
    expect(screen.getByText('Preview mode')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Sign in' })).toBeInTheDocument()
  })
})
