export type AdminAssistantHttpMethod = 'PUT' | 'POST' | 'DELETE';

export interface AdminAssistantRequest {
  method: AdminAssistantHttpMethod;
  path: string;
  body?: unknown;
}

export interface AdminAssistantChangeSet {
  version: 1;
  summary?: string;
  requests: AdminAssistantRequest[];
}

export type ExtractChangeSetResult =
  | { ok: true; changeSet: AdminAssistantChangeSet }
  | { ok: false; error: string };

const MAX_CHANGESET_REQUESTS = 50;

const SUPPORTED_INSTANCE_SETTING_KEYS = new Set([
  'instance_name',
  'primary_color',
  'description',
  'logo_url',
  'favicon_url',
  'apple_touch_icon_url',
  'icon',
  'assistant_icon',
  'user_icon',
  'assistant_name',
  'user_label',
  'header_layout',
  'header_tagline',
  'chat_bubble_style',
  'chat_bubble_shadow',
  'surface_style',
  'status_icon_set',
  'typography_preset',
  'default_language',
  'default_theme',
  'auto_approve_users',
  'reachout_enabled',
  'reachout_mode',
  'reachout_title',
  'reachout_description',
  'reachout_button_label',
  'reachout_success_message',
  'reachout_to_email',
  'reachout_subject_prefix',
  'reachout_rate_limit_per_hour',
  'reachout_rate_limit_per_day',
  'reachout_include_ip',
]);

const SUPPORTED_DEFAULT_LANGUAGE_CODES = new Set([
  'ar',
  'bn',
  'cs',
  'da',
  'de',
  'el',
  'en',
  'es',
  'fa',
  'fi',
  'fr',
  'he',
  'hi',
  'hu',
  'id',
  'it',
  'ja',
  'ko',
  'nl',
  'no',
  'pl',
  'pt',
  'ro',
  'ru',
  'sv',
  'th',
  'tr',
  'uk',
  'vi',
  'zh-Hans',
  'zh-Hant',
]);

const DEFAULT_LANGUAGE_LABEL_TO_CODE: Record<string, string> = {
  arabic: 'ar',
  bengali: 'bn',
  czech: 'cs',
  danish: 'da',
  german: 'de',
  greek: 'el',
  english: 'en',
  spanish: 'es',
  persian: 'fa',
  farsi: 'fa',
  finnish: 'fi',
  french: 'fr',
  hebrew: 'he',
  hindi: 'hi',
  hungarian: 'hu',
  indonesian: 'id',
  italian: 'it',
  japanese: 'ja',
  korean: 'ko',
  dutch: 'nl',
  norwegian: 'no',
  polish: 'pl',
  portuguese: 'pt',
  romanian: 'ro',
  russian: 'ru',
  swedish: 'sv',
  thai: 'th',
  turkish: 'tr',
  ukrainian: 'uk',
  vietnamese: 'vi',
  'simplified chinese': 'zh-Hans',
  'traditional chinese': 'zh-Hant',
};

function _isPlainObject(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === 'object' && !Array.isArray(value);
}

function _readInt(value: unknown): number | undefined {
  if (typeof value === 'number' && Number.isFinite(value))
    return Math.trunc(value);
  if (typeof value === 'string') {
    const trimmed = value.trim();
    if (!/^-?\d+$/.test(trimmed)) return undefined;
    const parsed = Number.parseInt(trimmed, 10);
    return Number.isFinite(parsed) ? parsed : undefined;
  }
  return undefined;
}

function _readBoolean(value: unknown): boolean | undefined {
  if (typeof value === 'boolean') return value;
  if (typeof value === 'number')
    return value === 1 ? true : value === 0 ? false : undefined;
  if (typeof value !== 'string') return undefined;
  const normalized = value.trim().toLowerCase();
  if (['true', '1', 'yes', 'on'].includes(normalized)) return true;
  if (['false', '0', 'no', 'off'].includes(normalized)) return false;
  return undefined;
}

function _readString(value: unknown): string | undefined {
  return typeof value === 'string' ? value : undefined;
}

function _readNonEmptyString(value: unknown): string | undefined {
  if (typeof value !== 'string') return undefined;
  const trimmed = value.trim();
  return trimmed ? trimmed : undefined;
}

function _readUserTypeId(value: unknown): number | string | undefined {
  if (typeof value === 'number' && Number.isInteger(value) && value > 0)
    return value;
  if (typeof value !== 'string') return undefined;
  const trimmed = value.trim();
  if (!trimmed) return undefined;
  if (/^@type:[a-z0-9_]+$/.test(trimmed)) return trimmed;
  if (/^\d+$/.test(trimmed)) {
    const parsed = Number.parseInt(trimmed, 10);
    if (Number.isFinite(parsed) && parsed > 0) return parsed;
  }
  return undefined;
}

function _readTraceVisibility(value: unknown): string | undefined {
  if (typeof value !== 'string') return undefined;
  const normalized = value.trim().toLowerCase();
  return ['off', 'minimal', 'summary', 'detailed'].includes(normalized)
    ? normalized
    : undefined;
}

function _readAgentSettingsKey(path: string): string | undefined {
  const match =
    /^\/admin\/ai-config\/(?:user-type\/[^/]+\/)?([a-z0-9_]+)$/i.exec(path);
  return match?.[1]?.toLowerCase();
}

function _isJsonStringArray(value: string): boolean {
  try {
    const parsed = JSON.parse(value);
    return (
      Array.isArray(parsed) && parsed.every((item) => typeof item === 'string')
    );
  } catch {
    return false;
  }
}

function normalizeAdminAssistantPath(path: string): string {
  return path.replace(/^\/admin\/user_types(?=\/|$)/, '/admin/user-types');
}

function normalizeDefaultLanguageValue(value: unknown): unknown {
  if (typeof value !== 'string') return value;
  const trimmed = value.trim();
  if (SUPPORTED_DEFAULT_LANGUAGE_CODES.has(trimmed)) return trimmed;
  return DEFAULT_LANGUAGE_LABEL_TO_CODE[trimmed.toLowerCase()] ?? value;
}

function normalizeSettingsPatchBody(
  body: Record<string, unknown>
): Record<string, unknown> {
  const normalized: Record<string, unknown> = {};
  for (const [rawKey, rawValue] of Object.entries(body)) {
    const key = rawKey === 'tagline' ? 'header_tagline' : rawKey;
    if (rawKey === 'tagline' && 'header_tagline' in body) continue;
    normalized[key] =
      key === 'default_language'
        ? normalizeDefaultLanguageValue(rawValue)
        : rawValue;
  }
  return normalized;
}

/**
 * Normalize supported request shapes into the exact backend schemas.
 *
 * Today the backend supports updating instance settings via:
 *   PUT /admin/settings  with a JSON body like { "instance_name": "...", ... }
 *
 * But LLMs often emit per-key endpoints like:
 *   PUT /admin/settings/instance_name  body: { "value": "..." }
 *
 * We coalesce those into a single PUT /admin/settings to make the assistant
 * more forgiving, while still keeping the strict allowlist intact.
 */
function normalizeAdminAssistantChangeSet(
  changeSet: AdminAssistantChangeSet
): AdminAssistantChangeSet {
  const settingsPatch: Record<string, unknown> = {};
  let sawSettingsPatch = false;

  const out: AdminAssistantRequest[] = [];
  const perKeyRe = /^\/admin\/settings\/([A-Za-z0-9_]+)$/;

  for (const req of changeSet.requests) {
    if (!req || typeof req !== 'object') continue;
    const path = normalizeAdminAssistantPath(req.path);
    const normalizedReq =
      path === req.path
        ? req
        : ({ ...req, path } satisfies AdminAssistantRequest);

    if (
      normalizedReq.method === 'PUT' &&
      normalizedReq.path === '/admin/settings' &&
      _isPlainObject(normalizedReq.body)
    ) {
      Object.assign(
        settingsPatch,
        normalizeSettingsPatchBody(normalizedReq.body)
      );
      sawSettingsPatch = true;
      continue;
    }

    const m =
      normalizedReq.method === 'PUT' ? perKeyRe.exec(normalizedReq.path) : null;
    if (m) {
      const key = m[1];
      if (
        _isPlainObject(normalizedReq.body) &&
        Object.keys(normalizedReq.body).length === 1 &&
        'value' in normalizedReq.body
      ) {
        const normalizedBody = normalizeSettingsPatchBody({
          [key]: (normalizedReq.body as Record<string, unknown>).value,
        });
        Object.assign(settingsPatch, normalizedBody);
        sawSettingsPatch = true;
        continue;
      }
      // Keep the original request so validation can fail loudly if it's not in the supported shape.
      out.push(normalizedReq);
      continue;
    }

    // Normalize canonical LLM payload formats to match backend schemas.
    if (normalizedReq.method === 'POST' && _isPlainObject(normalizedReq.body)) {
      // /admin/user-types expects: { name, description?, icon?, display_order? }
      if (
        normalizedReq.method === 'POST' &&
        normalizedReq.path === '/admin/user-types'
      ) {
        const b = normalizedReq.body;
        const name = _readNonEmptyString(b.name);
        const description = _readString(b.description);
        const icon = _readString(b.icon);
        const displayOrder = _readInt(b.display_order);
        const normalizedBody: Record<string, unknown> = {};
        if (name !== undefined) normalizedBody.name = name;
        if (description !== undefined) normalizedBody.description = description;
        if (icon !== undefined) normalizedBody.icon = icon;
        if (displayOrder !== undefined)
          normalizedBody.display_order = displayOrder;
        out.push({ ...normalizedReq, body: normalizedBody });
        continue;
      }

      // /admin/user-fields expects: { field_name, field_type, required?, display_order?, user_type_id?, placeholder?, options?, encryption_enabled?, include_in_chat? }
      if (
        normalizedReq.method === 'POST' &&
        normalizedReq.path === '/admin/user-fields'
      ) {
        const b = normalizedReq.body;
        const fieldName = _readNonEmptyString(b.field_name);
        const fieldType = _readNonEmptyString(b.field_type);
        const displayOrder = _readInt(b.display_order);
        const required = _readBoolean(b.required);
        const encryptionEnabled = _readBoolean(b.encryption_enabled);
        const includeInChat = _readBoolean(b.include_in_chat);
        const userTypeId = _readUserTypeId(b.user_type_id);
        const placeholder = _readString(b.placeholder);

        const normalizedBody: Record<string, unknown> = {};
        if (fieldName !== undefined) normalizedBody.field_name = fieldName;
        if (fieldType !== undefined) normalizedBody.field_type = fieldType;
        if (required !== undefined) normalizedBody.required = required;
        if (displayOrder !== undefined)
          normalizedBody.display_order = displayOrder;
        if (userTypeId !== undefined) normalizedBody.user_type_id = userTypeId;
        if (placeholder !== undefined) normalizedBody.placeholder = placeholder;
        if (encryptionEnabled !== undefined)
          normalizedBody.encryption_enabled = encryptionEnabled;
        if (includeInChat !== undefined)
          normalizedBody.include_in_chat = includeInChat;

        // Only select fields use options in the current UI, but the backend accepts it.
        // Normalize options to an array of strings when present.
        const opts = b.options;
        if (Array.isArray(opts) && opts.every((o) => typeof o === 'string')) {
          if (String(fieldType || '').toLowerCase() === 'select')
            normalizedBody.options = opts;
        }

        out.push({ ...normalizedReq, body: normalizedBody });
        continue;
      }
    }

    out.push(normalizedReq);
  }

  const requests = sawSettingsPatch
    ? [
        {
          method: 'PUT',
          path: '/admin/settings',
          body: settingsPatch,
        } satisfies AdminAssistantRequest,
        ...out,
      ]
    : out;

  // If we didn't change anything, return original object for referential stability.
  const same =
    requests.length === changeSet.requests.length &&
    requests.every((r, i) => r === changeSet.requests[i]);
  if (same) return changeSet;

  return { ...changeSet, requests };
}

function _extractJsonCodeBlocks(text: string): string[] {
  // Matches ```json ... ``` and ``` ... ```; we prefer explicit json blocks.
  const blocks: string[] = [];
  const re = /```(?:json)?\s*([\s\S]*?)\s*```/gi;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text)) !== null) {
    const body = (m[1] || '').trim();
    if (body) blocks.push(body);
  }
  return blocks;
}

function _safeJsonParse(value: string): unknown | null {
  try {
    return JSON.parse(value);
  } catch {
    return null;
  }
}

function _extractRawJsonCandidates(text: string): string[] {
  const trimmed = text.trim();
  if (!trimmed.includes('"requests"')) return [];

  const candidates: string[] = [];
  if (trimmed.startsWith('{') && trimmed.endsWith('}')) {
    candidates.push(trimmed);
  }

  const firstBrace = trimmed.indexOf('{');
  const lastBrace = trimmed.lastIndexOf('}');
  if (firstBrace !== -1 && lastBrace > firstBrace) {
    const candidate = trimmed.slice(firstBrace, lastBrace + 1);
    if (!candidates.includes(candidate)) candidates.push(candidate);
  }

  return candidates;
}

function _coerceChangeSet(parsed: unknown): AdminAssistantChangeSet | null {
  if (!parsed || typeof parsed !== 'object') return null;
  const obj = parsed as Record<string, unknown>;
  if (obj.version !== 1) return null;
  if (!Array.isArray(obj.requests)) return null;

  const summary = typeof obj.summary === 'string' ? obj.summary : undefined;
  const requests: AdminAssistantRequest[] = [];
  for (const r of obj.requests) {
    if (!r || typeof r !== 'object') return null;
    const ro = r as Record<string, unknown>;
    const method = ro.method;
    const path = ro.path;
    if (method !== 'PUT' && method !== 'POST' && method !== 'DELETE')
      return null;
    if (typeof path !== 'string') return null;
    const body = ro.body;
    requests.push({ method, path, ...(body !== undefined ? { body } : {}) });
  }

  return {
    version: 1,
    ...(summary ? { summary } : {}),
    requests,
  };
}

/**
 * Strict change set extraction.
 * - Exactly 1 valid change set must be present (otherwise ambiguous).
 * - The extracted change set must also pass allowlist validation.
 */
export function extractAdminAssistantChangeSetStrict(
  text: string
): ExtractChangeSetResult {
  const blocks = _extractJsonCodeBlocks(text);
  const candidateTexts =
    blocks.length > 0 ? blocks : _extractRawJsonCandidates(text);
  if (candidateTexts.length === 0)
    return { ok: false, error: 'No JSON change set found' };

  const candidates: AdminAssistantChangeSet[] = [];
  for (const candidateText of candidateTexts) {
    const parsed = _safeJsonParse(candidateText);
    const coerced = _coerceChangeSet(parsed);
    if (coerced) candidates.push(coerced);
  }

  if (candidates.length === 0)
    return { ok: false, error: 'No valid change set found' };
  if (candidates.length > 1)
    return {
      ok: false,
      error: 'Multiple change sets found. Please output exactly one.',
    };

  const changeSet = normalizeAdminAssistantChangeSet(candidates[0]);
  const validation = validateAdminAssistantChangeSet(changeSet);
  if (!validation.ok)
    return { ok: false, error: validation.error || 'Invalid change set' };

  return { ok: true, changeSet };
}

export function coerceAdminAssistantChangeSetPayload(
  payload: unknown
): ExtractChangeSetResult {
  const coerced = _coerceChangeSet(payload);
  if (!coerced) return { ok: false, error: 'No valid change set found' };

  const changeSet = normalizeAdminAssistantChangeSet(coerced);
  const validation = validateAdminAssistantChangeSet(changeSet);
  if (!validation.ok)
    return { ok: false, error: validation.error || 'Invalid change set' };

  return { ok: true, changeSet };
}

export function stripAdminAssistantChangeSetJson(text: string): string {
  if (!text || !text.includes('"requests"')) return text;
  const shouldStripChangeSet = (value: unknown): boolean => {
    const coerced = _coerceChangeSet(value);
    if (!coerced) return false;
    return validateAdminAssistantChangeSet(
      normalizeAdminAssistantChangeSet(coerced)
    ).ok;
  };
  const withoutBlocks = text.replace(
    /```(?:json)?\s*([\s\S]*?)\s*```/gi,
    (match, body) => {
      const parsed = _safeJsonParse(String(body).trim());
      return shouldStripChangeSet(parsed) ? '' : match;
    }
  );
  const withoutRaw = withoutBlocks.replace(
    /\{[\s\S]*"requests"[\s\S]*\}/g,
    (match) => {
      const parsed = _safeJsonParse(match.trim());
      return shouldStripChangeSet(parsed) ? '' : match;
    }
  );
  return withoutRaw.replace(/\n{3,}/g, '\n\n').trim();
}

export function validateAdminAssistantChangeSet(
  changeSet: AdminAssistantChangeSet
): { ok: boolean; error?: string } {
  if (!changeSet || changeSet.version !== 1) {
    return { ok: false, error: 'Unsupported change set version' };
  }
  if (!Array.isArray(changeSet.requests) || changeSet.requests.length === 0) {
    return { ok: false, error: 'Change set contains no requests' };
  }
  if (changeSet.requests.length > MAX_CHANGESET_REQUESTS) {
    return {
      ok: false,
      error: `Change set has too many requests (max ${MAX_CHANGESET_REQUESTS})`,
    };
  }

  const allowedMethods = new Set<AdminAssistantHttpMethod>([
    'PUT',
    'POST',
    'DELETE',
  ]);

  // Intentionally narrow allowlist: only explicit admin mutation endpoints.
  // Regexes are anchored to avoid accidental prefix matches.
  //
  // Note: We allow a user-type placeholder token `@type:<slug>` in certain routes
  // so a single change set can create user types and then reference them without
  // guessing numeric IDs. The apply pipeline resolves placeholders to IDs.
  const userTypeSegment = '(?:\\d+|@type:[a-z0-9_]+)';
  const allowedPathByMethod: Record<AdminAssistantHttpMethod, RegExp[]> = {
    PUT: [
      /^\/admin\/deployment\/config\/[A-Z0-9_]+$/,
      /^\/admin\/settings$/,
      /^\/admin\/ai-config\/[a-z0-9_]+$/i,
      new RegExp(
        `^/admin/ai-config/user-type/${userTypeSegment}/[a-z0-9_]+$`,
        'i'
      ),
      /^\/admin\/user-types\/\d+$/,
      /^\/admin\/user-fields\/\d+$/,
      /^\/admin\/user-fields\/\d+\/encryption$/,
      /^\/ingest\/admin\/documents\/[A-Za-z0-9_-]+\/defaults$/,
      /^\/ingest\/admin\/documents\/defaults\/batch$/,
      new RegExp(
        `^/ingest/admin/documents/[A-Za-z0-9_-]+/defaults/user-type/${userTypeSegment}$`
      ),
      /^\/admin\/resources\/[A-Za-z0-9_-]+$/,
      /^\/admin\/help-types\/[a-z0-9_]+$/i,
    ],
    POST: [
      /^\/admin\/user-types$/,
      /^\/admin\/user-fields$/,
      /^\/admin\/resources$/,
    ],
    DELETE: [
      /^\/admin\/user-types\/\d+$/,
      /^\/admin\/user-fields\/\d+$/,
      new RegExp(
        `^/admin/ai-config/user-type/${userTypeSegment}/[a-z0-9_]+$`,
        'i'
      ),
      new RegExp(
        `^/ingest/admin/documents/[A-Za-z0-9_-]+/defaults/user-type/${userTypeSegment}$`
      ),
      /^\/admin\/resources\/[A-Za-z0-9_-]+$/,
      /^\/admin\/help-types\/[a-z0-9_]+$/i,
    ],
  };

  for (const req of changeSet.requests) {
    if (!req || typeof req !== 'object')
      return { ok: false, error: 'Invalid request entry' };
    if (!allowedMethods.has(req.method))
      return { ok: false, error: `Unsupported method: ${String(req.method)}` };
    if (typeof req.path !== 'string' || !req.path.startsWith('/'))
      return { ok: false, error: 'Invalid request path' };
    if (req.path.includes('..'))
      return { ok: false, error: 'Invalid request path' };

    // Block high-risk reads and generic tool execution explicitly.
    const pathLower = req.path.toLowerCase();
    if (
      pathLower.includes('/reveal') ||
      pathLower.includes('/export') ||
      pathLower.includes('/prompts/preview') ||
      pathLower.startsWith('/admin/tools/execute')
    ) {
      return { ok: false, error: `Disallowed request path: ${req.path}` };
    }

    const allowed = allowedPathByMethod[req.method].some((re) =>
      re.test(req.path)
    );
    if (!allowed)
      return {
        ok: false,
        error: `Disallowed request: ${req.method} ${req.path}`,
      };

    if (req.method === 'PUT' && req.path === '/admin/settings') {
      if (!_isPlainObject(req.body)) {
        return {
          ok: false,
          error: 'PUT /admin/settings requires an object body',
        };
      }
      for (const [key, value] of Object.entries(req.body)) {
        if (!SUPPORTED_INSTANCE_SETTING_KEYS.has(key)) {
          return {
            ok: false,
            error: `Unsupported instance setting key: ${key}`,
          };
        }
        if (
          key === 'default_language' &&
          (typeof value !== 'string' ||
            !SUPPORTED_DEFAULT_LANGUAGE_CODES.has(value))
        ) {
          return {
            ok: false,
            error: `Unsupported default_language value: ${value}`,
          };
        }
        if (
          key === 'default_theme' &&
          (typeof value !== 'string' ||
            !['light', 'dark', 'system'].includes(value))
        ) {
          return {
            ok: false,
            error: `Unsupported default_theme value: ${value}`,
          };
        }
      }
    }

    if (req.method === 'POST' && req.path === '/admin/user-types') {
      if (!_isPlainObject(req.body) || !_readNonEmptyString(req.body.name)) {
        return {
          ok: false,
          error: 'POST /admin/user-types requires body.name',
        };
      }
    }

    if (req.method === 'PUT' && pathLower.startsWith('/admin/ai-config/')) {
      const value = _isPlainObject(req.body) ? req.body.value : undefined;
      if (typeof value !== 'string') {
        return {
          ok: false,
          error: `${req.path} body.value must be a string`,
        };
      }

      const key = _readAgentSettingsKey(req.path);
      if (
        (key === 'prompt_rules' || key === 'prompt_forbidden') &&
        !_isJsonStringArray(value)
      ) {
        return {
          ok: false,
          error: `${req.path} body.value must be a JSON array of strings`,
        };
      }
    }

    if (
      req.method === 'PUT' &&
      pathLower === '/admin/ai-config/user_trace_visibility'
    ) {
      const value = _isPlainObject(req.body)
        ? _readTraceVisibility(req.body.value)
        : undefined;
      if (value === 'detailed') {
        return {
          ok: false,
          error: 'User Conversation trace visibility cannot be detailed',
        };
      }
    }
  }

  return { ok: true };
}

export function redactSecrets(text: string, secrets: string[]): string {
  if (!text || secrets.length === 0) return text;

  // Replace exact occurrences of known secret values. Keep it simple and deterministic.
  // Sort by descending length so longer secrets are replaced first, preventing
  // substring fragmentation (e.g. "secretkey" fragmenting "mysecretkey123").
  const sorted = [...secrets].sort((a, b) => b.length - a.length);
  let out = text;
  for (const secret of sorted) {
    if (!secret) continue;
    if (secret.length < 6) continue; // Avoid over-redacting common short strings
    if (!out.includes(secret)) continue;
    out = out.split(secret).join('[REDACTED]');
  }
  return out;
}

export function redactAdminDeploymentSecretChangeSets(text: string): string {
  if (!text || !text.includes('/admin/deployment/config/')) return text;

  const redactParsedBlock = (match: string, body: string): string => {
    try {
      const parsed = JSON.parse(body);
      if (!parsed || parsed.version !== 1 || !Array.isArray(parsed.requests))
        return match;
      let changed = false;
      const requests = parsed.requests.map((request: unknown) => {
        if (!_isPlainObject(request)) return request;
        const path = typeof request.path === 'string' ? request.path : '';
        const key = path.startsWith('/admin/deployment/config/')
          ? path.split('/').pop() || ''
          : '';
        const bodyValue = request.body;
        if (
          request.method === 'PUT' &&
          /SECRET|TOKEN|KEY|PASSWORD/i.test(key) &&
          _isPlainObject(bodyValue) &&
          typeof bodyValue.value === 'string' &&
          bodyValue.value.length > 0
        ) {
          changed = true;
          return { ...request, body: { ...bodyValue, value: '[REDACTED]' } };
        }
        return request;
      });
      if (!changed) return match;
      return `\`\`\`json\n${JSON.stringify({ ...parsed, requests }, null, 2)}\n\`\`\``;
    } catch {
      return match;
    }
  };

  let out = text.replace(
    /```(?:json)?\s*([\s\S]*?)\s*```/gi,
    redactParsedBlock
  );

  out = out.replace(
    /("path"\s*:\s*"\/admin\/deployment\/config\/[^"]*(?:SECRET|TOKEN|KEY|PASSWORD)[^"]*"[\s\S]*?"value"\s*:\s*")([^"]*)/gi,
    (_match, prefix: string) => `${prefix}[REDACTED]`
  );

  return out;
}
