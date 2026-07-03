const KNOWLEDGE_TOOL_ID = 'knowledge-search';
const WEB_SEARCH_TOOL_ID = 'web-search';
const USER_CONVERSATION_TOOL_IDS = new Set([
  'curated-resources',
  KNOWLEDGE_TOOL_ID,
  WEB_SEARCH_TOOL_ID,
]);

export type KnowledgeSourceScope = 'none' | 'selected' | 'all';

export interface UserConversationSessionDefaults {
  tools: string[];
  documentIds: string[];
  knowledgeSourceScope: KnowledgeSourceScope;
}

function uniqueTools(tools: string[]): string[] {
  const seen = new Set<string>();
  return tools.filter((tool) => {
    if (!USER_CONVERSATION_TOOL_IDS.has(tool) || seen.has(tool)) return false;
    seen.add(tool);
    return true;
  });
}

function parseDocumentIds(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((id): id is string => typeof id === 'string' && Boolean(id))
    : [];
}

function parseKnowledgeSourceScope(
  value: unknown,
  fallbackDocumentIds: string[]
): KnowledgeSourceScope {
  if (value === 'none' || value === 'selected' || value === 'all') {
    return value;
  }
  return fallbackDocumentIds.length > 0 ? 'selected' : 'none';
}

export function resolveUserConversationSessionDefaults(
  data: unknown
): UserConversationSessionDefaults {
  const record =
    data && typeof data === 'object' ? (data as Record<string, unknown>) : {};
  const serverDocumentIds = parseDocumentIds(record.default_document_ids);
  const scope = parseKnowledgeSourceScope(
    record.knowledge_source_scope,
    serverDocumentIds
  );
  const serverTools = Array.isArray(record.default_tool_ids)
    ? uniqueTools(
        record.default_tool_ids.filter(
          (tool): tool is string => typeof tool === 'string'
        )
      )
    : record.web_search_enabled === true
      ? [WEB_SEARCH_TOOL_ID]
      : [];

  const tools = serverTools.filter((tool) => tool !== KNOWLEDGE_TOOL_ID);
  if (scope === 'all') {
    tools.push(KNOWLEDGE_TOOL_ID);
    return {
      tools: uniqueTools(tools),
      documentIds: [],
      knowledgeSourceScope: scope,
    };
  }
  if (scope === 'selected' && serverDocumentIds.length > 0) {
    tools.push(KNOWLEDGE_TOOL_ID);
    return {
      tools: uniqueTools(tools),
      documentIds: serverDocumentIds,
      knowledgeSourceScope: scope,
    };
  }

  return {
    tools: uniqueTools(tools),
    documentIds: [],
    knowledgeSourceScope: 'none',
  };
}
