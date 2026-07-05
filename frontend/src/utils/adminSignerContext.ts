import { adminFetch } from './adminApi';
import {
  decryptField,
  hasNip04Support,
  type EncryptedField,
} from './encryption';

export interface AdminSignerDecryptedUser {
  id: number;
  approved?: boolean;
  user_type_id?: number | null;
  created_at?: string | null;
  pubkey_present?: boolean;
  email?: string;
  name?: string;
  fields?: Record<string, string>;
}

export interface AdminSignerDecryptedContext {
  source: 'admin-signer-user-roster';
  generated_at: string;
  users: AdminSignerDecryptedUser[];
  truncated: boolean;
  warnings: string[];
}

interface AdminUserForSignerContext {
  id: number;
  pubkey?: string | null;
  email?: string | null;
  name?: string | null;
  email_encrypted?: EncryptedField | null;
  name_encrypted?: EncryptedField | null;
  user_type_id?: number | null;
  approved?: boolean;
  created_at?: string | null;
  fields?: Record<string, unknown>;
  fields_encrypted?: Record<string, EncryptedField | null | undefined>;
}

interface AdminUsersResponse {
  users?: AdminUserForSignerContext[];
}

const DEFAULT_MAX_USERS = 25;
const DEFAULT_MAX_VALUE_CHARS = 500;
const DEFAULT_MAX_SERIALIZED_CHARS = 12_000;
const DECRYPT_BATCH_SIZE = 5;

async function mapInBatches<T, R>(
  items: T[],
  batchSize: number,
  mapper: (item: T) => Promise<R>
): Promise<R[]> {
  const results: R[] = [];
  for (let index = 0; index < items.length; index += batchSize) {
    const batch = items.slice(index, index + batchSize);
    results.push(...(await Promise.all(batch.map(mapper))));
  }
  return results;
}

function cleanValue(value: unknown): string | undefined {
  if (value === null || value === undefined) return undefined;
  const text = String(value).trim();
  if (!text) return undefined;
  return text.length > DEFAULT_MAX_VALUE_CHARS
    ? `${text.slice(0, DEFAULT_MAX_VALUE_CHARS)}...`
    : text;
}

async function decryptOrPlaintext(
  encrypted: EncryptedField | null | undefined,
  plaintext: unknown
): Promise<string | undefined> {
  if (encrypted?.ciphertext) {
    return cleanValue(await decryptField(encrypted));
  }
  return cleanValue(plaintext);
}

async function buildUserContext(
  user: AdminUserForSignerContext
): Promise<AdminSignerDecryptedUser> {
  const [email, name] = await Promise.all([
    decryptOrPlaintext(user.email_encrypted, user.email),
    decryptOrPlaintext(user.name_encrypted, user.name),
  ]);
  const fields: Record<string, string> = {};

  for (const [fieldName, value] of Object.entries(user.fields ?? {})) {
    const cleaned = cleanValue(value);
    if (cleaned) fields[fieldName] = cleaned;
  }

  const decryptedFields = await mapInBatches(
    Object.entries(user.fields_encrypted ?? {}),
    DECRYPT_BATCH_SIZE,
    async ([fieldName, encrypted]) =>
      [
        fieldName,
        encrypted?.ciphertext
          ? cleanValue(await decryptField(encrypted))
          : undefined,
      ] as const
  );
  for (const [fieldName, value] of decryptedFields) {
    if (value) fields[fieldName] = value;
  }

  return {
    id: user.id,
    approved: user.approved,
    user_type_id: user.user_type_id ?? null,
    created_at: user.created_at ?? null,
    pubkey_present: Boolean(user.pubkey),
    ...(email ? { email } : {}),
    ...(name ? { name } : {}),
    ...(Object.keys(fields).length > 0 ? { fields } : {}),
  };
}

function trimUsersToSerializedBudget(
  context: AdminSignerDecryptedContext,
  maxSerializedChars: number
): AdminSignerDecryptedContext {
  const users: AdminSignerDecryptedUser[] = [];
  for (const user of context.users) {
    const candidate = { ...context, users: [...users, user] };
    if (JSON.stringify(candidate).length > maxSerializedChars) {
      return {
        ...context,
        users,
        truncated: true,
        warnings: [...context.warnings, 'serialized_context_truncated'],
      };
    }
    users.push(user);
  }
  return context;
}

export async function buildAdminSignerDecryptedContext(options?: {
  maxUsers?: number;
  maxSerializedChars?: number;
}): Promise<AdminSignerDecryptedContext | null> {
  if (!hasNip04Support()) {
    return null;
  }

  const warnings: string[] = [];
  try {
    await window.nostr?.getPublicKey?.();
  } catch (error) {
    console.warn('Failed to trigger NIP-07 signer permission prompt:', error);
    warnings.push('signer_permission_prompt_failed');
  }

  let response: Response;
  try {
    response = await adminFetch('/admin/users');
  } catch (error) {
    console.warn('Failed to load Users for signer-decrypted context:', error);
    return null;
  }
  if (!response.ok) {
    return null;
  }

  const payload = (await response
    .json()
    .catch(() => ({}))) as AdminUsersResponse;
  const sourceUsers = Array.isArray(payload.users) ? payload.users : [];
  if (sourceUsers.length === 0) {
    return null;
  }

  const maxUsers = options?.maxUsers ?? DEFAULT_MAX_USERS;
  const selectedUsers = sourceUsers.slice(0, maxUsers);
  const users = await mapInBatches(
    selectedUsers,
    DECRYPT_BATCH_SIZE,
    buildUserContext
  );

  const context: AdminSignerDecryptedContext = {
    source: 'admin-signer-user-roster',
    generated_at: new Date().toISOString(),
    users,
    truncated: sourceUsers.length > selectedUsers.length,
    warnings,
  };

  return trimUsersToSerializedBudget(
    context,
    options?.maxSerializedChars ?? DEFAULT_MAX_SERIALIZED_CHARS
  );
}
