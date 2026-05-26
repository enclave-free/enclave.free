import { describe, expect, it, vi } from 'vitest';
import {
  buildFullAdminConfigContext,
  buildScopedAdminConfigContext,
  fetchServerScopedConfigContext,
} from './adminConfigContext';
import type { ServerScopedConfigContextResponse } from './adminConfigContext';

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

const instanceSettingsResponse: ServerScopedConfigContextResponse = {
  version: 1,
  primary_scope: 'instance-settings',
  included_scopes: ['instance-settings'],
  context_text:
    'SCOPED CONFIG CONTEXT\nscope: instance-settings\n\nINSTANCE SETTINGS (/admin/settings)\n- default_theme: dark',
  warnings: [],
  generated_at: '2026-05-25T12:00:00+00:00',
  secret_policy: { mode: 'masked' },
  deployment_secret_keys: [],
};

const fullRefreshResponse: ServerScopedConfigContextResponse = {
  version: 1,
  primary_scope: 'overview',
  included_scopes: [
    'overview',
    'instance-settings',
    'deployment-settings',
    'agent-settings',
    'user-types',
    'document-defaults',
    'health',
  ],
  context_text:
    'SCOPED CONFIG CONTEXT\nscope: overview\n\nAGENT SETTINGS (/admin/ai-config)\nUSER TYPES (/admin/user-types)',
  warnings: [],
  generated_at: '2026-05-25T12:05:00+00:00',
  secret_policy: { mode: 'masked' },
  deployment_secret_keys: ['SMTP_PASSWORD'],
};

describe('fetchServerScopedConfigContext', () => {
  it('posts to the admin scoped-config-context endpoint', async () => {
    const fetchJson = mockFetchJson(async (endpoint, options) => {
      expect(endpoint).toBe('/admin/scoped-config-context');
      expect(options?.method).toBe('POST');
      expect(JSON.parse(String(options?.body))).toEqual({
        query: 'update the theme',
        mode: 'auto',
      });
      return instanceSettingsResponse;
    });

    const response = await fetchServerScopedConfigContext({
      query: 'update the theme',
      fetchJson,
    });

    expect(response.primary_scope).toBe('instance-settings');
    expect(fetchJson).toHaveBeenCalledTimes(1);
  });
});

describe('buildScopedAdminConfigContext', () => {
  it('uses server-built context instead of client-side admin fetches', async () => {
    const fetchJson = mockFetchJson(async (endpoint) => {
      if (endpoint === '/admin/scoped-config-context') {
        return instanceSettingsResponse;
      }
      throw new Error(`unexpected fetch: ${endpoint}`);
    });

    const result = await buildScopedAdminConfigContext({
      query: 'Set up the theme from the uploaded guide.',
      shareSecrets: false,
      fetchJson,
    });

    expect(fetchJson).toHaveBeenCalledTimes(1);
    expect(result.scope).toBe('instance-settings');
    expect(result.primaryScope).toBe('instance-settings');
    expect(result.mode).toBe('scoped');
    expect(result.context).toContain('SCOPED CONFIG CONTEXT');
    expect(result.context).toContain('default_theme');
    expect(result.generatedAtIso).toBe('2026-05-25T12:00:00+00:00');
    expect(result.warnings).toEqual([]);
  });

  it('preserves deployment secret redaction metadata without echoing raw secrets', async () => {
    const fetchJson = mockFetchJson(async (endpoint) => {
      if (endpoint === '/admin/scoped-config-context') {
        return {
          ...instanceSettingsResponse,
          primary_scope: 'deployment-settings',
          included_scopes: ['deployment-settings'],
          context_text: 'SCOPED CONFIG CONTEXT\nSMTP_PASSWORD = [REDACTED]',
          deployment_secret_keys: ['SMTP_PASSWORD'],
        };
      }
      throw new Error(`unexpected fetch: ${endpoint}`);
    });

    const result = await buildScopedAdminConfigContext({
      query: 'Review deployment config.',
      shareSecrets: false,
      fetchJson,
    });

    expect(result.deploymentSecretKeys).toEqual(new Set(['SMTP_PASSWORD']));
    expect(result.secretValues).toEqual([]);
    expect(result.context).toContain('[REDACTED]');
    expect(result.context).not.toContain('super-secret');
  });

  it('surfaces server warnings in result metadata', async () => {
    const fetchJson = mockFetchJson(async () => ({
      ...instanceSettingsResponse,
      primary_scope: 'user-types',
      included_scopes: ['user-types'],
      warnings: ['user-fields user_type_id=2 failed'],
    }));

    const result = await buildScopedAdminConfigContext({
      query: 'Add onboarding questions',
      shareSecrets: false,
      fetchJson,
    });

    expect(result.warnings).toEqual(['user-fields user_type_id=2 failed']);
  });
});

describe('buildFullAdminConfigContext', () => {
  it('requests server full refresh mode for manual context refresh', async () => {
    const fetchJson = mockFetchJson(async (endpoint, options) => {
      expect(endpoint).toBe('/admin/scoped-config-context');
      expect(JSON.parse(String(options?.body))).toMatchObject({
        mode: 'full',
      });
      return fullRefreshResponse;
    });

    const result = await buildFullAdminConfigContext({
      shareSecrets: false,
      fetchJson,
    });

    expect(result.mode).toBe('full');
    expect(result.scope).toBe('full');
    expect(result.includedScopes).toHaveLength(7);
    expect(result.deploymentSecretKeys).toEqual(new Set(['SMTP_PASSWORD']));
    expect(result.context).toContain('AGENT SETTINGS (/admin/ai-config)');
  });

  it('reveals secret values only when shareSecrets is enabled', async () => {
    const fetchJson = mockFetchJson(async (endpoint) => {
      if (endpoint === '/admin/scoped-config-context') {
        return fullRefreshResponse;
      }
      if (endpoint === '/admin/deployment/config/SMTP_PASSWORD/reveal') {
        return { key: 'SMTP_PASSWORD', value: 'smtp-secret-value' };
      }
      throw new Error(`unexpected fetch: ${endpoint}`);
    });

    const result = await buildFullAdminConfigContext({
      shareSecrets: true,
      fetchJson,
    });

    expect(result.secretValues).toEqual(['smtp-secret-value']);
    expect(result.context).not.toContain('smtp-secret-value');
  });

  it('rejects unsupported server contract versions before revealing secrets', async () => {
    const fetchJson = mockFetchJson(async (endpoint) => {
      if (endpoint === '/admin/scoped-config-context') {
        return {
          ...fullRefreshResponse,
          version: 2,
        };
      }
      if (endpoint === '/admin/deployment/config/SMTP_PASSWORD/reveal') {
        throw new Error('secret reveal should not be called');
      }
      throw new Error(`unexpected fetch: ${endpoint}`);
    });

    await expect(
      buildFullAdminConfigContext({
        shareSecrets: true,
        fetchJson,
      })
    ).rejects.toThrow('Unsupported scoped config context version: 2');
    expect(fetchJson).toHaveBeenCalledTimes(1);
  });
});
