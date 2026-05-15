import { describe, expect, it } from 'vitest'
import { extractAdminAssistantChangeSetStrict } from './adminAssistant'

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
})
