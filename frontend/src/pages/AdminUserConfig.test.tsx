import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AdminUserConfig } from './AdminUserConfig';
import { adminFetch } from '../utils/adminApi';
import { decryptField, hasNip04Support } from '../utils/encryption';

vi.mock('../utils/adminApi', () => ({
  adminFetch: vi.fn(),
  isAdminAuthenticated: vi.fn(() => true),
}));

vi.mock('../utils/encryption', () => ({
  decryptField: vi.fn(),
  hasNip04Support: vi.fn(),
}));

const mockAdminFetch = vi.mocked(adminFetch);
const mockDecryptField = vi.mocked(decryptField);
const mockHasNip04Support = vi.mocked(hasNip04Support);

let userTypesResponse: unknown[] = [];
let fieldsResponse: unknown[] = [];
let usersResponse: unknown[] = [];
let anchorClickSpy: ReturnType<typeof vi.spyOn>;

describe('AdminUserConfig', () => {
  beforeEach(() => {
    userTypesResponse = [];
    fieldsResponse = [];
    usersResponse = [];
    Object.defineProperty(window.URL, 'createObjectURL', {
      configurable: true,
      value: vi.fn(() => 'blob:user-roster-export'),
    });
    Object.defineProperty(window.URL, 'revokeObjectURL', {
      configurable: true,
      value: vi.fn(),
    });
    anchorClickSpy = vi
      .spyOn(HTMLAnchorElement.prototype, 'click')
      .mockImplementation(() => {});
    mockHasNip04Support.mockReturnValue(true);
    mockDecryptField.mockImplementation(async (encrypted) => {
      const values: Record<string, string> = {
        'email-cipher': 'austin@example.com',
        'name-cipher': 'Austin Kelsay',
        'migration-email-cipher': 'jamie@example.com',
        'migration-name-cipher': 'Jamie Tester',
        'profile-cipher': 'Local decrypted profile note',
      };
      return encrypted ? (values[encrypted.ciphertext] ?? null) : null;
    });

    mockAdminFetch.mockImplementation(
      (endpoint: string, options?: RequestInit) => {
        if (endpoint === '/admin/user-types') {
          return Promise.resolve(Response.json({ types: userTypesResponse }));
        }
        if (endpoint === '/admin/user-fields') {
          return Promise.resolve(Response.json({ fields: fieldsResponse }));
        }
        if (endpoint === '/admin/users') {
          return Promise.resolve(Response.json({ users: usersResponse }));
        }
        if (
          endpoint === '/admin/users/roster-export' &&
          options?.method === 'POST'
        ) {
          return Promise.resolve(
            Response.json({ success: true, message: 'recorded' })
          );
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
    anchorClickSpy?.mockRestore();
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
        email_encrypted: {
          ciphertext: 'email-cipher',
          ephemeral_pubkey: 'ephemeral-email',
        },
        name_encrypted: {
          ciphertext: 'name-cipher',
          ephemeral_pubkey: 'ephemeral-name',
        },
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
    expect(await screen.findAllByText('Austin Kelsay')).toHaveLength(2);
    expect(await screen.findAllByText('austin@example.com')).toHaveLength(2);

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
        email_encrypted: {
          ciphertext: 'migration-email-cipher',
          ephemeral_pubkey: 'ephemeral-email',
        },
        name_encrypted: {
          ciphertext: 'migration-name-cipher',
          ephemeral_pubkey: 'ephemeral-name',
        },
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
    expect(await screen.findByText('Jamie Tester')).toBeInTheDocument();
    expect(await screen.findByText('jamie@example.com')).toBeInTheDocument();

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

  it('downloads a User Roster Export and records copied export metadata', async () => {
    userTypesResponse = [
      { id: 1, name: 'Member', description: 'Community member', icon: 'User' },
    ];
    fieldsResponse = [
      {
        id: 1,
        field_name: 'Organization',
        field_type: 'text',
        required: true,
        user_type_id: null,
        encryption_enabled: false,
        include_in_chat: true,
        display_order: 0,
      },
      {
        id: 2,
        field_name: 'Case Notes',
        field_type: 'textarea',
        required: false,
        user_type_id: 1,
        encryption_enabled: true,
        include_in_chat: false,
        display_order: 1,
      },
    ];
    usersResponse = [
      {
        id: 7,
        pubkey: null,
        user_type_id: 1,
        user_type: {
          id: 1,
          name: 'Member',
          description: 'Community member',
          icon: 'User',
          display_order: 0,
        },
        approved: false,
        created_at: '2026-06-30T17:57:16Z',
        email_encrypted: {
          ciphertext: 'email-cipher',
          ephemeral_pubkey: 'ephemeral-email',
        },
        name_encrypted: {
          ciphertext: 'name-cipher',
          ephemeral_pubkey: 'ephemeral-name',
        },
        fields: {
          Organization: 'Enclave',
        },
        fields_encrypted: {
          'Case Notes': {
            ciphertext: 'profile-cipher',
            ephemeral_pubkey: 'ephemeral-profile',
          },
        },
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

    expect(await screen.findAllByText('Austin Kelsay')).toHaveLength(2);
    await user.click(screen.getByRole('button', { name: 'Export users' }));

    await waitFor(() => {
      expect(mockAdminFetch).toHaveBeenCalledWith(
        '/admin/users/roster-export',
        expect.objectContaining({
          method: 'POST',
          body: expect.any(String),
        })
      );
    });

    const auditCall = mockAdminFetch.mock.calls.find(
      ([endpoint]) => endpoint === '/admin/users/roster-export'
    );
    expect(auditCall).toBeDefined();
    const body = JSON.parse(String(auditCall?.[1]?.body));
    expect(body.filename).toMatch(/^enclave_users_.*\.xlsx$/);
    expect(body.user_count).toBe(1);
    expect(body.pending_count).toBe(1);
    expect(body.includes_decrypted_browser_values).toBe(true);
    expect(anchorClickSpy).toHaveBeenCalled();
    expect(
      await screen.findByRole('note', { name: 'User roster export ready' })
    ).toHaveTextContent('User roster spreadsheet downloaded.');
  });
});
