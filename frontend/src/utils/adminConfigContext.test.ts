import { describe, expect, it, vi } from 'vitest';
import {
  loadDeploymentSecretKeysFromConfig,
  refreshAdminConfigRedactionMetadata,
} from './adminConfigContext';

function mockFetchJson(
  handler: (endpoint: string, options?: RequestInit) => Promise<unknown>
): (<T>(endpoint: string, options?: RequestInit) => Promise<T>) & {
  mock: { calls: unknown[][] };
} {
  return vi.fn(handler) as unknown as (<T>(
    endpoint: string,
    options?: RequestInit
  ) => Promise<T>) & { mock: { calls: unknown[][] } };
}

describe('loadDeploymentSecretKeysFromConfig', () => {
  it('collects secret keys from deployment config without scoped context text', async () => {
    const fetchJson = mockFetchJson(async (endpoint) => {
      expect(endpoint).toBe('/admin/deployment/config');
      return {
        general: [
          { key: 'LLM_API_KEY', is_secret: true },
          { key: 'PUBLIC_URL', is_secret: false },
        ],
      };
    });

    const keys = await loadDeploymentSecretKeysFromConfig(fetchJson);

    expect(keys).toEqual(new Set(['LLM_API_KEY']));
  });
});

describe('refreshAdminConfigRedactionMetadata', () => {
  it('reveals secret values only when shareSecrets is enabled', async () => {
    const fetchJson = mockFetchJson(async (endpoint) => {
      if (endpoint === '/admin/deployment/config') {
        return {
          general: [{ key: 'SMTP_PASSWORD', is_secret: true }],
        };
      }
      if (endpoint === '/admin/deployment/config/SMTP_PASSWORD/reveal') {
        return { key: 'SMTP_PASSWORD', value: 'smtp-secret-value' };
      }
      throw new Error(`unexpected fetch: ${endpoint}`);
    });

    const result = await refreshAdminConfigRedactionMetadata({
      shareSecrets: true,
      fetchJson,
    });

    expect(result.secretValues).toEqual(['smtp-secret-value']);
    expect(result.deploymentSecretKeys).toEqual(new Set(['SMTP_PASSWORD']));
  });

  it('does not reveal secret values by default', async () => {
    const fetchJson = mockFetchJson(async (endpoint) => {
      if (endpoint === '/admin/deployment/config') {
        return {
          general: [{ key: 'SMTP_PASSWORD', is_secret: true }],
        };
      }
      throw new Error(`unexpected fetch: ${endpoint}`);
    });

    const result = await refreshAdminConfigRedactionMetadata({
      shareSecrets: false,
      fetchJson,
    });

    expect(fetchJson).toHaveBeenCalledTimes(1);
    expect(result.secretValues).toEqual([]);
    expect(result.deploymentSecretKeys).toEqual(new Set(['SMTP_PASSWORD']));
  });
});
