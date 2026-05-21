import { describe, expect, it } from 'vitest'
import * as adminAssistant from './adminAssistant'
import { extractAdminAssistantChangeSetStrict, redactAdminDeploymentSecretChangeSets } from './adminAssistant'

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
            instance_name: 'World Liberty Congress - Political Prisoners Support',
            description: 'Support resources and knowledge base',
            primary_color: '#1E40AF',
            typography_preset: 'humanist',
            status_icon_set: 'minimal',
            surface_style: 'plain',
          },
        },
      ],
    })

    const extracted = extractAdminAssistantChangeSetStrict(raw)

    expect(extracted.ok).toBe(true)
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
      })
    }
  })

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
    })

    const extracted = extractAdminAssistantChangeSetStrict(raw)

    expect(extracted.ok).toBe(false)
    if (!extracted.ok) {
      expect(extracted.error).toContain('Disallowed')
    }
  })

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
    })

    const extracted = extractAdminAssistantChangeSetStrict(raw)

    expect(extracted.ok).toBe(true)
  })

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
    })

    const extracted = extractAdminAssistantChangeSetStrict(raw)

    expect(extracted.ok).toBe(false)
    if (!extracted.ok) {
      expect(extracted.error).toContain('User Conversation')
    }
  })

  it('does not export the old non-strict change set extractor', () => {
    expect('extractAdminAssistantChangeSet' in adminAssistant).toBe(false)
  })

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
    })

    const extracted = extractAdminAssistantChangeSetStrict(raw)

    expect(extracted.ok).toBe(true)
    if (extracted.ok) {
      expect(extracted.changeSet.requests[0].body).toEqual({ name: 'Members' })
    }
  })

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
    })

    const extracted = extractAdminAssistantChangeSetStrict(raw)

    expect(extracted.ok).toBe(true)
    if (extracted.ok) {
      expect(extracted.changeSet.requests[0].body).toEqual({})
    }
  })
})

describe('redactAdminDeploymentSecretChangeSets', () => {
  it('redacts secret deployment values before a streamed JSON fence is complete', () => {
    const streamedPartial = [
      'Here is the update.',
      '```json',
      '{"version":1,"summary":"Rotate key","requests":[{"method":"PUT","path":"/admin/deployment/config/LLM_API_KEY","body":{"value":"sk-live-secret-value"}}]}',
    ].join('\n')

    const redacted = redactAdminDeploymentSecretChangeSets(streamedPartial)

    expect(redacted).toContain('[REDACTED]')
    expect(redacted).not.toContain('sk-live-secret-value')
  })

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
    }

    const redacted = redactAdminDeploymentSecretChangeSets(`\`\`\`json\n${JSON.stringify(changeSet)}\n\`\`\``)

    expect(redacted).toContain('https://example.test')
  })
})
