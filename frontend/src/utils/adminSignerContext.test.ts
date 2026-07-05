import { beforeEach, describe, expect, it, vi } from 'vitest';
import { buildAdminSignerDecryptedContext } from './adminSignerContext';
import { adminFetch } from './adminApi';

vi.mock('./adminApi', () => ({
  adminFetch: vi.fn(),
}));

describe('buildAdminSignerDecryptedContext', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    Object.defineProperty(window, 'nostr', {
      configurable: true,
      value: {
        getPublicKey: vi.fn().mockResolvedValue('admin-pubkey'),
        nip04: {
          decrypt: vi.fn(async (_pubkey: string, ciphertext: string) => {
            const values: Record<string, string> = {
              cipher_email: 'marisol@example.test',
              cipher_name: 'Marisol Rivera',
              cipher_org: 'Families United',
            };
            return values[ciphertext] ?? '';
          }),
        },
      },
    });
  });

  it('builds bounded signer-decrypted User context from the admin Users API', async () => {
    vi.mocked(adminFetch).mockResolvedValueOnce(
      Response.json({
        users: [
          {
            id: 7,
            approved: false,
            user_type_id: 3,
            created_at: '2026-07-03T16:40:00Z',
            pubkey: null,
            email_encrypted: {
              ciphertext: 'cipher_email',
              ephemeral_pubkey: 'email-ephemeral',
            },
            name_encrypted: {
              ciphertext: 'cipher_name',
              ephemeral_pubkey: 'name-ephemeral',
            },
            fields_encrypted: {
              organization: {
                ciphertext: 'cipher_org',
                ephemeral_pubkey: 'org-ephemeral',
              },
            },
          },
        ],
      })
    );

    const context = await buildAdminSignerDecryptedContext();

    expect(adminFetch).toHaveBeenCalledWith('/admin/users');
    expect(context).toEqual(
      expect.objectContaining({
        source: 'admin-signer-user-roster',
        users: [
          {
            id: 7,
            approved: false,
            user_type_id: 3,
            created_at: '2026-07-03T16:40:00Z',
            pubkey_present: false,
            email: 'marisol@example.test',
            name: 'Marisol Rivera',
            fields: { organization: 'Families United' },
          },
        ],
      })
    );
  });

  it('returns null when NIP-04 signer decryption is unavailable', async () => {
    Object.defineProperty(window, 'nostr', {
      configurable: true,
      value: {},
    });

    const context = await buildAdminSignerDecryptedContext();

    expect(context).toBeNull();
    expect(adminFetch).not.toHaveBeenCalled();
  });
});
