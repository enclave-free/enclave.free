import { describe, expect, it } from 'vitest';
import * as adminAssistant from './adminAssistant';
import {
  coerceAdminAssistantChangeSetPayload,
  extractAdminAssistantChangeSetStrict,
  redactAdminDeploymentSecretChangeSets,
  stripAdminAssistantChangeSetJson,
} from './adminAssistant';

describe('extractAdminAssistantChangeSetStrict', () => {
  it('accepts a raw JSON change set without a fenced code block', () => {
    const raw = JSON.stringify({
      version: 1,
      summary: 'Apply theme',
      requests: [
        {
          method: 'PUT',
          path: '/admin/settings',
          body: {
            instance_name:
              'World Liberty Congress - Political Prisoners Support',
            description: 'Support resources and knowledge base',
            primary_color: '#1E40AF',
            typography_preset: 'humanist',
            status_icon_set: 'minimal',
            surface_style: 'plain',
          },
        },
      ],
    });

    const extracted = extractAdminAssistantChangeSetStrict(raw);

    expect(extracted.ok).toBe(true);
    if (extracted.ok) {
      expect(extracted.changeSet.requests[0]).toEqual({
        method: 'PUT',
        path: '/admin/settings',
        body: {
          instance_name: 'World Liberty Congress - Political Prisoners Support',
          description: 'Support resources and knowledge base',
          primary_color: '#1E40AF',
          typography_preset: 'humanist',
          status_icon_set: 'minimal',
          surface_style: 'plain',
        },
      });
    }
  });

  it('still rejects raw JSON for disallowed mutation paths', () => {
    const raw = JSON.stringify({
      version: 1,
      requests: [
        {
          method: 'PUT',
          path: '/admin/tools/execute',
          body: { tool_id: 'db-query' },
        },
      ],
    });

    const extracted = extractAdminAssistantChangeSetStrict(raw);

    expect(extracted.ok).toBe(false);
    if (!extracted.ok) {
      expect(extracted.error).toContain('Disallowed');
    }
  });

  it('allows confirmed Trace Visibility Policy changes through Agent Settings', () => {
    const raw = JSON.stringify({
      version: 1,
      summary: 'Show summary traces to users',
      requests: [
        {
          method: 'PUT',
          path: '/admin/ai-config/user_trace_visibility',
          body: { value: 'summary' },
        },
      ],
    });

    const extracted = extractAdminAssistantChangeSetStrict(raw);

    expect(extracted.ok).toBe(true);
  });

  it('rejects detailed Trace Visibility Policy for User Conversations', () => {
    const raw = JSON.stringify({
      version: 1,
      summary: 'Show detailed traces to users',
      requests: [
        {
          method: 'PUT',
          path: '/admin/ai-config/user_trace_visibility',
          body: { value: 'detailed' },
        },
      ],
    });

    const extracted = extractAdminAssistantChangeSetStrict(raw);

    expect(extracted.ok).toBe(false);
    if (!extracted.ok) {
      expect(extracted.error).toContain('User Conversation');
    }
  });

  it('does not export the old non-strict change set extractor', () => {
    expect('extractAdminAssistantChangeSet' in adminAssistant).toBe(false);
  });

  it('does not normalize user type alias body keys', () => {
    const raw = JSON.stringify({
      version: 1,
      requests: [
        {
          method: 'POST',
          path: '/admin/user-types',
          body: {
            name: 'Members',
            order: 2,
          },
        },
      ],
    });

    const extracted = extractAdminAssistantChangeSetStrict(raw);

    expect(extracted.ok).toBe(true);
    if (extracted.ok) {
      expect(extracted.changeSet.requests[0].body).toEqual({ name: 'Members' });
    }
  });

  it('does not normalize user field alias body keys', () => {
    const raw = JSON.stringify({
      version: 1,
      requests: [
        {
          method: 'POST',
          path: '/admin/user-fields',
          body: {
            label: 'Chapter',
            type: 'text',
            order: 3,
            includeInChat: true,
            userTypeId: '4',
          },
        },
      ],
    });

    const extracted = extractAdminAssistantChangeSetStrict(raw);

    expect(extracted.ok).toBe(true);
    if (extracted.ok) {
      expect(extracted.changeSet.requests[0].body).toEqual({});
    }
  });
});

describe('coerceAdminAssistantChangeSetPayload', () => {
  it('accepts structured Sage proposal payloads without requiring message JSON', () => {
    const extracted = coerceAdminAssistantChangeSetPayload({
      version: 1,
      summary: 'Set instance name',
      requests: [
        {
          method: 'PUT',
          path: '/admin/settings',
          body: { instance_name: 'FreeThem' },
        },
      ],
    });

    expect(extracted.ok).toBe(true);
    if (extracted.ok) {
      expect(extracted.changeSet.summary).toBe('Set instance name');
      expect(extracted.changeSet.requests[0]).toEqual({
        method: 'PUT',
        path: '/admin/settings',
        body: { instance_name: 'FreeThem' },
      });
    }
  });

  it('canonicalizes structured proposal payload drift before staging', () => {
    const extracted = coerceAdminAssistantChangeSetPayload({
      version: 1,
      summary: 'Complete setup',
      requests: [
        {
          method: 'PUT',
          path: '/admin/settings',
          body: {
            tagline: 'Support for political prisoners and their families',
            default_language: 'English',
          },
        },
        {
          method: 'POST',
          path: '/admin/user_types',
          body: {
            name: 'Current Support',
            description: 'Family and friends of current political prisoners',
          },
        },
      ],
    });

    expect(extracted.ok).toBe(true);
    if (extracted.ok) {
      expect(extracted.changeSet.requests[0]).toEqual({
        method: 'PUT',
        path: '/admin/settings',
        body: {
          header_tagline: 'Support for political prisoners and their families',
          default_language: 'en',
        },
      });
      expect(extracted.changeSet.requests[1].path).toBe('/admin/user-types');
    }
  });

  it('rejects unsupported instance setting keys before staging', () => {
    const extracted = coerceAdminAssistantChangeSetPayload({
      version: 1,
      requests: [
        {
          method: 'PUT',
          path: '/admin/settings',
          body: { made_up_setting: 'nope' },
        },
      ],
    });

    expect(extracted.ok).toBe(false);
    if (!extracted.ok) {
      expect(extracted.error).toContain('Unsupported instance setting key');
    }
  });

  it('accepts behavior rules through Agent Settings before staging', () => {
    const rules = JSON.stringify([
      'Ask users where they are from before giving location-specific guidance.',
    ]);
    const extracted = coerceAdminAssistantChangeSetPayload({
      version: 1,
      summary: 'Ask where users are from',
      requests: [
        {
          method: 'PUT',
          path: '/admin/ai-config/prompt_rules',
          body: { value: rules },
        },
      ],
    });

    expect(extracted.ok).toBe(true);
    if (extracted.ok) {
      expect(extracted.changeSet.requests[0]).toEqual({
        method: 'PUT',
        path: '/admin/ai-config/prompt_rules',
        body: { value: rules },
      });
    }
  });

  it('rejects malformed behavior rule Agent Settings payloads before staging', () => {
    const extracted = coerceAdminAssistantChangeSetPayload({
      version: 1,
      requests: [
        {
          method: 'PUT',
          path: '/admin/ai-config/prompt_rules',
          body: { value: 'Ask users where they are from.' },
        },
      ],
    });

    expect(extracted.ok).toBe(false);
    if (!extracted.ok) {
      expect(extracted.error).toContain('JSON array of strings');
    }
  });

  it('accepts forbidden topics through Agent Settings before staging', () => {
    const forbidden = JSON.stringify(['Do not provide legal advice.']);
    const extracted = coerceAdminAssistantChangeSetPayload({
      version: 1,
      requests: [
        {
          method: 'PUT',
          path: '/admin/ai-config/prompt_forbidden',
          body: { value: forbidden },
        },
      ],
    });

    expect(extracted.ok).toBe(true);
    if (extracted.ok) {
      expect(extracted.changeSet.requests[0]).toEqual({
        method: 'PUT',
        path: '/admin/ai-config/prompt_forbidden',
        body: { value: forbidden },
      });
    }
  });

  it('rejects malformed forbidden topics Agent Settings payloads before staging', () => {
    const extracted = coerceAdminAssistantChangeSetPayload({
      version: 1,
      requests: [
        {
          method: 'PUT',
          path: '/admin/ai-config/prompt_forbidden',
          body: { value: 'Do not provide legal advice.' },
        },
      ],
    });

    expect(extracted.ok).toBe(false);
    if (!extracted.ok) {
      expect(extracted.error).toContain('JSON array of strings');
    }
  });

  it('accepts user-type scoped behavior rules before staging', () => {
    const rules = JSON.stringify(['Ask for region before recommendations.']);
    const extracted = coerceAdminAssistantChangeSetPayload({
      version: 1,
      requests: [
        {
          method: 'PUT',
          path: '/admin/ai-config/user-type/1/prompt_rules',
          body: { value: rules },
        },
      ],
    });

    expect(extracted.ok).toBe(true);
    if (extracted.ok) {
      expect(extracted.changeSet.requests[0]).toEqual({
        method: 'PUT',
        path: '/admin/ai-config/user-type/1/prompt_rules',
        body: { value: rules },
      });
    }
  });

  it('rejects malformed user-type scoped behavior rules before staging', () => {
    const extracted = coerceAdminAssistantChangeSetPayload({
      version: 1,
      requests: [
        {
          method: 'PUT',
          path: '/admin/ai-config/user-type/1/prompt_rules',
          body: { value: 'Ask for region before recommendations.' },
        },
      ],
    });

    expect(extracted.ok).toBe(false);
    if (!extracted.ok) {
      expect(extracted.error).toContain('JSON array of strings');
    }
  });

  it('rejects non-string language and theme setting values before staging', () => {
    const invalidLanguage = coerceAdminAssistantChangeSetPayload({
      version: 1,
      requests: [
        {
          method: 'PUT',
          path: '/admin/settings',
          body: { default_language: true },
        },
      ],
    });
    expect(invalidLanguage.ok).toBe(false);
    if (!invalidLanguage.ok) {
      expect(invalidLanguage.error).toContain(
        'Unsupported default_language value'
      );
    }

    const invalidTheme = coerceAdminAssistantChangeSetPayload({
      version: 1,
      requests: [
        {
          method: 'PUT',
          path: '/admin/settings',
          body: { default_theme: false },
        },
      ],
    });
    expect(invalidTheme.ok).toBe(false);
    if (!invalidTheme.ok) {
      expect(invalidTheme.error).toContain('Unsupported default_theme value');
    }
  });

  it('rejects structured payloads with disallowed requests', () => {
    const extracted = coerceAdminAssistantChangeSetPayload({
      version: 1,
      requests: [
        {
          method: 'PUT',
          path: '/admin/tools/execute',
          body: { tool_id: 'db-query' },
        },
      ],
    });

    expect(extracted.ok).toBe(false);
    if (!extracted.ok) expect(extracted.error).toContain('Disallowed');
  });
});

describe('redactAdminDeploymentSecretChangeSets', () => {
  it('redacts secret deployment values before a streamed JSON fence is complete', () => {
    const streamedPartial = [
      'Here is the update.',
      '```json',
      '{"version":1,"summary":"Rotate key","requests":[{"method":"PUT","path":"/admin/deployment/config/LLM_API_KEY","body":{"value":"sk-live-secret-value"}}]}',
    ].join('\n');

    const redacted = redactAdminDeploymentSecretChangeSets(streamedPartial);

    expect(redacted).toContain('[REDACTED]');
    expect(redacted).not.toContain('sk-live-secret-value');
  });

  it('keeps non-secret deployment values visible in complete changesets', () => {
    const changeSet = {
      version: 1,
      summary: 'Set public base URL',
      requests: [
        {
          method: 'PUT',
          path: '/admin/deployment/config/PUBLIC_BASE_URL',
          body: { value: 'https://example.test' },
        },
      ],
    };

    const redacted = redactAdminDeploymentSecretChangeSets(
      `\`\`\`json\n${JSON.stringify(changeSet)}\n\`\`\``
    );

    expect(redacted).toContain('https://example.test');
  });
});

describe('stripAdminAssistantChangeSetJson', () => {
  it('keeps structurally valid but disallowed raw change sets visible', () => {
    const disallowed = JSON.stringify({
      version: 1,
      requests: [
        {
          method: 'PUT',
          path: '/admin/tools/execute',
          body: { tool_id: 'db-query' },
        },
      ],
    });

    expect(
      stripAdminAssistantChangeSetJson(`Review this:\n${disallowed}`)
    ).toBe(`Review this:\n${disallowed}`);
  });
});
