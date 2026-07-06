import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import type { TFunction } from 'i18next';
import { useTranslation } from 'react-i18next';
import {
  ArrowLeft,
  CalendarDays,
  Download,
  Fingerprint,
  Key,
  Loader2,
  Mail,
  RefreshCw,
  Shield,
  ShieldCheck,
  UserRound,
  UserRoundCheck,
  Users,
} from 'lucide-react';
import * as nip19 from 'nostr-tools/nip19';
import { Link, useParams } from 'react-router-dom';
import { AppHeader } from '../components/shared/AppHeader';
import {
  Badge,
  Button,
  Callout,
  SelectField,
  TextField,
} from '../components/ui';
import type {
  CustomField,
  FieldDefinitionResponse,
  FieldType,
  UserType,
} from '../types/onboarding';
import { STORAGE_KEYS } from '../types/onboarding';
import { adminFetch } from '../utils/adminApi';
import { decryptField, hasNip04Support } from '../utils/encryption';
import {
  buildUserRosterWorkbook,
  type EncryptedFieldValue,
  type UserRosterExportUser,
  type UserRosterIdentity,
} from '../utils/userRosterExport';

const EXPORT_DECRYPT_BATCH_SIZE = 5;

type ApprovalFilter = 'all' | 'pending' | 'approved';
type TypeFilter = 'all' | 'untyped' | string;

interface AdminUserSummary extends UserRosterExportUser {
  user_type?: UserType | null;
  fields?: Record<string, unknown>;
  fields_encrypted?: Record<string, EncryptedFieldValue | null | undefined>;
}

type IdentityState = UserRosterIdentity;

interface AdminUserFieldResponse extends FieldDefinitionResponse {
  placeholder?: string;
  options?: string[];
  encryption_enabled?: boolean;
  include_in_chat?: boolean;
}

interface UserProfileStatus {
  tone: 'success' | 'warning' | 'neutral';
  label: string;
  detail: string;
  missingRequired: number;
}

interface ProfileFieldValueState {
  status: 'decrypting' | 'ready' | 'failed' | 'unavailable';
  value: string | null;
}

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

function formatPubkeyShort(hexPubkey: string): string {
  try {
    const npub = nip19.npubEncode(hexPubkey);
    return `${npub.slice(0, 9)}...${npub.slice(-4)}`;
  } catch {
    return `${hexPubkey.slice(0, 8)}...`;
  }
}

function pubkeySearchValues(hexPubkey: string | null | undefined): string[] {
  if (!hexPubkey) return [];
  try {
    const npub = nip19.npubEncode(hexPubkey);
    return [hexPubkey, npub, formatPubkeyShort(hexPubkey)];
  } catch {
    return [hexPubkey, formatPubkeyShort(hexPubkey)];
  }
}

function formatJoinedDate(
  value: string | null | undefined,
  unknownLabel: string
): string {
  if (!value) return unknownLabel;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

function userDetailPath(userId: number): string {
  return `/admin/user-manager/${userId}`;
}

function formatFieldValue(value: unknown, t: TFunction): string | null {
  if (value === null || value === undefined) return null;
  if (typeof value === 'string') {
    const trimmed = value.trim();
    return trimmed || null;
  }
  if (typeof value === 'boolean') {
    return value
      ? t('adminUserManager.detail.booleanYes', 'Yes')
      : t('adminUserManager.detail.booleanNo', 'No');
  }
  if (Array.isArray(value)) {
    const joined = value
      .map((item) => formatFieldValue(item, t))
      .filter(Boolean)
      .join(', ');
    return joined || null;
  }
  if (typeof value === 'object') {
    try {
      return JSON.stringify(value);
    } catch {
      return String(value);
    }
  }
  return String(value);
}

async function parseErrorMessage(
  response: Response,
  fallback: string
): Promise<string> {
  try {
    const contentType = response.headers.get('content-type') || '';
    if (contentType.includes('application/json')) {
      const payload = await response.json();
      if (typeof payload?.detail === 'string' && payload.detail.trim()) {
        return payload.detail;
      }
      if (typeof payload?.message === 'string' && payload.message.trim()) {
        return payload.message;
      }
    } else {
      const text = await response.text();
      if (text.trim()) return text;
    }
  } catch {
    return fallback;
  }
  return fallback;
}

function mapFieldDefinition(field: AdminUserFieldResponse): CustomField {
  return {
    id: String(field.id),
    name: field.field_name,
    type: field.field_type as FieldType,
    required: Boolean(field.required),
    placeholder: field.placeholder,
    options: field.options,
    user_type_id: field.user_type_id,
    encryption_enabled: field.encryption_enabled ?? true,
    include_in_chat: field.include_in_chat ?? false,
    display_order: field.display_order ?? 0,
  };
}

function hasEncryptedIdentity(user: AdminUserSummary): boolean {
  return Boolean(
    user.email_encrypted?.ciphertext || user.name_encrypted?.ciphertext
  );
}

function fieldAppliesToUser(field: CustomField, user: AdminUserSummary) {
  return (
    field.user_type_id === null ||
    field.user_type_id === undefined ||
    field.user_type_id === user.user_type_id
  );
}

function hasProfileValue(user: AdminUserSummary, fieldName: string): boolean {
  const plainValue = user.fields?.[fieldName];
  if (
    plainValue !== null &&
    plainValue !== undefined &&
    String(plainValue).trim() !== ''
  ) {
    return true;
  }
  return Boolean(user.fields_encrypted?.[fieldName]?.ciphertext);
}

function profileStatusForUser(
  user: AdminUserSummary,
  fields: CustomField[],
  t: TFunction
): UserProfileStatus {
  const applicableFields = fields.filter((field) =>
    fieldAppliesToUser(field, user)
  );
  const requiredFields = applicableFields.filter((field) => field.required);
  const answeredCount = applicableFields.filter((field) =>
    hasProfileValue(user, field.name)
  ).length;
  const missingRequired = requiredFields.filter(
    (field) => !hasProfileValue(user, field.name)
  ).length;

  if (applicableFields.length === 0) {
    return {
      tone: 'neutral',
      label: t('adminUserManager.profile.noQuestions', 'No questions'),
      detail: t(
        'adminUserManager.profile.noQuestionsDetail',
        'No onboarding questions apply.'
      ),
      missingRequired,
    };
  }

  if (missingRequired > 0) {
    return {
      tone: 'warning',
      label: t('adminUserManager.profile.needsProfile', 'Needs profile'),
      detail:
        missingRequired === 1
          ? t(
              'adminUserManager.profile.missingRequiredOne',
              '1 required answer missing'
            )
          : t('adminUserManager.profile.missingRequiredMany', {
              count: missingRequired,
              defaultValue: '{{count}} required answers missing',
            }),
      missingRequired,
    };
  }

  if (answeredCount === 0) {
    return {
      tone: 'neutral',
      label: t('adminUserManager.profile.noProfileYet', 'No profile yet'),
      detail: t('adminUserManager.profile.noAnswersSaved', 'No answers saved.'),
      missingRequired,
    };
  }

  return {
    tone: 'success',
    label: t('adminUserManager.profile.ready', 'Profile ready'),
    detail:
      answeredCount === 1
        ? t('adminUserManager.profile.answersSavedOne', '1 answer saved')
        : t('adminUserManager.profile.answersSavedMany', {
            count: answeredCount,
            defaultValue: '{{count}} answers saved',
          }),
    missingRequired,
  };
}

function profileValueForField(
  user: AdminUserSummary,
  field: CustomField,
  values: Record<number, Record<string, ProfileFieldValueState | undefined>>,
  t: TFunction
): { value: string; helper: string | null; encrypted: boolean } {
  const plainValue = formatFieldValue(user.fields?.[field.name], t);
  if (plainValue) return { value: plainValue, helper: null, encrypted: false };

  const encrypted = user.fields_encrypted?.[field.name];
  if (encrypted?.ciphertext) {
    const state = values[user.id]?.[field.name];
    if (state?.status === 'ready' && state.value) {
      return {
        value: state.value,
        helper: t(
          'adminUserManager.detail.fieldUnlocked',
          'Encrypted answer unlocked in this browser.'
        ),
        encrypted: true,
      };
    }
    if (state?.status === 'decrypting') {
      return {
        value: t(
          'adminUserManager.detail.decryptingField',
          'Decrypting answer...'
        ),
        helper: null,
        encrypted: true,
      };
    }
    if (state?.status === 'unavailable') {
      return {
        value: t(
          'adminUserManager.detail.encryptedFieldUnavailable',
          'Encrypted answer needs a browser signer.'
        ),
        helper: null,
        encrypted: true,
      };
    }
    if (state?.status === 'failed') {
      return {
        value: t(
          'adminUserManager.detail.encryptedFieldFailed',
          'Encrypted answer could not be unlocked.'
        ),
        helper: null,
        encrypted: true,
      };
    }
    return {
      value: t(
        'adminUserManager.detail.encryptedFieldLocked',
        'Encrypted answer is locked.'
      ),
      helper: null,
      encrypted: true,
    };
  }

  return {
    value: t('adminUserManager.detail.notAnswered', 'Not answered'),
    helper: field.required
      ? t('adminUserManager.detail.requiredMissing', 'Required answer missing.')
      : null,
    encrypted: false,
  };
}

function identityForUser(
  user: AdminUserSummary,
  identities: Record<number, IdentityState | undefined>,
  t: TFunction
) {
  const identity = identities[user.id];
  const decryptedName = identity?.name?.trim() || null;
  const decryptedEmail = identity?.email?.trim() || null;
  const plainName = user.name?.trim() || null;
  const plainEmail = user.email?.trim() || null;
  const name = decryptedName || plainName;
  const email = decryptedEmail || plainEmail;
  const fallback = user.pubkey
    ? formatPubkeyShort(user.pubkey)
    : t('adminUserManager.userFallback', {
        id: user.id,
        defaultValue: 'User #{{id}}',
      });
  const primary = name || email || fallback;
  const secondary = name && email ? email : null;
  const encrypted = hasEncryptedIdentity(user);
  let helper: string | null = null;

  if (
    encrypted &&
    !decryptedName &&
    !decryptedEmail &&
    !plainName &&
    !plainEmail
  ) {
    if (identity?.status === 'decrypting') {
      helper = t(
        'adminUserManager.identity.decrypting',
        'Decrypting name and email...'
      );
    } else if (identity?.status === 'failed') {
      helper = t(
        'adminUserManager.identity.failed',
        'Encrypted details could not be unlocked.'
      );
    } else if (identity?.status === 'unavailable') {
      helper = t(
        'adminUserManager.identity.unavailable',
        'Encrypted details need a browser signer.'
      );
    } else {
      helper = t(
        'adminUserManager.identity.locked',
        'Encrypted details are locked.'
      );
    }
  }

  return {
    primary,
    secondary,
    name,
    email,
    helper,
    searchText: [
      primary,
      secondary,
      helper,
      ...pubkeySearchValues(user.pubkey),
      `#${user.id}`,
    ]
      .filter(Boolean)
      .join(' ')
      .toLowerCase(),
  };
}

function downloadBlob(blob: Blob, filename: string) {
  const url = window.URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  window.setTimeout(() => {
    window.URL.revokeObjectURL(url);
  }, 0);
  document.body.removeChild(anchor);
}

function Metric({
  label,
  value,
  detail,
}: {
  label: string;
  value: number;
  detail: string;
}) {
  return (
    <section
      aria-label={label}
      className="rounded-lg border border-border bg-surface-raised px-4 py-3"
    >
      <p className="text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
        {label}
      </p>
      <p className="mt-2 flex items-baseline gap-2">
        <span className="text-2xl font-semibold text-text">{value}</span>
        <span className="text-xs text-text-muted">{detail}</span>
      </p>
    </section>
  );
}

function DetailItem({
  label,
  icon,
  children,
}: {
  label: string;
  icon?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="rounded-lg border border-border bg-surface-overlay px-4 py-3">
      <dt className="flex items-center gap-2 text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
        {icon}
        {label}
      </dt>
      <dd className="mt-2 break-words text-sm font-medium text-text">
        {children}
      </dd>
    </div>
  );
}

export function AdminUserManager() {
  const { t } = useTranslation();
  const { userId } = useParams<{ userId?: string }>();
  const [users, setUsers] = useState<AdminUserSummary[]>([]);
  const [userTypes, setUserTypes] = useState<UserType[]>([]);
  const [fields, setFields] = useState<CustomField[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [approvalFilter, setApprovalFilter] = useState<ApprovalFilter>('all');
  const [typeFilter, setTypeFilter] = useState<TypeFilter>('all');
  const [query, setQuery] = useState('');
  const [identities, setIdentities] = useState<
    Record<number, IdentityState | undefined>
  >({});
  const [identityDecryptNonce, setIdentityDecryptNonce] = useState(0);
  const [approvalUpdatingIds, setApprovalUpdatingIds] = useState<Set<number>>(
    new Set()
  );
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [exportMessage, setExportMessage] = useState<string | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);
  const [profileValues, setProfileValues] = useState<
    Record<number, Record<string, ProfileFieldValueState | undefined>>
  >({});
  const decryptRunIdRef = useRef(0);
  const profileDecryptRunIdRef = useRef(0);

  const detailRequested = userId !== undefined;
  const parsedUserId = userId ? Number(userId) : null;
  const detailUserId =
    parsedUserId !== null && Number.isInteger(parsedUserId) && parsedUserId > 0
      ? parsedUserId
      : null;

  const loadDashboard = useCallback(async () => {
    setLoading(true);
    setLoadError(null);

    try {
      const [usersResponse, typesResponse, fieldsResponse] = await Promise.all([
        adminFetch('/admin/users'),
        adminFetch('/admin/user-types'),
        adminFetch('/admin/user-fields'),
      ]);

      const errors: string[] = [];

      if (!usersResponse.ok) {
        errors.push(
          await parseErrorMessage(
            usersResponse,
            t('adminUserManager.errors.loadUsers', 'Failed to load users.')
          )
        );
      }
      if (!typesResponse.ok) {
        errors.push(
          await parseErrorMessage(
            typesResponse,
            t(
              'adminUserManager.errors.loadUserTypes',
              'Failed to load user types.'
            )
          )
        );
      }
      if (!fieldsResponse.ok) {
        errors.push(
          await parseErrorMessage(
            fieldsResponse,
            t(
              'adminUserManager.errors.loadQuestions',
              'Failed to load onboarding questions.'
            )
          )
        );
      }

      if (errors.length > 0) {
        setLoadError(errors.join(' '));
        return;
      }

      const [usersData, typesData, fieldsData] = await Promise.all([
        usersResponse.json(),
        typesResponse.json(),
        fieldsResponse.json(),
      ]);

      setUsers((usersData.users || []) as AdminUserSummary[]);
      setUserTypes((typesData.types || []) as UserType[]);
      setFields((fieldsData.fields || []).map(mapFieldDefinition));
    } catch (error) {
      setLoadError(
        error instanceof Error
          ? error.message
          : t('adminUserManager.errors.loadUsers', 'Failed to load users.')
      );
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void loadDashboard();
  }, [loadDashboard]);

  useEffect(() => {
    const usersWithEncryptedIdentity = users.filter(hasEncryptedIdentity);
    if (usersWithEncryptedIdentity.length === 0) {
      setIdentities({});
      return;
    }

    const runId = decryptRunIdRef.current + 1;
    decryptRunIdRef.current = runId;

    setIdentities((previous) => {
      const next = { ...previous };
      for (const user of usersWithEncryptedIdentity) {
        if (!next[user.id] || identityDecryptNonce > 0) {
          next[user.id] = { status: 'decrypting', email: null, name: null };
        }
      }
      return next;
    });

    if (!hasNip04Support()) {
      setIdentities((previous) => {
        const next = { ...previous };
        for (const user of usersWithEncryptedIdentity) {
          next[user.id] = { status: 'unavailable', email: null, name: null };
        }
        return next;
      });
      return;
    }

    void mapInBatches(
      usersWithEncryptedIdentity,
      EXPORT_DECRYPT_BATCH_SIZE,
      async (user) => {
        try {
          const [email, name] = await Promise.all([
            decryptField(user.email_encrypted),
            decryptField(user.name_encrypted),
          ]);
          return {
            userId: user.id,
            identity: {
              status: email || name ? 'ready' : 'failed',
              email,
              name,
            } satisfies IdentityState,
          };
        } catch {
          return {
            userId: user.id,
            identity: {
              status: 'failed',
              email: null,
              name: null,
            } satisfies IdentityState,
          };
        }
      }
    ).then((entries) => {
      if (decryptRunIdRef.current !== runId) return;
      setIdentities((previous) => {
        const next = { ...previous };
        for (const entry of entries) {
          next[entry.userId] = entry.identity;
        }
        return next;
      });
    });
  }, [identityDecryptNonce, users]);

  const profileStatuses = useMemo(
    () =>
      Object.fromEntries(
        users.map((user) => [user.id, profileStatusForUser(user, fields, t)])
      ) as Record<number, UserProfileStatus>,
    [fields, t, users]
  );

  const userTypeOptions = useMemo(
    () =>
      [...userTypes].sort(
        (a, b) =>
          (a.display_order ?? 0) - (b.display_order ?? 0) ||
          a.name.localeCompare(b.name)
      ),
    [userTypes]
  );

  const metrics = useMemo(() => {
    const pending = users.filter((user) => !user.approved).length;
    const incomplete = users.filter(
      (user) => profileStatuses[user.id]?.missingRequired > 0
    ).length;
    return {
      total: users.length,
      pending,
      approved: users.length - pending,
      incomplete,
    };
  }, [profileStatuses, users]);

  const hasActiveFilters =
    approvalFilter !== 'all' || typeFilter !== 'all' || query.trim() !== '';

  const filteredUsers = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return users.filter((user) => {
      if (approvalFilter === 'pending' && user.approved) return false;
      if (approvalFilter === 'approved' && !user.approved) return false;
      if (typeFilter === 'untyped' && user.user_type_id != null) {
        return false;
      }
      if (
        typeFilter !== 'all' &&
        typeFilter !== 'untyped' &&
        String(user.user_type_id) !== typeFilter
      ) {
        return false;
      }
      if (!normalizedQuery) return true;

      const identity = identityForUser(user, identities, t);
      const typeName =
        user.user_type?.name ??
        t('adminUserManager.noUserType', 'No User Type');
      return [identity.searchText, typeName.toLowerCase()]
        .join(' ')
        .includes(normalizedQuery);
    });
  }, [approvalFilter, identities, query, t, typeFilter, users]);

  const selectedUser = useMemo(
    () =>
      detailUserId === null
        ? null
        : (users.find((user) => user.id === detailUserId) ?? null),
    [detailUserId, users]
  );

  const selectedUserFields = useMemo(
    () =>
      selectedUser
        ? fields
            .filter((field) => fieldAppliesToUser(field, selectedUser))
            .sort(
              (a, b) =>
                (a.display_order ?? 0) - (b.display_order ?? 0) ||
                a.name.localeCompare(b.name)
            )
        : [],
    [fields, selectedUser]
  );

  useEffect(() => {
    if (!selectedUser) return;

    const encryptedFields = selectedUserFields
      .map((field) => ({
        field,
        encrypted: selectedUser.fields_encrypted?.[field.name],
      }))
      .filter(({ encrypted }) => Boolean(encrypted?.ciphertext));

    if (encryptedFields.length === 0) return;

    const runId = profileDecryptRunIdRef.current + 1;
    profileDecryptRunIdRef.current = runId;

    setProfileValues((previous) => {
      const userValues = { ...(previous[selectedUser.id] ?? {}) };
      for (const { field } of encryptedFields) {
        userValues[field.name] = { status: 'decrypting', value: null };
      }
      return { ...previous, [selectedUser.id]: userValues };
    });

    if (!hasNip04Support()) {
      setProfileValues((previous) => {
        const userValues = { ...(previous[selectedUser.id] ?? {}) };
        for (const { field } of encryptedFields) {
          userValues[field.name] = { status: 'unavailable', value: null };
        }
        return { ...previous, [selectedUser.id]: userValues };
      });
      return;
    }

    void mapInBatches(
      encryptedFields,
      EXPORT_DECRYPT_BATCH_SIZE,
      async ({ field, encrypted }) => {
        try {
          const value = await decryptField(encrypted);
          return {
            fieldName: field.name,
            state: {
              status: value ? 'ready' : 'failed',
              value,
            } satisfies ProfileFieldValueState,
          };
        } catch {
          return {
            fieldName: field.name,
            state: {
              status: 'failed',
              value: null,
            } satisfies ProfileFieldValueState,
          };
        }
      }
    ).then((entries) => {
      if (profileDecryptRunIdRef.current !== runId) return;
      setProfileValues((previous) => {
        const userValues = { ...(previous[selectedUser.id] ?? {}) };
        for (const entry of entries) {
          userValues[entry.fieldName] = entry.state;
        }
        return { ...previous, [selectedUser.id]: userValues };
      });
    });
  }, [identityDecryptNonce, selectedUser, selectedUserFields]);

  const handleUnlockIdentities = async () => {
    if (hasNip04Support()) {
      try {
        await window.nostr?.getPublicKey?.();
      } catch (error) {
        console.warn('Failed to prompt for signer access:', error);
      }
    }
    setIdentityDecryptNonce((current) => current + 1);
  };

  const handleApproveUser = async (user: AdminUserSummary) => {
    const identity = identityForUser(user, identities, t);
    setActionMessage(null);
    setActionError(null);
    setApprovalUpdatingIds((previous) => {
      const next = new Set(previous);
      next.add(user.id);
      return next;
    });

    try {
      const response = await adminFetch(`/users/${user.id}`, {
        method: 'PUT',
        body: JSON.stringify({ approved: true }),
      });

      if (!response.ok) {
        setActionError(
          await parseErrorMessage(
            response,
            t(
              'adminUserManager.errors.approvalUpdate',
              'User approval could not be updated.'
            )
          )
        );
        return;
      }

      const updated = (await response.json()) as AdminUserSummary;
      setUsers((previous) =>
        previous.map((candidate) =>
          candidate.id === user.id ? { ...candidate, ...updated } : candidate
        )
      );
      setActionMessage(
        t('adminUserManager.approvalSuccess', {
          name: identity.primary,
          defaultValue: '{{name}} approved.',
        })
      );
    } catch (error) {
      setActionError(
        error instanceof Error
          ? error.message
          : t(
              'adminUserManager.errors.approvalUpdate',
              'User approval could not be updated.'
            )
      );
    } finally {
      setApprovalUpdatingIds((previous) => {
        const next = new Set(previous);
        next.delete(user.id);
        return next;
      });
    }
  };

  const collectExportProfileValues = async (
    exportUsers: AdminUserSummary[]
  ): Promise<Record<number, Record<string, string | null>>> => {
    if (!hasNip04Support()) return {};

    const values = Object.fromEntries(
      exportUsers.map((user) => [user.id, {}])
    ) as Record<number, Record<string, string | null>>;
    const encryptedFields = exportUsers.flatMap((user) =>
      Object.entries(user.fields_encrypted ?? {}).map(
        ([fieldName, encrypted]) => ({
          userId: user.id,
          fieldName,
          encrypted,
        })
      )
    );

    const decryptedFields = await mapInBatches(
      encryptedFields,
      EXPORT_DECRYPT_BATCH_SIZE,
      async ({ userId, fieldName, encrypted }) => ({
        userId,
        fieldName,
        value: await decryptField(encrypted),
      })
    );

    for (const field of decryptedFields) {
      values[field.userId][field.fieldName] = field.value;
    }

    return values;
  };

  const decryptIdentityForExport = async (
    user: AdminUserSummary
  ): Promise<IdentityState | undefined> => {
    const existing = identities[user.id];
    if (existing?.status === 'ready') return existing;
    if (!hasEncryptedIdentity(user)) return existing;

    if (!hasNip04Support()) {
      return { status: 'unavailable', email: null, name: null };
    }

    const [email, name] = await Promise.all([
      decryptField(user.email_encrypted),
      decryptField(user.name_encrypted),
    ]);

    return {
      status: email || name ? 'ready' : 'failed',
      email,
      name,
    };
  };

  const collectExportIdentities = async (
    exportUsers: AdminUserSummary[]
  ): Promise<Record<number, IdentityState | undefined>> => {
    const entries = await mapInBatches(
      exportUsers,
      EXPORT_DECRYPT_BATCH_SIZE,
      async (user) => [user.id, await decryptIdentityForExport(user)] as const
    );
    return Object.fromEntries(entries);
  };

  const handleExportVisibleRoster = async () => {
    setExportMessage(null);
    setExportError(null);
    setExporting(true);

    try {
      if (hasNip04Support()) {
        try {
          await window.nostr?.getPublicKey?.();
        } catch (error) {
          console.warn(
            'Failed to prompt for signer access before export:',
            error
          );
        }
      }

      const exportedAt = new Date();
      const [exportIdentities, profileValues] = await Promise.all([
        collectExportIdentities(filteredUsers),
        collectExportProfileValues(filteredUsers),
      ]);
      const workbook = buildUserRosterWorkbook({
        users: filteredUsers,
        userTypes,
        onboardingFields: fields,
        identities: exportIdentities,
        profileValues,
        exportedAt,
        exportedBy: localStorage.getItem(STORAGE_KEYS.ADMIN_PUBKEY),
      });

      const auditResponse = await adminFetch('/admin/users/roster-export', {
        method: 'POST',
        body: JSON.stringify({
          filename: workbook.filename,
          user_count: filteredUsers.length,
          pending_count: filteredUsers.filter((user) => !user.approved).length,
          includes_decrypted_browser_values: workbook.includesDecryptedValues,
        }),
      });

      if (!auditResponse.ok) {
        setExportError(
          await parseErrorMessage(
            auditResponse,
            t(
              'adminUserManager.errors.exportAudit',
              'User roster export could not be audited.'
            )
          )
        );
        return;
      }

      downloadBlob(workbook.blob, workbook.filename);
      setExportMessage(
        t(
          'adminUserManager.exportSuccess',
          'User roster spreadsheet downloaded.'
        )
      );
    } catch (error) {
      setExportError(
        error instanceof Error
          ? error.message
          : t(
              'adminUserManager.errors.exportRoster',
              'Failed to export user roster.'
            )
      );
    } finally {
      setExporting(false);
    }
  };

  const hasEncryptedUsers = users.some(hasEncryptedIdentity);

  if (detailRequested) {
    const selectedIdentity = selectedUser
      ? identityForUser(selectedUser, identities, t)
      : null;
    const selectedProfile = selectedUser
      ? profileStatuses[selectedUser.id]
      : undefined;
    const updating = selectedUser
      ? approvalUpdatingIds.has(selectedUser.id)
      : false;
    const selectedUserHasEncryptedDetails = selectedUser
      ? hasEncryptedIdentity(selectedUser) ||
        selectedUserFields.some((field) =>
          Boolean(selectedUser.fields_encrypted?.[field.name]?.ciphertext)
        )
      : false;

    return (
      <div className="min-h-screen bg-surface">
        <AppHeader
          showBackButton
          backTo="/admin/user-manager"
          backLabel={t(
            'adminUserManager.detail.backToUserManager',
            'Back to User Manager'
          )}
        />
        <main className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8">
          <Link
            to="/admin/user-manager"
            className="focus-ring inline-flex w-fit items-center gap-2 rounded-lg text-sm font-medium text-text-secondary hover:text-text"
            aria-label={t(
              'adminUserManager.detail.backToRoster',
              'Back to user roster'
            )}
          >
            <ArrowLeft className="h-4 w-4" aria-hidden="true" />
            {t('adminUserManager.detail.backToRoster', 'Back to user roster')}
          </Link>

          {loading ? (
            <div
              role="status"
              aria-label={t(
                'adminUserManager.loadingLabel',
                'Loading user roster'
              )}
              className="flex items-center gap-2 rounded-lg border border-border bg-surface-raised px-5 py-10 text-sm text-text-muted"
            >
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              {t('adminUserManager.loadingUsers', 'Loading users...')}
            </div>
          ) : loadError ? (
            <Callout
              label={t(
                'adminUserManager.callouts.loadFailed',
                'User roster load failed'
              )}
              tone="error"
              aria-live="assertive"
              aria-atomic="true"
            >
              <p className="text-error">{loadError}</p>
            </Callout>
          ) : !selectedUser || !selectedIdentity ? (
            <section className="rounded-lg border border-border bg-surface-raised px-5 py-8">
              <div className="label mb-2">
                {t('adminUserManager.detail.eyebrow', 'User details')}
              </div>
              <h1 className="heading-xl">
                {t('adminUserManager.detail.notFoundTitle', 'User not found')}
              </h1>
              <p className="mt-3 max-w-xl text-sm leading-6 text-text-muted">
                {t(
                  'adminUserManager.detail.notFoundBody',
                  'This user is not in the current admin roster.'
                )}
              </p>
            </section>
          ) : (
            <>
              <section className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
                <div className="max-w-3xl">
                  <div className="label mb-2">
                    {t('adminUserManager.detail.eyebrow', 'User details')}
                  </div>
                  <h1 className="heading-xl">{selectedIdentity.primary}</h1>
                  <p className="mt-3 max-w-2xl text-sm leading-6 text-text-muted">
                    {t(
                      'adminUserManager.detail.subtitle',
                      'Review this user status, profile answers, and access details.'
                    )}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  {selectedUserHasEncryptedDetails && (
                    <Button
                      variant="secondary"
                      onClick={handleUnlockIdentities}
                      leadingIcon={
                        <Key className="h-4 w-4" aria-hidden="true" />
                      }
                    >
                      {t('adminUserManager.unlockDetails', 'Unlock details')}
                    </Button>
                  )}
                  <Button
                    variant="secondary"
                    onClick={loadDashboard}
                    disabled={loading}
                    leadingIcon={
                      <RefreshCw
                        className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`}
                        aria-hidden="true"
                      />
                    }
                  >
                    {t('adminUserManager.refreshRoster', 'Refresh roster')}
                  </Button>
                  {!selectedUser.approved && (
                    <Button
                      onClick={() => handleApproveUser(selectedUser)}
                      disabled={updating}
                      leadingIcon={
                        updating ? (
                          <Loader2
                            className="h-4 w-4 animate-spin"
                            aria-hidden="true"
                          />
                        ) : (
                          <ShieldCheck className="h-4 w-4" aria-hidden="true" />
                        )
                      }
                      aria-label={t('adminUserManager.actions.approveUser', {
                        name: selectedIdentity.primary,
                        defaultValue: 'Approve {{name}}',
                      })}
                    >
                      {t('adminUserManager.actions.approve', 'Approve')}
                    </Button>
                  )}
                </div>
              </section>

              {actionMessage && (
                <Callout
                  label={t(
                    'adminUserManager.callouts.approvalUpdated',
                    'User approval updated'
                  )}
                  tone="success"
                  aria-live="polite"
                  aria-atomic="true"
                >
                  <p className="text-success">{actionMessage}</p>
                </Callout>
              )}
              {actionError && (
                <Callout
                  label={t(
                    'adminUserManager.callouts.approvalFailed',
                    'User approval update failed'
                  )}
                  tone="error"
                  aria-live="assertive"
                  aria-atomic="true"
                >
                  <p className="text-error">{actionError}</p>
                </Callout>
              )}

              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <section
                  aria-label={t(
                    'adminUserManager.detail.approvalStatus',
                    'Approval status'
                  )}
                  className="rounded-lg border border-border bg-surface-raised px-4 py-3"
                >
                  <p className="text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
                    {t('adminUserManager.columns.approval', 'Approval')}
                  </p>
                  <div className="mt-2">
                    {selectedUser.approved ? (
                      <Badge
                        tone="success"
                        leadingIcon={
                          <ShieldCheck
                            className="h-3.5 w-3.5"
                            aria-hidden="true"
                          />
                        }
                      >
                        {t('adminUserManager.status.approved', 'Approved')}
                      </Badge>
                    ) : (
                      <Badge
                        tone="warning"
                        leadingIcon={
                          <Shield className="h-3.5 w-3.5" aria-hidden="true" />
                        }
                      >
                        {t('adminUserManager.status.pending', 'Pending')}
                      </Badge>
                    )}
                  </div>
                  <p className="mt-2 text-xs text-text-muted">
                    {selectedUser.approved
                      ? t(
                          'adminUserManager.metrics.approvedDetail',
                          'can enter chat'
                        )
                      : t(
                          'adminUserManager.detail.waitingApproval',
                          'waiting for approval'
                        )}
                  </p>
                </section>
                <section
                  aria-label={t(
                    'adminUserManager.columns.userType',
                    'User Type'
                  )}
                  className="rounded-lg border border-border bg-surface-raised px-4 py-3"
                >
                  <p className="text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
                    {t('adminUserManager.columns.userType', 'User Type')}
                  </p>
                  <p className="mt-2 text-sm font-medium text-text">
                    {selectedUser.user_type?.name ??
                      t('adminUserManager.noUserType', 'No User Type')}
                  </p>
                </section>
                <section
                  aria-label={t(
                    'adminUserManager.columns.userProfile',
                    'User Profile'
                  )}
                  className="rounded-lg border border-border bg-surface-raised px-4 py-3"
                >
                  <p className="text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
                    {t('adminUserManager.columns.userProfile', 'User Profile')}
                  </p>
                  <div className="mt-2 space-y-1">
                    <Badge tone={selectedProfile?.tone ?? 'neutral'}>
                      {selectedProfile?.label ??
                        t('adminUserManager.unknown', 'Unknown')}
                    </Badge>
                    {selectedProfile?.detail && (
                      <p className="text-xs text-text-muted">
                        {selectedProfile.detail}
                      </p>
                    )}
                  </div>
                </section>
                <section
                  aria-label={t('adminUserManager.columns.joined', 'Joined')}
                  className="rounded-lg border border-border bg-surface-raised px-4 py-3"
                >
                  <p className="text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
                    {t('adminUserManager.columns.joined', 'Joined')}
                  </p>
                  <p className="mt-2 text-sm font-medium text-text">
                    {formatJoinedDate(
                      selectedUser.created_at,
                      t('adminUserManager.unknown', 'Unknown')
                    )}
                  </p>
                </section>
              </div>

              <section
                aria-labelledby="user-detail-identity-title"
                className="rounded-lg border border-border bg-surface-raised px-4 py-4 sm:px-5"
              >
                <h2 id="user-detail-identity-title" className="heading-sm">
                  {t('adminUserManager.detail.identityTitle', 'Identity')}
                </h2>
                <dl className="mt-4 grid gap-3 md:grid-cols-2">
                  <DetailItem
                    label={t('adminUserManager.detail.name', 'Name')}
                    icon={
                      <UserRound className="h-3.5 w-3.5" aria-hidden="true" />
                    }
                  >
                    {selectedIdentity.name ??
                      t(
                        'adminUserManager.detail.nameUnavailable',
                        'Not available'
                      )}
                  </DetailItem>
                  <DetailItem
                    label={t('adminUserManager.detail.email', 'Email')}
                    icon={<Mail className="h-3.5 w-3.5" aria-hidden="true" />}
                  >
                    {selectedIdentity.email ??
                      selectedIdentity.helper ??
                      t(
                        'adminUserManager.detail.emailUnavailable',
                        'Not available'
                      )}
                  </DetailItem>
                  <DetailItem
                    label={t('adminUserManager.detail.userId', 'User ID')}
                    icon={
                      <Fingerprint className="h-3.5 w-3.5" aria-hidden="true" />
                    }
                  >
                    #{selectedUser.id}
                  </DetailItem>
                  <DetailItem
                    label={t('adminUserManager.columns.joined', 'Joined')}
                    icon={
                      <CalendarDays
                        className="h-3.5 w-3.5"
                        aria-hidden="true"
                      />
                    }
                  >
                    {formatJoinedDate(
                      selectedUser.created_at,
                      t('adminUserManager.unknown', 'Unknown')
                    )}
                  </DetailItem>
                  <div className="rounded-lg border border-border bg-surface-overlay px-4 py-3 md:col-span-2">
                    <dt className="text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
                      {t('adminUserManager.detail.publicKey', 'Public key')}
                    </dt>
                    <dd className="mt-2 break-all font-mono text-xs text-text">
                      {selectedUser.pubkey ??
                        t(
                          'adminUserManager.detail.noPublicKey',
                          'No public key'
                        )}
                    </dd>
                  </div>
                </dl>
              </section>

              <section
                aria-labelledby="user-detail-fields-title"
                className="rounded-lg border border-border bg-surface-raised"
              >
                <div className="border-b border-border px-4 py-4 sm:px-5">
                  <h2 id="user-detail-fields-title" className="heading-sm">
                    {t('adminUserManager.detail.fieldsTitle', 'Profile fields')}
                  </h2>
                  <p className="mt-1 text-sm text-text-muted">
                    {t('adminUserManager.detail.fieldsShown', {
                      count: selectedUserFields.length,
                      defaultValue: '{{count}} fields apply to this user.',
                    })}
                  </p>
                </div>
                {selectedUserFields.length === 0 ? (
                  <div className="px-5 py-8 text-sm text-text-muted">
                    {t(
                      'adminUserManager.detail.noFields',
                      'No onboarding fields apply to this user.'
                    )}
                  </div>
                ) : (
                  <div className="divide-y divide-border">
                    {selectedUserFields.map((field) => {
                      const fieldValue = profileValueForField(
                        selectedUser,
                        field,
                        profileValues,
                        t
                      );
                      return (
                        <article
                          key={field.id}
                          className="grid gap-4 px-4 py-4 sm:px-5 md:grid-cols-[minmax(12rem,18rem)_1fr]"
                        >
                          <div>
                            <h3 className="text-sm font-semibold text-text">
                              {field.name}
                            </h3>
                            <div className="mt-2 flex flex-wrap gap-2">
                              <Badge
                                tone={field.required ? 'warning' : 'neutral'}
                              >
                                {field.required
                                  ? t(
                                      'adminUserManager.detail.required',
                                      'Required'
                                    )
                                  : t(
                                      'adminUserManager.detail.optional',
                                      'Optional'
                                    )}
                              </Badge>
                              <Badge
                                tone={
                                  fieldValue.encrypted ? 'warning' : 'neutral'
                                }
                              >
                                {fieldValue.encrypted
                                  ? t(
                                      'adminUserManager.detail.encrypted',
                                      'Encrypted'
                                    )
                                  : t('adminUserManager.detail.plain', 'Plain')}
                              </Badge>
                              {field.include_in_chat && (
                                <Badge tone="success">
                                  {t(
                                    'adminUserManager.detail.chatContext',
                                    'Chat context'
                                  )}
                                </Badge>
                              )}
                            </div>
                          </div>
                          <div>
                            <p className="whitespace-pre-wrap break-words text-sm font-medium text-text">
                              {fieldValue.value}
                            </p>
                            {fieldValue.helper && (
                              <p className="mt-1 text-xs text-text-muted">
                                {fieldValue.helper}
                              </p>
                            )}
                          </div>
                        </article>
                      );
                    })}
                  </div>
                )}
              </section>
            </>
          )}
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-surface">
      <AppHeader
        showBackButton
        backTo="/admin/setup"
        backLabel={t('adminUserManager.backToAdmin', 'Back to Admin Dashboard')}
      />
      <main className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8">
        <section className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div className="max-w-3xl">
            <div className="label mb-2">
              {t('adminUserManager.eyebrow', 'Admin operations')}
            </div>
            <h1 className="heading-xl">
              {t('adminUserManager.title', 'User Manager')}
            </h1>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-text-muted">
              {t(
                'adminUserManager.subtitle',
                'Review users, understand their status, and approve access from one simple dashboard.'
              )}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {hasEncryptedUsers && (
              <Button
                variant="secondary"
                onClick={handleUnlockIdentities}
                leadingIcon={<Key className="h-4 w-4" aria-hidden="true" />}
              >
                {t('adminUserManager.unlockDetails', 'Unlock details')}
              </Button>
            )}
            <Button
              variant="secondary"
              onClick={loadDashboard}
              disabled={loading}
              leadingIcon={
                <RefreshCw
                  className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`}
                  aria-hidden="true"
                />
              }
            >
              {t('adminUserManager.refreshRoster', 'Refresh roster')}
            </Button>
            <Button
              onClick={handleExportVisibleRoster}
              disabled={exporting || filteredUsers.length === 0}
              leadingIcon={
                exporting ? (
                  <Loader2
                    className="h-4 w-4 animate-spin"
                    aria-hidden="true"
                  />
                ) : (
                  <Download className="h-4 w-4" aria-hidden="true" />
                )
              }
            >
              {t('adminUserManager.exportVisible', 'Export visible roster')}
            </Button>
          </div>
        </section>

        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Metric
            label={t('adminUserManager.metrics.total', 'Total users')}
            value={metrics.total}
            detail={t('adminUserManager.metrics.totalDetail', 'in roster')}
          />
          <Metric
            label={t(
              'adminUserManager.metrics.pendingApproval',
              'Pending approval'
            )}
            value={metrics.pending}
            detail={t('adminUserManager.metrics.pendingDetail', {
              count: metrics.pending,
              defaultValue: '{{count}} pending',
            })}
          />
          <Metric
            label={t('adminUserManager.metrics.approved', 'Approved')}
            value={metrics.approved}
            detail={t(
              'adminUserManager.metrics.approvedDetail',
              'can enter chat'
            )}
          />
          <Metric
            label={t(
              'adminUserManager.metrics.incompleteProfiles',
              'Incomplete profiles'
            )}
            value={metrics.incomplete}
            detail={t(
              'adminUserManager.metrics.incompleteDetail',
              'need required answers'
            )}
          />
        </div>

        {loadError && (
          <Callout
            label={t(
              'adminUserManager.callouts.loadFailed',
              'User roster load failed'
            )}
            tone="error"
            aria-live="assertive"
            aria-atomic="true"
          >
            <p className="text-error">{loadError}</p>
          </Callout>
        )}
        {actionMessage && (
          <Callout
            label={t(
              'adminUserManager.callouts.approvalUpdated',
              'User approval updated'
            )}
            tone="success"
            aria-live="polite"
            aria-atomic="true"
          >
            <p className="text-success">{actionMessage}</p>
          </Callout>
        )}
        {actionError && (
          <Callout
            label={t(
              'adminUserManager.callouts.approvalFailed',
              'User approval update failed'
            )}
            tone="error"
            aria-live="assertive"
            aria-atomic="true"
          >
            <p className="text-error">{actionError}</p>
          </Callout>
        )}
        {exportMessage && (
          <Callout
            label={t(
              'adminUserManager.callouts.exportReady',
              'User roster export ready'
            )}
            tone="success"
            aria-live="polite"
            aria-atomic="true"
          >
            <p className="text-success">{exportMessage}</p>
          </Callout>
        )}
        {exportError && (
          <Callout
            label={t(
              'adminUserManager.callouts.exportFailed',
              'User roster export failed'
            )}
            tone="error"
            aria-live="assertive"
            aria-atomic="true"
          >
            <p className="text-error">{exportError}</p>
          </Callout>
        )}

        <section
          aria-labelledby="user-manager-table-title"
          className="rounded-lg border border-border bg-surface-raised"
        >
          <div className="border-b border-border px-4 py-4 sm:px-5">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
              <div>
                <h2 id="user-manager-table-title" className="heading-sm">
                  {t('adminUserManager.rosterTitle', 'User roster')}
                </h2>
                <p className="mt-1 text-sm text-text-muted">
                  {t('adminUserManager.rosterShown', {
                    shown: filteredUsers.length,
                    total: users.length,
                    defaultValue: '{{shown}} shown from {{total}} total.',
                  })}
                </p>
              </div>
              <div className="grid gap-3 sm:grid-cols-3 lg:min-w-[42rem]">
                <TextField
                  label={t('adminUserManager.filters.search', 'Search users')}
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder={t(
                    'adminUserManager.filters.searchPlaceholder',
                    'Name, email, public key, or #ID'
                  )}
                />
                <SelectField
                  label={t(
                    'adminUserManager.filters.approvalStatus',
                    'Approval status'
                  )}
                  value={approvalFilter}
                  onChange={(event) =>
                    setApprovalFilter(event.target.value as ApprovalFilter)
                  }
                >
                  <option value="all">
                    {t(
                      'adminUserManager.filters.allApprovalStates',
                      'All approval states'
                    )}
                  </option>
                  <option value="pending">
                    {t(
                      'adminUserManager.filters.pendingApproval',
                      'Pending approval'
                    )}
                  </option>
                  <option value="approved">
                    {t('adminUserManager.filters.approved', 'Approved')}
                  </option>
                </SelectField>
                <SelectField
                  label={t('adminUserManager.columns.userType', 'User Type')}
                  value={typeFilter}
                  onChange={(event) => setTypeFilter(event.target.value)}
                >
                  <option value="all">
                    {t(
                      'adminUserManager.filters.allUserTypes',
                      'All User Types'
                    )}
                  </option>
                  <option value="untyped">
                    {t('adminUserManager.noUserType', 'No User Type')}
                  </option>
                  {userTypeOptions.map((type) => (
                    <option key={type.id} value={String(type.id)}>
                      {type.name}
                    </option>
                  ))}
                </SelectField>
              </div>
            </div>
          </div>

          {loading ? (
            <div
              role="status"
              aria-label={t(
                'adminUserManager.loadingLabel',
                'Loading user roster'
              )}
              className="flex items-center gap-2 px-5 py-10 text-sm text-text-muted"
            >
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              {t('adminUserManager.loadingUsers', 'Loading users...')}
            </div>
          ) : loadError ? (
            <div className="px-5 py-10 text-sm text-text-muted">
              {t(
                'adminUserManager.loadRetry',
                'User roster could not load. Use Refresh roster to try again.'
              )}
            </div>
          ) : filteredUsers.length === 0 ? (
            <div className="px-5 py-10 text-sm text-text-muted">
              {users.length === 0 && !hasActiveFilters
                ? t(
                    'adminUserManager.emptyNoUsers',
                    'No users yet. New authenticated users will appear here.'
                  )
                : t(
                    'adminUserManager.emptyFiltered',
                    'No users match these filters.'
                  )}
            </div>
          ) : (
            <>
              <div className="divide-y divide-border sm:hidden">
                {filteredUsers.map((user) => {
                  const identity = identityForUser(user, identities, t);
                  const profile = profileStatuses[user.id];
                  const updating = approvalUpdatingIds.has(user.id);

                  return (
                    <article key={user.id} className="px-4 py-4">
                      <div className="flex items-start gap-3">
                        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-accent-subtle text-accent">
                          <Users className="h-5 w-5" aria-hidden="true" />
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <h3 className="text-sm font-semibold text-text">
                              <Link
                                to={userDetailPath(user.id)}
                                className="focus-ring rounded text-text hover:text-accent"
                                aria-label={t(
                                  'adminUserManager.actions.viewUserDetails',
                                  {
                                    name: identity.primary,
                                    defaultValue: 'View {{name}} details',
                                  }
                                )}
                              >
                                {identity.primary}
                              </Link>
                            </h3>
                            <span className="font-mono text-[11px] text-text-muted">
                              #{user.id}
                            </span>
                          </div>
                          {identity.secondary && (
                            <p className="mt-1 break-all text-xs text-text-muted">
                              {identity.secondary}
                            </p>
                          )}
                          {identity.helper && (
                            <p className="mt-1 text-xs text-text-muted">
                              {identity.helper}
                            </p>
                          )}
                        </div>
                      </div>

                      <dl className="mt-4 grid gap-3 text-sm">
                        <div className="flex items-center justify-between gap-3">
                          <dt className="text-text-muted">
                            {t('adminUserManager.columns.approval', 'Approval')}
                          </dt>
                          <dd>
                            {user.approved ? (
                              <Badge
                                tone="success"
                                leadingIcon={
                                  <ShieldCheck
                                    className="h-3.5 w-3.5"
                                    aria-hidden="true"
                                  />
                                }
                              >
                                {t(
                                  'adminUserManager.status.approved',
                                  'Approved'
                                )}
                              </Badge>
                            ) : (
                              <Badge
                                tone="warning"
                                leadingIcon={
                                  <Shield
                                    className="h-3.5 w-3.5"
                                    aria-hidden="true"
                                  />
                                }
                              >
                                {t(
                                  'adminUserManager.status.pending',
                                  'Pending'
                                )}
                              </Badge>
                            )}
                          </dd>
                        </div>
                        <div className="flex items-center justify-between gap-3">
                          <dt className="text-text-muted">
                            {t(
                              'adminUserManager.columns.userType',
                              'User Type'
                            )}
                          </dt>
                          <dd className="text-right text-text-secondary">
                            {user.user_type?.name ??
                              t('adminUserManager.noUserType', 'No User Type')}
                          </dd>
                        </div>
                        <div className="flex items-start justify-between gap-3">
                          <dt className="text-text-muted">
                            {t(
                              'adminUserManager.columns.userProfile',
                              'User Profile'
                            )}
                          </dt>
                          <dd className="space-y-1 text-right">
                            <Badge tone={profile?.tone ?? 'neutral'}>
                              {profile?.label ??
                                t('adminUserManager.unknown', 'Unknown')}
                            </Badge>
                            {profile?.detail && (
                              <p className="text-xs text-text-muted">
                                {profile.detail}
                              </p>
                            )}
                          </dd>
                        </div>
                        <div className="flex items-center justify-between gap-3">
                          <dt className="text-text-muted">
                            {t('adminUserManager.columns.joined', 'Joined')}
                          </dt>
                          <dd className="text-right text-text-secondary">
                            {formatJoinedDate(
                              user.created_at,
                              t('adminUserManager.unknown', 'Unknown')
                            )}
                          </dd>
                        </div>
                      </dl>

                      <div className="mt-4">
                        {user.approved ? (
                          <span className="inline-flex min-h-10 w-full items-center justify-center gap-2 rounded-lg border border-border bg-surface-overlay px-3 py-2 text-sm font-medium text-text-muted">
                            <UserRoundCheck
                              className="h-3.5 w-3.5"
                              aria-hidden="true"
                            />
                            {t('adminUserManager.status.approved', 'Approved')}
                          </span>
                        ) : (
                          <Button
                            size="sm"
                            onClick={() => handleApproveUser(user)}
                            disabled={updating}
                            className="w-full"
                            leadingIcon={
                              updating ? (
                                <Loader2
                                  className="h-3.5 w-3.5 animate-spin"
                                  aria-hidden="true"
                                />
                              ) : (
                                <ShieldCheck
                                  className="h-3.5 w-3.5"
                                  aria-hidden="true"
                                />
                              )
                            }
                            aria-label={t(
                              'adminUserManager.actions.approveUser',
                              {
                                name: identity.primary,
                                defaultValue: 'Approve {{name}}',
                              }
                            )}
                          >
                            {t('adminUserManager.actions.approve', 'Approve')}
                          </Button>
                        )}
                      </div>
                    </article>
                  );
                })}
              </div>
              <div className="hidden overflow-x-auto sm:block">
                <table
                  className="min-w-full text-left"
                  aria-label={t('adminUserManager.tableLabel', 'User roster')}
                >
                  <thead className="bg-surface-overlay text-xs uppercase tracking-[0.08em] text-text-muted">
                    <tr>
                      <th scope="col" className="px-4 py-3 font-semibold">
                        {t('adminUserManager.columns.user', 'User')}
                      </th>
                      <th scope="col" className="px-4 py-3 font-semibold">
                        {t('adminUserManager.columns.approval', 'Approval')}
                      </th>
                      <th scope="col" className="px-4 py-3 font-semibold">
                        {t('adminUserManager.columns.userType', 'User Type')}
                      </th>
                      <th scope="col" className="px-4 py-3 font-semibold">
                        {t(
                          'adminUserManager.columns.userProfile',
                          'User Profile'
                        )}
                      </th>
                      <th scope="col" className="px-4 py-3 font-semibold">
                        {t('adminUserManager.columns.joined', 'Joined')}
                      </th>
                      <th
                        scope="col"
                        className="px-4 py-3 text-right font-semibold"
                      >
                        {t('adminUserManager.columns.action', 'Action')}
                      </th>
                    </tr>
                  </thead>
                  <tbody
                    aria-label={t(
                      'adminUserManager.tableRowsLabel',
                      'User roster rows'
                    )}
                    className="divide-y divide-border"
                  >
                    {filteredUsers.map((user) => {
                      const identity = identityForUser(user, identities, t);
                      const profile = profileStatuses[user.id];
                      const updating = approvalUpdatingIds.has(user.id);

                      return (
                        <tr key={user.id} className="align-top">
                          <th scope="row" className="px-4 py-4">
                            <div className="flex min-w-[14rem] items-start gap-3">
                              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-accent-subtle text-accent">
                                <Users className="h-5 w-5" aria-hidden="true" />
                              </div>
                              <div className="min-w-0">
                                <div className="flex flex-wrap items-center gap-2">
                                  <Link
                                    to={userDetailPath(user.id)}
                                    className="focus-ring rounded font-medium text-text hover:text-accent"
                                    aria-label={t(
                                      'adminUserManager.actions.viewUserDetails',
                                      {
                                        name: identity.primary,
                                        defaultValue: 'View {{name}} details',
                                      }
                                    )}
                                  >
                                    {identity.primary}
                                  </Link>
                                  <span className="font-mono text-[11px] text-text-muted">
                                    #{user.id}
                                  </span>
                                </div>
                                {identity.secondary && (
                                  <p className="mt-1 break-all text-xs text-text-muted">
                                    {identity.secondary}
                                  </p>
                                )}
                                {identity.helper && (
                                  <p className="mt-1 text-xs text-text-muted">
                                    {identity.helper}
                                  </p>
                                )}
                              </div>
                            </div>
                          </th>
                          <td className="px-4 py-4">
                            {user.approved ? (
                              <Badge
                                tone="success"
                                leadingIcon={
                                  <ShieldCheck
                                    className="h-3.5 w-3.5"
                                    aria-hidden="true"
                                  />
                                }
                              >
                                {t(
                                  'adminUserManager.status.approved',
                                  'Approved'
                                )}
                              </Badge>
                            ) : (
                              <Badge
                                tone="warning"
                                leadingIcon={
                                  <Shield
                                    className="h-3.5 w-3.5"
                                    aria-hidden="true"
                                  />
                                }
                              >
                                {t(
                                  'adminUserManager.status.pending',
                                  'Pending'
                                )}
                              </Badge>
                            )}
                          </td>
                          <td className="px-4 py-4 text-sm text-text-secondary">
                            {user.user_type?.name ??
                              t('adminUserManager.noUserType', 'No User Type')}
                          </td>
                          <td className="px-4 py-4">
                            <div className="space-y-1">
                              <Badge tone={profile?.tone ?? 'neutral'}>
                                {profile?.label ??
                                  t('adminUserManager.unknown', 'Unknown')}
                              </Badge>
                              {profile?.detail && (
                                <p className="text-xs text-text-muted">
                                  {profile.detail}
                                </p>
                              )}
                            </div>
                          </td>
                          <td className="px-4 py-4 text-sm text-text-secondary">
                            {formatJoinedDate(
                              user.created_at,
                              t('adminUserManager.unknown', 'Unknown')
                            )}
                          </td>
                          <td className="px-4 py-4 text-right">
                            {user.approved ? (
                              <span className="inline-flex min-h-10 items-center justify-center gap-2 rounded-lg border border-border bg-surface-overlay px-3 py-2 text-sm font-medium text-text-muted">
                                <UserRoundCheck
                                  className="h-3.5 w-3.5"
                                  aria-hidden="true"
                                />
                                {t(
                                  'adminUserManager.status.approved',
                                  'Approved'
                                )}
                              </span>
                            ) : (
                              <Button
                                size="sm"
                                onClick={() => handleApproveUser(user)}
                                disabled={updating}
                                leadingIcon={
                                  updating ? (
                                    <Loader2
                                      className="h-3.5 w-3.5 animate-spin"
                                      aria-hidden="true"
                                    />
                                  ) : (
                                    <ShieldCheck
                                      className="h-3.5 w-3.5"
                                      aria-hidden="true"
                                    />
                                  )
                                }
                                aria-label={t(
                                  'adminUserManager.actions.approveUser',
                                  {
                                    name: identity.primary,
                                    defaultValue: 'Approve {{name}}',
                                  }
                                )}
                              >
                                {t(
                                  'adminUserManager.actions.approve',
                                  'Approve'
                                )}
                              </Button>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </section>
      </main>
    </div>
  );
}
