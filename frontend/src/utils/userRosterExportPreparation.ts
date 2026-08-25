import type { CustomField, UserType } from '../types/onboarding';
import {
  buildUserRosterWorkbook,
  type EncryptedFieldValue,
  type UserRosterExportUser,
  type UserRosterIdentity,
  type UserRosterWorkbook,
} from './userRosterExport';

type DecryptAdapter = (
  encrypted: EncryptedFieldValue
) => Promise<string | null>;

export interface UserRosterExportPreparationInput {
  users: UserRosterExportUser[];
  userTypes: UserType[];
  onboardingFields: CustomField[];
  exportedAt: Date;
  exportedBy?: string | null;
  decrypt?: DecryptAdapter;
}

export interface PreparedUserRosterExport {
  readonly requestUserIds: readonly number[];
  readonly userCount: number;
  readonly pendingCount: number;
  readonly workbook: Readonly<UserRosterWorkbook>;
}

const preparedRosterContent = new WeakMap<PreparedUserRosterExport, string>();

type FailedDecryptionTarget =
  | {
      kind: 'identity';
      userId: number;
      fieldName: 'email' | 'name';
    }
  | { kind: 'profile'; userId: number; fieldName: string };

export type UserRosterExportPreparationResult =
  | { ok: true; snapshot: PreparedUserRosterExport }
  | { ok: false; reason: 'decrypt-unavailable' }
  | {
      ok: false;
      reason: 'decryption-failed';
      target: FailedDecryptionTarget;
    };

interface EncryptedValueTask {
  encrypted: EncryptedFieldValue;
  target: FailedDecryptionTarget;
}

function hasCiphertext(
  encrypted: EncryptedFieldValue | null | undefined
): encrypted is EncryptedFieldValue {
  return encrypted?.ciphertext !== null && encrypted?.ciphertext !== undefined;
}

function requestedUserIds(users: UserRosterExportUser[]): number[] {
  return [...new Set(users.map((user) => user.id))].sort(
    (left, right) => left - right
  );
}

function canonicalize(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(canonicalize);
  if (typeof value !== 'object' || value === null) return value;

  return Object.fromEntries(
    Object.entries(value)
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([key, child]) => [key, canonicalize(child)])
  );
}

function canonicalRosterContent(users: UserRosterExportUser[]): string {
  return JSON.stringify(
    users.map((user) =>
      canonicalize({
        id: user.id,
        pubkey: user.pubkey,
        email: user.email,
        name: user.name,
        email_encrypted: user.email_encrypted,
        name_encrypted: user.name_encrypted,
        user_type_id: user.user_type_id,
        user_type_name: user.user_type?.name,
        approved: user.approved,
        created_at: user.created_at,
        fields: user.fields,
        fields_encrypted: user.fields_encrypted,
      })
    )
  );
}

function encryptedValueTasks(
  users: UserRosterExportUser[]
): EncryptedValueTask[] {
  return users.flatMap((user) => {
    const tasks: EncryptedValueTask[] = [];

    if (hasCiphertext(user.email_encrypted)) {
      tasks.push({
        encrypted: user.email_encrypted,
        target: { kind: 'identity', userId: user.id, fieldName: 'email' },
      });
    }
    if (hasCiphertext(user.name_encrypted)) {
      tasks.push({
        encrypted: user.name_encrypted,
        target: { kind: 'identity', userId: user.id, fieldName: 'name' },
      });
    }

    for (const [fieldName, encrypted] of Object.entries(
      user.fields_encrypted ?? {}
    )) {
      if (!hasCiphertext(encrypted)) continue;
      tasks.push({
        encrypted,
        target: { kind: 'profile', userId: user.id, fieldName },
      });
    }

    return tasks;
  });
}

export function isPreparedUserRosterExportCurrent(
  snapshot: PreparedUserRosterExport,
  users: UserRosterExportUser[]
): boolean {
  const currentIds = requestedUserIds(users);
  return (
    currentIds.length === snapshot.requestUserIds.length &&
    currentIds.every(
      (userId, index) => userId === snapshot.requestUserIds[index]
    ) &&
    canonicalRosterContent(users) === preparedRosterContent.get(snapshot)
  );
}

export async function prepareUserRosterExport(
  input: UserRosterExportPreparationInput
): Promise<UserRosterExportPreparationResult> {
  const tasks = encryptedValueTasks(input.users);
  if (tasks.length > 0 && !input.decrypt) {
    return { ok: false, reason: 'decrypt-unavailable' };
  }

  const decrypted = await Promise.all(
    tasks.map(async (task) => {
      try {
        return {
          ...task,
          value: await input.decrypt!(task.encrypted),
        };
      } catch {
        return { ...task, value: null };
      }
    })
  );
  const failed = decrypted.find(({ value }) => value === null);
  if (failed) {
    return {
      ok: false,
      reason: 'decryption-failed',
      target: failed.target,
    };
  }

  const identities: Record<number, UserRosterIdentity | undefined> = {};
  const profileValues: Record<
    number,
    Record<string, string | null | undefined>
  > = Object.fromEntries(input.users.map((user) => [user.id, {}]));

  for (const field of decrypted) {
    if (field.target.kind === 'profile') {
      profileValues[field.target.userId][field.target.fieldName] = field.value;
      continue;
    }

    const identity = identities[field.target.userId] ?? {
      status: 'ready' as const,
      email: null,
      name: null,
    };
    identity[field.target.fieldName] = field.value;
    identities[field.target.userId] = identity;
  }

  const workbook = Object.freeze(
    buildUserRosterWorkbook({
      users: input.users,
      userTypes: input.userTypes,
      onboardingFields: input.onboardingFields,
      identities,
      profileValues,
      exportedAt: input.exportedAt,
      exportedBy: input.exportedBy,
    })
  );
  const requestUserIds = Object.freeze(requestedUserIds(input.users));
  const snapshot = Object.freeze({
    requestUserIds,
    userCount: input.users.length,
    pendingCount: input.users.filter((user) => !user.approved).length,
    workbook,
  });
  preparedRosterContent.set(snapshot, canonicalRosterContent(input.users));

  return { ok: true, snapshot };
}
