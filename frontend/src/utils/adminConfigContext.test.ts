import { describe, expect, it, vi } from 'vitest';
import {
  buildFullAdminConfigContext,
  buildScopedAdminConfigContext,
  selectAdminConfigScope,
  selectDeploymentCategory,
} from './adminConfigContext';
import type { DeploymentConfigResponse } from '../types/config';

const emptyDeploymentConfig = (): DeploymentConfigResponse => ({
  llm: [],
  embedding: [],
  email: [],
  storage: [],
  security: [],
  search: [],
  domains: [],
  ssl: [],
  general: [],
});

function mockFetchJson(
  handler: (endpoint: string) => Promise<unknown>
): (<T>(endpoint: string) => Promise<T>) & { mock: { calls: unknown[][] } } {
  return vi.fn(handler) as unknown as (<T>(endpoint: string) => Promise<T>) & {
    mock: { calls: unknown[][] };
  };
}

describe('selectAdminConfigScope', () => {
  it('selects instance-settings for branding and theme requests', () => {
    expect(
      selectAdminConfigScope('Set up the theme from the uploaded guide.')
    ).toBe('instance-settings');
    expect(
      selectAdminConfigScope('Update primary color and typography preset')
    ).toBe('instance-settings');
  });

  it('selects deployment-settings for provider and env requests', () => {
    expect(selectAdminConfigScope('Review deployment config.')).toBe(
      'deployment-settings'
    );
    expect(
      selectAdminConfigScope('Change the model provider and restart settings')
    ).toBe('deployment-settings');
  });

  it('selects agent-settings for prompt and model behavior requests', () => {
    expect(
      selectAdminConfigScope('Change the admin prompt and max tokens')
    ).toBe('agent-settings');
  });

  it('selects user-types for onboarding field requests', () => {
    expect(
      selectAdminConfigScope('Add a new onboarding question for advocates')
    ).toBe('user-types');
  });

  it('selects document-defaults for ingestion default requests', () => {
    expect(selectAdminConfigScope('Update default document access rules')).toBe(
      'document-defaults'
    );
  });

  it('selects health for readiness and validation requests', () => {
    expect(
      selectAdminConfigScope('Check deployment readiness and service health')
    ).toBe('health');
    expect(selectAdminConfigScope('Check service status and readiness')).toBe(
      'health'
    );
  });

  it('selects instance-settings for status icon configuration requests', () => {
    expect(selectAdminConfigScope('Update status icon set to minimal')).toBe(
      'instance-settings'
    );
  });

  it('falls back to overview for ambiguous admin configuration requests', () => {
    expect(selectAdminConfigScope('Help me configure this instance')).toBe(
      'overview'
    );
    expect(selectAdminConfigScope('your suggestions above')).toBe('overview');
  });
});

describe('selectDeploymentCategory', () => {
  it('narrows deployment scope to the relevant category when possible', () => {
    expect(selectDeploymentCategory('Update SMTP host and port')).toBe('email');
    expect(selectDeploymentCategory('Change the model provider')).toBe('llm');
  });
});

describe('buildScopedAdminConfigContext', () => {
  it('builds instance-settings context without loading unrelated admin surfaces', async () => {
    const fetchJson = mockFetchJson(async (endpoint: string) => {
      if (endpoint === '/admin/settings') {
        return {
          settings: {
            instance_name: 'Enclave',
            primary_color: 'blue',
            typography_preset: 'modern',
          },
        };
      }
      throw new Error(`unexpected fetch: ${endpoint}`);
    });

    const result = await buildScopedAdminConfigContext({
      query: 'Set up the theme from the uploaded guide.',
      shareSecrets: false,
      fetchJson,
      configCategories: {},
      deploymentMeta: {},
      tracePolicyLines: ['- Trace policy line'],
    });

    expect(fetchJson).toHaveBeenCalledTimes(1);
    expect(fetchJson).toHaveBeenCalledWith('/admin/settings');
    expect(result.scope).toBe('instance-settings');
    expect(result.mode).toBe('scoped');
    expect(result.context).toContain('SCOPED CONFIG CONTEXT');
    expect(result.context).toContain('scope: instance-settings');
    expect(result.context).toContain('INSTANCE VISUAL IDENTITY SETTINGS');
    expect(result.context).toContain('primary_color');
    expect(result.context).not.toContain('AI CONFIG');
    expect(result.context).not.toContain('DEPLOYMENT CONFIG');
  });

  it('builds deployment-settings context while preserving secret opt-in behavior', async () => {
    const fetchJson = mockFetchJson(async (endpoint: string) => {
      if (endpoint === '/admin/deployment/config') {
        return {
          ...emptyDeploymentConfig(),
          general: [
            {
              key: 'LLM_API_KEY',
              value: '[CONFIGURED]',
              is_secret: true,
              requires_restart: true,
              description: 'Model Provider API key',
            },
          ],
        };
      }
      throw new Error(`unexpected fetch: ${endpoint}`);
    });

    const result = await buildScopedAdminConfigContext({
      query: 'Review deployment config.',
      shareSecrets: false,
      fetchJson,
      configCategories: { general: 'General' },
      deploymentMeta: {},
      tracePolicyLines: [],
    });

    expect(fetchJson).toHaveBeenCalledWith('/admin/deployment/config');
    expect(fetchJson).not.toHaveBeenCalledWith(
      '/admin/deployment/config/LLM_API_KEY/reveal'
    );
    expect(result.scope).toBe('deployment-settings');
    expect(result.context).toContain('LLM_API_KEY');
    expect(result.context).toContain('secret=true');
    expect(result.context).toContain('Secret env vars are NOT included');
    expect(result.secretValues).toEqual([]);
  });

  it('builds agent-settings context with Agent Settings data', async () => {
    const fetchJson = mockFetchJson(async (endpoint: string) => {
      if (endpoint === '/admin/ai-config') {
        return {
          prompt_sections: [{ id: 'tone', value: 'Helpful' }],
          parameters: [],
          defaults: [],
        };
      }
      if (endpoint === '/admin/user-types') {
        return { types: [] };
      }
      throw new Error(`unexpected fetch: ${endpoint}`);
    });

    const result = await buildScopedAdminConfigContext({
      query: 'Change the admin prompt and max tokens',
      shareSecrets: false,
      fetchJson,
      configCategories: {},
      deploymentMeta: {},
      tracePolicyLines: [],
    });

    expect(fetchJson).toHaveBeenCalledWith('/admin/ai-config');
    expect(result.scope).toBe('agent-settings');
    expect(result.context).toContain('AGENT SETTINGS');
    expect(result.context).toContain('prompt_sections');
    expect(result.context).not.toContain('DEPLOYMENT CONFIG');
  });

  it('builds bounded overview context for ambiguous requests', async () => {
    const fetchJson = mockFetchJson(async (endpoint: string) => {
      if (endpoint === '/admin/settings') {
        return {
          settings: {
            instance_name: 'Enclave',
            instance_description: 'Secure knowledge base',
          },
        };
      }
      throw new Error(`unexpected fetch: ${endpoint}`);
    });

    const result = await buildScopedAdminConfigContext({
      query: 'Help me configure this instance',
      shareSecrets: false,
      fetchJson,
      configCategories: {},
      deploymentMeta: {},
      tracePolicyLines: [],
    });

    expect(fetchJson).toHaveBeenCalledTimes(1);
    expect(result.scope).toBe('overview');
    expect(result.context).toContain('scope: overview');
    expect(result.context).toContain('instance_name');
    expect(result.context).not.toContain('DEPLOYMENT CONFIG');
    expect(result.context).not.toContain('AI CONFIG');
  });
});

describe('buildFullAdminConfigContext', () => {
  it('loads the full manual snapshot across admin surfaces', async () => {
    const fetchJson = mockFetchJson(async (endpoint: string) => {
      if (endpoint === '/admin/settings')
        return { settings: { instance_name: 'Enclave' } };
      if (endpoint === '/admin/deployment/config')
        return emptyDeploymentConfig();
      if (endpoint === '/admin/ai-config')
        return { prompt_sections: [], parameters: [], defaults: [] };
      if (endpoint === '/admin/user-types') return { types: [] };
      if (endpoint === '/ingest/admin/documents/defaults')
        return { documents: [] };
      if (endpoint === '/ingest/admin/documents/context-preview')
        return { excerpts: [] };
      if (endpoint === '/admin/deployment/health') return { ok: true };
      throw new Error(`unexpected fetch: ${endpoint}`);
    });

    const result = await buildFullAdminConfigContext({
      shareSecrets: false,
      fetchJson,
      configCategories: {},
      deploymentMeta: {},
      tracePolicyLines: [],
    });

    expect(result.mode).toBe('full');
    expect(result.context).toContain('FULL ADMIN CONFIG SNAPSHOT');
    expect(result.context).toContain('DEPLOYMENT CONFIG');
    expect(result.context).toContain('AI CONFIG');
    expect(fetchJson).toHaveBeenCalledWith('/admin/deployment/config');
    expect(fetchJson).toHaveBeenCalledWith('/admin/ai-config');
  });
});
