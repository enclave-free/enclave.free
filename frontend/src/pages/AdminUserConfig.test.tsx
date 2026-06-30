import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AdminUserConfig } from './AdminUserConfig';
import { adminFetch } from '../utils/adminApi';

vi.mock('../utils/adminApi', () => ({
  adminFetch: vi.fn(),
  isAdminAuthenticated: vi.fn(() => true),
}));

const mockAdminFetch = vi.mocked(adminFetch);

let userTypesResponse: unknown[] = [];
let usersResponse: unknown[] = [];

describe('AdminUserConfig', () => {
  beforeEach(() => {
    userTypesResponse = [];
    usersResponse = [];

    mockAdminFetch.mockImplementation(
      (endpoint: string, options?: RequestInit) => {
        if (endpoint === '/admin/user-types') {
          return Promise.resolve(Response.json({ types: userTypesResponse }));
        }
        if (endpoint === '/admin/user-fields') {
          return Promise.resolve(Response.json({ fields: [] }));
        }
        if (endpoint === '/admin/users') {
          return Promise.resolve(Response.json({ users: usersResponse }));
        }
        if (endpoint.startsWith('/users/') && options?.method === 'PUT') {
          const userId = Number(endpoint.split('/')[2]);
          const payload = JSON.parse(String(options.body || '{}')) as {
            approved?: boolean;
          };
          const existing = (usersResponse as any[]).find(
            (user) => user.id === userId
          );
          const updated = { ...existing, approved: payload.approved };
          usersResponse = (usersResponse as any[]).map((user) =>
            user.id === userId ? updated : user
          );
          return Promise.resolve(Response.json(updated));
        }
        if (
          endpoint === '/admin/users/migrate-type/batch' &&
          options?.method === 'POST'
        ) {
          return Promise.resolve(
            Response.json({
              success: true,
              migrated: 1,
              failed: 0,
              results: [
                {
                  user_id: 42,
                  success: true,
                  previous_user_type_id: null,
                  target_user_type_id: 1,
                  missing_required_count: 1,
                  missing_required_fields: ['Company'],
                },
              ],
            })
          );
        }
        if (endpoint === '/admin/settings' && options?.method === 'PUT') {
          return Promise.resolve(
            Response.json({ settings: { auto_approve_users: 'true' } })
          );
        }
        if (endpoint === '/admin/settings') {
          return Promise.resolve(
            Response.json({
              settings: {
                auto_approve_users: 'false',
                reachout_enabled: 'false',
              },
            })
          );
        }
        throw new Error(
          `Unhandled adminFetch mock call: ${options?.method ?? 'GET'} ${endpoint}`
        );
      }
    );
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('lets an admin configure whether new users require User Approval', async () => {
    const user = userEvent.setup();

    render(
      <MemoryRouter initialEntries={['/admin/users']}>
        <Routes>
          <Route path="/admin/users" element={<AdminUserConfig />} />
        </Routes>
      </MemoryRouter>
    );

    const manualApproval = await screen.findByRole('checkbox', {
      name: /require manual approval for new users/i,
    });
    const saveUserApproval = await screen.findByRole('button', {
      name: /save user approval/i,
    });

    await waitFor(() => {
      expect(manualApproval).toBeEnabled();
      expect(saveUserApproval).toBeEnabled();
    });

    expect(manualApproval).toBeChecked();

    await user.click(manualApproval);
    await user.click(saveUserApproval);

    await waitFor(() => {
      expect(mockAdminFetch).toHaveBeenCalledWith(
        '/admin/settings',
        expect.objectContaining({
          method: 'PUT',
          body: JSON.stringify({ auto_approve_users: 'true' }),
        })
      );
    });

    expect(
      await screen.findByRole('note', { name: /user approval saved/i })
    ).toHaveTextContent('Saved');
  });

  it('lets an admin approve a pending user from User Settings', async () => {
    usersResponse = [
      {
        id: 7,
        pubkey: null,
        user_type_id: null,
        user_type: null,
        approved: false,
        created_at: '2026-06-30T17:57:16Z',
      },
    ];
    const user = userEvent.setup();

    render(
      <MemoryRouter initialEntries={['/admin/users']}>
        <Routes>
          <Route path="/admin/users" element={<AdminUserConfig />} />
        </Routes>
      </MemoryRouter>
    );

    expect(await screen.findByText('Pending approvals')).toBeInTheDocument();
    expect(
      await screen.findByText('1 user needs approval before chat access.')
    ).toBeInTheDocument();

    await user.click(screen.getAllByRole('button', { name: 'Approve' })[0]);

    await waitFor(() => {
      expect(mockAdminFetch).toHaveBeenCalledWith(
        '/users/7',
        expect.objectContaining({
          method: 'PUT',
          body: JSON.stringify({ approved: true }),
        })
      );
    });

    expect(
      await screen.findByRole('note', { name: 'User approval updated' })
    ).toHaveTextContent('User #7 approved.');
    expect(
      await screen.findByText('No users are waiting for approval.')
    ).toBeInTheDocument();
  });

  it('shows User Type migration results as a named status note after a batch migration', async () => {
    userTypesResponse = [
      { id: 1, name: 'Member', description: 'Community member', icon: 'User' },
    ];
    usersResponse = [
      {
        id: 42,
        pubkey: null,
        user_type_id: null,
        user_type: null,
        approved: true,
        created_at: '2026-05-01T12:00:00Z',
      },
    ];
    const user = userEvent.setup();

    render(
      <MemoryRouter initialEntries={['/admin/users']}>
        <Routes>
          <Route path="/admin/users" element={<AdminUserConfig />} />
        </Routes>
      </MemoryRouter>
    );

    await screen.findByText('User Type Migration');

    await user.click(screen.getByRole('button', { name: 'Select visible' }));
    const migrateButton = screen.getByRole('button', {
      name: 'Migrate selected (1)',
    });
    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: 'Migrate selected (1)' })
      ).toBeEnabled();
    });

    await user.click(migrateButton);

    await waitFor(() => {
      expect(mockAdminFetch).toHaveBeenCalledWith(
        '/admin/users/migrate-type/batch',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({
            user_ids: [42],
            target_user_type_id: 1,
            allow_incomplete: true,
          }),
        })
      );
    });

    expect(
      await screen.findByRole('note', { name: 'User type migration summary' })
    ).toHaveTextContent('Migration complete. Migrated: 1. Failed: 0.');
  });
});
