/**
 * Admin Configuration Assistant metadata helpers.
 *
 * Sage owns Admin Config Tool reads. The browser may keep redaction metadata for
 * display safety, but it must not fetch or inject scoped admin prompt context.
 */

export interface AdminConfigRedactionMetadata {
  secretValues: string[];
  deploymentSecretKeys: Set<string>;
}

type FetchJsonFn = <T>(endpoint: string, options?: RequestInit) => Promise<T>;

type DeploymentConfigPayload = Record<
  string,
  Array<{ is_secret?: boolean; key?: unknown }> | unknown
>;

/**
 * Load deployment secret key names from deployment config (no scoped context text).
 */
export async function loadDeploymentSecretKeysFromConfig(
  fetchJson: FetchJsonFn
): Promise<Set<string>> {
  const payload = await fetchJson<DeploymentConfigPayload>(
    '/admin/deployment/config'
  );
  const secretKeys = new Set<string>();
  for (const value of Object.values(payload || {})) {
    if (!Array.isArray(value)) continue;
    for (const item of value) {
      if (item?.is_secret && typeof item.key === 'string') {
        secretKeys.add(item.key);
      }
    }
  }
  return secretKeys;
}

/**
 * Refresh client-side redaction metadata without embedding secrets in prompt text.
 */
export async function refreshAdminConfigRedactionMetadata(options: {
  shareSecrets: boolean;
  fetchJson: FetchJsonFn;
}): Promise<AdminConfigRedactionMetadata> {
  const deploymentSecretKeys = await loadDeploymentSecretKeysFromConfig(
    options.fetchJson
  );
  const secretValues = options.shareSecrets
    ? await revealDeploymentSecretValues(options.fetchJson, [
        ...deploymentSecretKeys,
      ])
    : [];
  return { secretValues, deploymentSecretKeys };
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
