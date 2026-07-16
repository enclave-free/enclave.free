import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { AdminResourcesDirectory } from './AdminResourcesDirectory';
import { adminFetch } from '../utils/adminApi';

vi.mock('../utils/adminApi', () => ({
  ADMIN_RESOURCES_CHANGED_EVENT: 'enclave:admin-resources-changed',
  adminFetch: vi.fn(),
}));

const mockAdminFetch = vi.mocked(adminFetch);

function jsonResponse(body: unknown) {
  return {
    ok: true,
    json: async () => body,
  } as Response;
}

async function openAddResourceForm() {
  const addButtons = await screen.findAllByRole('button', {
    name: 'Add resource',
  });
  fireEvent.click(addButtons[0]);
}

describe('AdminResourcesDirectory', () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it('labels create/edit and delete modals as accessible dialogs', async () => {
    mockAdminFetch.mockImplementation(async (endpoint) => {
      if (endpoint === '/admin/resources') {
        return jsonResponse({
          resources: [
            {
              resource_id: 'legal-aid',
              name: 'Legal Aid',
              resource_type: 'ngo',
              description: 'Legal support.',
              contact: { url: 'https://example.test' },
              languages: ['en'],
              scope_level: 'global',
              scope_code: null,
              coverage: 'Global',
              help_types: ['legal'],
              status: 'ready',
              missing_fields: [],
              verified_at: '2026-06-09T00:00:00Z',
              vetted_by: 'test',
              source_note: 'test',
              display_order: 0,
            },
          ],
        });
      }
      if (endpoint === '/admin/help-types') {
        return jsonResponse({
          help_types: [{ key: 'legal', label: 'Legal', description: null }],
        });
      }
      return jsonResponse({});
    });

    render(
      <MemoryRouter>
        <AdminResourcesDirectory />
      </MemoryRouter>
    );

    expect(
      await screen.findByRole('link', { name: 'Back to Admin Dashboard' })
    ).toHaveAttribute('href', '/admin/setup');

    await openAddResourceForm();
    expect(
      screen.getByRole('dialog', { name: 'Add resource' })
    ).toHaveAttribute('aria-modal', 'true');
    expect(screen.getByRole('button', { name: 'Close' })).toBeEnabled();
    fireEvent.click(screen.getByRole('button', { name: 'Close' }));

    await waitFor(() => {
      expect(screen.queryByRole('dialog', { name: 'Add resource' })).toBeNull();
    });

    fireEvent.click(screen.getByRole('button', { name: 'Delete' }));
    expect(
      screen.getByRole('dialog', { name: 'Delete resource?' })
    ).toHaveAttribute('aria-modal', 'true');
    expect(screen.getByRole('button', { name: 'Cancel' })).toBeEnabled();
  });

  it('keeps core directory data usable when region taxonomy loading fails', async () => {
    mockAdminFetch.mockImplementation(async (endpoint) => {
      if (endpoint === '/admin/resources') {
        return jsonResponse({ resources: [] });
      }
      if (endpoint === '/admin/help-types') {
        return jsonResponse({ help_types: [] });
      }
      if (endpoint === '/admin/regions') {
        throw new Error('Region service unavailable');
      }
      throw new Error(`Unexpected endpoint: ${endpoint}`);
    });

    render(
      <MemoryRouter>
        <AdminResourcesDirectory />
      </MemoryRouter>
    );

    await openAddResourceForm();
    fireEvent.change(screen.getByLabelText('Coverage level'), {
      target: { value: 'country' },
    });
    fireEvent.change(screen.getByLabelText('Coverage code'), {
      target: { value: 'NI' },
    });

    expect(screen.getByLabelText('Coverage code')).toHaveValue('NI');
    expect(
      screen.getByText('Region directory unavailable. Enter a code manually.')
    ).toBeInTheDocument();
    expect(
      screen.queryByText('Failed to load directory')
    ).not.toBeInTheDocument();
  });

  it('uses manual coverage codes when region taxonomy entries are malformed', async () => {
    mockAdminFetch.mockImplementation(async (endpoint) => {
      if (endpoint === '/admin/resources') {
        return jsonResponse({ resources: [] });
      }
      if (endpoint === '/admin/help-types') {
        return jsonResponse({ help_types: [] });
      }
      if (endpoint === '/admin/regions') {
        return jsonResponse({ countries: [{}], subregions: [], regions: [] });
      }
      throw new Error(`Unexpected endpoint: ${endpoint}`);
    });

    render(
      <MemoryRouter>
        <AdminResourcesDirectory />
      </MemoryRouter>
    );

    await openAddResourceForm();
    fireEvent.change(screen.getByLabelText('Coverage level'), {
      target: { value: 'country' },
    });
    fireEvent.change(screen.getByLabelText('Coverage code'), {
      target: { value: 'NI' },
    });

    expect(screen.getByLabelText('Coverage code')).toHaveValue('NI');
    expect(
      screen.getByText('Region directory unavailable. Enter a code manually.')
    ).toBeInTheDocument();
  });
});
