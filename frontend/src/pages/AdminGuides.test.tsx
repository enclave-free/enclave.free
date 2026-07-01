import { cleanup, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it } from 'vitest';
import { AdminGuides } from './AdminGuides';

function renderAdminGuides() {
  render(
    <MemoryRouter>
      <AdminGuides />
    </MemoryRouter>
  );
}

describe('AdminGuides', () => {
  afterEach(() => {
    cleanup();
  });

  it('starts admins with a short beginner setup path', () => {
    renderAdminGuides();

    expect(
      screen.getByRole('heading', { name: 'Admin Guides' })
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        'Get to a small useful setup first. Improve it after testing.'
      )
    ).toBeInTheDocument();

    const quickStart = screen.getByRole('region', { name: 'Start with this' });
    expect(
      within(quickStart).getByText('Sign in as admin')
    ).toBeInTheDocument();
    expect(
      within(quickStart).getByText('Run Guided Setup')
    ).toBeInTheDocument();
    expect(
      within(quickStart).getByText('Test like a user')
    ).toBeInTheDocument();
  });

  it('links the guide to the admin work pages', () => {
    renderAdminGuides();

    expect(
      screen.getByRole('link', { name: 'Back to Admin Dashboard' })
    ).toHaveAttribute('href', '/admin/setup');
    expect(screen.getByRole('link', { name: /Guided Setup/ })).toHaveAttribute(
      'href',
      '/admin/onboarding'
    );
    expect(screen.getByRole('link', { name: /User Settings/ })).toHaveAttribute(
      'href',
      '/admin/users'
    );
    expect(
      screen.getByRole('link', { name: /Document Upload/ })
    ).toHaveAttribute('href', '/admin/upload');
    expect(
      screen.getByRole('link', { name: /Resource Directory/ })
    ).toHaveAttribute('href', '/admin/resources');
    expect(
      screen.getByRole('link', { name: /Test User Session/ })
    ).toHaveAttribute('href', '/admin/test-and-feedback');
    expect(
      screen.getByRole('link', { name: /Deployment Settings/ })
    ).toHaveAttribute('href', '/admin/deployment');
  });

  it('keeps safety copy short and concrete', () => {
    renderAdminGuides();

    expect(screen.getByText('Safety basics')).toBeInTheDocument();
    expect(
      screen.getByText('Review every change before clicking Apply.')
    ).toBeInTheDocument();
    expect(
      screen.getByText('Keep admin login keys out of chat, email, and tickets.')
    ).toBeInTheDocument();
  });
});
