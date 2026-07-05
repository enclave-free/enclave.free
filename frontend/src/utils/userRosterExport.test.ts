import { describe, expect, it } from 'vitest';
import { buildUserRosterWorkbook } from './userRosterExport';

async function workbookText(blob: Blob): Promise<string> {
  return new TextDecoder().decode(await blob.arrayBuffer());
}

describe('buildUserRosterWorkbook', () => {
  it('builds a User Roster Export workbook without raw ciphertext', async () => {
    const workbook = buildUserRosterWorkbook({
      exportedAt: new Date('2026-07-03T18:30:00Z'),
      exportedBy: 'admin-pubkey',
      userTypes: [
        {
          id: 1,
          name: 'Member',
          description: 'Community member',
          icon: 'User',
          display_order: 0,
        },
        {
          id: 2,
          name: 'Partner',
          description: 'Partner organization',
          icon: 'Building',
          display_order: 1,
        },
      ],
      onboardingFields: [
        {
          id: '1',
          name: 'Organization',
          type: 'text',
          required: true,
          user_type_id: null,
          encryption_enabled: true,
          include_in_chat: false,
          display_order: 0,
        },
        {
          id: '2',
          name: 'Case Notes',
          type: 'textarea',
          required: false,
          user_type_id: 1,
          encryption_enabled: true,
          include_in_chat: false,
          display_order: 1,
        },
        {
          id: '3',
          name: 'Case Notes',
          type: 'textarea',
          required: false,
          user_type_id: 2,
          encryption_enabled: true,
          include_in_chat: false,
          display_order: 1,
        },
      ],
      identities: {
        7: {
          status: 'ready',
          email: 'austin@example.com',
          name: 'Austin Kelsay',
        },
        8: {
          status: 'unavailable',
          email: null,
          name: null,
        },
      },
      profileValues: {
        7: {
          Organization: 'Enclave\x01',
          'Case Notes': 'Local decrypted profile note',
        },
      },
      users: [
        {
          id: 7,
          pubkey: 'admin-facing-pubkey',
          user_type_id: 1,
          user_type: {
            id: 1,
            name: 'Member',
            description: 'Community member',
            icon: 'User',
            display_order: 0,
          },
          approved: true,
          created_at: '2026-06-30T17:57:16Z',
          email_encrypted: {
            ciphertext: 'email-ciphertext-should-not-export',
            ephemeral_pubkey: 'ephemeral-email',
          },
          name_encrypted: {
            ciphertext: 'name-ciphertext-should-not-export',
            ephemeral_pubkey: 'ephemeral-name',
          },
          fields_encrypted: {
            Organization: {
              ciphertext: 'organization-ciphertext-should-not-export',
              ephemeral_pubkey: 'ephemeral-profile',
            },
          },
        },
        {
          id: 8,
          pubkey: null,
          user_type_id: null,
          approved: false,
          created_at: '2026-07-01T12:00:00Z',
          email_encrypted: {
            ciphertext: 'locked-email-ciphertext-should-not-export',
            ephemeral_pubkey: 'ephemeral-email',
          },
        },
      ],
    });

    const text = await workbookText(workbook.blob);

    expect(workbook.filename).toBe('enclave_users_20260703T183000Z.xlsx');
    expect(workbook.includesDecryptedValues).toBe(true);
    expect(workbook.blob.type).toBe(
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    );
    expect(text).toContain('Users');
    expect(text).toContain('Pending Approval');
    expect(text).toContain('User Types');
    expect(text).toContain('Field Dictionary');
    expect(text).toContain('Export Notes');
    expect(text).toContain('numFmtId="164"');
    expect(text).toContain('<c r="F2" s="1"><v>');
    expect(text).toContain('Austin Kelsay');
    expect(text).toContain('austin@example.com');
    expect(text).toContain('Enclave');
    expect(text).not.toContain('Enclave\x01');
    expect(text).toContain('Local decrypted profile note');
    expect(text.match(/Local decrypted profile note/g)).toHaveLength(1);
    expect(text).toContain('Copied Export');
    expect(text).toContain('Locked');
    expect(text).not.toContain('ciphertext-should-not-export');
  });
});
