import {
  cleanup,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import * as nip19 from 'nostr-tools/nip19';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AdminUserManager } from './AdminUserManager';
import { InstanceConfigProvider } from '../context/InstanceConfigContext';
import { ThemeProvider } from '../theme';
import { adminFetch } from '../utils/adminApi';
import { decryptField, hasNip04Support } from '../utils/encryption';

vi.mock('../utils/adminApi', () => ({
  adminFetch: vi.fn(),
  isAdminAuthenticated: vi.fn(() => true),
}));

vi.mock('../utils/encryption', () => ({
  decryptField: vi.fn(),
  hasNip04Support: vi.fn(),
  // The inline decrypt-progress indicator subscribes to the queue; return a
  // no-op unsubscribe so the component can mount under this mock. See #648.
  subscribeToDecryptQueue: vi.fn(() => () => {}),
  getDecryptQueueState: vi.fn(() => ({ done: 0, total: 0, active: false })),
}));

const mockAdminFetch = vi.mocked(adminFetch);
const mockDecryptField = vi.mocked(decryptField);
const mockHasNip04Support = vi.mocked(hasNip04Support);

interface MockEncryptedValue {
  ciphertext: string;
  ephemeral_pubkey: string;
}

interface MockRosterUser {
  id: number;
  pubkey: string | null;
  user_type_id: number | null;
  user_type: unknown;
  approved: boolean;
  created_at: string;
  fields?: Record<string, string>;
  fields_encrypted?: Record<string, MockEncryptedValue>;
  email_encrypted?: MockEncryptedValue;
  name_encrypted?: MockEncryptedValue;
}

let userTypesResponse: unknown[] = [];
let fieldsResponse: unknown[] = [];
let usersResponse: MockRosterUser[] = [];
let failApproval = false;
let failUsersLoad = false;
let failExportAudit = false;
let anchorClickSpy: ReturnType<typeof vi.spyOn>;

function renderUserManager(initialEntry = '/admin/user-manager') {
  render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <ThemeProvider>
        <InstanceConfigProvider>
          <Routes>
            <Route path="/admin/user-manager" element={<AdminUserManager />} />
            <Route
              path="/admin/user-manager/:userId"
              element={<AdminUserManager />}
            />
          </Routes>
        </InstanceConfigProvider>
      </ThemeProvider>
    </MemoryRouter>
  );
}

async function unlockDetails(user: ReturnType<typeof userEvent.setup>) {
  await user.click(
    await screen.findByRole('button', { name: 'Unlock details' })
  );
}

function seedRoster() {
  userTypesResponse = [
    { id: 1, name: 'Member', description: 'Community member', icon: 'User' },
    { id: 2, name: 'Partner', description: 'Partner org', icon: 'Users' },
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
      field_name: 'Role',
      field_type: 'text',
      required: true,
      user_type_id: 2,
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
      user_type: userTypesResponse[0],
      approved: false,
      created_at: '2026-06-30T17:57:16Z',
      fields: { Organization: 'Austin AI Club' },
      email_encrypted: {
        ciphertext: 'austin-email',
        ephemeral_pubkey: 'ephemeral-email',
      },
      name_encrypted: {
        ciphertext: 'austin-name',
        ephemeral_pubkey: 'ephemeral-name',
      },
    },
    {
      id: 42,
      pubkey:
        'abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890',
      user_type_id: 2,
      user_type: userTypesResponse[1],
      approved: true,
      created_at: '2026-07-01T10:00:00Z',
      fields: { Organization: 'Partner Org' },
      fields_encrypted: {
        Role: { ciphertext: 'role-cipher', ephemeral_pubkey: 'role-ephemeral' },
      },
      email_encrypted: {
        ciphertext: 'jamie-email',
        ephemeral_pubkey: 'ephemeral-email',
      },
      name_encrypted: {
        ciphertext: 'jamie-name',
        ephemeral_pubkey: 'ephemeral-name',
      },
    },
  ];
}

describe('AdminUserManager', () => {
  beforeEach(() => {
    seedRoster();
    failApproval = false;
    failUsersLoad = false;
    failExportAudit = false;
    localStorage.setItem('enclave-theme', 'light');
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        json: vi.fn().mockResolvedValue({}),
      })
    );
    vi.stubGlobal(
      'matchMedia',
      vi.fn().mockReturnValue({
        matches: false,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      })
    );
    Object.defineProperty(window.URL, 'createObjectURL', {
      configurable: true,
      value: vi.fn(() => 'blob:user-manager-export'),
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
        'austin-email': 'austin@example.com',
        'austin-name': 'Austin Kelsay',
        'jamie-email': 'jamie@example.com',
        'jamie-name': 'Jamie Tester',
        'role-cipher': 'Operations lead',
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
          if (failUsersLoad) {
            return Promise.resolve(
              Response.json(
                { detail: 'Roster service unavailable' },
                { status: 503 }
              )
            );
          }
          return Promise.resolve(Response.json({ users: usersResponse }));
        }
        if (endpoint.startsWith('/users/') && options?.method === 'PUT') {
          if (failApproval) {
            return Promise.resolve(
              Response.json(
                { detail: 'Approval service unavailable' },
                { status: 503 }
              )
            );
          }
          const userId = Number(endpoint.split('/')[2]);
          const payload = JSON.parse(String(options.body || '{}')) as {
            approved?: boolean;
          };
          const existing = usersResponse.find((user) => user.id === userId);
          if (!existing) {
            return Promise.resolve(
              Response.json({ detail: 'User not found' }, { status: 404 })
            );
          }
          const updated = {
            ...existing,
            approved: payload.approved ?? existing.approved,
          };
          usersResponse = usersResponse.map((user) =>
            user.id === userId ? updated : user
          );
          return Promise.resolve(Response.json(updated));
        }
        if (
          endpoint === '/admin/users/roster-export' &&
          options?.method === 'POST'
        ) {
          if (failExportAudit) {
            return Promise.resolve(
              Response.json(
                { detail: 'Audit service unavailable' },
                { status: 503 }
              )
            );
          }
          return Promise.resolve(
            Response.json({ success: true, message: 'recorded' })
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
    vi.unstubAllGlobals();
    vi.clearAllMocks();
    localStorage.clear();
    document.documentElement.classList.remove('dark');
  });

  it('shows an accessible roster table with summary counts and filters', async () => {
    const user = userEvent.setup();
    renderUserManager();
    await unlockDetails(user);

    expect(
      await screen.findByRole('heading', { name: 'User Manager' })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('table', { name: 'User roster' })
    ).toBeInTheDocument();
    expect(
      screen.getByText('Total users').closest('section')
    ).toHaveTextContent('2');
    expect(screen.getByText('1 pending')).toBeInTheDocument();
    expect(
      screen.getByText('can enter chat').closest('section')
    ).toHaveTextContent('1');
    expect(await screen.findAllByText('Austin Kelsay')).not.toHaveLength(0);
    expect(await screen.findAllByText('Jamie Tester')).not.toHaveLength(0);

    const searchField = screen.getByLabelText('Search users');

    await user.selectOptions(
      screen.getByLabelText('Approval status'),
      'pending'
    );

    expect(screen.getAllByText('Austin Kelsay')).not.toHaveLength(0);
    expect(screen.queryByText('Jamie Tester')).not.toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText('Approval status'), 'all');
    await user.type(searchField, 'jamie');

    expect(screen.queryByText('Austin Kelsay')).not.toBeInTheDocument();
    expect(screen.getAllByText('Jamie Tester')).not.toHaveLength(0);

    await user.clear(searchField);
    await user.selectOptions(screen.getByLabelText('User Type'), '2');

    expect(screen.queryByText('Austin Kelsay')).not.toBeInTheDocument();
    expect(screen.getAllByText('Jamie Tester')).not.toHaveLength(0);

    await user.selectOptions(screen.getByLabelText('User Type'), 'all');
    await user.type(searchField, '#42');

    expect(screen.queryByText('Austin Kelsay')).not.toBeInTheDocument();
    expect(screen.getAllByText('Jamie Tester')).not.toHaveLength(0);

    await user.clear(searchField);
    await user.type(searchField, 'abcdef');

    expect(screen.queryByText('Austin Kelsay')).not.toBeInTheDocument();
    expect(screen.getAllByText('Jamie Tester')).not.toHaveLength(0);

    await user.clear(searchField);
    const jamieNpub = nip19.npubEncode(String(usersResponse[1].pubkey));
    await user.type(searchField, jamieNpub.slice(0, 12));

    expect(screen.queryByText('Austin Kelsay')).not.toBeInTheDocument();
    expect(screen.getAllByText('Jamie Tester')).not.toHaveLength(0);
  });

  it('lets an admin approve a pending user from the table', async () => {
    const user = userEvent.setup();
    renderUserManager();
    await unlockDetails(user);

    const row = await screen.findByRole('row', { name: /Austin Kelsay/i });
    await user.click(
      within(row).getByRole('button', { name: /approve Austin Kelsay/i })
    );

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
    ).toHaveTextContent('Austin Kelsay approved.');
    expect(screen.getByText('0 pending')).toBeInTheDocument();
    await waitFor(() => {
      expect(
        within(row).queryByRole('button', { name: /approve Austin Kelsay/i })
      ).not.toBeInTheDocument();
    });
  });

  it('opens a user detail screen from the roster and shows all fields', async () => {
    const user = userEvent.setup();
    renderUserManager();
    await unlockDetails(user);

    await screen.findAllByText('Jamie Tester');
    await user.click(
      screen.getAllByRole('link', {
        name: /view Jamie Tester details/i,
      })[0]
    );

    expect(
      await screen.findByRole('heading', { name: 'Jamie Tester' })
    ).toBeInTheDocument();
    expect(screen.getByText('User details')).toBeInTheDocument();
    expect(screen.getByText('jamie@example.com')).toBeInTheDocument();
    expect(screen.getAllByText('Partner')).not.toHaveLength(0);
    expect(
      screen.getByText(
        'abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890'
      )
    ).toBeInTheDocument();
    expect(screen.getByText('Organization')).toBeInTheDocument();
    expect(screen.getByText('Partner Org')).toBeInTheDocument();
    expect(screen.getByText('Role')).toBeInTheDocument();
    expect(await screen.findByText('Operations lead')).toBeInTheDocument();
    expect(
      screen.getByRole('link', { name: 'Back to user roster' })
    ).toHaveAttribute('href', '/admin/user-manager');
  });

  it('lets an admin approve a pending user from the detail screen', async () => {
    const user = userEvent.setup();
    renderUserManager('/admin/user-manager/7');
    await unlockDetails(user);

    expect(
      await screen.findByRole('heading', { name: 'Austin Kelsay' })
    ).toBeInTheDocument();
    await user.click(
      screen.getByRole('button', { name: /approve Austin Kelsay/i })
    );

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
    ).toHaveTextContent('Austin Kelsay approved.');
    expect(
      screen.queryByRole('button', { name: /approve Austin Kelsay/i })
    ).not.toBeInTheDocument();
    expect(screen.getByText('can enter chat')).toBeInTheDocument();
  });

  it('offers unlock on detail screens with encrypted profile fields', async () => {
    const user = userEvent.setup();
    usersResponse = usersResponse.map((user) =>
      user.id === 42
        ? {
            ...user,
            email_encrypted: undefined,
            name_encrypted: undefined,
          }
        : user
    );

    renderUserManager('/admin/user-manager/42');

    expect(await screen.findByText('Role')).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'Unlock details' })
    ).toBeInTheDocument();
    expect(mockDecryptField).not.toHaveBeenCalled();

    await user.click(screen.getByRole('button', { name: 'Unlock details' }));

    await waitFor(() => {
      expect(mockDecryptField).toHaveBeenCalled();
    });
  });

  it('shows a helpful not-found state for unknown user detail routes', async () => {
    renderUserManager('/admin/user-manager/999');

    expect(
      await screen.findByRole('heading', { name: 'User not found' })
    ).toBeInTheDocument();
    expect(
      screen.getByText('This user is not in the current admin roster.')
    ).toBeInTheDocument();
    expect(
      screen.getByRole('link', { name: 'Back to user roster' })
    ).toHaveAttribute('href', '/admin/user-manager');
  });

  it('shows an accessible error if approval fails', async () => {
    const user = userEvent.setup();
    failApproval = true;
    renderUserManager();
    await unlockDetails(user);

    const row = await screen.findByRole('row', { name: /Austin Kelsay/i });
    await user.click(
      within(row).getByRole('button', { name: /approve Austin Kelsay/i })
    );

    expect(
      await screen.findByRole('note', { name: 'User approval update failed' })
    ).toHaveTextContent('Approval service unavailable');
    expect(screen.getByText('1 pending')).toBeInTheDocument();
  });

  it('keeps the roster usable when encrypted identity unlock fails', async () => {
    const user = userEvent.setup();
    mockDecryptField.mockRejectedValue(new Error('Signer rejected decrypt'));
    renderUserManager();
    await unlockDetails(user);

    expect(
      await screen.findAllByText('Encrypted details could not be unlocked.')
    ).not.toHaveLength(0);
    expect(
      screen.getByRole('table', { name: 'User roster' })
    ).toBeInTheDocument();
    expect(screen.getByText('2 shown from 2 total.')).toBeInTheDocument();
  });

  it('separates load errors from an empty user roster', async () => {
    failUsersLoad = true;
    renderUserManager();

    expect(
      await screen.findByRole('note', { name: 'User roster load failed' })
    ).toHaveTextContent('Roster service unavailable');
    expect(
      screen.getByText(
        'User roster could not load. Use Refresh roster to try again.'
      )
    ).toBeInTheDocument();

    cleanup();
    vi.clearAllMocks();
    seedRoster();
    usersResponse = [];
    failUsersLoad = false;
    renderUserManager();

    expect(
      await screen.findByText(
        'No users yet. New authenticated users will appear here.'
      )
    ).toBeInTheDocument();
  });

  it('refreshes the roster and exports an audited User Roster Export', async () => {
    const user = userEvent.setup();
    renderUserManager();
    await unlockDetails(user);

    await screen.findAllByText('Austin Kelsay');
    await user.click(screen.getByRole('button', { name: 'Refresh roster' }));

    await waitFor(() => {
      expect(
        mockAdminFetch.mock.calls.filter(
          ([endpoint]) => endpoint === '/admin/users'
        )
      ).toHaveLength(2);
    });

    await user.selectOptions(screen.getByLabelText('User Type'), '2');
    await user.click(
      screen.getByRole('button', { name: 'Export visible roster' })
    );

    await waitFor(() => {
      expect(mockAdminFetch).toHaveBeenCalledWith(
        '/admin/users/roster-export',
        expect.objectContaining({
          method: 'POST',
          body: expect.stringContaining('"user_count":1'),
        })
      );
    });
    expect(mockAdminFetch).toHaveBeenCalledWith(
      '/admin/users/roster-export',
      expect.objectContaining({
        method: 'POST',
        body: expect.stringContaining('"pending_count":0'),
      })
    );
    expect(anchorClickSpy).toHaveBeenCalled();
    expect(
      await screen.findByRole('note', { name: 'User roster export ready' })
    ).toHaveTextContent('User roster spreadsheet downloaded.');
  });

  it('shows profile completion cues and incomplete profile counts', async () => {
    usersResponse = usersResponse.map((user) =>
      user.id === 7 ? { ...user, fields: {} } : user
    );

    renderUserManager();

    expect(
      await screen.findByRole('heading', { name: 'User Manager' })
    ).toBeInTheDocument();
    expect(
      screen.getByText('Incomplete profiles').closest('section')
    ).toHaveTextContent('1');
    expect(screen.getAllByText('Needs profile')).not.toHaveLength(0);
    expect(screen.getAllByText('1 required answer missing')).not.toHaveLength(
      0
    );
  });

  it('does not download the roster if export auditing fails', async () => {
    const user = userEvent.setup();
    failExportAudit = true;
    renderUserManager();
    await unlockDetails(user);

    await screen.findAllByText('Austin Kelsay');
    await user.click(
      screen.getByRole('button', { name: 'Export visible roster' })
    );

    expect(
      await screen.findByRole('note', { name: 'User roster export failed' })
    ).toHaveTextContent('Audit service unavailable');
    expect(anchorClickSpy).not.toHaveBeenCalled();
  });
});
