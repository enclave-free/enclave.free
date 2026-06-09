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

    fireEvent.click(
      await screen.findByRole('button', { name: 'Add resource' })
    );
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
});
