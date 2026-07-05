import { describe, expect, it } from 'vitest';
import { resolveUserConversationSessionDefaults } from './sessionDefaults';

describe('resolveUserConversationSessionDefaults', () => {
  it('fails closed for missing and invalid fields', () => {
    expect(resolveUserConversationSessionDefaults(null)).toEqual({
      tools: [],
      documentIds: [],
      knowledgeSourceScope: 'none',
    });

    expect(
      resolveUserConversationSessionDefaults({
        default_document_ids: 'doc-1',
        default_tool_ids: 'web-search',
        knowledge_source_scope: 'selected',
      })
    ).toEqual({
      tools: [],
      documentIds: [],
      knowledgeSourceScope: 'none',
    });
  });

  it('does not enable selected Knowledge without selected documents', () => {
    expect(
      resolveUserConversationSessionDefaults({
        default_document_ids: [],
        default_tool_ids: [
          'curated-resources',
          'knowledge-search',
          'web-search',
        ],
        knowledge_source_scope: 'selected',
      })
    ).toEqual({
      tools: ['curated-resources', 'web-search'],
      documentIds: [],
      knowledgeSourceScope: 'none',
    });
  });

  it('enables all Knowledge without sending document constraints', () => {
    expect(
      resolveUserConversationSessionDefaults({
        default_document_ids: ['doc-1'],
        default_tool_ids: [
          'curated-resources',
          'knowledge-search',
          'web-search',
          'knowledge-search',
        ],
        knowledge_source_scope: 'all',
      })
    ).toEqual({
      tools: ['curated-resources', 'web-search', 'knowledge-search'],
      documentIds: [],
      knowledgeSourceScope: 'all',
    });
  });

  it('filters and deduplicates malformed tool and document IDs', () => {
    expect(
      resolveUserConversationSessionDefaults({
        default_document_ids: ['doc-1', '', 'doc-1', 'doc-2', 12],
        default_tool_ids: [
          'web-search',
          'admin-config',
          'curated-resources',
          'web-search',
          'knowledge-search',
          null,
        ],
        knowledge_source_scope: 'selected',
      })
    ).toEqual({
      tools: ['web-search', 'curated-resources', 'knowledge-search'],
      documentIds: ['doc-1', 'doc-2'],
      knowledgeSourceScope: 'selected',
    });
  });
});
