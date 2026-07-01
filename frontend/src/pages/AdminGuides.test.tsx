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

  it('starts admins with a short setup path', () => {
    renderAdminGuides();

    expect(
      screen.getByRole('heading', { name: 'Admin Guides' })
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        'A simple map of what admins configure, what the product can do, and what needs care before launch.'
      )
    ).toBeInTheDocument();

    const quickStart = screen.getByRole('region', { name: 'Start here' });
    expect(
      within(quickStart).getByText('Sign in as admin')
    ).toBeInTheDocument();
    expect(within(quickStart).getByText('Set the basics')).toBeInTheDocument();
    expect(
      within(quickStart).getByText('Define your users')
    ).toBeInTheDocument();
    expect(
      within(quickStart).getByText('Test before launch')
    ).toBeInTheDocument();
  });

  it('maps product configuration areas to the real admin pages', () => {
    renderAdminGuides();

    expect(
      screen.getByRole('link', { name: /Identity and look/ })
    ).toHaveAttribute('href', '/admin/instance');
    expect(
      screen.getByRole('link', { name: /People and access/ })
    ).toHaveAttribute('href', '/admin/users');
    expect(
      screen.getByRole('link', { name: /Agent behavior/ })
    ).toHaveAttribute('href', '/admin/ai');
    expect(
      screen.getByRole('link', { name: /Document knowledge/ })
    ).toHaveAttribute('href', '/admin/upload');
    expect(
      screen.getByRole('link', { name: /Vetted resources/ })
    ).toHaveAttribute('href', '/admin/resources');
    expect(
      screen.getByRole('link', { name: /Operations and runtime/ })
    ).toHaveAttribute('href', '/admin/deployment');
  });

  it('describes the important admin-controlled features', () => {
    renderAdminGuides();

    expect(
      screen.getByText(
        'Logo, favicon, icon, accent color, theme, typography, and chat style.'
      )
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        'Onboarding fields, required questions, options, placeholders, and per-type fields.'
      )
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        'Feature defaults for Knowledge, Resources, Web, Config, and Database tools.'
      )
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        'Runtime env export, readiness, stale settings, and admin key migration.'
      )
    ).toBeInTheDocument();
  });

  it('states product truths and safety boundaries plainly', () => {
    renderAdminGuides();

    expect(
      screen.getByText(
        'Knowledge, Resources, Web, Config, and Database are visible tool sets, not separate chat systems.'
      )
    ).toBeInTheDocument();
    expect(
      screen.getByText('Admins use NIP-07. Users use email magic links.')
    ).toBeInTheDocument();
    expect(
      screen.getByText('Encrypted profile fields stay out of chat context.')
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        'Deployment Settings store desired runtime values. Operators still export env and restart services when needed.'
      )
    ).toBeInTheDocument();
  });

  it('keeps workflows and assistant prompts beginner friendly', () => {
    renderAdminGuides();

    expect(
      screen.getByRole('link', { name: /Admin Assistant/ })
    ).toHaveAttribute('href', '/chat');
    expect(screen.getByRole('link', { name: /Guided Setup/ })).toHaveAttribute(
      'href',
      '/admin/onboarding'
    );
    expect(
      screen.getByRole('link', { name: /Test and feedback/ })
    ).toHaveAttribute('href', '/admin/test-and-feedback');
    expect(
      screen.getByRole('link', { name: /Database Explorer/ })
    ).toHaveAttribute('href', '/admin/database');
    expect(
      screen.getByText(
        'What is still missing before this instance is ready for users?'
      )
    ).toBeInTheDocument();
  });
});
