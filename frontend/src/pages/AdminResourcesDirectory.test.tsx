import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
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

function genericResource(kind: 'person' | 'product' | 'method' | 'reference') {
  return {
    resource_id: `admin-${kind}`,
    name: `Admin ${kind}`,
    kind,
    tags: ['generic', kind],
    pointers: [{ type: 'url', value: `https://${kind}.example.test` }],
    regions: [{ level: 'global', code: null }],
    provenance: {},
    description: `A curated ${kind}.`,
    languages: ['en'],
    status: 'ready',
    missing_fields: [],
    display_order: 0,
  };
}

async function openAddResourceForm() {
  const addButtons = await screen.findAllByRole('button', {
    name: 'Add resource',
  });
  fireEvent.click(addButtons[0]);
}

describe('AdminResourcesDirectory', () => {
  afterEach(() => {
    cleanup();
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
              kind: 'organization',
              tags: ['legal'],
              pointers: [{ type: 'url', value: 'https://example.test' }],
              regions: [{ level: 'global', code: null }],
              provenance: {
                verified_at: '2026-06-09T00:00:00Z',
                vetted_by: 'test',
                source_note: 'test',
              },
              description: 'Legal support.',
              languages: ['en'],
              status: 'ready',
              missing_fields: [],
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

  it('creates resources with the generic contract', async () => {
    mockAdminFetch.mockImplementation(async (endpoint) => {
      if (endpoint === '/admin/resources') {
        return jsonResponse({ resources: [] });
      }
      if (endpoint === '/admin/regions') {
        return jsonResponse({ countries: [], subregions: [], regions: [] });
      }
      throw new Error(`Unexpected endpoint: ${endpoint}`);
    });

    render(
      <MemoryRouter>
        <AdminResourcesDirectory />
      </MemoryRouter>
    );

    await openAddResourceForm();
    fireEvent.change(screen.getByLabelText('Name'), {
      target: { value: 'Bitcoin Handbook' },
    });
    fireEvent.change(screen.getByLabelText('Kind'), {
      target: { value: 'reference' },
    });
    fireEvent.change(screen.getByLabelText('Tags (comma-separated)'), {
      target: { value: ' Bitcoin, Education ' },
    });
    fireEvent.change(screen.getByLabelText('Description'), {
      target: { value: 'A curated Bitcoin reference.' },
    });
    fireEvent.change(screen.getByLabelText('Display order'), {
      target: { value: '7' },
    });
    fireEvent.change(screen.getByLabelText('Pointer 1 type'), {
      target: { value: 'url' },
    });
    fireEvent.change(screen.getByLabelText('Pointer 1 value'), {
      target: { value: ' https://bitcoin.example.test ' },
    });
    fireEvent.change(screen.getByLabelText('Coverage level'), {
      target: { value: 'global' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => {
      expect(screen.queryByRole('dialog', { name: 'Add resource' })).toBeNull();
    });
    const createCall = mockAdminFetch.mock.calls.find(
      ([endpoint, options]) =>
        endpoint === '/admin/resources' && options?.method === 'POST'
    );
    expect(createCall).toBeDefined();
    expect(JSON.parse(String(createCall?.[1]?.body))).toMatchObject({
      name: 'Bitcoin Handbook',
      kind: 'reference',
      tags: ['bitcoin', 'education'],
      description: 'A curated Bitcoin reference.',
      display_order: 7,
      pointers: [
        {
          type: 'url',
          value: 'https://bitcoin.example.test',
          label: null,
        },
      ],
      regions: [{ level: 'global', code: null }],
    });
    expect(mockAdminFetch).not.toHaveBeenCalledWith('/admin/help-types');
  });

  it.each(['person', 'product', 'method', 'reference'] as const)(
    'renders and opens the generic %s contract for editing',
    async (kind) => {
      mockAdminFetch.mockImplementation(async (endpoint) => {
        if (endpoint === '/admin/resources') {
          return jsonResponse({ resources: [genericResource(kind)] });
        }
        if (endpoint === '/admin/regions') {
          return jsonResponse({ countries: [], subregions: [], regions: [] });
        }
        throw new Error(`Unexpected endpoint: ${endpoint}`);
      });

      render(
        <MemoryRouter>
          <AdminResourcesDirectory />
        </MemoryRouter>
      );

      expect(await screen.findByText(`Admin ${kind}`)).toBeInTheDocument();
      fireEvent.click(screen.getByRole('button', { name: 'Edit' }));
      expect(
        screen.getByRole('dialog', { name: 'Edit resource' })
      ).toBeVisible();
      expect(screen.getByLabelText('Kind')).toHaveValue(kind);
      expect(screen.getByLabelText('Pointer 1 value')).toHaveValue(
        `https://${kind}.example.test`
      );
    }
  );

  it('searches generic resource fields in the Admin product flow', async () => {
    mockAdminFetch.mockImplementation(async (endpoint) => {
      if (endpoint === '/admin/resources') {
        return jsonResponse({
          resources: [genericResource('person'), genericResource('product')],
        });
      }
      if (endpoint === '/admin/regions') {
        return jsonResponse({ countries: [], subregions: [], regions: [] });
      }
      throw new Error(`Unexpected endpoint: ${endpoint}`);
    });

    render(
      <MemoryRouter>
        <AdminResourcesDirectory />
      </MemoryRouter>
    );

    expect(await screen.findByText('Admin person')).toBeInTheDocument();
    expect(screen.getByText('Admin product')).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Search resources'), {
      target: { value: 'product.example.test' },
    });

    expect(screen.queryByText('Admin person')).toBeNull();
    expect(screen.getByText('Admin product')).toBeInTheDocument();
  });
});
