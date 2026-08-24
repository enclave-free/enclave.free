import { describe, expect, it, vi } from 'vitest';
import type { CustomField, UserType } from '../types/onboarding';
import type { UserRosterExportUser } from './userRosterExport';
import {
  isPreparedUserRosterExportCurrent,
  prepareUserRosterExport,
} from './userRosterExportPreparation';

const userTypes: UserType[] = [
  {
    id: 1,
    name: 'Member',
    description: 'Community member',
    display_order: 0,
  },
];

const onboardingFields: CustomField[] = [
  {
    id: '10',
    name: 'Case Notes',
    type: 'textarea',
    required: false,
    user_type_id: 1,
    encryption_enabled: true,
  },
];

const encryptedUser: UserRosterExportUser = {
  id: 7,
  pubkey: 'admin-visible-pubkey',
  user_type_id: 1,
  approved: false,
  email_encrypted: {
    ciphertext: 'email-cipher',
    ephemeral_pubkey: 'email-sender',
  },
  name_encrypted: {
    ciphertext: 'name-cipher',
    ephemeral_pubkey: 'name-sender',
  },
  fields_encrypted: {
    'Case Notes': {
      ciphertext: 'profile-cipher',
      ephemeral_pubkey: 'profile-sender',
    },
  },
};

const exportedAt = new Date('2026-08-24T12:00:00.000Z');

function buildPreparationInput(
  users: UserRosterExportUser[],
  decrypt?: (encrypted: {
    ciphertext: string;
    ephemeral_pubkey: string;
  }) => Promise<string | null>
) {
  return {
    users,
    userTypes,
    onboardingFields,
    exportedAt,
    exportedBy: 'admin-pubkey',
    decrypt,
  };
}

describe('prepareUserRosterExport', () => {
  it('returns one complete immutable snapshot after decrypting every ciphertext', async () => {
    const decrypt = vi.fn(async ({ ciphertext }: { ciphertext: string }) => {
      const plaintext: Record<string, string> = {
        'email-cipher': 'austin@example.com',
        'name-cipher': 'Austin Kelsay',
        'profile-cipher': 'Needs a follow-up',
      };
      return plaintext[ciphertext] ?? null;
    });

    const result = await prepareUserRosterExport(
      buildPreparationInput([encryptedUser], decrypt)
    );

    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(decrypt.mock.calls.map(([value]) => value.ciphertext)).toEqual([
      'email-cipher',
      'name-cipher',
      'profile-cipher',
    ]);
    expect(result.snapshot.userCount).toBe(1);
    expect(result.snapshot.pendingCount).toBe(1);
    expect(result.snapshot.workbook.includesDecryptedValues).toBe(true);
    expect(Object.isFrozen(result.snapshot)).toBe(true);
  });

  it('fails when encrypted values require unavailable browser decryption', async () => {
    const result = await prepareUserRosterExport(
      buildPreparationInput([encryptedUser])
    );

    expect(result).toEqual({ ok: false, reason: 'decrypt-unavailable' });
  });

  it('fails the whole preparation when one encrypted identity does not decrypt', async () => {
    const result = await prepareUserRosterExport(
      buildPreparationInput([encryptedUser], async ({ ciphertext }) =>
        ciphertext === 'name-cipher' ? null : 'decrypted'
      )
    );

    expect(result).toEqual({
      ok: false,
      reason: 'decryption-failed',
      target: { kind: 'identity', userId: 7, fieldName: 'name' },
    });
  });

  it('fails the whole preparation when one encrypted User Profile value does not decrypt', async () => {
    const result = await prepareUserRosterExport(
      buildPreparationInput([encryptedUser], async ({ ciphertext }) =>
        ciphertext === 'profile-cipher' ? null : 'decrypted'
      )
    );

    expect(result).toEqual({
      ok: false,
      reason: 'decryption-failed',
      target: {
        kind: 'profile',
        userId: 7,
        fieldName: 'Case Notes',
      },
    });
  });

  it('accepts optional values that have no ciphertext', async () => {
    const result = await prepareUserRosterExport(
      buildPreparationInput([
        {
          id: 8,
          user_type_id: 1,
          approved: true,
          email_encrypted: null,
          name_encrypted: undefined,
          fields_encrypted: { 'Case Notes': null },
        },
      ])
    );

    expect(result.ok).toBe(true);
  });

  it('marks a prepared snapshot stale when the requested Users change', async () => {
    const result = await prepareUserRosterExport(
      buildPreparationInput([encryptedUser], async () => 'decrypted')
    );

    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(
      isPreparedUserRosterExportCurrent(result.snapshot, [encryptedUser])
    ).toBe(true);
    expect(
      isPreparedUserRosterExportCurrent(result.snapshot, [
        encryptedUser,
        { id: 8, user_type_id: null, approved: true },
      ])
    ).toBe(false);
  });
});
