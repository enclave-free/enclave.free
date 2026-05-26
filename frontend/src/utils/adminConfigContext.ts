/**
 * Admin Configuration Assistant scoped context client.
 *
 * Scoped Config Context assembly is owned by the Enclave Control Plane.
 * This module fetches server-built context for sidebar and refresh flows.
 */

export type AdminConfigScope =
  | 'overview'
  | 'instance-settings'
  | 'deployment-settings'
  | 'agent-settings'
  | 'user-types'
  | 'document-defaults'
  | 'health';

export type AdminConfigContextMode = 'scoped' | 'full';

export interface AdminConfigContextResult {
  context: string;
  scope: AdminConfigScope | 'full';
  mode: AdminConfigContextMode;
  secretValues: string[];
  deploymentSecretKeys: Set<string>;
  generatedAtIso: string;
  primaryScope: AdminConfigScope;
  includedScopes: AdminConfigScope[];
  warnings: string[];
}

export interface ServerScopedConfigContextResponse {
  version: number;
  primary_scope: AdminConfigScope;
  included_scopes: AdminConfigScope[];
  context_text: string;
  warnings: string[];
  generated_at: string;
  secret_policy: { mode: string };
  deployment_secret_keys: string[];
}

type FetchJsonFn = <T>(endpoint: string, options?: RequestInit) => Promise<T>;

const EXPECTED_SCOPED_CONFIG_CONTEXT_VERSION = 1;

interface AdminConfigContextBaseOptions {
  shareSecrets: boolean;
  fetchJson: FetchJsonFn;
}

interface BuildScopedAdminConfigContextOptions extends AdminConfigContextBaseOptions {
  query: string;
}

/**
 * Returns whether a query contains any of the provided keywords.
 * Used by document-context helpers; scope classification is server-owned.
 */
export function containsKeyword(
  query: string,
  keywords: ReadonlySet<string>
): boolean {
  const tokens = new Set(
    query
      .toLowerCase()
      .split(/[^a-z0-9]+/)
      .filter(Boolean)
  );
  for (const keyword of keywords) {
    if (tokens.has(keyword)) return true;
  }
  return false;
}

/**
 * Fetch server-owned scoped config context from the Control Plane.
 */
export async function fetchServerScopedConfigContext(options: {
  query: string;
  mode?: 'auto' | 'overview' | 'full';
  requestedScopes?: AdminConfigScope[];
  fetchJson: FetchJsonFn;
}): Promise<ServerScopedConfigContextResponse> {
  return options.fetchJson<ServerScopedConfigContextResponse>(
    '/admin/scoped-config-context',
    {
      method: 'POST',
      body: JSON.stringify({
        query: options.query,
        mode: options.mode ?? 'auto',
        requested_scopes: options.requestedScopes,
      }),
    }
  );
}

/**
 * Reveal deployment secret values when the admin explicitly opts in.
 * Values are session-local redaction metadata only; they are not added to context text.
 */
async function revealDeploymentSecretValues(
  fetchJson: FetchJsonFn,
  secretKeys: string[]
): Promise<string[]> {
  const revealResults = await Promise.all(
    secretKeys.map(async (key) => {
      try {
        const payload = await fetchJson<{ key: string; value: string }>(
          `/admin/deployment/config/${key}/reveal`
        );
        return payload?.value ?? '';
      } catch {
        return '';
      }
    })
  );
  return revealResults.filter(
    (value): value is string => typeof value === 'string' && value.length > 0
  );
}

function mapServerResponseToResult(
  response: ServerScopedConfigContextResponse,
  options: {
    mode: AdminConfigContextMode;
    scope: AdminConfigScope | 'full';
    shareSecrets: boolean;
    fetchJson: FetchJsonFn;
  }
): Promise<AdminConfigContextResult> {
  if (response.version !== EXPECTED_SCOPED_CONFIG_CONTEXT_VERSION) {
    throw new Error(
      `Unsupported scoped config context version: ${String(response.version)}`
    );
  }

  const deploymentSecretKeys = new Set(response.deployment_secret_keys);
  const revealPromise = options.shareSecrets
    ? revealDeploymentSecretValues(
        options.fetchJson,
        response.deployment_secret_keys
      )
    : Promise.resolve<string[]>([]);

  return revealPromise.then((secretValues) => ({
    context: response.context_text,
    scope: options.scope,
    mode: options.mode,
    secretValues,
    deploymentSecretKeys,
    generatedAtIso: response.generated_at,
    primaryScope: response.primary_scope,
    includedScopes: response.included_scopes,
    warnings: response.warnings,
  }));
}

/**
 * Builds scoped admin config context for sidebar assistant turns.
 */
export async function buildScopedAdminConfigContext(
  options: BuildScopedAdminConfigContextOptions
): Promise<AdminConfigContextResult> {
  const response = await fetchServerScopedConfigContext({
    query: options.query,
    mode: 'auto',
    fetchJson: options.fetchJson,
  });

  return mapServerResponseToResult(response, {
    mode: 'scoped',
    scope: response.primary_scope,
    shareSecrets: options.shareSecrets,
    fetchJson: options.fetchJson,
  });
}

/**
 * Refreshes server-built full scoped context metadata for manual/debug refresh.
 */
export async function buildFullAdminConfigContext(
  options: AdminConfigContextBaseOptions
): Promise<AdminConfigContextResult> {
  const response = await fetchServerScopedConfigContext({
    query: 'Refresh admin configuration context snapshot',
    mode: 'full',
    fetchJson: options.fetchJson,
  });

  return mapServerResponseToResult(response, {
    mode: 'full',
    scope: 'full',
    shareSecrets: options.shareSecrets,
    fetchJson: options.fetchJson,
  });
}
